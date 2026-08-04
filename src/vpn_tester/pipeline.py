"""End-to-end pipeline: download -> TCP filter -> country filter -> URL tests."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from pathlib import Path

import aiohttp

from .config import Settings
from .cores import Cores
from .geoip import GeoCache
from .models import Config, flag_from_country_code
from .parsers import extract_stealth_info, is_supported, parse_uri
from .runtime import (
    STAGE_COUNTRY,
    STAGE_DOWNLOAD,
    STAGE_FINALIZE,
    STAGE_STEALTH,
    STAGE_TCP,
    STAGE_URL_TESTS,
    reporter,
)
from .subscription import fetch_subscription
from .tcp_ping import tcp_ping
from .xray_runner import CoreRunner

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
        stealth = extract_stealth_info(parsed)
        configs.append(
            Config(
                uri=uri,
                name=parsed.name,
                protocol=parsed.protocol,
                server=parsed.server,
                port=parsed.port,
                transport=stealth["transport"],
                security=stealth["security"],
                fingerprint=stealth["fingerprint"],
                stealth_score=stealth["stealth_score"],
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
                reporter.set_progress(STAGE_TCP, done, total, 0.06, 0.20)

    results = await asyncio.gather(*[_ping(c) for c in configs])
    kept = [c for c, ok in zip(configs, results) if ok >= settings.tcp_ping_min_success]
    log.info(
        "TCP filter: kept %d / %d (need >=%d successes)",
        len(kept),
        len(configs),
        settings.tcp_ping_min_success,
    )
    return kept


def stealth_filter(configs: list[Config], settings: Settings) -> list[Config]:
    """Drop configs with a stealth score below the minimum threshold.

    Only active when ``stealth_mode`` is ``"strict"``; in ``"prefer"`` mode the
    score is used as a ranking tiebreaker in ``select_top`` instead.  In ``"off"``
    mode this function is a no-op.

    The filter logs a per-category breakdown so operators can see which ISP-risky
    patterns were eliminated.
    """
    mode = settings.stealth_mode
    if mode not in ("strict",):
        return configs

    reporter.set_stage(STAGE_STEALTH, "filtering low-stealth configs")
    threshold = settings.stealth_min_score
    kept: list[Config] = []
    dropped_by_reason: dict[str, int] = {}

    for c in configs:
        if c.stealth_score >= threshold:
            kept.append(c)
        else:
            # Build a human-readable reason
            reason = f"{c.protocol}/{c.transport}/{c.security}"
            dropped_by_reason[reason] = dropped_by_reason.get(reason, 0) + 1

    if dropped_by_reason:
        log.info(
            "Stealth filter (threshold=%.2f): dropped %d / %d configs",
            threshold,
            len(configs) - len(kept),
            len(configs),
        )
        for reason, count in sorted(dropped_by_reason.items(), key=lambda x: -x[1]):
            log.info("  dropped %3d  %s", count, reason)
    else:
        log.info("Stealth filter: all %d configs above threshold %.2f", len(configs), threshold)

    reporter.set_progress(STAGE_STEALTH, 1, 1, 0.20, 0.24)
    return kept


async def country_filter(configs: list[Config], cores: Cores, settings: Settings) -> list[Config]:
    """Keep only configs whose exit IP is in the allowed country set.

    Each config is probed through its own core process + SOCKS tunnel,
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
                async with CoreRunner(cores, cfg, port, settings) as runner:
                    result = await cache.get_country(runner.session, settings.connect_timeout)
            except Exception:
                result = None
            finally:
                done += 1
                reporter.set_progress(STAGE_COUNTRY, done, total, 0.24, 0.55)
            return result

    tasks = [_check(i, c) for i, c in enumerate(configs)]
    results = await asyncio.gather(*tasks)

    allowed = settings.allowed_countries
    kept: list[Config] = []
    for cfg, cc in zip(configs, results):
        if cc and cc in allowed:
            cfg.country = cc
            cfg.country_name, cfg.flag = allowed[cc]
            if not cfg.flag:
                cfg.flag = flag_from_country_code(cc)
            kept.append(cfg)
        else:
            log.info("Dropping %s — exit country: %s", cfg.display_name(), cc)
    log.info("Country filter: %d configs remain", len(kept))
    return kept


async def url_test_all(
    configs: list[Config], cores: Cores, settings: Settings, rounds: int | None = None
) -> None:
    """Run all URL-test rounds, reusing one core process per config.

    Each config keeps a single process + SOCKS tunnel alive for all rounds
    (instead of restarting it per round). Results are tracked per target so the
    final error rate can be weighted.
    """
    rounds = rounds if rounds is not None else settings.url_test_rounds
    sem = asyncio.Semaphore(settings.max_concurrent)
    targets = settings.test_urls
    total = len(configs)
    done = 0

    async def _test(i: int, cfg: Config) -> None:
        nonlocal done
        port = settings.socks_port_base + i
        async with sem:
            try:
                async with CoreRunner(cores, cfg, port, settings) as runner:
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

    Keeps the best configs for every allowed country, in the
    order countries appear in `settings.allowed_countries`. The number kept per
    country is the maximum of `configs_per_country` (for main subscription) and
    `per_country_output_count` (for per-country files). Ranking uses:

    1. Target-weighted error rate (lower is better)
    2. Stealth score (higher is better) — when ``stealth_mode`` is ``"prefer"``
       or ``"strict"``, this separates configs with the same error rate,
       ensuring cross-ISP resilience.
    3. Average latency (lower is better)
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

    use_stealth = settings.stealth_mode in ("prefer", "strict")
    # Keep enough for both main subscription and per-country files
    per_country_limit = max(settings.configs_per_country, settings.per_country_output_count)

    result: list[Config] = []
    for cc in settings.allowed_countries:
        pool = [c for c in candidates if c.country == cc]
        if use_stealth:
            # Sort by error_rate ASC, stealth_score DESC, latency ASC
            pool.sort(
                key=lambda c: (
                    c.weighted_error_rate(weights),
                    -c.stealth_score,
                    c.avg_latency,
                )
            )
        else:
            pool.sort(key=lambda c: (c.weighted_error_rate(weights), c.avg_latency))
        result.extend(pool[:per_country_limit])
    return result


def assign_indices(configs: list[Config]) -> None:
    """Number configs 01..NN globally across the whole output."""
    for i, c in enumerate(configs, 1):
        c.index = i


# -- incremental / carry-forward -------------------------------------------


def load_previous_configs(settings: Settings) -> list[Config]:
    """Reconstruct last run's Config list from the published output + metadata.

    Returns [] when there is no previous output, so the first run is unaffected.
    """
    out_path = Path(settings.output_file)
    if not out_path.exists():
        return []
    try:
        raw = re.sub(r"\s+", "", out_path.read_text(encoding="utf-8"))
        uris = base64.b64decode(raw + "==").decode("utf-8", errors="ignore").splitlines()
    except Exception:
        return []

    meta: dict = {}
    meta_path = Path(settings.metadata_file)
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    items = meta.get("items") or []

    configs: list[Config] = []
    for i, uri in enumerate(uris):
        item = items[i] if i < len(items) else {}
        parsed = parse_uri(uri)
        if parsed is None:
            continue
        country = item.get("country") or ""
        # Restore the flag so carried-forward configs keep it in their display
        # name. Older metadata files predate the stored "flag" field, so fall
        # back to the allow-list and finally to a code-derived emoji.
        flag = item.get("flag") or ""
        if not flag and country:
            allowed = settings.allowed_countries.get(country)
            flag = allowed[1] if allowed else flag_from_country_code(country)
        # Restore stealth info; recompute if not in older metadata.
        stealth = extract_stealth_info(parsed)
        configs.append(
            Config(
                uri=uri,
                name=parsed.name,
                protocol=parsed.protocol,
                server=parsed.server,
                port=parsed.port,
                country=country,
                country_name=item.get("country_name") or "",
                flag=flag,
                index=int(item.get("index") or 0),
                transport=item.get("transport") or stealth["transport"],
                security=item.get("security") or stealth["security"],
                stealth_score=float(item.get("stealth_score") or stealth["stealth_score"]),
            )
        )
    log.info("Loaded %d config(s) from previous run", len(configs))
    return configs


async def quick_test_previous(
    configs: list[Config], cores: Cores, settings: Settings
) -> list[Config]:
    """One fast URL round per previous config; keep the ones still alive."""
    if not configs:
        return []
    await url_test_all(configs, cores, settings, rounds=1)
    weights = {label: w for label, _url, w in settings.test_urls}
    alive = [c for c in configs if c.weighted_error_rate(weights) <= settings.max_error_rate]
    log.info(
        "Carry-forward: %d / %d previous configs still alive",
        len(alive),
        len(configs),
    )
    return alive


def merge_incremental(
    new_top: list[Config], previous_alive: list[Config], settings: Settings
) -> list[Config]:
    """Prefer still-working previous configs, then fill gaps with new ones.

    Total output is capped at configs_per_country * number of allowed countries,
    so the subscription stays a stable size across runs.
    """
    cap = settings.configs_per_country * max(1, len(settings.allowed_countries))
    merged: list[Config] = []
    seen: set[str] = set()

    # First, add still-working previous configs (up to cap per country)
    per_country_count: dict[str, int] = {}
    for c in previous_alive:
        if len(merged) >= cap:
            break
        country = c.country or "?"
        if per_country_count.get(country, 0) >= settings.configs_per_country:
            continue
        if c.uri in seen:
            continue
        seen.add(c.uri)
        merged.append(c)
        per_country_count[country] = per_country_count.get(country, 0) + 1

    # Then fill gaps with new top configs
    for c in new_top:
        if len(merged) >= cap:
            break
        country = c.country or "?"
        if per_country_count.get(country, 0) >= settings.configs_per_country:
            continue
        if c.uri in seen:
            continue
        seen.add(c.uri)
        merged.append(c)
        per_country_count[country] = per_country_count.get(country, 0) + 1

    return merged


async def run_pipeline(sub_urls: list[str], cores: Cores, settings: Settings) -> list[Config]:
    log.info("Cores: xray=%s sing-box=%s hysteria=%s", cores.xray, cores.sing_box, cores.hysteria)
    if settings.stealth_mode != "off":
        log.info(
            "Stealth mode: %s (min_score=%.2f)",
            settings.stealth_mode,
            settings.stealth_min_score,
        )

    configs = await download_configs(sub_urls, settings)
    if not configs:
        return []

    configs = await tcp_filter(configs, settings)
    if not configs:
        return []

    # Stealth filter runs before the expensive country/URL stages so we avoid
    # wasting core processes on configs that would be blocked anyway.
    if settings.stealth_mode == "strict":
        configs = stealth_filter(configs, settings)
        if not configs:
            log.warning("Stealth filter eliminated all configs; try lowering STEALTH_MIN_SCORE.")
            return []

    configs = await country_filter(configs, cores, settings)
    if not configs:
        return []

    log.info(
        "URL tests — %d rounds across %d targets",
        settings.url_test_rounds,
        len(settings.test_urls),
    )
    await url_test_all(configs, cores, settings)

    top = select_top(configs, settings)

    if settings.incremental:
        previous = load_previous_configs(settings)
        if previous:
            alive = await quick_test_previous(previous, cores, settings)
            top = merge_incremental(top, alive, settings)

    assign_indices(top)
    log.info("=" * 65)
    log.info("Top %d configs (by error-rate, stealth, latency):", len(top))
    for c in top:
        log.info(
            "  %s  drop=%.1f%%  stealth=%.2f  avg=%7.1fms  p95=%7.1fms  [%s/%s]",
            c.display_name(),
            c.error_rate * 100,
            c.stealth_score,
            c.avg_latency,
            c.p95,
            c.transport,
            c.security,
        )
    log.info("=" * 65)
    reporter.set_stage(STAGE_FINALIZE, "selecting best configs")
    reporter.set_progress(STAGE_FINALIZE, 1, 1, 0.95, 1.0)
    return top
