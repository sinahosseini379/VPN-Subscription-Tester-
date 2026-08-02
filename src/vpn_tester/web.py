# ruff: noqa: E501  # the embedded HTML/JS dashboard is intentionally long-lined
"""Web dashboard served alongside the scheduler loop.

Endpoints
---------
GET  /                          -> dashboard UI (single HTML page)
GET  /subscription              -> raw base64 subscription (profile-title/userinfo)
GET  /api/status                -> run status + progress snapshot
GET  /api/logs?after=N          -> incremental log lines
GET  /api/configs               -> final configs (URIs + metadata) from disk
POST /api/run                   -> trigger a manual run
GET  /api/subscriptions         -> current subscription URLs
POST /api/subscriptions         -> replace the full URL list
POST /api/subscriptions/add     -> append one URL
POST /api/subscriptions/remove  -> remove one URL
GET  /api/schedule              -> current schedule + timezone
POST /api/schedule              -> persist + apply a new schedule
"""

from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path

from aiohttp import web

from .config import Settings
from .runtime import RunCoordinator, reporter, seconds_until_next_run

log = logging.getLogger(__name__)

APP_SETTINGS = web.AppKey("settings", Settings)
APP_COORDINATOR = web.AppKey("coordinator", RunCoordinator)
APP_ENV_FILE = web.AppKey("env_file", str)

# The dashboard is a static single-page app shipped alongside this package.
STATIC_DIR = Path(__file__).parent / "static"

# -- file helpers -----------------------------------------------------------


def _load_configs(settings: Settings) -> dict:
    """Merge base64 output URIs with their metadata items."""
    meta: dict = {}
    meta_path = Path(settings.metadata_file)
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}

    items = meta.get("items") or []
    uris: list[str] = []
    out_path = Path(settings.output_file)
    if out_path.exists():
        try:
            raw = re.sub(r"\s+", "", out_path.read_text(encoding="utf-8"))
            decoded = base64.b64decode(raw + "==").decode("utf-8", errors="ignore")
            uris = decoded.splitlines()
        except Exception:
            uris = []

    configs = []
    for i, uri in enumerate(uris):
        item = items[i] if i < len(items) else {}
        configs.append({"uri": uri, **item})
    return {"generated_at": meta.get("generated_at"), "count": len(configs), "configs": configs}


def _read_subscriptions(settings: Settings) -> list[str]:
    p = Path(settings.subscriptions_file)
    if not p.exists():
        return []
    return [
        line.strip()
        for line in p.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def _write_subscriptions(settings: Settings, urls: list[str]) -> list[str]:
    cap = settings.max_subscription_urls
    if len(urls) > cap:
        urls = urls[:cap]
    p = Path(settings.subscriptions_file)
    header = f"# Subscription URLs — one per line, max {cap}. Lines starting with # are ignored.\n"
    p.write_text(header + "\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")
    return urls


def _update_env(path: str, key: str, value: str) -> None:
    """Set/replace one KEY=VALUE in an env file, uncommenting if needed."""
    p = Path(path)
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    prefix = key + "="
    found = False
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        body = stripped.lstrip("#").strip()
        if body.startswith(prefix):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    p.write_text("\n".join(out) + "\n", encoding="utf-8")


# -- handlers ---------------------------------------------------------------


async def _index(_request: web.Request) -> web.Response:
    return web.FileResponse(STATIC_DIR / "index.html")


async def _favicon(_request: web.Request) -> web.Response:
    return web.Response(status=204)


async def _status(_request: web.Request) -> web.Response:
    return web.json_response(reporter.snapshot())


async def _subscription(request: web.Request) -> web.Response:
    """Serve the published subscription with profile headers clients understand.

    GitHub raw files can't carry `subscription-userinfo`/`profile-title`, so the
    dashboard exposes the same bytes with the headers that make mobile apps
    display the profile name and honour the auto-update interval.
    """
    settings: Settings = request.app[APP_SETTINGS]
    out_path = Path(settings.output_file)
    if not out_path.exists():
        raise web.HTTPNotFound(text="No subscription has been published yet.")
    content = out_path.read_text(encoding="utf-8").strip()
    interval = settings.subscription_interval_hours * 3600
    title_b64 = base64.b64encode(settings.subscription_name.encode("utf-8")).decode("ascii")
    headers = {
        "content-type": "text/plain; charset=utf-8",
        "profile-title": title_b64,
        "subscription-userinfo": f"interval={interval}",
        "profile-update-interval": str(interval),
    }
    return web.Response(text=content, headers=headers)


async def _logs(request: web.Request) -> web.Response:
    try:
        after = int(request.query.get("after", "0"))
    except ValueError:
        after = 0
    seq, lines = reporter.logs_after(after)
    return web.json_response({"seq": seq, "lines": lines})


async def _configs(request: web.Request) -> web.Response:
    settings: Settings = request.app[APP_SETTINGS]
    return web.json_response(_load_configs(settings))


async def _run(request: web.Request) -> web.Response:
    coordinator: RunCoordinator = request.app[APP_COORDINATOR]
    started = coordinator.trigger_run()
    return web.json_response({"started": started, "status": reporter.status})


async def _get_subscriptions(request: web.Request) -> web.Response:
    settings: Settings = request.app[APP_SETTINGS]
    return web.json_response(
        {"urls": _read_subscriptions(settings), "max": settings.max_subscription_urls}
    )


async def _set_subscriptions(request: web.Request) -> web.Response:
    settings: Settings = request.app[APP_SETTINGS]
    data = await request.json()
    urls = data.get("urls") or []
    if not isinstance(urls, list):
        raise web.HTTPBadRequest(text="urls must be a list")
    cleaned = [str(u).strip() for u in urls if str(u).strip()]
    return web.json_response({"urls": _write_subscriptions(settings, cleaned)})


async def _add_subscription(request: web.Request) -> web.Response:
    settings: Settings = request.app[APP_SETTINGS]
    data = await request.json()
    url = str(data.get("url", "")).strip()
    if not url:
        raise web.HTTPBadRequest(text="url required")
    urls = _read_subscriptions(settings)
    if url not in urls:
        urls.append(url)
    return web.json_response({"urls": _write_subscriptions(settings, urls)})


async def _remove_subscription(request: web.Request) -> web.Response:
    settings: Settings = request.app[APP_SETTINGS]
    data = await request.json()
    url = str(data.get("url", "")).strip()
    urls = [u for u in _read_subscriptions(settings) if u != url]
    return web.json_response({"urls": _write_subscriptions(settings, urls)})


async def _get_schedule(request: web.Request) -> web.Response:
    settings: Settings = request.app[APP_SETTINGS]
    return web.json_response(
        {"schedule_time": settings.schedule_time, "timezone": settings.timezone}
    )


async def _set_schedule(request: web.Request) -> web.Response:
    settings: Settings = request.app[APP_SETTINGS]
    coordinator: RunCoordinator = request.app[APP_COORDINATOR]
    env_file: str = request.app[APP_ENV_FILE]
    data = await request.json()

    schedule_time = str(data.get("schedule_time", settings.schedule_time)).strip()
    timezone = str(data.get("timezone", settings.timezone)).strip()
    if not schedule_time or not timezone:
        raise web.HTTPBadRequest(text="schedule_time and timezone are required")

    try:
        seconds_until_next_run(schedule_time, tz_name=timezone)
    except ValueError as exc:
        raise web.HTTPBadRequest(text=str(exc)) from None

    settings.schedule_time = schedule_time
    settings.timezone = timezone
    _update_env(env_file, "SCHEDULE_TIME", schedule_time)
    _update_env(env_file, "TIMEZONE", timezone)
    coordinator.request_schedule_change()
    log.info("Schedule updated via dashboard: %s %s", schedule_time, timezone)
    return web.json_response({"schedule_time": schedule_time, "timezone": timezone})


# -- app factory ------------------------------------------------------------


def create_app(
    settings: Settings, coordinator: RunCoordinator, env_file: str = "config.env"
) -> web.Application:
    app = web.Application()
    app[APP_SETTINGS] = settings
    app[APP_COORDINATOR] = coordinator
    app[APP_ENV_FILE] = env_file

    app.router.add_get("/", _index)
    app.router.add_get("/favicon.ico", _favicon)
    app.router.add_get("/subscription", _subscription)
    app.router.add_get("/api/status", _status)
    app.router.add_get("/api/logs", _logs)
    app.router.add_get("/api/configs", _configs)
    app.router.add_post("/api/run", _run)
    app.router.add_get("/api/subscriptions", _get_subscriptions)
    app.router.add_post("/api/subscriptions", _set_subscriptions)
    app.router.add_post("/api/subscriptions/add", _add_subscription)
    app.router.add_post("/api/subscriptions/remove", _remove_subscription)
    app.router.add_get("/api/schedule", _get_schedule)
    app.router.add_post("/api/schedule", _set_schedule)
    app.router.add_static("/static/", STATIC_DIR, name="static")
    return app


async def start_dashboard(
    settings: Settings, coordinator: RunCoordinator, env_file: str
) -> web.AppRunner:
    app = create_app(settings, coordinator, env_file)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.dashboard_host, settings.dashboard_port)
    await site.start()
    log.info(
        "Dashboard listening on http://%s:%d", settings.dashboard_host, settings.dashboard_port
    )
    return runner
