<div dir="rtl">

# تست

پروژه با `pytest` (حالت asyncio خودکار) و `ruff` برای lint و format پوشش داده شده. پیکربندی در `pyproject.toml` است: `asyncio_mode = "auto"`، `testpaths = ["tests"]`، `pythonpath = ["src"]`.

## نصب وابستگی‌های توسعه

```bash
pip install -e ".[dev]"
```

این کار `pytest`, `pytest-asyncio` و `ruff` را نصب می‌کند.

## اجرای تست‌ها

```bash
pytest -q                 # همه‌ی تست‌ها
pytest tests/test_web.py  # یک فایل مشخص
```

## Lint و Format

```bash
ruff check src tests            # بررسی lint
ruff format --check src tests   # بررسی قالب‌بندی (بدون تغییر)
ruff format src tests           # اعمال قالب‌بندی
```

قوانین فعال lint: `E, F, W, I, UP, B, SIM`؛ طول خط ۱۰۰ و سبک نقل‌قول دوتایی.

## فایل‌های تست

| فایل | پوشش |
|------|------|
| `test_config.py` | بارگذاری و تجزیه‌ی تنظیمات. |
| `test_cores.py` | منطق به‌روزرسانی خودکار هسته. |
| `test_geoip.py` | تجزیه‌ی پاسخ ارائه‌دهنده‌ها و کش کشور. |
| `test_github_push.py` | منطق ارسال (Mock). |
| `test_main.py` | CLI و راه‌اندازی لاگ. |
| `test_models.py` | مدل `Config`، نرخ خطای وزنی، صدک‌ها. |
| `test_output.py` | خروجی base64 و متادیتا. |
| `test_parsers.py` | تجزیه‌ی URI برای همه‌ی پروتکل‌ها و حالت‌های مرزی. |
| `test_pipeline.py` | خط لوله‌ی کامل (با هسته‌های Mock). |
| `test_runtime.py` | گزارش‌گر پیشرفت و هماهنگ‌کننده. |
| `test_scheduler.py` | محاسبه‌ی زمان اجرای بعدی. |
| `test_subscription.py` | دیکود (base64 / JSON / متن ساده). |
| `test_web.py` | API داشبورد (با TestClient آی‌او‌اچ‌تی‌تی‌پی). |
| `test_socks.py` | تست رگرسیون واقعی SOCKS5. |

## تست واقعی SOCKS5

`test_socks.py` یک تست رگرسیون برای باگ حیاتی مسیر پروکسی است: `proxy=` در aiohttp فقط پروکسی HTTP را می‌فهمد، پس تونل کردن از طریق هسته به `aiohttp_socks.ProxyConnector` نیاز دارد. این تست یک **رله‌ی واقعی SOCKS5** و یک **سرور HTTP هدف** را به‌صورت محلی بالا می‌آورد و ثابت می‌کند درخواست‌ها واقعاً از داخل تونل عبور می‌کنند. به هیچ باینری خارجی (Xray) نیاز ندارد و کاملاً درون‌فرایندی اجرا می‌شود.

</div>

---

# Testing

The project is covered by `pytest` (automatic asyncio mode) and `ruff` for linting and formatting. Configuration lives in `pyproject.toml`: `asyncio_mode = "auto"`, `testpaths = ["tests"]`, `pythonpath = ["src"]`.

## Install Dev Dependencies

```bash
pip install -e ".[dev]"
```

This installs `pytest`, `pytest-asyncio`, and `ruff`.

## Run Tests

```bash
pytest -q                 # all tests
pytest tests/test_web.py  # a single file
```

## Lint & Format

```bash
ruff check src tests            # lint check
ruff format --check src tests   # format check (no changes)
ruff format src tests           # apply formatting
```

Enabled lint rules: `E, F, W, I, UP, B, SIM`; line length 100 and double-quote style.

## Test Files

| File | Covers |
|------|--------|
| `test_config.py` | Settings loading and parsing. |
| `test_cores.py` | Core auto-update logic. |
| `test_geoip.py` | Provider-response parsing and country cache. |
| `test_github_push.py` | Push logic (mocked). |
| `test_main.py` | CLI and logging setup. |
| `test_models.py` | The `Config` model, weighted error rate, percentiles. |
| `test_output.py` | Base64 output and metadata. |
| `test_parsers.py` | URI parsing for all protocols and edge cases. |
| `test_pipeline.py` | Full pipeline (mocked cores). |
| `test_runtime.py` | Progress reporter and coordinator. |
| `test_scheduler.py` | Next-run time calculation. |
| `test_subscription.py` | Decoding (base64 / JSON / plain text). |
| `test_web.py` | Dashboard API (aiohttp TestClient). |
| `test_socks.py` | Real SOCKS5 regression test. |

## Real SOCKS5 Test

`test_socks.py` is a regression test for the critical proxy-path bug: aiohttp's `proxy=` only understands HTTP proxies, so tunnelling through a core requires an `aiohttp_socks.ProxyConnector`. The test spins up a **real SOCKS5 relay** and a **target HTTP server** locally and proves that requests actually travel through the tunnel. It needs no external binary (Xray) and runs entirely in-process.
