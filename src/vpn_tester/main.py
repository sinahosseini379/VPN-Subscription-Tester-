"""CLI entry point: `vpn-tester` or `python -m vpn_tester.main`."""

from __future__ import annotations

import argparse
import asyncio
import datetime
import logging
import shutil
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import __version__
from .config import load_settings
from .github_push import push_to_github
from .output import write_subscription
from .pipeline import run_pipeline

log = logging.getLogger("vpn_tester")


def setup_logging(settings, verbose: bool) -> None:
    level = logging.DEBUG if verbose else getattr(settings.log_level, logging.INFO)

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


def find_xray(settings) -> str:
    candidates = [
        settings.xray_bin,
        "xray",
        "/usr/local/bin/xray",
        "/usr/bin/xray",
        str(Path.home() / ".local/bin/xray"),
        str(Path(__file__).resolve().parent.parent.parent / "xray"),
        str(Path(__file__).resolve().parent.parent.parent / "bin" / "xray"),
    ]
    for cand in candidates:
        if cand:
            path = shutil.which(cand)
            if path:
                return path
    raise FileNotFoundError(
        "xray binary not found. Install from https://github.com/XTLS/Xray-core/releases "
        "or set XRAY_BIN=/path/to/xray."
    )


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
    sub_urls = load_sub_urls(settings)
    log.info("Loaded %d subscription(s)", len(sub_urls))

    top = await run_pipeline(sub_urls, find_xray(settings), settings)
    if not top:
        log.error("No configs survived; nothing written.")
        return False

    if len(top) < settings.alert_min_configs:
        log.warning(
            "Only %d configs survived (< ALERT_MIN_CONFIGS=%d); "
            "refusing to overwrite the published output.",
            len(top),
            settings.alert_min_configs,
        )
        return False

    write_subscription(top, settings)

    if do_push:
        try:
            ok = await push_to_github(settings)
            if not ok:
                log.error("GitHub push failed after retries.")
                return False
        except ValueError as exc:
            log.error("%s (set GITHUB_* in config.env)", exc)
            return False
    return True


def seconds_until_next_run(
    schedule_time: str,
    now: datetime.datetime | None = None,
    tz_name: str = "Asia/Tehran",
) -> float:
    """Seconds until the next occurrence of HH:MM in the given timezone.

    `now` defaults to the current UTC instant; a naive `now` is treated as
    UTC. Raises ValueError for malformed times or unknown timezones. If the
    time already passed in that timezone, the target is the same time tomorrow.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        raise ValueError(f"Unknown timezone {tz_name!r}") from None

    try:
        hour, minute = (int(p) for p in schedule_time.split(":", 1))
    except (ValueError, TypeError):
        raise ValueError(f"Invalid SCHEDULE_TIME {schedule_time!r}: expected 'HH:MM'") from None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid SCHEDULE_TIME {schedule_time!r}: hour 0-23, minute 0-59")

    now_tz = now.astimezone(tz)
    target = now_tz.replace(hour=hour, minute=minute, second=0, microsecond=0)
    target = target.astimezone(tz)
    if target <= now_tz:
        target = (target + datetime.timedelta(days=1)).astimezone(tz)
    return (target - now_tz).total_seconds()


async def _loop(settings, *, do_push: bool) -> None:
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
        await asyncio.sleep(wait)
        try:
            ok = await run_once(settings, do_push=do_push)
            if not ok and settings.alert_webhook:
                await _send_alert(settings, "VPN tester run produced no usable output.")
        except Exception:
            log.exception("Pipeline error")
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
    parser.add_argument("--verbose", action="store_true", help="debug logging")
    args = parser.parse_args(argv)

    settings = load_settings(args.config)
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
