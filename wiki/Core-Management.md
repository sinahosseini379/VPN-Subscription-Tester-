<div dir="rtl">

# مدیریت هسته‌ها

پروژه به سه هسته‌ی پروکسی متکی است و همه را می‌تواند به‌صورت خودکار دانلود و به‌روز نگه دارد. ماژول **فعال**، `cores.py` است (تابع `ensure_cores` که در `main.py` صدا زده می‌شود).

## هسته‌های پشتیبانی‌شده

| هسته | مخزن گیت‌هاب | الگوی asset (لینوکس amd64) | باینری |
|------|-------------|----------------------------|--------|
| Xray | `XTLS/Xray-core` | `Xray-linux-64.zip` | `xray` |
| sing-box | `SagerNet/sing-box` | `sing-box-*-linux-amd64.tar.gz` | `sing-box` |
| Hysteria | `apernet/hysteria` | `hysteria-linux-amd64` | `hysteria` |

## منطق دانلود و به‌روزرسانی خودکار (`cores.py`)

اگر `AUTO_UPDATE_CORES=true` باشد، در هر اجرا برای هر هسته:

۱. اگر مسیر صریح (`XRAY_BIN` / `SING_BOX_BIN` / `HYSTERIA_BIN`) تنظیم شده باشد، همان استفاده می‌شود و از دانلود صرف‌نظر می‌گردد.
۲. نسخه‌ی نصب‌شده با اجرای باینری و subcommand ‏`version` تشخیص داده می‌شود (با regex مخصوص هر هسته).
۳. آخرین ریلیز از GitHub API پرس‌وجو می‌شود و `tag_name` به‌عنوان آخرین نسخه گرفته می‌شود.
۴. اگر باینری موجود، نسخه‌ی نصب‌شده و آخرین نسخه یکی باشند، همان مسیر استفاده می‌شود («up to date»).
۵. در غیر این صورت asset مناسب انتخاب و دانلود می‌شود، از آرشیو استخراج می‌گردد، مجوز اجرا می‌گیرد، سپس با یک بررسی نسخه سلامت آن تأیید می‌شود و در پایان با `os.replace` به‌صورت اتمیک جای‌گزین باینری فعال می‌شود.

اگر `AUTO_UPDATE_CORES=false` باشد، فقط مسیرهای صریح `*_BIN` استفاده می‌شوند و هیچ دانلودی رخ نمی‌دهد.

## جایگزینی اتمیک و ایمن

دانلود در فایل‌های موقت کنار مقصد انجام می‌شود:

```
دانلود ← ‎.<binary>.download‎  →  استخراج ← ‎.<binary>.tmp‎  →  بررسی نسخه  →  os.replace به مقصد
```

- اگر باینری دانلودشده در بررسی نسخه شکست بخورد، جایگزینی انجام نمی‌شود؛ بنابراین یک دانلود خراب هرگز روی نسخه‌ی سالم نمی‌نشیند.
- اگر پرس‌وجوی نسخه یا asset ناموفق باشد، هرچه از قبل موجود است حفظ می‌شود.
- فایل‌های موقت در بلوک `finally` پاک‌سازی می‌شوند.

## تشخیص نسخه (regex هر هسته)

| هسته | الگو |
|------|------|
| Xray | `Xray\s+([0-9A-Za-z._-]+)` |
| sing-box | `sing-box\s+([0-9A-Za-z._-]+)` |
| Hysteria | `Version:\s+v?([0-9]+\.[0-9]+\.[0-9]+)` |

نسخه‌ها با حذف پیشوند `v`/`V` نرمال‌سازی می‌شوند تا مقایسه‌ی `installed == latest` درست کار کند.

## انتخاب هسته در زمان اجرا

`xray_runner.CoreRunner` برای هر کانفیگ مناسب‌ترین هسته را انتخاب می‌کند:

- کانفیگ‌های `hysteria2` ← هسته‌ی اختصاصی **Hysteria** (در صورت موجود بودن).
- سایر پروتکل‌ها ← **Xray** (اولویت اول).
- اگر Xray نباشد ← **sing-box** به‌عنوان جایگزین.
- اگر هیچ هسته‌ای در دسترس نباشد، خطای صریح داده می‌شود.

## داکر

`Dockerfile` هنگام ساخت ایمیج، آخرین Xray را در `/opt/xray` نصب و `XRAY_BIN=/opt/xray/xray` را تنظیم می‌کند تا کانتینر بدون دانلود زمان‌اجرا هم آماده باشد.

</div>

---

# Core Management

The project relies on three proxy cores and can download and keep all of them up to date automatically. The **active** module is `cores.py` (its `ensure_cores` is what `main.py` calls).

## Supported Cores

| Core | GitHub repo | Asset pattern (linux amd64) | Binary |
|------|-------------|-----------------------------|--------|
| Xray | `XTLS/Xray-core` | `Xray-linux-64.zip` | `xray` |
| sing-box | `SagerNet/sing-box` | `sing-box-*-linux-amd64.tar.gz` | `sing-box` |
| Hysteria | `apernet/hysteria` | `hysteria-linux-amd64` | `hysteria` |

## Auto-download & auto-update logic (`cores.py`)

When `AUTO_UPDATE_CORES=true`, on every run, for each core:

1. If an explicit path (`XRAY_BIN` / `SING_BOX_BIN` / `HYSTERIA_BIN`) is set, use it and skip downloading.
2. The installed version is detected by running the binary with its `version` subcommand (per-core regex).
3. The latest release is queried from the GitHub API; `tag_name` is taken as the latest version.
4. If the binary exists and the installed version equals the latest, the existing path is used ("up to date").
5. Otherwise the matching asset is selected and downloaded, extracted from the archive, made executable, verified with a version check, and finally swapped into place atomically with `os.replace`.

When `AUTO_UPDATE_CORES=false`, only explicit `*_BIN` paths are used and no downloads happen.

## Atomic, safe replacement

Downloads happen in temp files next to the target:

```
download -> .<binary>.download  →  extract -> .<binary>.tmp  →  version check  →  os.replace to target
```

- If the downloaded binary fails the version check, no replacement happens, so a bad download never overwrites a working one.
- If the version query or asset lookup fails, whatever already exists is kept.
- Temp files are cleaned up in a `finally` block.

## Version detection (per-core regex)

| Core | Pattern |
|------|---------|
| Xray | `Xray\s+([0-9A-Za-z._-]+)` |
| sing-box | `sing-box\s+([0-9A-Za-z._-]+)` |
| Hysteria | `Version:\s+v?([0-9]+\.[0-9]+\.[0-9]+)` |

Versions are normalized by stripping a leading `v`/`V` so the `installed == latest` comparison works.

## Core selection at runtime

`xray_runner.CoreRunner` picks the most appropriate core per config:

- `hysteria2` configs → the dedicated **Hysteria** core (if present).
- All other protocols → **Xray** (first choice).
- If Xray is absent → **sing-box** as a fallback.
- If no core is available, an explicit error is raised.

## Docker

The `Dockerfile` installs the latest Xray to `/opt/xray` at image-build time and sets `XRAY_BIN=/opt/xray/xray`, so the container is ready without a runtime download.
