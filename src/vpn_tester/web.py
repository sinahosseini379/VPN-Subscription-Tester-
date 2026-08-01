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
    return web.Response(text=HTML, content_type="text/html")


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


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VPN Subscription Tester</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: ui-monospace, "Cascadia Mono", Consolas, monospace;
    background: #0f1419; color: #e6edf3; padding: 20px;
  }
  h1 { font-size: 18px; margin: 0 0 4px; }
  .sub { color: #8b949e; font-size: 12px; margin-bottom: 16px; }
  .card {
    background: #161b22; border: 1px solid #30363d; border-radius: 8px;
    padding: 16px; margin-bottom: 16px;
  }
  .card h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .5px;
    color: #8b949e; margin: 0 0 12px; }
  .row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  .badge { padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }
  .idle   { background:#21262d; color:#8b949e; }
  .running{ background:#1f6feb33; color:#58a6ff; }
  .done   { background:#23863633; color:#3fb950; }
  .failed { background:#f8514933; color:#f85149; }
  .bar { background: #21262d; border-radius: 6px; height: 14px; overflow: hidden; margin-top: 8px; }
  .fill { background: linear-gradient(90deg,#1f6feb,#3fb950); height: 100%; width: 0%;
    transition: width .4s ease; }
  .msg { margin-top: 6px; font-size: 12px; color: #8b949e; min-height: 16px; }
  button {
    background: #238636; color: #fff; border: 0; border-radius: 6px;
    padding: 8px 14px; font-size: 13px; cursor: pointer; font-family: inherit;
  }
  button:hover { background: #2ea043; }
  button:disabled { background: #21262d; color: #8b949e; cursor: not-allowed; }
  button.mini { background: #21262d; color: #58a6ff; padding: 4px 10px; font-size: 12px; }
  button.mini:hover { background: #30363d; }
  button.danger { background: #f85149; }
  button.danger:hover { background: #da3633; }
  pre.logs {
    background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
    padding: 10px; height: 260px; overflow-y: auto; font-size: 12px; line-height: 1.5;
    margin: 0; white-space: pre-wrap; word-break: break-word; color: #9da7b3;
  }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #21262d; }
  th { color: #8b949e; font-weight: 600; font-size: 12px; }
  td.uri { font-size: 12px; color: #9da7b3; word-break: break-all; }
  .empty { color: #8b949e; font-size: 13px; padding: 10px 0; }
  input[type=text], input[type=time], select {
    background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
    color: #e6edf3; padding: 8px 10px; font-size: 13px; font-family: inherit;
  }
  .flag { margin-right: 4px; }
  .toast { position: fixed; bottom: 16px; right: 16px; background: #238636; color: #fff;
    padding: 10px 16px; border-radius: 6px; font-size: 13px; opacity: 0; transition: opacity .3s; }
  .toast.show { opacity: 1; }
  ul.subs { list-style: none; margin: 0; padding: 0; }
  ul.subs li { display: flex; gap: 8px; align-items: center; padding: 6px 0;
    border-bottom: 1px solid #21262d; }
  ul.subs .url { flex: 1; font-size: 12px; color: #9da7b3; word-break: break-all; }
  a { color: #58a6ff; }
</style>
</head>
<body>
  <h1>VPN Subscription Tester</h1>
  <div class="sub">Live dashboard — port 30445</div>

  <div class="card">
    <div class="row">
      <span class="badge idle" id="badge">idle</span>
      <span id="stage" style="font-size:13px;color:#8b949e"></span>
      <button id="runBtn" onclick="runNow()">Run now</button>
    </div>
    <div class="bar"><div class="fill" id="fill"></div></div>
    <div class="msg" id="msg"></div>
    <pre class="logs" id="logs" style="margin-top:10px"></pre>
  </div>

  <div class="card">
    <h2>Final configs</h2>
    <div id="configs"><div class="empty">No published configs yet.</div></div>
  </div>

  <div class="card">
    <h2>Subscriptions</h2>
    <ul class="subs" id="subs"></ul>
    <div class="row" style="margin-top:10px">
      <input type="text" id="newSub" placeholder="https://.../subscription" style="flex:1">
      <button onclick="addSub()">Add</button>
    </div>
    <div class="msg">Up to <span id="subMax"></span> URLs.</div>
  </div>

  <div class="card">
    <h2>Automatic run schedule</h2>
    <div class="row">
      <label>Time <input type="time" id="schedTime"></label>
      <label>Timezone <input type="text" id="schedTz" placeholder="Asia/Tehran"></label>
      <button onclick="saveSchedule()">Save</button>
    </div>
    <div class="msg" id="schedMsg"></div>
  </div>

  <div class="toast" id="toast"></div>

<script>
let logSeq = 0;
const $ = id => document.getElementById(id);

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    let txt = r.statusText;
    try { txt = (await r.json()).detail || txt; } catch (e) {}
    throw new Error(txt);
  }
  return r.json();
}

function toast(msg) {
  const t = $("toast"); t.textContent = msg; t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 1800);
}

function badge(status) {
  const b = $("badge");
  b.className = "badge " + status;
  b.textContent = status;
}

async function refreshStatus() {
  try {
    const s = await api("/api/status");
    badge(s.status);
    $("stage").textContent = s.stage || "";
    $("msg").textContent = s.message || "";
    $("fill").style.width = Math.round(s.progress * 100) + "%";
    $("runBtn").disabled = s.status === "running";
    return s;
  } catch (e) { console.error(e); return null; }
}

async function refreshLogs() {
  try {
    const d = await api("/api/logs?after=" + logSeq);
    if (d.lines && d.lines.length) {
      logSeq = d.seq;
      const el = $("logs");
      el.textContent += d.lines.join("\\n") + "\\n";
      el.scrollTop = el.scrollHeight;
    }
  } catch (e) { console.error(e); }
}

async function refreshConfigs() {
  try {
    const d = await api("/api/configs");
    const box = $("configs");
    if (!d.configs || !d.configs.length) {
      box.innerHTML = '<div class="empty">No published configs yet.</div>';
      return;
    }
    const rows = d.configs.map((c, i) => {
      const name = (c.country_name ? (c.flag + " " + c.country_name) : (c.name || "config")) + "  #" + (i + 1);
      const lat = c.avg_latency_ms != null ? Math.round(c.avg_latency_ms) + "ms" : "-";
      const err = c.weighted_error_rate != null ? Math.round(c.weighted_error_rate * 100) + "%" : "-";
      const uriJson = JSON.stringify(c.uri);
      return `<tr><td>${name}</td><td class="uri">${c.uri}</td>` +
        `<td>${lat}</td><td>${err}</td>` +
        `<td><button class="mini" onclick='copyUri(${uriJson})'>Copy</button></td></tr>`;
    }).join("");
    box.innerHTML = `<table><thead><tr><th>Name</th><th>URI</th><th>Latency</th><th>Errors</th><th></th></tr></thead><tbody>${rows}</tbody></table>`;
  } catch (e) { console.error(e); }
}

async function copyUri(uri) {
  try { await navigator.clipboard.writeText(uri); toast("Copied"); }
  catch (e) {
    const ta = document.createElement("textarea");
    ta.value = uri; document.body.appendChild(ta); ta.select();
    document.execCommand("copy"); ta.remove(); toast("Copied");
  }
}

async function runNow() {
  $("runBtn").disabled = true;
  try {
    const d = await api("/api/run", { method: "POST" });
    toast(d.started ? "Run started" : "A run is already in progress");
    await refreshStatus();
  } catch (e) { toast("Run failed: " + e.message); }
}

async function refreshSubs() {
  try {
    const d = await api("/api/subscriptions");
    $("subMax").textContent = d.max;
    const ul = $("subs");
    ul.innerHTML = d.urls.length ? d.urls.map(u =>
      `<li><span class="url">${u}</span>` +
      `<button class="mini danger" onclick='delSub(${JSON.stringify(u)})'>Remove</button></li>`
    ).join("") : `<li><span class="url" style="color:#8b949e">No subscriptions configured.</span></li>`;
  } catch (e) { console.error(e); }
}

async function addSub() {
  const url = $("newSub").value.trim();
  if (!url) return;
  try {
    await api("/api/subscriptions/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });
    $("newSub").value = "";
    await refreshSubs();
  } catch (e) { toast("Error: " + e.message); }
}

async function delSub(url) {
  try {
    await api("/api/subscriptions/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });
    await refreshSubs();
  } catch (e) { toast("Error: " + e.message); }
}

async function refreshSchedule() {
  try {
    const d = await api("/api/schedule");
    $("schedTime").value = d.schedule_time;
    $("schedTz").value = d.timezone;
  } catch (e) { console.error(e); }
}

async function saveSchedule() {
  try {
    const d = await api("/api/schedule", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ schedule_time: $("schedTime").value, timezone: $("schedTz").value.trim() })
    });
    $("schedMsg").textContent = "Saved — next run at " + d.schedule_time + " " + d.timezone;
  } catch (e) { $("schedMsg").textContent = "Error: " + e.message; }
}

refreshStatus(); refreshLogs(); refreshConfigs(); refreshSubs(); refreshSchedule();
setInterval(async () => {
  const s = await refreshStatus();
  await refreshLogs();
  if (s && s.status === "done") refreshConfigs();
}, 1500);
setInterval(refreshSubs, 10000);
</script>
</body>
</html>
"""
