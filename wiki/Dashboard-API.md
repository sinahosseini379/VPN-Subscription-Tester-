<div dir="rtl">

# داشبورد و API

وقتی `DASHBOARD_ENABLED=true` باشد، یک سرور aiohttp در کنار حلقه‌ی زمان‌بندی روی `DASHBOARD_HOST:DASHBOARD_PORT` (پیش‌فرض `0.0.0.0:30445`) اجرا می‌شود. مسیرها در `create_app` در `web.py` تعریف شده‌اند.

داشبورد یک صفحه‌ی HTML تک‌فایلی است که هر ۱.۵ ثانیه `/api/status` و `/api/logs` را نظرسنجی می‌کند (و هر ۱۰ ثانیه لیست اشتراک‌ها را). لاگ‌ها در یک بافر حلقوی نگه داشته می‌شوند.

## اندپوینت‌ها

| متد | مسیر | توضیح |
|-----|------|-------|
| `GET` | `/` | صفحه‌ی HTML داشبورد. |
| `GET` | `/favicon.ico` | پاسخ خالی `204`. |
| `GET` | `/subscription` | اشتراک base64 خام به‌همراه هدرهای پروفایل. |
| `GET` | `/api/status` | وضعیت و پیشرفت اجرای جاری. |
| `GET` | `/api/logs?after=N` | خطوط لاگ جدیدتر از دنباله‌ی N. |
| `GET` | `/api/configs` | کانفیگ‌های منتشرشده به‌همراه متادیتا. |
| `POST` | `/api/run` | آغاز یک اجرای دستی. |
| `GET` | `/api/subscriptions` | فهرست URLهای اشتراک. |
| `POST` | `/api/subscriptions` | جای‌گزینی کل فهرست. |
| `POST` | `/api/subscriptions/add` | افزودن یک URL. |
| `POST` | `/api/subscriptions/remove` | حذف یک URL. |
| `GET` | `/api/schedule` | خواندن زمان‌بندی. |
| `POST` | `/api/schedule` | ذخیره و اعمال زمان‌بندی جدید. |

## GET /subscription

همان بایت‌های فایل خروجی را به‌همراه هدرهایی که کلاینت‌های موبایل می‌فهمند برمی‌گرداند (فایل خام گیت‌هاب نمی‌تواند این هدرها را حمل کند). اگر هنوز چیزی منتشر نشده باشد، `404`.

```
profile-title: <base64 of SUBSCRIPTION_NAME>
subscription-userinfo: interval=<seconds>
profile-update-interval: <seconds>
```

مقدار `interval` برابر `SUBSCRIPTION_INTERVAL_HOURS × 3600` است.

## GET /api/status

عکس فوری از گزارش‌گر (`reporter.snapshot()`):

```json
{
  "status": "idle",
  "stage": "url-tests",
  "message": "url-tests: 42/120",
  "progress": 0.73,
  "started_at": 1730500000.12,
  "finished_at": null,
  "log_seq": 318
}
```

`status` یکی از `idle | running | done | failed` است و `progress` عددی بین ۰ تا ۱.

## GET /api/logs?after=N

خطوط لاگِ اکیداً جدیدتر از دنباله‌ی `after` را برمی‌گرداند:

```json
{ "seq": 320, "lines": ["...", "..."] }
```

کلاینت مقدار `seq` بازگشتی را برای درخواست بعدی به‌عنوان `after` استفاده می‌کند.

## GET /api/configs

خروجی base64 روی دیسک با آیتم‌های متادیتا ادغام می‌شود:

```json
{
  "generated_at": "2026-08-02T01:04:00+00:00",
  "count": 12,
  "configs": [
    {
      "uri": "vless://...",
      "name": "🇩🇪 Germany | 01",
      "index": 1,
      "protocol": "vless",
      "country": "DE",
      "country_name": "Germany",
      "weighted_error_rate": 0.0,
      "avg_latency_ms": 210.4
    }
  ]
}
```

هر عنصر آرایه، URI را با آیتم متناظر در متادیتا ترکیب می‌کند؛ فیلدهای دقیق همان‌هایی‌اند که `output.build_metadata` می‌نویسد.

## POST /api/run

یک اجرای دستی را در پس‌زمینه آغاز می‌کند. بدنه لازم نیست.

```json
{ "started": true, "status": "running" }
```

اگر اجرایی از قبل درجریان باشد، `started` برابر `false` است (اجرای تک‌درجریان توسط `RunCoordinator`).

## GET /api/subscriptions

```json
{ "urls": ["https://...", "https://..."], "max": 10 }
```

## POST /api/subscriptions

کل فهرست را جای‌گزین می‌کند. بدنه:

```json
{ "urls": ["https://a", "https://b"] }
```

مقادیر خالی حذف و فهرست به `MAX_SUBSCRIPTION_URLS` بریده می‌شود. اگر `urls` لیست نباشد، `400`. پاسخ: `{ "urls": [...] }`.

## POST /api/subscriptions/add

```json
{ "url": "https://new-source" }
```

اگر `url` خالی باشد `400`. URL تکراری دوباره افزوده نمی‌شود. پاسخ: فهرست به‌روزشده.

## POST /api/subscriptions/remove

```json
{ "url": "https://source-to-drop" }
```

پاسخ: فهرست به‌روزشده بدون آن URL.

## GET /api/schedule

```json
{ "schedule_time": "04:04", "timezone": "Asia/Tehran" }
```

## POST /api/schedule

```json
{ "schedule_time": "05:30", "timezone": "Asia/Tehran" }
```

زمان و منطقه‌ی زمانی اعتبارسنجی می‌شوند (`seconds_until_next_run`)؛ در صورت نامعتبر بودن `400`. مقادیر معتبر در `config.env` ذخیره می‌شوند (`SCHEDULE_TIME` و `TIMEZONE`)، به `Settings` جاری اعمال و به‌کمک `RunCoordinator.request_schedule_change` بلافاصله زمان اجرای بعدی بازمحاسبه می‌شود. پاسخ: مقادیر ذخیره‌شده.

</div>

---

# Dashboard & API

When `DASHBOARD_ENABLED=true`, an aiohttp server runs alongside the scheduler loop on `DASHBOARD_HOST:DASHBOARD_PORT` (default `0.0.0.0:30445`). Routes are defined in `create_app` in `web.py`.

The dashboard is a single-page HTML app that polls `/api/status` and `/api/logs` every 1.5s (and the subscription list every 10s). Logs are kept in a ring buffer.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Dashboard HTML page. |
| `GET` | `/favicon.ico` | Empty `204` response. |
| `GET` | `/subscription` | Raw base64 subscription plus profile headers. |
| `GET` | `/api/status` | Current run status and progress. |
| `GET` | `/api/logs?after=N` | Log lines newer than sequence N. |
| `GET` | `/api/configs` | Published configs with metadata. |
| `POST` | `/api/run` | Start a manual run. |
| `GET` | `/api/subscriptions` | List subscription URLs. |
| `POST` | `/api/subscriptions` | Replace the whole list. |
| `POST` | `/api/subscriptions/add` | Add one URL. |
| `POST` | `/api/subscriptions/remove` | Remove one URL. |
| `GET` | `/api/schedule` | Read the schedule. |
| `POST` | `/api/schedule` | Save and apply a new schedule. |

## GET /subscription

Returns the same bytes as the output file plus headers mobile clients understand (the raw GitHub file can't carry these). Returns `404` if nothing has been published yet.

```
profile-title: <base64 of SUBSCRIPTION_NAME>
subscription-userinfo: interval=<seconds>
profile-update-interval: <seconds>
```

`interval` equals `SUBSCRIPTION_INTERVAL_HOURS × 3600`.

## GET /api/status

A snapshot from the reporter (`reporter.snapshot()`):

```json
{
  "status": "idle",
  "stage": "url-tests",
  "message": "url-tests: 42/120",
  "progress": 0.73,
  "started_at": 1730500000.12,
  "finished_at": null,
  "log_seq": 318
}
```

`status` is one of `idle | running | done | failed`, and `progress` is a number from 0 to 1.

## GET /api/logs?after=N

Returns log lines strictly newer than the `after` sequence:

```json
{ "seq": 320, "lines": ["...", "..."] }
```

The client uses the returned `seq` as `after` on its next request.

## GET /api/configs

Merges the base64 output on disk with metadata items:

```json
{
  "generated_at": "2026-08-02T01:04:00+00:00",
  "count": 12,
  "configs": [
    {
      "uri": "vless://...",
      "name": "🇩🇪 Germany | 01",
      "index": 1,
      "protocol": "vless",
      "country": "DE",
      "country_name": "Germany",
      "weighted_error_rate": 0.0,
      "avg_latency_ms": 210.4
    }
  ]
}
```

Each array element combines the URI with its matching metadata item; the exact fields are those written by `output.build_metadata`.

## POST /api/run

Starts a manual run in the background. No body required.

```json
{ "started": true, "status": "running" }
```

If a run is already in progress, `started` is `false` (single-flight via `RunCoordinator`).

## GET /api/subscriptions

```json
{ "urls": ["https://...", "https://..."], "max": 10 }
```

## POST /api/subscriptions

Replaces the whole list. Body:

```json
{ "urls": ["https://a", "https://b"] }
```

Empty values are dropped and the list is truncated to `MAX_SUBSCRIPTION_URLS`. If `urls` is not a list, `400`. Response: `{ "urls": [...] }`.

## POST /api/subscriptions/add

```json
{ "url": "https://new-source" }
```

`400` if `url` is empty. A duplicate URL is not re-added. Response: the updated list.

## POST /api/subscriptions/remove

```json
{ "url": "https://source-to-drop" }
```

Response: the updated list without that URL.

## GET /api/schedule

```json
{ "schedule_time": "04:04", "timezone": "Asia/Tehran" }
```

## POST /api/schedule

```json
{ "schedule_time": "05:30", "timezone": "Asia/Tehran" }
```

The time and timezone are validated (`seconds_until_next_run`); invalid input returns `400`. Valid values are persisted to `config.env` (`SCHEDULE_TIME` and `TIMEZONE`), applied to the live `Settings`, and the next run is recomputed immediately via `RunCoordinator.request_schedule_change`. Response: the stored values.
