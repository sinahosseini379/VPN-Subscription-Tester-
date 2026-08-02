"""CLI entry point: `vpn-tester` or `python -m vpn_tester.main`."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import __version__
from .config import load_settings
from .cores import ensure_cores
from .github_push import push_to_github
from .output import write_subscription
from .pipeline import run_pipeline
from .runtime import (
    LogCapture,
    RunCoordinator,
    reporter,
    seconds_until_next_run,
)
from .web import start_dashboard

log = logging.getLogger("vpn_tester")


def setup_logging(settings, verbose: bool) -> None:
    level = logging.DEBUG if verbose else getattr(logging, settings.log_level, logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if settings.log_file:
        handlers.append(
            RotatingFileHandler(
                settings.log_file,
                maxBytes=settings.log_rotate_mb * 1024 * 1024,
                backupCount=settings.log_backup_count,
                encoding="utf-8",
            )
        )
    logging.basicConfig(
        level=level, format="%(asctime)s [%(levelname)s] %(message)s", handlers=handlers
    )
    # Mirror every log line into the dashboard's ring buffer.
    logging.getLogger().addHandler(LogCapture(reporter))


def load_sub_urls(settings) -> list[str]:
    p = Path(settings.subscriptions_file)
    if not p.exists():
        log.error("Subscription list not found: %s", p)
        sys.exit(1)
    urls = [
        line.strip()
        for line in p.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    if len(urls) > settings.max_subscription_urls:
        log.warning(
            "More than %d URLs; using the first %d.",
            settings.max_subscription_urls,
            settings.max_subscription_urls,
        )
        urls = urls[: settings.max_subscription_urls]
    return urls


async def run_once(settings, *, do_push: bool) -> bool:
    if reporter.status == "running":
        log.warning("A run is already in progress; skipping this one.")
        return False

    reporter.begin_run("pipeline run")
    sub_urls = load_sub_urls(settings)
    log.info("Loaded %d subscription(s)", len(sub_urls))
    try:
        cores = await ensure_cores(settings)
        top = await run_pipeline(sub_urls, cores, settings)
        if not top:
            log.error("No configs survived; nothing written.")
            reporter.finish(False)
            return False

        if len(top) < settings.alert_min_configs:
            log.warning(
                "Only %d configs survived (< ALERT_MIN_CONFIGS=%d); "
                "refusing to overwrite the published output.",
                len(top),
                settings.alert_min_configs,
            )
            reporter.finish(False)
            return False

        meta = write_subscription(top, settings)

        if do_push:
            # Publish the per-country files this run produced alongside the
            # configured outputs, without mutating settings across runs.
            extra = [f for f in meta.get("written_files", []) if f not in settings.github_files]
            push_files = settings.github_files + extra
            try:
                ok = await push_to_github(settings, files=push_files)
                if not ok:
                    log.error("GitHub push failed after retries.")
                    reporter.finish(False, meta)
                    return False
            except ValueError as exc:
                log.error("%s (set GITHUB_* in config.env)", exc)
                reporter.finish(False, meta)
                return False
        reporter.finish(True, meta)
        return True
    except Exception:
        log.exception("Pipeline error")
        reporter.finish(False)
        raise


async def _loop(settings, *, do_push: bool) -> None:
    coordinator = RunCoordinator(settings, run_once)

    if settings.dashboard_enabled:
        await start_dashboard(settings, coordinator, settings.config_file)

    while True:
        try:
            wait = seconds_until_next_run(settings.schedule_time, tz_name=settings.timezone)
        except ValueError as exc:
            log.error("%s", exc)
            return
        log.info(
            "Next run scheduled at %s %s (in %d s)",
            settings.schedule_time,
            settings.timezone,
            int(wait),
        )
        try:
            await asyncio.wait_for(coordinator.schedule_changed.wait(), timeout=wait)
            coordinator.schedule_changed.clear()
            log.info("Schedule changed; recomputing next run time.")
            continue
        except asyncio.TimeoutError:
            pass

        try:
            ok = await run_once(settings, do_push=do_push)
            if not ok and settings.alert_webhook:
                await _send_alert(settings, "VPN tester run produced no usable output.")
        except Exception:
            if settings.alert_webhook:
                await _send_alert(settings, "VPN tester pipeline crashed.")


async def _send_alert(settings, message: str) -> None:
    url = settings.alert_webhook
    try:
        import aiohttp
        from aiohttp import ClientTimeout

        async with aiohttp.ClientSession(timeout=ClientTimeout(total=15)) as session:
            payload = {"text": message} if "api.telegram.org" in url else message
            async with session.post(url, json=payload) as resp:
                log.info("Alert sent: %s (HTTP %s)", url, resp.status)
    except Exception as exc:
        log.warning("Alert failed: %s", exc)


def cli(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="vpn-tester",
        description="Download subscriptions, live-test configs through Xray, "
        "publish the best ones to GitHub.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--config", default="config.env", help="env file with settings (default: config.env)"
    )
    parser.add_argument("--once", action="store_true", help="run a single pipeline and exit")
    parser.add_argument("--no-push", action="store_true", help="skip the GitHub push step")
    parser.add_argument("--no-dashboard", action="store_true", help="disable the web dashboard")
    parser.add_argument("--port", type=int, help="override DASHBOARD_PORT")
    parser.add_argument("--verbose", action="store_true", help="debug logging")
    args = parser.parse_args(argv)

    settings = load_settings(args.config)
    if args.no_dashboard:
        settings.dashboard_enabled = False
    if args.port:
        settings.dashboard_port = args.port
    setup_logging(settings, verbose=args.verbose)

    do_push = not args.no_push
    try:
        if args.once:
            ok = asyncio.run(run_once(settings, do_push=do_push))
            return 0 if ok else 1
        asyncio.run(_loop(settings, do_push=do_push))
    except KeyboardInterrupt:
        log.info("Interrupted by user.")
    except Exception:
        log.exception("Fatal error")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
