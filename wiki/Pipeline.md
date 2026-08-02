<div dir="rtl">

# خط لوله (Pipeline)

`run_pipeline` در `pipeline.py` کل مسیر را از URLهای اشتراک تا فهرست نهایی کانفیگ‌ها اجرا می‌کند. پیشرفت هر مرحله روی یک بازه‌ی درصدی نگاشت می‌شود تا داشبورد یک نوار پیشرفت پیوسته نشان دهد.

## مراحل هفت‌گانه

| # | مرحله | ثابت | بازه‌ی پیشرفت | کار |
|---|-------|------|---------------|-----|
| ۱ | دانلود | `downloading` | ۰–۶٪ | دانلود هم‌زمان اشتراک‌ها، دیکود (base64/JSON/متن ساده)، تجزیه و یکتا کردن URIها، اعمال `MAX_CONFIGS`. |
| ۲ | پینگ TCP | `tcp-ping` | ۶–۲۲٪ | پینگ TCP همه‌ی سرورها؛ نگه‌داشتن آن‌هایی که حداقل `TCP_PING_MIN_SUCCESS` بار پاسخ دادند. |
| ۳ | بررسی کشور | `country-check` | ۲۲–۵۵٪ | راه‌اندازی یک پروسه‌ی هسته + تونل SOCKS برای هر کانفیگ و تشخیص کشور خروجی از طریق geoip. |
| ۴ | تست‌های URL | `url-tests` | ۵۵–۹۵٪ | استفاده‌ی مجدد از همان پروسه؛ تست هدف‌های وزنی در `URL_TEST_ROUNDS` دور و ثبت نتیجه‌ی هر هدف. |
| ۵ | انتخاب | (بخشی از finalizing) | — | حذف کانفیگ‌های بالای `MAX_ERROR_RATE`، مرتب‌سازی و انتخاب `CONFIGS_PER_COUNTRY` بهترین برای هر کشور. |
| ۶ | افزایشی (اختیاری) | (بخشی از finalizing) | — | نگه‌داشتن کانفیگ‌های سالم اجرای قبل و پر کردن جاهای خالی (بخش «اجراهای افزایشی»). |
| ۷ | نهایی‌سازی | `finalizing` | ۹۵–۱۰۰٪ | شماره‌گذاری سراسری، نوشتن اشتراک base64 + متادیتا، سپس ارسال به گیت‌هاب. |

> نکته: پیشرفت واقعی روی پنج مرحله‌ی ردیابی‌شده (`downloading`, `tcp-ping`, `country-check`, `url-tests`, `finalizing`) نگاشت می‌شود؛ «انتخاب» و «افزایشی» گام‌های منطقی درون نهایی‌سازی هستند. یک ثابت `pushing` هم برای مرحله‌ی ارسال تعریف شده است.

## کنترل هم‌روندی

- **پینگ TCP:** `asyncio.Semaphore(min(TCP_CONCURRENCY, تعداد کانفیگ‌ها))` از طوفان سوکت جلوگیری می‌کند (پیش‌فرض ۱۰۰).
- **پروسه‌های هسته:** `asyncio.Semaphore(MAX_CONCURRENT)` تعداد پروسه‌های هم‌زمان را محدود می‌کند (پیش‌فرض ۱۰). هم در بررسی کشور و هم در تست‌های URL اعمال می‌شود.
- **تست‌های URL:** برای هر کانفیگ یک پروسه‌ی هسته در طول همه‌ی دورها زنده می‌ماند (به‌جای راه‌اندازی مجدد در هر دور).
- **آمادگی پورت:** به‌جای `sleep` ثابت، تا زمان باز شدن پورت SOCKS (تا `XRAY_STARTUP_TIMEOUT`) نظرسنجی می‌شود.
- هر کانفیگ روی پورت محلی `SOCKS_PORT_BASE + index` اجرا می‌شود.

## فرمول نرخ خطای وزنی

هر هدف تست یک وزن دارد (پیش‌فرض ۱.۰). برای هر کانفیگ، نتایج هر هدف جداگانه ثبت می‌شوند و نرخ خطای نهایی به‌صورت وزنی محاسبه می‌شود:

```
weighted_error_rate = Σ( wᵢ × failᵢ ) / Σ( wᵢ × (okᵢ + failᵢ) )
```

- `wᵢ` وزن هدف `i` است، `okᵢ`/`failᵢ` تعداد موفقیت/شکست همان هدف در همه‌ی دورها.
- اگر هیچ نمونه‌ای ثبت نشده باشد، نرخ خطا برابر `1.0` (بدترین) در نظر گرفته می‌شود.
- این فرمول اجازه می‌دهد هدف‌های مهم‌تر (مثلاً YouTube) وزن بیشتری بگیرند.

## اعتبارسنجی موفقیت

در `CoreRunner.test_url` فقط پاسخ‌های HTTP با کد `2xx`/`3xx` (به‌طور دقیق `200 ≤ status < 400`) موفق شمرده می‌شوند و مقدار تأخیر (میلی‌ثانیه) برمی‌گردانند؛ در غیر این صورت `None`. ترافیک از طریق `aiohttp_socks.ProxyConnector` با `rdns=True` تونل می‌شود تا DNS هم داخل تونل بماند و نشتی رخ ندهد.

## مرتب‌سازی برای انتخاب

در `select_top`، برای هر کشور به‌ترتیبِ لیست `ALLOWED_COUNTRIES`، کاندیداها ابتدا بر اساس `weighted_error_rate` و سپس `avg_latency` مرتب می‌شوند و `CONFIGS_PER_COUNTRY` تای اول برداشته می‌شود.

</div>

---

# Pipeline

`run_pipeline` in `pipeline.py` drives the whole path from subscription URLs to the final config list. Each stage's progress is mapped onto a percentage range so the dashboard can show a continuous progress bar.

## The Seven Stages

| # | Stage | Constant | Progress range | Work |
|---|-------|----------|----------------|------|
| 1 | Download | `downloading` | 0–6% | Concurrently download subscriptions, decode (base64/JSON/plain), parse and dedupe URIs, apply `MAX_CONFIGS`. |
| 2 | TCP ping | `tcp-ping` | 6–22% | TCP-ping every server; keep those that answered at least `TCP_PING_MIN_SUCCESS` times. |
| 3 | Country check | `country-check` | 22–55% | Launch one core process + SOCKS tunnel per config and detect the exit country via geoip. |
| 4 | URL tests | `url-tests` | 55–95% | Reuse the same process; test weighted targets over `URL_TEST_ROUNDS` rounds, recording each target's result. |
| 5 | Select | (part of finalizing) | — | Drop configs above `MAX_ERROR_RATE`, sort, and take the `CONFIGS_PER_COUNTRY` best per country. |
| 6 | Incremental (optional) | (part of finalizing) | — | Keep still-working previous configs and fill gaps (see Incremental Runs). |
| 7 | Finalize | `finalizing` | 95–100% | Global numbering, write base64 subscription + metadata, then push to GitHub. |

> Note: actual progress is mapped onto the five tracked stages (`downloading`, `tcp-ping`, `country-check`, `url-tests`, `finalizing`); "Select" and "Incremental" are logical steps inside finalizing. A `pushing` constant also exists for the push step.

## Concurrency Control

- **TCP ping:** `asyncio.Semaphore(min(TCP_CONCURRENCY, len(configs)))` prevents a socket storm (default 100).
- **Core processes:** `asyncio.Semaphore(MAX_CONCURRENT)` caps concurrent processes (default 10). Applied to both the country check and the URL tests.
- **URL tests:** one core process stays alive across all rounds per config (instead of restarting per round).
- **Port readiness:** instead of a fixed `sleep`, the code polls until the SOCKS port opens (up to `XRAY_STARTUP_TIMEOUT`).
- Each config runs on local port `SOCKS_PORT_BASE + index`.

## Weighted Error-Rate Formula

Each test target has a weight (default 1.0). For each config, per-target results are recorded separately and the final error rate is weighted:

```
weighted_error_rate = Σ( wᵢ × failᵢ ) / Σ( wᵢ × (okᵢ + failᵢ) )
```

- `wᵢ` is target `i`'s weight; `okᵢ`/`failᵢ` are that target's successes/failures across all rounds.
- If no samples were recorded, the error rate is treated as `1.0` (worst).
- This lets more important targets (e.g. YouTube) count for more.

## Success Validation

In `CoreRunner.test_url`, only HTTP `2xx`/`3xx` responses (precisely `200 ≤ status < 400`) count as success and return a latency in milliseconds; otherwise `None`. Traffic is tunnelled through an `aiohttp_socks.ProxyConnector` with `rdns=True` so DNS stays inside the tunnel and cannot leak.

## Sorting for Selection

In `select_top`, for each country in `ALLOWED_COUNTRIES` order, candidates are sorted by `weighted_error_rate` then `avg_latency`, and the first `CONFIGS_PER_COUNTRY` are taken.
