# Technical Wiki

This wiki contains technical documentation for VPN Subscription Tester.

## Table of Contents

- [Architecture](Architecture)
- [Configuration](Configuration)
- [Core Management](Core-Management)
- [Pipeline](Pipeline)
- [Incremental Runs](Incremental-Runs)
- [Dashboard API](Dashboard-API)
- [GitHub Push](GitHub-Push)
- [Deployment](Deployment)
- [Testing](Testing)

---

## Architecture

### Overview

The system is composed of several independent modules:

```
┌─────────────────────────────────────────────────────────────────┐
│                        vpn-tester CLI                            │
├─────────────────────────────────────────────────────────────────┤
│  config.py          - All settings from config.env / env vars   │
│  main.py            - CLI entry, scheduler, dashboard           │
│  pipeline.py        - Orchestration: download → test → select   │
├─────────────────────────────────────────────────────────────────┤
│  cores.py           - Xray / Sing-box / Hysteria auto-update    │
│  parsers.py         - URI → Xray/JSON outbound configs          │
│  xray_runner.py     - Spawns Xray processes, readiness polling  │
│  tcp_ping.py        - Cheap TCP pre-filter                      │
│  geoip.py           - Exit-country detection (3 providers)      │
│  subscription.py    - Download & decode (base64/JSON/plain)     │
├─────────────────────────────────────────────────────────────────┤
│  output.py          - Base64 subscription + metadata JSON       │
│  github_push.py     - Secure push via GitHub Contents API       │
├─────────────────────────────────────────────────────────────────┤
│  runtime.py         - Progress reporter + run coordinator       │
│  web.py             - Dashboard (HTML/JS + JSON API)            │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Download** – Fetch subscription URLs, decode (base64/JSON/plain), extract URIs
2. **TCP Filter** – Cheap TCP ping to filter unreachable servers (concurrency-capped)
3. **Country Filter** – Launch one core process per config, probe exit IP via geoip
4. **URL Tests** – Reuse core processes, test weighted target URLs over multiple rounds
5. **Select** – Drop high-error configs, take best N per country, assign indices
6. **Output** – Write base64 subscription + metadata JSON
7. **Push** – Upload to GitHub via Contents API (Bearer token, no token on disk)

---

## Configuration

All settings live in `config.env` (or environment variables). See [config.env.example](../config.env.example) for the complete list.

### Key Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_TOKEN` | — | GitHub PAT with `repo` scope |
| `GITHUB_OWNER` | — | GitHub username/org |
| `GITHUB_REPO` | — | Target repository name |
| `GITHUB_BRANCH` | `main` | Branch to push to |
| `OUTPUT_FILE` | `best_configs.txt` | Local output filename |
| `SCHEDULE_TIME` | `04:04` | Daily run time (HH:MM) |
| `TIMEZONE` | `Asia/Tehran` | IANA timezone |
| `ALLOWED_COUNTRIES` | `DE:Germany:🇩🇪,FI:Finland:🇫🇮,...` | Comma-separated `CC:Name:Flag` |
| `TEST_URLS` | `Google,http://...,1.0\|...` | Pipe-separated `Label,URL[,weight]` |
| `MAX_CONFIGS` | `500` | Hard cap on configs entering pipeline |
| `CONFIGS_PER_COUNTRY` | `2` | Best configs to keep per country |
| `URL_TEST_ROUNDS` | `5` | Test rounds per target |
| `TCP_CONCURRENCY` | `100` | Max parallel TCP pings |
| `MAX_CONCURRENT` | `10` | Max parallel core processes |
| `AUTO_UPDATE_CORES` | `true` | Auto-download Xray/Sing-box/Hysteria |
| `CORES_DIR` | `cores` | Directory for managed cores |
| `INCREMENTAL` | `true` | Reuse working configs from previous run |
| `SUBSCRIPTION_NAME` | `Fiddel` | Subscription name in VPN apps |
| `SUBSCRIPTION_UPDATE_INTERVAL_HOURS` | `24` | Auto-update hint for VPN apps |
| `DASHBOARD_ENABLED` | `true` | Enable web dashboard |
| `DASHBOARD_PORT` | `30445` | Dashboard port |

---

## Core Management

### Supported Cores

| Core | Repo | Asset Pattern | Version Cmd |
|------|------|---------------|-------------|
| Xray | `XTLS/Xray-core` | `xray-linux-64.zip` | `xray version` |
| Sing-box | `SagerNet/sing-box` | `sing-box-*-linux-amd64.tar.gz` | `sing-box version` |
| Hysteria | `apernet/hysteria` | `hysteria-linux-amd64*` | `hysteria version` |

### Auto-Update Logic

On every run (if `AUTO_UPDATE_CORES=true`):

1. For each core, check if explicit `*_BIN` is set → use that
2. Otherwise, query GitHub API for latest release
3. Compare installed version vs latest tag
4. If newer available, download asset, extract, verify version, replace
5. Atomic replace: download → temp file → version check → atomic `os.replace`

### Version Detection

Each core has a version regex:
- Xray: `Xray\s+([0-9A-Za-z._-]+)`
- Sing-box: `sing-box\s+([0-9A-Za-z._-]+)`
- Hysteria: `[Hh]ysteria\s+v?([0-9]+\.[0-9]+\.[0-9]+)`

---

## Pipeline

### Stages

| Stage | Progress | Description |
|-------|----------|-------------|
| `downloading` | 0–6% | Download subscriptions, extract URIs |
| `tcp-ping` | 6–22% | TCP ping all servers (capped concurrency) |
| `country-check` | 22–55% | Launch cores, probe exit country via geoip |
| `url-tests` | 55–95% | Reuse cores, test weighted URLs over rounds |
| `finalize` | 95–100% | Select best, write output, push to GitHub |

### Concurrency Control

- **TCP**: `asyncio.Semaphore(TCP_CONCURRENCY)` – caps socket storm
- **Core processes**: `asyncio.Semaphore(MAX_CONCURRENT)` – caps process spawns
- **URL tests**: Reuses one core process per config for all rounds

### Weighted Targets

Each test URL has a weight (default 1.0). The final error rate is:

```
weighted_error_rate = Σ(weight_i * fail_i) / Σ(weight_i * total_i)
```

This lets you prioritize critical targets (e.g., YouTube) over auxiliary ones.

---

## Incremental Runs

When `INCREMENTAL=true` (default):

1. Load previous run's configs from `output_file` + `metadata_file`
2. Run **one fast URL round** on each previous config
3. Keep configs that still pass `max_error_rate`
4. Merge: prefer still-working previous configs, then fill with new ones
5. Cap total at `configs_per_country * allowed_countries`

Benefits:
- Stable subscription – configs don't flip-flop between runs
- Faster – fewer full URL test rounds on stable configs
- Predictable size – output stays at configured cap

---

## Dashboard API

The dashboard runs on port `30445` (configurable) and provides a web UI + JSON API.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | HTML dashboard |
| `GET` | `/api/status` | Current run status (stage, progress, logs) |
| `GET` | `/api/logs?after=N` | Log lines after sequence N |
| `GET` | `/api/configs` | Current best configs with metadata |
| `POST` | `/api/run` | Trigger manual run |
| `GET` | `/api/subscriptions` | List subscription URLs |
| `POST` | `/api/subscriptions` | Replace all URLs |
| `POST` | `/api/subscriptions/add` | Add one URL |
| `POST` | `/api/subscriptions/remove` | Remove one URL |
| `GET` | `/api/schedule` | Get schedule (time, timezone) |
| `POST` | `/api/schedule` | Update schedule (persists to `config.env`) |

### Live Updates

The dashboard polls `/api/status` and `/api/logs` every 1.5s to show:
- Real-time progress bar (stage + percentage)
- Streaming log output (last 200 lines ring buffer)
- Manual run button with instant feedback

---

## GitHub Push

### Security

- Uses **GitHub Contents API** (`PUT /repos/{owner}/{repo}/contents/{path}`)
- Token sent as `Authorization: Bearer <token>` header
- Token **never touches disk** (not in remote URL, not in git config)
- Supports nested paths (e.g., `outputs/best_configs.txt`)

### Process

1. Read local `output_file` and `metadata_file`
2. For each file in `GITHUB_FILES`:
   - GET current file SHA (if exists)
   - PUT new content with commit message
   - Retry up to 3 times on transient errors
3. Commit author: `VPN Tester Bot <vpn-bot@noreply.local>`

### Refusal to Publish

If `len(top) < ALERT_MIN_CONFIGS` (default 3), the run aborts and **does not overwrite** the published subscription. This prevents bad runs from wiping a working subscription.

---

## Deployment

### Docker

```yaml
# docker-compose.yml
services:
  tester:
    build: .
    restart: unless-stopped
    env_file: config.env
    ports:
      - "30445:30445"
    volumes:
      - ./config.env:/app/config.env
      - ./subscriptions.txt:/app/subscriptions.txt
      - ./output:/app/output
```

### Systemd (User Service)

```ini
# ~/.config/systemd/user/vpn-tester.service
[Unit]
Description=VPN Subscription Tester (scheduler + dashboard :30445)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/vpn-tester
ExecStart=%h/vpn-tester/.venv/bin/vpn-tester
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

Enable lingering for user services to run at boot:
```bash
loginctl enable-linger $USER
systemctl --user enable --now vpn-tester
```

### Requirements

- Python 3.11+
- Xray / Sing-box / Hysteria (auto-managed if `AUTO_UPDATE_CORES=true`)
- GitHub PAT with `repo` scope

---

## Testing

### Test Suite

```
tests/
├── test_config.py       - Settings loading, parsing
├── test_cores.py        - Core auto-update logic
├── test_github_push.py  - Push logic (mocked)
├── test_main.py         - CLI, logging setup
├── test_output.py       - Base64 output + metadata
├── test_pipeline.py     - Full pipeline (mocked cores)
├── test_scheduler.py    - Time calculation
├── test_subscription.py - Decoding (base64/JSON/plain)
├── test_parsers.py      - URI parsing (all protocols)
├── test_runtime.py      - Progress reporter, coordinator
├── test_web.py          - Dashboard API (aiohttp TestClient)
├── test_socks.py        - Real SOCKS5 regression test
├── test_parsers.py      - URI parsing + edge cases
└── test_scheduler.py    - Schedule time calculation
```

### Run Tests

```bash
# All tests
pytest -q

# With coverage
pytest --cov=src/vpn_tester -q

# Lint + format
ruff check src tests && ruff format --check src tests
```

### Real SOCKS5 Test

`test_socks.py` spawns a real Xray process with a known working config and tests the SOCKS5 proxy path end-to-end. Requires `xray` binary in PATH.