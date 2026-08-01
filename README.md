# VPN Subscription Tester — professional edition

Download subscriptions → live-test **every** config through a real Xray process →
filter by TCP reachability + exit-country → score by disruption% / latency →
publish the best configs to GitHub automatically.

Replaces the original `vpn_tester.py` / `github_push.py` / `run.py` monolith
with a tested, configurable, container-friendly package.

## What changed vs v1

| Area | v1 | v2 |
|---|---|---|
| GitHub push | `git` with the token embedded in the remote URL (leaks into `.git/config` & logs) | **GitHub Contents API**, Bearer header only — token never touches disk |
| run.py | `push_to_github()` was dead code behind an infinite loop | fixed via `--once` / loop modes |
| Country check | unbounded process spawn | concurrency-limited by `MAX_CONCURRENT` |
| Xray startup | fixed 1.5s sleep | **readiness polling** until SOCKS accepts |
| URL test | any HTTP status counted as success | only **2xx/3xx** validated |
| Geo-IP | single `ipapi.co` | 3 fallback providers + per-IP cache |
| Unsupported protocols | accepted then silently dropped | reported & skipped |
| Unused tunables | `MAX_ERROR_RATE`, `EXTRA_ROUNDS` dead code | wired up / removed |
| Tests / CI / Docker | none | pytest + ruff + GitHub Actions + Dockerfile |

## Layout

```
src/vpn_tester/
├── config.py        # all settings from config.env / env vars
├── models.py        # Config dataclass (latency, error rate, percentiles)
├── parsers.py       # URI → Xray JSON (vless/vmess/trojan/ss, ws/grpc/reality…)
├── subscription.py  # download + decode (base64 / JSON / plain)
├── geoip.py         # exit-country via 3 providers + cache
├── tcp_ping.py      # cheap TCP pre-filter
├── xray_runner.py   # one Xray process per config, readiness polling, cleanup
├── pipeline.py      # orchestration
├── output.py        # best_configs.txt (base64) + meta.json
├── github_push.py   # secure GitHub push (Contents API)
└── main.py          # CLI: vpn-tester
```

## Quick start

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate
pip install -e ".[dev]"

# 2. Configure
cp config.env.example config.env   # fill GITHUB_TOKEN (fine-grained, repo Contents: R/W)
# edit subscriptions.txt — one URL per line, max 10

# 3. Run once
python -m vpn_tester.main --once

# 4. Run forever (runs once daily at SCHEDULE_TIME in TIMEZONE, default 04:04 Asia/Tehran)
python -m vpn_tester.main
```

### CLI

```
vpn-tester --once         run a single pipeline then exit
vpn-tester --no-push      skip the GitHub upload
vpn-tester --config PATH  alternate env file
vpn-tester --verbose      debug logging
```

## Docker

```bash
docker compose up -d --build
docker compose run --rm tester vpn-tester --once
```

The image bundles the latest Xray-core and runs the loop with a healthcheck.

## Config knobs (config.env)

`CONFIGS_PER_COUNTRY` (best N per allowed country, in list order), `SCHEDULE_TIME`
(one run per day, HH:MM), `TIMEZONE` (IANA zone for the schedule, default
`Asia/Tehran`), `URL_TEST_ROUNDS`,
`TCP_PING_TRIES`, `TCP_PING_MIN_SUCCESS`, `MAX_ERROR_RATE`,
`MAX_CONCURRENT`, `MAX_SUBSCRIPTION_URLS`,
`ALLOWED_COUNTRIES` (default `DE,FI,NL,GB,US,TR`), `GEOIP_PROVIDERS`,
`XRAY_BIN`, `OUTPUT_FILE`, `METADATA_FILE`, `GITHUB_*`, `ALERT_WEBHOOK`
(Telegram or ntfy), `TEST_URLS`.

The final output contains up to `CONFIGS_PER_COUNTRY` best configs for each
allowed country, listed in `ALLOWED_COUNTRIES` order.

## Security notes

- `config.env` is gitignored; only `config.env.example` is committed.
- Use a **fine-grained PAT** scoped to `Contents: read and write` on the repo,
  never a full-account token.
- The token is sent as a `Bearer` header and is never written into any git
  remote/credential file.
- Sharing VPN configs publicly may violate the upstream providers' ToS — keep
  the output repo private if that is a concern.

## Development

```bash
pip install -e ".[dev]"
ruff check src tests && ruff format src tests
pytest -q
```
