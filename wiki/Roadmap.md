<div dir="rtl">

# نقشه‌راه و پیشنهادهای حرفه‌ای‌سازی

این سند از دید یک CTO نوشته شده و اولویت‌بندی‌شده است: از «برد سریع» (کم‌هزینه، اثر زیاد) تا کارهای بلندمدت. هر مورد با دلیل فنی و ارجاع به محل کد آمده است.

> این پروژه هم‌اکنون سالم و باکیفیت است: معماری ماژولار، توابع خالص و تست‌پذیر، تست واقعی SOCKS5، مدیریت خودکار هسته‌ها، اجرای incremental و push امن به گیت‌هاب. پیشنهادهای زیر برای رساندن آن به سطح «محصول تولیدی» است، نه رفع خرابی.

---

## اولویت ۱ — امنیت (باید انجام شود)

### ۱.۱ احراز هویت داشبورد
داشبورد روی `0.0.0.0:30445` گوش می‌دهد (`config.py`) و endpointهای `POST` هیچ احراز هویتی ندارند (`web.py`). یعنی هر کسی در شبکه می‌تواند اجرا را تریگر کند، لیست اشتراک را بازنویسی کند یا زمان‌بندی را عوض کند.
- **پیشنهاد:** یک توکن ساده (`DASHBOARD_TOKEN`) با هدر `Authorization: Bearer` یا کوکی امضاشده. حداقل، bind پیش‌فرض را به `127.0.0.1` تغییر دهید و انتشار روی شبکه را انتخابی کنید.
- **هزینه:** کم (یک middleware در `create_app`).

### ۱.۲ محافظت CSRF/Origin روی endpointهای نویسنده
درخواست‌های `POST` هیچ بررسی `Origin`/`Referer` ندارند. با یک middleware ساده که `Origin` را چک کند، حملهٔ CSRF از مرورگر بسته می‌شود.

### ۱.۳ محدودسازی نرخ (rate-limit) روی `/api/run`
اجرای دستی می‌تواند پروسه‌های زیادی اسپاون کند. یک محدودیت زمانی حداقلی بین اجراها اضافه شود.

---

## اولویت ۲ — قابلیت مشاهده و پایش (Observability)

### ۲.۱ endpoint سلامت `/healthz`
یک endpoint سبک که وضعیت (idle/running)، زمان آخرین اجرای موفق و تعداد کانفیگ منتشرشده را برگرداند — برای Kubernetes/Docker healthcheck و مانیتورینگ بیرونی.

### ۲.۲ متریک‌های Prometheus `/metrics`
شمارنده‌ها و گِیج‌ها: تعداد کانفیگ به تفکیک کشور، میانگین/‏p95 تأخیر، نرخ خطا، مدت هر مرحله از پایپلاین، تعداد اجراهای ناموفق. داده‌ها هم‌اکنون در `metadata` و `reporter` هستند؛ فقط باید در قالب Prometheus صادر شوند.

### ۲.۳ غنی‌سازی هشدارها
`_send_alert` در `main.py` فقط یک متن ساده می‌فرستد. پیام تلگرام می‌تواند شامل خلاصهٔ اجرا (تعداد کانفیگ به تفکیک کشور، بهترین تأخیر، دلیل شکست) باشد.

---

## اولویت ۳ — کیفیت انتخاب کانفیگ

### ۳.۱ تست سرعت واقعی (throughput) به‌جای فقط ۲۰۴
الان فقط در دسترس‌بودن (`generate_204`) و تأخیر سنجیده می‌شود (`pipeline.py`). افزودن یک دانلود کوچک (مثلاً ۱–۵ مگابایت از یک CDN) و ثبت Mbps، کیفیت انتخاب را واقعی‌تر می‌کند.

### ۳.۲ تنوع IP/ASN علاوه بر کشور
دو کانفیگ ممکن است هر دو در «آلمان» ولی روی یک دیتاسنتر/ASN باشند. با نگه‌داشتن ASN خروجی (ip-api آن را می‌دهد) و ترجیح تنوع ASN، تاب‌آوری اشتراک بالا می‌رود.

### ۳.۳ امتیازدهی ترکیبی
به‌جای مرتب‌سازی صرفاً بر پایهٔ نرخ خطا و سپس تأخیر (`select_top`)، یک امتیاز ترکیبی (خطا + p95 + throughput + پایداری بین اجراها) تعریف شود.

---

## اولویت ۴ — پوشش پروتکل و پلتفرم

### ۴.۱ پشتیبانی TUIC و WireGuard
`parsers.py` هم‌اکنون `tuic://` را «معتبر» می‌شناسد ولی parse نمی‌کند. افزودن TUIC (و در ادامه WireGuard) پوشش را کامل می‌کند.

### ۴.۲ هسته‌های چند-معماری
`cores.py` الگوی asset لینوکس amd64 را دارد. افزودن arm64 (برای Raspberry Pi / سرورهای ARM) و در صورت نیاز ویندوز، دامنهٔ استقرار را گسترش می‌دهد.

---

## اولویت ۵ — یکپارچگی و اعتماد

### ۵.۱ خروجی چند-فرمت (Clash/sing-box بومی)
README چند لینک را به یک فایل base64 اشاره می‌دهد. تولید خروجی بومی Clash YAML و sing-box JSON، تجربهٔ کاربر را در آن اپ‌ها بهتر می‌کند (زیربنای تبدیل در `parsers.py` موجود است).

### ۵.۲ امضای انتشار
یک هش/امضا (مثلاً یک فایل `.sha256` یا امضای minisign) کنار `felfelconfig.txt` منتشر شود تا کاربران بتوانند صحت اشتراک را بررسی کنند.

### ۵.۳ CI کامل‌تر
گردش‌کار موجود (`.github/workflows/ci.yml`) تست/لینت را اجرا می‌کند. افزودن یک job زمان‌بندی‌شده (cron) که خود پایپلاین را روی GitHub Actions اجرا و نتیجه را commit کند، وابستگی به یک ماشین همیشه‌روشن را حذف می‌کند.

---

## جمع‌بندی اولویت‌ها

| اولویت | کار | اثر | هزینه |
|--------|-----|-----|-------|
| ۱ | احراز هویت داشبورد + bind لوکال | 🔴 بحرانی | کم |
| ۱ | CSRF/Origin روی POST | 🔴 بحرانی | کم |
| ۲ | `/healthz` + متریک Prometheus | 🟠 بالا | متوسط |
| ۳ | تست throughput واقعی | 🟠 بالا | متوسط |
| ۳ | تنوع ASN | 🟡 متوسط | متوسط |
| ۴ | TUIC / WireGuard | 🟡 متوسط | متوسط |
| ۵ | خروجی Clash/sing-box بومی | 🟢 خوب‌است‌داشتن | متوسط |
| ۵ | CI زمان‌بندی‌شده | 🟢 خوب‌است‌داشتن | کم |

</div>

---

# Roadmap & Professionalization Proposal

Written from a CTO's perspective and prioritized from quick wins (low cost, high impact) to longer-term work. Each item includes the technical rationale and a code reference.

> The project is already healthy and well-built: modular architecture, pure/testable functions, a real SOCKS5 test, automatic core management, incremental runs, and a secure GitHub push. The items below take it from "solid" to "production-grade" — they are enhancements, not bug fixes.

---

## Priority 1 — Security (must do)

### 1.1 Dashboard authentication
The dashboard binds to `0.0.0.0:30445` (`config.py`) and the `POST` endpoints have no auth (`web.py`). Anyone on the network can trigger runs, overwrite the subscription list, or change the schedule.
- **Proposal:** a simple `DASHBOARD_TOKEN` checked via an `Authorization: Bearer` header (or a signed cookie). At minimum, default the bind to `127.0.0.1` and make network exposure opt-in.
- **Cost:** low (one middleware in `create_app`).

### 1.2 CSRF / Origin protection on writer endpoints
`POST` requests do no `Origin`/`Referer` validation. A small middleware that checks `Origin` closes the browser-based CSRF vector.

### 1.3 Rate-limit `/api/run`
Manual runs can spawn many processes. Add a minimum interval between runs.

---

## Priority 2 — Observability

### 2.1 `/healthz` endpoint
A lightweight endpoint returning status (idle/running), last successful run time, and published config count — for Kubernetes/Docker healthchecks and external monitoring.

### 2.2 Prometheus metrics `/metrics`
Counters and gauges: configs per country, avg/p95 latency, error rate, per-stage pipeline duration, failed-run count. The data already lives in `metadata` and `reporter`; it just needs a Prometheus exposition format.

### 2.3 Richer alerts
`_send_alert` in `main.py` sends a plain string. The Telegram message could include a run summary (configs per country, best latency, failure reason).

---

## Priority 3 — Config selection quality

### 3.1 Real throughput testing (not just 204)
Today only reachability (`generate_204`) and latency are measured (`pipeline.py`). Adding a small download (e.g. 1–5 MB from a CDN) and recording Mbps makes selection reflect real quality.

### 3.2 IP/ASN diversity beyond country
Two configs can both be "Germany" but on the same datacenter/ASN. Keeping the exit ASN (ip-api provides it) and preferring ASN diversity increases subscription resilience.

### 3.3 Composite scoring
Instead of sorting purely by error rate then latency (`select_top`), define a composite score (error + p95 + throughput + cross-run stability).

---

## Priority 4 — Protocol & platform coverage

### 4.1 TUIC and WireGuard support
`parsers.py` currently treats `tuic://` as *valid* but does not parse it. Adding TUIC (and later WireGuard) completes coverage.

### 4.2 Multi-architecture cores
`cores.py` uses a linux-amd64 asset pattern. Adding arm64 (Raspberry Pi / ARM servers) and optionally Windows widens the deployment surface.

---

## Priority 5 — Integrity & trust

### 5.1 Multi-format output (native Clash/sing-box)
The README points several links at one base64 file. Generating native Clash YAML and sing-box JSON improves UX in those apps (the conversion groundwork already exists in `parsers.py`).

### 5.2 Signed releases
Publish a hash/signature (e.g. a `.sha256` file or a minisign signature) alongside `felfelconfig.txt` so users can verify subscription integrity.

### 5.3 Fuller CI
The existing workflow (`.github/workflows/ci.yml`) runs tests/lint. Adding a scheduled (cron) job that runs the pipeline itself on GitHub Actions and commits the result removes the dependency on an always-on machine.

---

## Priority summary

| Priority | Item | Impact | Cost |
|----------|------|--------|------|
| 1 | Dashboard auth + local bind | 🔴 Critical | Low |
| 1 | CSRF/Origin on POST | 🔴 Critical | Low |
| 2 | `/healthz` + Prometheus metrics | 🟠 High | Medium |
| 3 | Real throughput test | 🟠 High | Medium |
| 3 | ASN diversity | 🟡 Medium | Medium |
| 4 | TUIC / WireGuard | 🟡 Medium | Medium |
| 5 | Native Clash/sing-box output | 🟢 Nice-to-have | Medium |
| 5 | Scheduled CI | 🟢 Nice-to-have | Low |
