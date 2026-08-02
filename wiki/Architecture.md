<div dir="rtl">

# معماری

سامانه از چند ماژول مستقل تشکیل شده که هر کدام یک مسئولیت مشخص دارند. نقطه‌ی ورود، فرمان `vpn-tester` (تابع `cli` در `main.py`) است.

## نقشه‌ی ماژول‌ها (۱۶ ماژول)

```
┌────────────────────────────────────────────────────────────────────┐
│                         vpn-tester (CLI)                            │
├────────────────────────────────────────────────────────────────────┤
│  __init__.py       - نسخه‌ی پکیج (__version__ = "2.4.0")            │
│  config.py         - بارگذاری تنظیمات از config.env / متغیر محیطی   │
│  main.py           - ورودی CLI، حلقه‌ی زمان‌بندی، اجرای تکی        │
│  pipeline.py       - ارکستراسیون: دانلود ← تست ← انتخاب            │
│  runtime.py        - گزارش‌گر پیشرفت، هماهنگ‌کننده اجرا، زمان‌بندی │
├────────────────────────────────────────────────────────────────────┤
│  subscription.py   - دانلود و دیکود (base64 / JSON / متن ساده)      │
│  parsers.py        - URI ← کانفیگ Xray / sing-box / Hysteria       │
│  tcp_ping.py       - پیش‌فیلتر ارزان TCP                            │
│  geoip.py          - تشخیص کشور خروجی (چند ارائه‌دهنده + کش)        │
│  models.py         - مدل داده‌ی Config و محاسبات آماری             │
├────────────────────────────────────────────────────────────────────┤
│  cores.py          - دانلود/به‌روزرسانی خودکار هسته‌ها (فعال)      │
│  core_manager.py   - پیاده‌سازی جایگزین مدیریت هسته                 │
│  xray_runner.py    - راه‌اندازی پروسه‌ی هسته + تونل SOCKS5         │
├────────────────────────────────────────────────────────────────────┤
│  output.py         - نوشتن اشتراک Base64 + متادیتای JSON            │
│  github_push.py    - ارسال امن از طریق GitHub Contents API         │
│  web.py            - داشبورد (HTML/JS + JSON API)                   │
└────────────────────────────────────────────────────────────────────┘
```

## شرح هر ماژول

| ماژول | مسئولیت |
|-------|---------|
| `__init__.py` | تعریف `__version__ = "2.4.0"`. |
| `config.py` | دیتاکلاس `Settings` و `load_settings`؛ اولویت: متغیر محیطی > `config.env` > پیش‌فرض. شامل پیش‌فرض‌های کشورها، هدف‌های تست و ارائه‌دهنده‌های geoip. |
| `main.py` | تجزیه‌ی آرگومان‌ها (`--once`, `--no-push`, `--no-dashboard`, `--port`, `--verbose`)، راه‌اندازی لاگ چرخشی، `run_once`، حلقه‌ی زمان‌بندی `_loop` و ارسال هشدار. |
| `pipeline.py` | خط لوله‌ی سرتاسری: `download_configs` ← `tcp_filter` ← `country_filter` ← `url_test_all` ← `select_top` و منطق افزایشی. |
| `runtime.py` | `Reporter` (وضعیت + بافر حلقوی لاگ)، `LogCapture`، `RunCoordinator` (اجرای تک‌درجریان) و `seconds_until_next_run`. ثابت‌های نام مراحل نیز اینجا هستند. |
| `subscription.py` | `fetch_subscription` و `decode_subscription`؛ تشخیص base64 / JSON (sing-box، Clash) / متن ساده و استخراج URI یکتا. |
| `parsers.py` | توابع خالص برای تبدیل URI به outbound؛ سازنده‌های کانفیگ Xray، sing-box و YAML کلاینت Hysteria. |
| `tcp_ping.py` | `tcp_ping`: تلاش چندباره‌ی اتصال TCP و شمارش موفقیت‌ها. |
| `geoip.py` | `GeoCache` و `fetch_country`؛ پرس‌وجوی چند ارائه‌دهنده به‌ترتیب، اولین موفقیت برنده و کش بر اساس IP خروجی. |
| `models.py` | دیتاکلاس `Config`: ثبت نتایج هر هدف، `weighted_error_rate`، `avg_latency`، صدک‌ها و `display_name`. |
| `cores.py` | ماژول **فعال** مدیریت هسته که `main.py` از آن `ensure_cores` را صدا می‌زند؛ دانلود، بررسی نسخه و جایگزینی اتمیک. |
| `core_manager.py` | پیاده‌سازی جایگزین (کلاس `CoreManager`) با ساختار دایرکتوری و فایل نسخه؛ در جریان اصلی صدا زده نمی‌شود. |
| `xray_runner.py` | `CoreRunner`: نوشتن کانفیگ موقت، راه‌اندازی پروسه، انتظار برای باز شدن پورت SOCKS، ساخت session با `ProxyConnector` و `test_url`. |
| `output.py` | `write_subscription` و `build_metadata`؛ خروجی base64 و JSON متادیتا. |
| `github_push.py` | `push_to_github`؛ GET SHA فعلی، سپس PUT محتوا از طریق Contents API با هدر Bearer. |
| `web.py` | `create_app` و `start_dashboard`؛ صفحه‌ی HTML تک‌فایلی به‌همراه JSON API. |

## جریان داده

1. **دانلود** — گرفتن URLهای اشتراک، دیکود (base64 / JSON / متن ساده)، استخراج و یکتا کردن URIها.
2. **فیلتر TCP** — پینگ ارزان TCP برای حذف سرورهای در دسترس‌نبودن (با سقف هم‌روندی).
3. **فیلتر کشور** — راه‌اندازی یک پروسه‌ی هسته برای هر کانفیگ و تشخیص IP خروجی از طریق geoip.
4. **تست‌های URL** — استفاده‌ی مجدد از همان پروسه‌ی هسته و تست هدف‌های وزنی در چند دور.
5. **انتخاب** — حذف کانفیگ‌های پرخطا، انتخاب بهترین N برای هر کشور و شماره‌گذاری.
6. **افزایشی (اختیاری)** — کانفیگ‌های سالم اجرای قبل نگه داشته می‌شوند و جاهای خالی با جدیدها پر می‌شود.
7. **خروجی و ارسال** — نوشتن اشتراک base64 + متادیتا و ارسال به گیت‌هاب.

</div>

---

# Architecture

The system is composed of several independent modules, each with one clear responsibility. The entry point is the `vpn-tester` command (`cli` in `main.py`).

## Module Map (16 modules)

```
┌────────────────────────────────────────────────────────────────────┐
│                         vpn-tester (CLI)                            │
├────────────────────────────────────────────────────────────────────┤
│  __init__.py       - Package version (__version__ = "2.4.0")        │
│  config.py         - Load settings from config.env / env vars       │
│  main.py           - CLI entry, scheduler loop, single run          │
│  pipeline.py       - Orchestration: download -> test -> select      │
│  runtime.py        - Progress reporter, run coordinator, scheduler   │
├────────────────────────────────────────────────────────────────────┤
│  subscription.py   - Download & decode (base64 / JSON / plain)      │
│  parsers.py        - URI -> Xray / sing-box / Hysteria configs      │
│  tcp_ping.py       - Cheap TCP pre-filter                           │
│  geoip.py          - Exit-country detection (multi-provider + cache)│
│  models.py         - Config data model + statistics                 │
├────────────────────────────────────────────────────────────────────┤
│  cores.py          - Core auto-download / auto-update (active)      │
│  core_manager.py   - Alternate core-management implementation       │
│  xray_runner.py    - Core process launcher + SOCKS5 tunnel          │
├────────────────────────────────────────────────────────────────────┤
│  output.py         - Base64 subscription + metadata JSON            │
│  github_push.py    - Secure push via GitHub Contents API            │
│  web.py            - Dashboard (HTML/JS + JSON API)                 │
└────────────────────────────────────────────────────────────────────┘
```

## Per-module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `__init__.py` | Defines `__version__ = "2.4.0"`. |
| `config.py` | `Settings` dataclass and `load_settings`; precedence env var > `config.env` > default. Holds defaults for countries, test targets, and geoip providers. |
| `main.py` | Argument parsing (`--once`, `--no-push`, `--no-dashboard`, `--port`, `--verbose`), rotating-log setup, `run_once`, the `_loop` scheduler, and alerting. |
| `pipeline.py` | End-to-end pipeline: `download_configs` → `tcp_filter` → `country_filter` → `url_test_all` → `select_top` plus incremental logic. |
| `runtime.py` | `Reporter` (status + log ring buffer), `LogCapture`, `RunCoordinator` (single-flight runs), and `seconds_until_next_run`. Stage-name constants live here. |
| `subscription.py` | `fetch_subscription` and `decode_subscription`; detects base64 / JSON (sing-box, Clash) / plain text and extracts unique URIs. |
| `parsers.py` | Pure URI→outbound functions; builders for Xray, sing-box, and the Hysteria client YAML. |
| `tcp_ping.py` | `tcp_ping`: repeated TCP connect attempts, counting successes. |
| `geoip.py` | `GeoCache` and `fetch_country`; queries providers in order, first success wins, caches per exit IP. |
| `models.py` | `Config` dataclass: per-target result recording, `weighted_error_rate`, `avg_latency`, percentiles, and `display_name`. |
| `cores.py` | The **active** core manager; `main.py` calls its `ensure_cores` — download, version check, atomic replace. |
| `core_manager.py` | Alternate implementation (`CoreManager`) with a directory layout and version file; not called by the main flow. |
| `xray_runner.py` | `CoreRunner`: writes a temp config, launches the process, waits for the SOCKS port, builds a `ProxyConnector` session, and `test_url`. |
| `output.py` | `write_subscription` and `build_metadata`; base64 output and JSON metadata. |
| `github_push.py` | `push_to_github`; GET current SHA, then PUT content via the Contents API with a Bearer header. |
| `web.py` | `create_app` and `start_dashboard`; a single-page HTML dashboard plus JSON API. |

## Data Flow

1. **Download** — fetch subscription URLs, decode (base64 / JSON / plain), extract and dedupe URIs.
2. **TCP filter** — cheap TCP ping to drop unreachable servers (concurrency-capped).
3. **Country filter** — launch one core process per config, probe exit IP via geoip.
4. **URL tests** — reuse the same core process, test weighted targets over multiple rounds.
5. **Select** — drop high-error configs, take the best N per country, assign indices.
6. **Incremental (optional)** — keep still-working previous configs, fill gaps with new ones.
7. **Output & push** — write the base64 subscription + metadata, push to GitHub.
