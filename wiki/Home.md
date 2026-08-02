<div dir="rtl">

# ویکی فنی — VPN Subscription Tester (فیدل)

به مستندات فنی پروژه‌ی **VPN Subscription Tester** (فیدل) خوش آمدید. این ابزار پایتونی اشتراک‌های VPN را دانلود می‌کند، هر کانفیگ را از طریق پروسه‌های واقعی Xray / sing-box / Hysteria2 به‌صورت زنده تست می‌کند، بهترین‌ها را برای هر کشور نگه می‌دارد و یک اشتراک Base64 را به‌صورت خودکار روی گیت‌هاب منتشر می‌کند. یک داشبورد وب زنده هم ارائه می‌دهد.

- نسخه: **۲.۴.۰**
- پایتون: **۳.۹ به بالا**
- مخزن: <https://github.com/sinahosseini379/VPN-Subscription-Tester->

## فهرست مطالب

| صفحه | توضیح |
|------|-------|
| [معماری (Architecture)](Architecture) | نقشه‌ی ۱۶ ماژول و جریان داده |
| [پیکربندی (Configuration)](Configuration) | مرجع کامل متغیرهای محیطی |
| [مدیریت هسته‌ها (Core Management)](Core-Management) | دانلود و به‌روزرسانی خودکار Xray / sing-box / Hysteria |
| [خط لوله (Pipeline)](Pipeline) | مراحل هفت‌گانه، کنترل هم‌روندی، فرمول نرخ خطای وزنی |
| [اجراهای افزایشی (Incremental Runs)](Incremental-Runs) | منطق حمل‌روبه‌جلوی کانفیگ‌های سالم |
| [داشبورد و API](Dashboard-API) | همه‌ی اندپوینت‌ها و شکل درخواست/پاسخ |
| [ارسال به گیت‌هاب (GitHub Push)](GitHub-Push) | جریان Contents API و امنیت توکن |
| [استقرار (Deployment)](Deployment) | داکر، systemd و نیازمندی‌ها |
| [تست (Testing)](Testing) | pytest، ruff و تست واقعی SOCKS5 |
| [نقشه‌راه (Roadmap)](Roadmap) | پیشنهادهای حرفه‌ای‌سازی و توسعه |

## نمای کلی سریع

```
subscriptions.txt ─┐
                   ▼
        دانلود و دیکود (Base64 / JSON / متن ساده)
                   ▼
        فیلتر TCP (پیش‌فیلتر ارزان)
                   ▼
        فیلتر کشور (پروسه‌ی هسته + geoip)
                   ▼
        تست‌های URL (چند دور، وزنی)
                   ▼
        انتخاب بهترین‌ها + اجرای افزایشی
                   ▼
        خروجی Base64 + متادیتای JSON
                   ▼
        ارسال به گیت‌هاب (Contents API)
```

</div>

---

# Technical Wiki — VPN Subscription Tester (Fiddel)

Welcome to the technical documentation for **VPN Subscription Tester** (Fiddel). This Python tool downloads VPN subscriptions, live-tests every config through real Xray / sing-box / Hysteria2 processes, keeps the best configs per country, and auto-publishes a base64 subscription to GitHub. It also serves a live web dashboard.

- Version: **2.4.0**
- Python: **3.9+**
- Repository: <https://github.com/sinahosseini379/VPN-Subscription-Tester->

## Table of Contents

| Page | Description |
|------|-------------|
| [Architecture](Architecture) | Map of the 16 modules and the data flow |
| [Configuration](Configuration) | Full environment-variable reference |
| [Core Management](Core-Management) | Auto-download & auto-update of Xray / sing-box / Hysteria |
| [Pipeline](Pipeline) | The seven stages, concurrency control, weighted error rate |
| [Incremental Runs](Incremental-Runs) | Carry-forward logic for still-working configs |
| [Dashboard API](Dashboard-API) | Every endpoint with request/response shapes |
| [GitHub Push](GitHub-Push) | Contents API flow and token security |
| [Deployment](Deployment) | Docker, systemd, requirements |
| [Testing](Testing) | pytest, ruff, and the real SOCKS5 test |
| [Roadmap](Roadmap) | Professionalization & development proposals |

## Quick Overview

```
subscriptions.txt ─┐
                   ▼
        Download & decode (base64 / JSON / plain text)
                   ▼
        TCP filter (cheap pre-filter)
                   ▼
        Country filter (core process + geoip)
                   ▼
        URL tests (multiple weighted rounds)
                   ▼
        Select best + incremental carry-forward
                   ▼
        Base64 output + metadata JSON
                   ▼
        Push to GitHub (Contents API)
```
