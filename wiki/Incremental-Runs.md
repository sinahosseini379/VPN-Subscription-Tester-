<div dir="rtl">

# اجراهای افزایشی (Incremental Runs)

وقتی `INCREMENTAL=true` باشد (پیش‌فرض)، پروژه از اجرای دوم به بعد به‌جای انتشار یک فهرست کاملاً تازه در هر بار، **کانفیگ‌های سالمِ قبلی را حمل می‌کند** و فقط جاهای خالی را با کانفیگ‌های جدید پر می‌کند. این کار باعث می‌شود اشتراک بین اجراها پایدار بماند.

## گام‌ها

۱. **بازخوانی اجرای قبل** (`load_previous_configs`): فایل خروجی `OUTPUT_FILE` (base64) دیکود و به URIها تبدیل می‌شود و متادیتای `METADATA_FILE` برای بازیابی کشور و ایندکس خوانده می‌شود. اگر خروجی قبلی وجود نداشته باشد، فهرست خالی برمی‌گردد و اجرای اول بی‌تأثیر می‌ماند.
۲. **تست سریع** (`quick_test_previous`): روی هر کانفیگ قبلی **یک دور** تست URL اجرا می‌شود.
۳. **نگه‌داشتن سالم‌ها**: کانفیگ‌هایی که نرخ خطای وزنی‌شان همچنان زیر `MAX_ERROR_RATE` است «زنده» شمرده می‌شوند.
۴. **ادغام** (`merge_incremental`): ابتدا کانفیگ‌های سالمِ قبلی افزوده می‌شوند، سپس جاهای خالی با بهترین‌های جدید پر می‌گردد.
۵. **سقف**: کل خروجی روی `CONFIGS_PER_COUNTRY × تعداد کشورهای مجاز` محدود می‌شود (پیش‌فرض ۲ × ۶ = ۱۲).

## قواعد ادغام

- برای هر کشور حداکثر `CONFIGS_PER_COUNTRY` کانفیگ نگه داشته می‌شود.
- URIهای تکراری حذف می‌شوند (بر اساس مجموعه‌ی `seen`).
- کانفیگ‌های قبلی **اولویت** دارند؛ فقط وقتی سهمیه‌ی یک کشور پر نشده باشد، کانفیگ جدید اضافه می‌شود.
- به‌محض رسیدن به سقف کل، ادغام متوقف می‌شود.

## چرا مفید است؟

- **پایداری:** کانفیگ‌ها بین اجراها بی‌دلیل تغییر نمی‌کنند؛ کاربر مجبور به تعویض مداوم نیست.
- **سرعت:** روی کانفیگ‌های پایدارِ قبلی فقط یک دور تست اجرا می‌شود، نه همه‌ی دورها.
- **اندازه‌ی قابل‌پیش‌بینی:** خروجی همیشه در سقف پیکربندی‌شده می‌ماند.

برای غیرفعال کردن این رفتار و تولید فهرست تازه در هر اجرا، `INCREMENTAL=false` قرار دهید.

</div>

---

# Incremental Runs

When `INCREMENTAL=true` (default), from the second run onward the project **carries forward still-working previous configs** instead of publishing a fresh list every time, filling only the gaps with new configs. This keeps the subscription stable across runs.

## Steps

1. **Reload the previous run** (`load_previous_configs`): the `OUTPUT_FILE` (base64) is decoded into URIs, and `METADATA_FILE` is read to recover country and index. If there is no previous output, an empty list is returned and the first run is unaffected.
2. **Quick test** (`quick_test_previous`): **one round** of URL tests is run on each previous config.
3. **Keep the survivors**: configs whose weighted error rate is still below `MAX_ERROR_RATE` are considered "alive".
4. **Merge** (`merge_incremental`): still-working previous configs are added first, then gaps are filled with the new best configs.
5. **Cap**: total output is capped at `CONFIGS_PER_COUNTRY × number of allowed countries` (default 2 × 6 = 12).

## Merge Rules

- Each country keeps at most `CONFIGS_PER_COUNTRY` configs.
- Duplicate URIs are removed (via a `seen` set).
- Previous configs take **priority**; a new config is only added when a country's quota is not yet full.
- Merging stops as soon as the overall cap is reached.

## Why It Helps

- **Stability:** configs don't churn between runs, so users aren't forced to switch constantly.
- **Speed:** stable previous configs get one round of testing, not the full set.
- **Predictable size:** the output always stays at the configured cap.

To disable this and produce a fresh list every run, set `INCREMENTAL=false`.
