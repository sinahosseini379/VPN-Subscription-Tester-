<div dir="rtl">

# ارسال به گیت‌هاب (GitHub Push)

پس از هر اجرای موفق، فایل‌های خروجی از طریق **GitHub Contents API** به مخزن منتشر می‌شوند. کل منطق در `github_push.py` (تابع `push_to_github`) قرار دارد.

## چرا Contents API به‌جای git؟

نسخه‌های اولیه توکن را داخل URL ریموت git می‌گذاشتند که دو مشکل داشت: توکن روی دیسک در `.git/config` ذخیره می‌شد و در خروجی خطای هر فرمان ناموفق ظاهر می‌شد. Contents API فقط از یک هدر Bearer استفاده می‌کند، بنابراین **توکن هرگز روی فایل‌سیستم یا آرگومان‌های پروسه قرار نمی‌گیرد**.

## جریان کار

برای هر فایل در `GITHUB_FILES` (پیش‌فرض `best_configs.txt` و `best_configs.txt.meta.json`):

۱. **گرفتن SHA فعلی** — یک `GET /repos/{owner}/{repo}/contents/{path}?ref={branch}`؛ اگر فایل وجود داشته باشد، `sha` آن گرفته می‌شود (برای به‌روزرسانی لازم است).
۲. **آپلود محتوا** — یک `PUT` روی همان مسیر با بدنه‌ی JSON شامل پیام کامیت، محتوای base64 فایل، شاخه، و نویسنده/کامیتر. اگر `sha` موجود باشد، فایل به‌روزرسانی و در غیر این صورت ایجاد می‌شود.
۳. **تلاش مجدد** — کل عملیات تا **۳ بار** تلاش می‌شود و بین تلاش‌ها ۲ ثانیه صبر می‌کند. اگر همه‌ی آپلودها موفق باشند `True` برمی‌گردد.

هدرهای هر درخواست:

```
Authorization: Bearer <GITHUB_TOKEN>
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
```

- پیام کامیت: `chore: update <path>`.
- نویسنده/کامیتر: `GITHUB_COMMIT_NAME <GITHUB_COMMIT_EMAIL>` (پیش‌فرض `VPN Tester Bot <vpn-bot@noreply.local>`).
- مسیرهای تودرتو (مثل `output/best_configs.txt`) پشتیبانی می‌شوند؛ مسیرهای مطلق محلی به نام پایه‌ی فایل نگاشت می‌شوند.
- اگر `GITHUB_TOKEN`/`GITHUB_OWNER`/`GITHUB_REPO` تنظیم نشده باشند، `ValueError` داده می‌شود.

## امنیت توکن

- توکن فقط در هدر `Authorization: Bearer` قرار می‌گیرد.
- هیچ‌گاه در URL ریموت، `.git/config`، آرگومان‌های خط فرمان یا لاگ‌ها نوشته نمی‌شود.
- توصیه: از یک Fine-grained PAT با تنها مجوز «Contents: Read and write» روی مخزن مقصد استفاده کنید.

## گارد امتناع از انتشار

پیش از هر Push، `main.run_once` تعداد کانفیگ‌های سالم را بررسی می‌کند:

- اگر **هیچ** کانفیگی زنده نماند، چیزی نوشته یا Push نمی‌شود.
- اگر تعداد کانفیگ‌های سالم کمتر از `ALERT_MIN_CONFIGS` (پیش‌فرض ۳) باشد، اجرا **از بازنویسی خروجی منتشرشده خودداری می‌کند** و در صورت تنظیم `ALERT_WEBHOOK` هشدار می‌فرستد.

این گارد جلوی آن را می‌گیرد که یک اجرای بد، اشتراک سالمِ قبلی را پاک کند.

</div>

---

# GitHub Push

After each successful run, the output files are published to the repository via the **GitHub Contents API**. All the logic lives in `github_push.py` (`push_to_github`).

## Why the Contents API instead of git?

Early versions put the token inside the git remote URL, which had two problems: the token was stored on disk in `.git/config` and appeared in the error output of every failed command. The Contents API uses only a Bearer header, so **the token never touches the filesystem or process arguments**.

## Flow

For each file in `GITHUB_FILES` (default `best_configs.txt` and `best_configs.txt.meta.json`):

1. **Get the current SHA** — a `GET /repos/{owner}/{repo}/contents/{path}?ref={branch}`; if the file exists, its `sha` is taken (needed to update).
2. **Upload content** — a `PUT` to the same path with a JSON body containing the commit message, the file's base64 content, the branch, and author/committer. If a `sha` is present the file is updated, otherwise created.
3. **Retry** — the whole operation is attempted up to **3 times**, sleeping 2 seconds between attempts. Returns `True` only if all uploads succeed.

Per-request headers:

```
Authorization: Bearer <GITHUB_TOKEN>
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
```

- Commit message: `chore: update <path>`.
- Author/committer: `GITHUB_COMMIT_NAME <GITHUB_COMMIT_EMAIL>` (default `VPN Tester Bot <vpn-bot@noreply.local>`).
- Nested paths (e.g. `output/best_configs.txt`) are supported; absolute local paths map to the file's basename.
- If `GITHUB_TOKEN`/`GITHUB_OWNER`/`GITHUB_REPO` are unset, a `ValueError` is raised.

## Token Security

- The token appears only in the `Authorization: Bearer` header.
- It is never written to the remote URL, `.git/config`, command-line arguments, or logs.
- Recommended: use a fine-grained PAT with only "Contents: Read and write" on the target repo.

## Refusal-to-Publish Guard

Before any push, `main.run_once` checks how many configs survived:

- If **no** configs survive, nothing is written or pushed.
- If the number of surviving configs is below `ALERT_MIN_CONFIGS` (default 3), the run **refuses to overwrite the published output** and sends an alert if `ALERT_WEBHOOK` is set.

This guard prevents a bad run from wiping a previously healthy subscription.
