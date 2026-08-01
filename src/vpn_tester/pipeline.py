"""End-to-end pipeline: download -> TCP filter -> country filter -> URL tests."""

from __future__ import annotations

import asyncio
import logging

import aiohttp

from .config import Settings
from .geoip import GeoCache
from .models import Config
from .parsers import is_supported, parse_uri
from .runtime import (
    STAGE_COUNTRY,
    STAGE_DOWNLOAD,
    STAGE_FINALIZE,
    STAGE_TCP,
    STAGE_URL_TESTS,
    reporter,
)
from .subscription import fetch_subscription
from .tcp_ping import tcp_ping
from .xray_runner import XrayRunner

log = logging.getLogger(__name__)


async def download_configs(sub_urls: list[str], settings: Settings) -> list[Config]:
    """Download all subscriptions concurrently and dedupe into Config objects."""
    reporter.set_stage(STAGE_DOWNLOAD, f"downloading {len(sub_urls)} subscription(s)")
    connector = aiohttp.TCPConnector(
        limit=min(20, max(4, settings.max_subscription_urls * 2)), ssl=False
    )
    async with aiohttp.ClientSession(connector=connector) as session:
        batches = await asyncio.gather(
            *[fetch_subscription(u, session, timeout=settings.download_timeout) for u in sub_urls]
        )

    seen: set[str] = set()
    configs: list[Config] = []
    for uri in (u for batch in batches for u in batch):
        if uri in seen:
            continue
        seen.add(uri)
        parsed = parse_uri(uri)
        if parsed is None:
            if is_supported(uri):
                log.warning("  Dropping unparseable config: %s", uri[:60])
            continue
        configs.append(
            Config(
                uri=uri,
                name=parsed.name,
                protocol=parsed.protocol,
                server=parsed.server,
                port=parsed.port,
            )
        )
    if len(configs) > settings.max_configs:
        log.warning("Truncating %d configs to MAX_CONFIGS=%d", len(configs), settings.max_configs)
        configs = configs[: settings.max_configs]
    log.info("Total unique configs: %d", len(configs))
    reporter.set_progress(STAGE_DOWNLOAD, 1, 1, 0.0, 0.06)
    return configs


async def tcp_filter(configs: list[Config], settings: Settings) -> list[Config]:
    """Keep only configs whose server answers the TCP ping reliably.

    Concurrency is capped to avoid a socket storm on large subscriptions.
    """

    sem = asyncio.Semaphore(min(settings.tcp_concurrency, max(1, len(configs))))
    total = len(configs)
    done = 0

    async def _ping(cfg: Config) -> int:
        nonlocal done
        async with sem:
            try:
                return await tcp_ping(cfg.server, cfg.port, settings.tcp_ping_tries)
            except Exception:
                return 0
            finally:
                done += 1
                reporter.set_progress(STAGE_TCP, done, total, 0.06, 0.22)

    results = await asyncio.gather(*[_ping(c) for c in configs])
    kept = [c for c, ok in zip(configs, results) if ok >= settings.tcp_ping_min_success]
    log.info(
        "TCP filter: kept %d / %d (need >=%d successes)",
        len(kept),
        len(configs),
        settings.tcp_ping_min_success,
    )
    return kept


async def country_filter(configs: list[Config], xray_bin: str, settings: Settings) -> list[Config]:
    """Keep only configs whose exit IP is in the allowed country set.

    Each config is probed through its own Xray process + SOCKS tunnel,
    concurrency-limited to avoid a process storm.
    """
    if not settings.allowed_countries:
        log.info("No allowed countries configured; skipping country filter.")
        for c in configs:
            c.country = c.country or ""
        return configs

    sem = asyncio.Semaphore(settings.max_concurrent)
    cache = GeoCache(settings.geoip_providers)
    total = len(configs)
    done = 0

    async def _check(i: int, cfg: Config) -> str | None:
        nonlocal done
        port = settings.socks_port_base + i
        async with sem:
            try:
                async with XrayRunner(xray_bin, cfg, port, settings) as runner:
                    result = await cache.get_country(runner.session, settings.connect_timeout)
            except Exception:
                result = None
            finally:
                done += 1
                reporter.set_progress(STAGE_COUNTRY, done, total, 0.22, 0.55)
            return result

    tasks = [_check(i, c) for i, c in enumerate(configs)]
    results = await asyncio.gather(*tasks)

    allowed = settings.allowed_countries
    kept: list[Config] = []
    for cfg, cc in zip(configs, results):
        if cc and cc in allowed:
            cfg.country = cc
            cfg.country_name, cfg.flag = allowed[cc]
            kept.append(cfg)
        else:
            log.info("Dropping %s — exit country: %s", cfg.display_name(), cc)
    log.info("Country filter: %d configs remain", len(kept))
    return kept


async def url_test_all(configs: list[Config], xray_bin: str, settings: Settings) -> None:
    """Run all URL-test rounds, reusing one Xray process per config.

    Each config keeps a single Xray process + SOCKS tunnel alive for all rounds
    (instead of restarting it per round). Results are tracked per target so the
    final error rate can be weighted.
    """
    sem = asyncio.Semaphore(settings.max_concurrent)
    rounds = settings.url_test_rounds
    targets = settings.test_urls
    total = len(configs)
    done = 0

    async def _test(i: int, cfg: Config) -> None:
        nonlocal done
        port = settings.socks_port_base + i
        async with sem:
            try:
                async with XrayRunner(xray_bin, cfg, port, settings) as runner:
                    for _ in range(rounds):
                        for label, url, _weight in targets:
                            ms = await runner.test_url(label, url)
                            cfg.record(label, ms is not None)
                            if ms is not None:
                                cfg.latencies.append(ms)
            except Exception as exc:
                log.debug("  [SKIP] %s: %s", cfg.display_name(), exc)
                for label, _url, _weight in targets:
                    for _ in range(rounds):
                        cfg.record(label, False)
            finally:
                done += 1
                reporter.set_progress(STAGE_URL_TESTS, done, total, 0.55, 0.95)
        # Totals are derived from recorded stats so error_rate is always exact.
        cfg.total = rounds * len(targets)
        cfg.errors = sum(st["fail"] for st in cfg.target_stats.values())

    await asyncio.gather(*[_test(i, c) for i, c in enumerate(configs)])


def select_top(configs: list[Config], settings: Settings) -> list[Config]:
    """Drop configs with too many errors, then take the best N per country.

    Keeps `configs_per_country` best configs for every allowed country, in the
    order countries appear in `settings.allowed_countries`. Ranking uses the
    target-weighted error rate, then average latency.
    """
    weights = {label: w for label, _url, w in settings.test_urls}
    candidates = [c for c in configs if c.weighted_error_rate(weights) <= settings.max_error_rate]
    dropped = len(configs) - len(candidates)
    if dropped:
        log.info(
            "Dropped %d configs exceeding max_error_rate=%.0f%%",
            dropped,
            settings.max_error_rate * 100,
        )

    result: list[Config] = []
    for cc in settings.allowed_countries:
        pool = [c for c in candidates if c.country == cc]
        pool.sort(key=lambda c: (c.weighted_error_rate(weights), c.avg_latency))
        result.extend(pool[: settings.configs_per_country])
    return result


async def run_pipeline(sub_urls: list[str], xray_bin: str, settings: Settings) -> list[Config]:
    log.info("Xray binary: %s", xray_bin)

    configs = await download_configs(sub_urls, settings)
    if not configs:
        return []

    configs = await tcp_filter(configs, settings)
    if not configs:
        return []

    configs = await country_filter(configs, xray_bin, settings)
    if not configs:
        return []

    log.info(
        "URL tests — %d rounds across %d targets",
        settings.url_test_rounds,
        len(settings.test_urls),
    )
    await url_test_all(configs, xray_bin, settings)

    top = select_top(configs, settings)
    log.info("=" * 55)
    log.info("Top %d configs (by error-rate then latency):", len(top))
    for i, c in enumerate(top, 1):
        log.info(
            "  %2d. drop=%.1f%%  avg=%7.1fms  p95=%7.1fms  %s",
            i,
            c.error_rate * 100,
            c.avg_latency,
            c.p95,
            c.display_name(),
        )
    log.info("=" * 55)
    reporter.set_stage(STAGE_FINALIZE, "selecting best configs")
    reporter.set_progress(STAGE_FINALIZE, 1, 1, 0.95, 1.0)
    return top
