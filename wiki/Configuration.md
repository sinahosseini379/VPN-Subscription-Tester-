<div dir="rtl">

# پیکربندی

همه‌ی تنظیمات از فایل `config.env` (یا متغیرهای محیطی) خوانده می‌شوند. اولویت از بالا به پایین: **متغیر محیطی واقعی > مقدار در `config.env` > پیش‌فرض کد**. برای شروع، `config.env.example` را در `config.env` کپی کنید.

- مقدار خالی به‌معنای «تنظیم‌نشده» است و پیش‌فرض اعمال می‌شود.
- مقادیر بولی این‌ها را `true` می‌شمارند: `1`, `true`, `yes`, `on`.
- خطوطی که با `#` شروع می‌شوند نادیده گرفته می‌شوند.

## گیت‌هاب (الزامی برای انتشار)

| متغیر | پیش‌فرض | توضیح |
|-------|---------|-------|
| `GITHUB_TOKEN` | — | توکن دسترسی با مجوز «Contents: Read and write». هرگز روی دیسک ذخیره نمی‌شود. |
| `GITHUB_OWNER` | — | نام کاربری/سازمان گیت‌هاب. |
| `GITHUB_REPO` | — | نام مخزن مقصد. |
| `GITHUB_BRANCH` | `main` | شاخه‌ای که فایل‌ها روی آن Push می‌شوند. |
| `GITHUB_FILES` | `best_configs.txt,best_configs.txt.meta.json` | فهرست فایل‌های آپلودی، جداشده با کاما. |
| `GITHUB_COMMIT_NAME` | `VPN Tester Bot` | نام نویسنده‌ی کامیت. |
| `GITHUB_COMMIT_EMAIL` | `vpn-bot@noreply.local` | ایمیل نویسنده‌ی کامیت. |

## رفتار خط لوله

| متغیر | پیش‌فرض | توضیح |
|-------|---------|-------|
| `CONFIGS_PER_COUNTRY` | `2` | تعداد بهترین کانفیگ‌ها برای هر کشور مجاز. |
| `URL_TEST_ROUNDS` | `5` | تعداد دورهای تست URL برای هر کانفیگ. |
| `TCP_PING_TRIES` | `5` | تعداد تلاش‌های پینگ TCP. |
| `TCP_PING_MIN_SUCCESS` | `4` | حداقل موفقیت TCP برای عبور از پیش‌فیلتر. |
| `TCP_CONCURRENCY` | `100` | حداکثر پینگ‌های TCP هم‌زمان. |
| `MAX_CONCURRENT` | `10` | حداکثر پروسه‌های هسته‌ی هم‌زمان. |
| `MAX_CONFIGS` | `500` | سقف سخت تعداد کانفیگ‌های واردشده به خط لوله. |
| `MAX_ERROR_RATE` | `0.15` | کانفیگ‌هایی با نرخ خطای وزنیِ بالاتر از این حذف می‌شوند. |
| `ALLOW_INSECURE` | `true` | تحمل TLS خودامضا/سست برای کاهش رد اشتباه. |
| `MAX_SUBSCRIPTION_URLS` | `10` | حداکثر تعداد URLهای اشتراک خوانده‌شده. |
| `INCREMENTAL` | `true` | حفظ کانفیگ‌های سالم اجرای قبل (بخش «اجراهای افزایشی»). |

## زمان‌بندی

| متغیر | پیش‌فرض | توضیح |
|-------|---------|-------|
| `SCHEDULE_TIME` | `04:04` | زمان اجرای روزانه به‌صورت `HH:MM`. |
| `TIMEZONE` | `Asia/Tehran` | منطقه‌ی زمانی IANA برای ارزیابی زمان‌بندی. |

## زمان‌سنج‌ها و پورت‌ها

| متغیر | پیش‌فرض | توضیح |
|-------|---------|-------|
| `XRAY_STARTUP_TIMEOUT` | `15` | ثانیه انتظار برای باز شدن پورت SOCKS هسته. |
| `SOCKS_PORT_BASE` | `20000` | پورت پایه‌ی محلی SOCKS (هر کانفیگ = base + ایندکس). |
| `CONNECT_TIMEOUT` | `10` | مهلت اتصال (ثانیه) در تست URL. |
| `REQUEST_TIMEOUT` | `15` | مهلت کل درخواست (ثانیه) در تست URL. |
| `DOWNLOAD_TIMEOUT` | `30` | مهلت دانلود هر اشتراک (ثانیه). |

## هدف‌های تست و کشورها

| متغیر | پیش‌فرض | توضیح |
|-------|---------|-------|
| `TEST_URLS` | چهار هدف پیش‌فرض | قالب `Label,URL[,weight]` جداشده با `\|`. وزن بیشتر = تأثیر بیشتر در امتیاز. |
| `ALLOWED_COUNTRIES` | DE,FI,NL,GB,US,TR | قالب `CODE:Display Name:Flag` جداشده با کاما. ترتیب لیست = ترتیب خروجی. خالی = رد کردن فیلتر کشور. |
| `GEOIP_PROVIDERS` | ipinfo, ip-api, ipapi | فهرست URLهای geoip جداشده با کاما؛ به‌ترتیب، اولین موفقیت برنده. |

پیش‌فرض `TEST_URLS`:
`Google,http://www.gstatic.com/generate_204 | YouTube,https://www.youtube.com/generate_204 | Cloudflare,http://cp.cloudflare.com/ | X.com,https://x.com/`

## مدیریت هسته‌ها

| متغیر | پیش‌فرض | توضیح |
|-------|---------|-------|
| `AUTO_UPDATE_CORES` | `true` | دانلود و به‌روزرسانی خودکار هسته‌ها. |
| `CORES_DIR` | `cores` | دایرکتوری نگه‌داری هسته‌های مدیریت‌شده. |
| `XRAY_BIN` | — | مسیر صریح Xray (بر به‌روزرسانی خودکار اولویت دارد). |
| `SING_BOX_BIN` | — | مسیر صریح sing-box. |
| `HYSTERIA_BIN` | — | مسیر صریح Hysteria. |
| `XRAY_EXTRA_ARGS` | — | آرگومان‌های اضافه‌ی هسته (جداشده با فاصله). |

## پروفایل اشتراک و خروجی

| متغیر | پیش‌فرض | توضیح |
|-------|---------|-------|
| `SUBSCRIPTION_NAME` | `Fiddel` | نامی که کلاینت‌ها نشان می‌دهند. |
| `SUBSCRIPTION_INTERVAL_HOURS` | `24` | فاصله‌ی به‌روزرسانی خودکاری که به کلاینت اعلام می‌شود. **نام قدیمی `SUBSCRIPTION_UPDATE_INTERVAL_HOURS` نیز برای سازگاری به‌عقب پذیرفته می‌شود.** |
| `OUTPUT_FILE` | `best_configs.txt` | نام فایل خروجی محلی (base64). |
| `METADATA_FILE` | `best_configs.txt.meta.json` | نام فایل متادیتای محلی. |
| `SUBSCRIPTIONS_FILE` | `subscriptions.txt` | فایل ورودی URLهای اشتراک. |
| `OUTPUT_NAMING_FORMAT` | `{country} \| {num:02d}` | قالب نام‌گذاری کانفیگ در خروجی. |

## لاگ

| متغیر | پیش‌فرض | توضیح |
|-------|---------|-------|
| `LOG_FILE` | `vpn_tester.log` | فایل لاگ چرخشی. |
| `LOG_LEVEL` | `INFO` | سطح لاگ. |
| `LOG_ROTATE_MB` | `20` | حجم چرخش لاگ (مگابایت). |
| `LOG_BACKUP_COUNT` | `5` | تعداد فایل‌های پشتیبان لاگ. |

## داشبورد

| متغیر | پیش‌فرض | توضیح |
|-------|---------|-------|
| `DASHBOARD_ENABLED` | `true` | ارائه‌ی داشبورد در کنار حلقه‌ی زمان‌بندی. |
| `DASHBOARD_HOST` | `0.0.0.0` | آدرس bind. |
| `DASHBOARD_PORT` | `30445` | پورت مرورگر. |

## هشدار (اختیاری)

| متغیر | پیش‌فرض | توضیح |
|-------|---------|-------|
| `ALERT_WEBHOOK` | — | وب‌هوک تلگرام یا ntfy برای هشدار؛ خالی = غیرفعال. |
| `ALERT_MIN_CONFIGS` | `3` | اگر کمتر از این تعداد کانفیگ سالم بماند، انتشار انجام نمی‌شود و هشدار ارسال می‌گردد. |

</div>

---

# Configuration

All settings are read from `config.env` (or environment variables). Precedence, highest first: **real environment variable > value in `config.env` > code default**. To get started, copy `config.env.example` to `config.env`.

- An empty value means "unset" and falls back to the default.
- Boolean values are truthy for: `1`, `true`, `yes`, `on`.
- Lines starting with `#` are ignored.

## GitHub (required to publish)

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_TOKEN` | — | Access token with "Contents: Read and write". Never stored on disk. |
| `GITHUB_OWNER` | — | GitHub username/org. |
| `GITHUB_REPO` | — | Target repository name. |
| `GITHUB_BRANCH` | `main` | Branch that files are pushed to. |
| `GITHUB_FILES` | `best_configs.txt,best_configs.txt.meta.json` | Comma-separated list of files to upload. |
| `GITHUB_COMMIT_NAME` | `VPN Tester Bot` | Commit author name. |
| `GITHUB_COMMIT_EMAIL` | `vpn-bot@noreply.local` | Commit author email. |

## Pipeline behaviour

| Variable | Default | Description |
|----------|---------|-------------|
| `CONFIGS_PER_COUNTRY` | `2` | Best configs to keep per allowed country. |
| `URL_TEST_ROUNDS` | `5` | URL-test rounds per config. |
| `TCP_PING_TRIES` | `5` | TCP ping attempts. |
| `TCP_PING_MIN_SUCCESS` | `4` | Minimum TCP successes to pass the pre-filter. |
| `TCP_CONCURRENCY` | `100` | Max parallel TCP pings. |
| `MAX_CONCURRENT` | `10` | Max parallel core processes. |
| `MAX_CONFIGS` | `500` | Hard cap on configs entering the pipeline. |
| `MAX_ERROR_RATE` | `0.15` | Drop configs whose weighted error rate exceeds this. |
| `ALLOW_INSECURE` | `true` | Tolerate self-signed/loose TLS to reduce false negatives. |
| `MAX_SUBSCRIPTION_URLS` | `10` | Max subscription URLs read. |
| `INCREMENTAL` | `true` | Keep working configs from the previous run (see Incremental Runs). |

## Schedule

| Variable | Default | Description |
|----------|---------|-------------|
| `SCHEDULE_TIME` | `04:04` | Daily run time as `HH:MM`. |
| `TIMEZONE` | `Asia/Tehran` | IANA timezone the schedule is evaluated in. |

## Timeouts & ports

| Variable | Default | Description |
|----------|---------|-------------|
| `XRAY_STARTUP_TIMEOUT` | `15` | Seconds to wait for the core's SOCKS port to open. |
| `SOCKS_PORT_BASE` | `20000` | Base local SOCKS port (each config uses base + index). |
| `CONNECT_TIMEOUT` | `10` | Connect timeout (s) during URL tests. |
| `REQUEST_TIMEOUT` | `15` | Total request timeout (s) during URL tests. |
| `DOWNLOAD_TIMEOUT` | `30` | Per-subscription download timeout (s). |

## Test targets & countries

| Variable | Default | Description |
|----------|---------|-------------|
| `TEST_URLS` | four default targets | Format `Label,URL[,weight]` separated by `\|`. Higher weight = more influence on the score. |
| `ALLOWED_COUNTRIES` | DE,FI,NL,GB,US,TR | Format `CODE:Display Name:Flag` separated by commas. List order = output order. Empty = skip the country filter. |
| `GEOIP_PROVIDERS` | ipinfo, ip-api, ipapi | Comma-separated geoip URLs; tried in order, first success wins. |

`TEST_URLS` default:
`Google,http://www.gstatic.com/generate_204 | YouTube,https://www.youtube.com/generate_204 | Cloudflare,http://cp.cloudflare.com/ | X.com,https://x.com/`

## Core management

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTO_UPDATE_CORES` | `true` | Auto-download and update cores. |
| `CORES_DIR` | `cores` | Directory for managed cores. |
| `XRAY_BIN` | — | Explicit Xray path (overrides auto-update). |
| `SING_BOX_BIN` | — | Explicit sing-box path. |
| `HYSTERIA_BIN` | — | Explicit Hysteria path. |
| `XRAY_EXTRA_ARGS` | — | Extra core arguments (space-separated). |

## Subscription profile & output

| Variable | Default | Description |
|----------|---------|-------------|
| `SUBSCRIPTION_NAME` | `Fiddel` | Name shown by client apps. |
| `SUBSCRIPTION_INTERVAL_HOURS` | `24` | Auto-update interval advertised to clients. **The legacy name `SUBSCRIPTION_UPDATE_INTERVAL_HOURS` is still accepted for back-compat.** |
| `OUTPUT_FILE` | `best_configs.txt` | Local output filename (base64). |
| `METADATA_FILE` | `best_configs.txt.meta.json` | Local metadata filename. |
| `SUBSCRIPTIONS_FILE` | `subscriptions.txt` | Input file of subscription URLs. |
| `OUTPUT_NAMING_FORMAT` | `{country} \| {num:02d}` | Naming template for configs in the output. |

## Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_FILE` | `vpn_tester.log` | Rotating log file. |
| `LOG_LEVEL` | `INFO` | Log level. |
| `LOG_ROTATE_MB` | `20` | Log rotation size (MB). |
| `LOG_BACKUP_COUNT` | `5` | Number of rotated log backups. |

## Dashboard

| Variable | Default | Description |
|----------|---------|-------------|
| `DASHBOARD_ENABLED` | `true` | Serve the dashboard alongside the scheduler loop. |
| `DASHBOARD_HOST` | `0.0.0.0` | Bind address. |
| `DASHBOARD_PORT` | `30445` | Browser port. |

## Alerting (optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `ALERT_WEBHOOK` | — | Telegram or ntfy webhook for alerts; empty = disabled. |
| `ALERT_MIN_CONFIGS` | `3` | If fewer than this many configs survive, the run refuses to publish and sends an alert. |
