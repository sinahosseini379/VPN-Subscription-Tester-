<div dir="rtl">

# استقرار (Deployment)

## نیازمندی‌ها

- **پایتون ۳.۹ به بالا**.
- هسته‌های Xray / sing-box / Hysteria — اگر `AUTO_UPDATE_CORES=true` باشد به‌صورت خودکار مدیریت می‌شوند.
- یک توکن گیت‌هاب با مجوز «Contents: Read and write» روی مخزن مقصد (برای انتشار).
- وابستگی‌های پایتون: `aiohttp`, `aiohttp-socks`, `PyYAML`, `tzdata` (و برای توسعه: `pytest`, `pytest-asyncio`, `ruff`).

## نصب دستی

```bash
git clone https://github.com/sinahosseini379/VPN-Subscription-Tester-
cd VPN-Subscription-Tester-
pip install -e ".[dev]"
cp config.env.example config.env
# GITHUB_TOKEN را در config.env تنظیم کنید
vpn-tester            # حلقه‌ی زمان‌بندی + داشبورد
vpn-tester --once     # فقط یک اجرا
```

اسکریپت `setup.sh` هم همین گام‌ها را (ساخت venv، نصب، دانلود Xray، ساخت config.env و یک تست دود) خودکار می‌کند.

### آرگومان‌های خط فرمان

| آرگومان | کار |
|---------|-----|
| `--config <file>` | فایل تنظیمات (پیش‌فرض `config.env`). |
| `--once` | یک اجرا و خروج. |
| `--no-push` | رد کردن مرحله‌ی ارسال به گیت‌هاب. |
| `--no-dashboard` | غیرفعال کردن داشبورد وب. |
| `--port <n>` | بازنویسی `DASHBOARD_PORT`. |
| `--verbose` | لاگ در سطح DEBUG. |
| `--version` | نمایش نسخه. |

## داکر

`docker-compose.yml`:

```yaml
services:
  tester:
    build: .
    container_name: vpn-subscription-tester
    restart: unless-stopped
    env_file:
      - config.env
    ports:
      - "30445:30445"
    volumes:
      - ./config.env:/app/config.env
      - ./subscriptions.txt:/app/subscriptions.txt
      - ./output:/app/output
    command: ["vpn-tester"]
    healthcheck:
      test: ["CMD", "pgrep", "-f", "vpn-tester"]
      interval: 5m
      timeout: 10s
      start_period: 30s
      retries: 3
```

```bash
docker compose up -d --build
```

- ایمیج بر پایه‌ی `python:3.11-slim` است و هنگام ساخت، آخرین Xray را در `/opt/xray` نصب و `XRAY_BIN=/opt/xray/xray` را تنظیم می‌کند.
- healthcheck صرفاً زنده بودن پروسه را بررسی می‌کند (`pgrep -f vpn-tester`).
- پورت داشبورد `30445` منتشر می‌شود.

## سرویس systemd (کاربری)

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

برای اجرا در زمان بوت (بدون نیاز به ورود کاربر):

```bash
loginctl enable-linger $USER
systemctl --user enable --now vpn-tester
```

</div>

---

# Deployment

## Requirements

- **Python 3.9+**.
- Xray / sing-box / Hysteria cores — managed automatically if `AUTO_UPDATE_CORES=true`.
- A GitHub token with "Contents: Read and write" on the target repo (for publishing).
- Python dependencies: `aiohttp`, `aiohttp-socks`, `PyYAML`, `tzdata` (and for development: `pytest`, `pytest-asyncio`, `ruff`).

## Manual Install

```bash
git clone https://github.com/sinahosseini379/VPN-Subscription-Tester-
cd VPN-Subscription-Tester-
pip install -e ".[dev]"
cp config.env.example config.env
# Set GITHUB_TOKEN in config.env
vpn-tester            # scheduler loop + dashboard
vpn-tester --once     # single run
```

The `setup.sh` script automates the same steps (venv creation, install, Xray download, config.env creation, and a smoke test).

### CLI Arguments

| Argument | Effect |
|----------|--------|
| `--config <file>` | Settings file (default `config.env`). |
| `--once` | Run once and exit. |
| `--no-push` | Skip the GitHub push step. |
| `--no-dashboard` | Disable the web dashboard. |
| `--port <n>` | Override `DASHBOARD_PORT`. |
| `--verbose` | DEBUG-level logging. |
| `--version` | Print the version. |

## Docker

`docker-compose.yml`:

```yaml
services:
  tester:
    build: .
    container_name: vpn-subscription-tester
    restart: unless-stopped
    env_file:
      - config.env
    ports:
      - "30445:30445"
    volumes:
      - ./config.env:/app/config.env
      - ./subscriptions.txt:/app/subscriptions.txt
      - ./output:/app/output
    command: ["vpn-tester"]
    healthcheck:
      test: ["CMD", "pgrep", "-f", "vpn-tester"]
      interval: 5m
      timeout: 10s
      start_period: 30s
      retries: 3
```

```bash
docker compose up -d --build
```

- The image is based on `python:3.11-slim` and installs the latest Xray to `/opt/xray` at build time, setting `XRAY_BIN=/opt/xray/xray`.
- The healthcheck only verifies the process is alive (`pgrep -f vpn-tester`).
- The dashboard port `30445` is published.

## systemd (user service)

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

To run at boot without an interactive login:

```bash
loginctl enable-linger $USER
systemctl --user enable --now vpn-tester
```
