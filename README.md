<div dir="rtl">

# فیدل (Fiddel) — اشتراک رایگان کانفیگ VPN

یک اشتراک VPN رایگان و به‌روزرسانی‌شونده که هر روز ساخته می‌شود؛ بهینه برای کاربران داخل ایران و سراسر جهان. هر کانفیگ پیش از انتشار با پروسه‌های واقعی Xray / sing-box / Hysteria2 به‌صورت زنده تست می‌شود و فقط بهترین‌ها برای هر کشور نگه داشته می‌شوند.

نسخه: **۲.۴.۰**

## لینک‌های مستقیم اشتراک

| نوع | لینک مستقیم (Raw) |
|-----|-------------------|
| **Base64 (همه اپلیکیشن‌ها)** | `https://raw.githubusercontent.com/sinahosseini379/VPN-Subscription-Tester-/main/felfelconfig.txt` |

> **نکته:** همه اپلیکیشن‌های مدرن VPN (SFA، sing-box، NekoBox، Clash Meta، v2rayNG، Shadowrocket، Streisand، Hiddify و…) یک URL اشتراک Base64 را می‌پذیرند. کافیست همین یک لینک را وارد کنید.

## نحوه افزودن به اپلیکیشن‌ها

### اندروید (Android)
| اپلیکیشن | روش افزودن |
|----------|------------|
| **SFA / Sing-box** | `Profiles` ← `Add` ← `Remote` ← لینک را بچسبانید |
| **NekoBox** | `Profile` ← `Import from URL` ← لینک را بچسبانید |
| **v2rayNG** | `+` ← `Import from clipboard` (پس از کپی لینک) |
| **Kitsunebi** | `+` ← `Import from URI` ← لینک را بچسبانید |
| **Hiddify** | `Config` ← `Add Subscription` ← لینک را بچسبانید |

### iOS / macOS
| اپلیکیشن | روش افزودن |
|----------|------------|
| **Shadowrocket** | `+` ← `Subscribe` ← لینک را بچسبانید |
| **Streisand** | `Subscriptions` ← `Add` ← لینک را بچسبانید |
| **FoXray** | `Configuration` ← `Add Subscription` ← لینک را بچسبانید |
| **Quantumult X** | `Subscription` ← `Add` ← لینک را بچسبانید |

### ویندوز / لینوکس (Windows / Linux)
| اپلیکیشن | روش افزودن |
|----------|------------|
| **NekoRay** | `Server` ← `Add from URL` ← لینک را بچسبانید |
| **v2rayN** | `Subscription` ← `Add` ← لینک را بچسبانید |
| **Clash Verge / Verge Rev** | `Profiles` ← `New` ← `Remote` ← لینک را بچسبانید |
| **کلاینت‌های گرافیکی (v2rayA و…)** | لینک اشتراک را در تنظیمات وارد کنید |

## چه چیزی درون اشتراک است؟

- **پروتکل‌ها:** VLESS، VMess، Trojan، Shadowsocks، Hysteria2
- **ترنسپورت‌ها:** TCP، WebSocket، gRPC، HTTP/2، HTTPUpgrade، SplitHTTP
- **امنیت:** TLS، Reality، none
- **کشورهای خروجی (پیش‌فرض):** آلمان 🇩🇪، فنلاند 🇫🇮، هلند 🇳🇱، انگلستان 🇬🇧، آمریکا 🇺🇸، ترکیه 🇹🇷
- **تست‌شده:** هر کانفیگ از طریق فیلتر TCP، تشخیص کشور خروجی و چند دور تست URL زنده عبور می‌کند.
- **به‌روزرسانی روزانه:** طبق زمان‌بندی (پیش‌فرض ۰۴:۰۴ به وقت `Asia/Tehran`).

## به‌روزرسانی خودکار

اشتراک یک راهنمای به‌روزرسانی خودکار به کلاینت اعلام می‌کند (`SUBSCRIPTION_INTERVAL_HOURS`، پیش‌فرض ۲۴ ساعت). اپلیکیشن‌های سازگار هر ۲۴ ساعت خودشان اشتراک را دوباره می‌گیرند. اگر اپلیکیشن شما به‌روزرسانی خودکار ندارد، روزی یک‌بار همان لینک را دوباره وارد کنید.

> هدرهای پروفایل (`profile-title`، `subscription-userinfo`، `profile-update-interval`) فقط از مسیر داشبورد `‎/subscription‎` ارائه می‌شوند؛ فایل خام گیت‌هاب این هدرها را ندارد اما همان محتوا را دارد.

## راه‌اندازی شخصی (Self-Hosting) — شروع سریع

```bash
git clone https://github.com/sinahosseini379/VPN-Subscription-Tester-
cd VPN-Subscription-Tester-
pip install -e ".[dev]"
cp config.env.example config.env
# GITHUB_TOKEN و در صورت نیاز GITHUB_OWNER / GITHUB_REPO را در config.env تنظیم کنید
vpn-tester
```

- به‌صورت پیش‌فرض یک حلقه زمان‌بندی‌شده به‌همراه داشبورد وب روی `http://0.0.0.0:30445` اجرا می‌شود.
- برای یک اجرای تکی: `vpn-tester --once`
- برای رد کردن مرحله‌ی ارسال به گیت‌هاب: `vpn-tester --no-push`
- نیازمندی‌ها: **پایتون ۳.۹ به بالا**. هسته‌های Xray / sing-box / Hysteria به‌صورت خودکار دانلود و به‌روزرسانی می‌شوند.

## داشبورد

<!-- تصویر داشبورد: TODO یک اسکرین‌شات از داشبورد زنده روی پورت 30445 اینجا قرار دهید -->
`![Fiddel dashboard](docs/dashboard.png)`

داشبورد پیشرفت زنده، لاگ‌های جاری، کانفیگ‌های منتشرشده، مدیریت لیست اشتراک‌ها و ویرایش زمان‌بندی را نشان می‌دهد.

## حریم خصوصی

- **بدون لاگ ترافیک:** تستر فقط اتصال‌پذیری را می‌سنجد؛ هیچ ترافیک کاربری از سرورهای ما عبور نمی‌کند.
- **بدون ردیابی:** نه آنالیتیکس، نه شناسه کاربر، نه تلِمتری.
- **متن‌باز:** کل کد در گیت‌هاب موجود است.

## سلب مسئولیت

این پروژه صرفاً کانفیگ‌های **عمومیِ در دسترس** پروکسی را برای پژوهش و استفاده شخصی گردآوری و تست می‌کند. ما هیچ سرور پروکسی‌ای را میزبانی، کنترل یا تأیید نمی‌کنیم. استفاده بر عهده کاربر و مطابق قوانین محلی است.

## حمایت

اگر این پروژه برایتان مفید بود، لطفاً به مخزن گیت‌هاب ⭐ بدهید:
[github.com/sinahosseini379/VPN-Subscription-Tester-](https://github.com/sinahosseini379/VPN-Subscription-Tester-)

</div>

---

# Fiddel — Free VPN Config Subscription

A free, daily-rebuilt VPN subscription optimized for users in Iran and worldwide. Every config is **live-tested** through real Xray / sing-box / Hysteria2 processes before it is published, and only the best configs per country are kept.

Version: **2.4.0**

## Quick Subscription Links

| Type | Direct (raw) link |
|------|-------------------|
| **Base64 (all apps)** | `https://raw.githubusercontent.com/sinahosseini379/VPN-Subscription-Tester-/main/felfelconfig.txt` |

> **Tip:** Every modern VPN app (SFA, sing-box, NekoBox, Clash Meta, v2rayNG, Shadowrocket, Streisand, Hiddify, …) accepts a single base64 subscription URL. Just paste this one link.

## How to Add to Apps

### Android
| App | How to Add |
|-----|------------|
| **SFA / Sing-box** | `Profiles` → `Add` → `Remote` → Paste URL |
| **NekoBox** | `Profile` → `Import from URL` → Paste URL |
| **v2rayNG** | `+` → `Import from clipboard` (after copying URL) |
| **Kitsunebi** | `+` → `Import from URI` → Paste URL |
| **Hiddify** | `Config` → `Add Subscription` → Paste URL |

### iOS / macOS
| App | How to Add |
|-----|------------|
| **Shadowrocket** | `+` → `Subscribe` → Paste URL |
| **Streisand** | `Subscriptions` → `Add` → Paste URL |
| **FoXray** | `Configuration` → `Add Subscription` → Paste URL |
| **Quantumult X** | `Subscription` → `Add` → Paste URL |

### Windows / Linux
| App | How to Add |
|-----|------------|
| **NekoRay** | `Server` → `Add from URL` → Paste URL |
| **v2rayN** | `Subscription` → `Add` → Paste URL |
| **Clash Verge / Verge Rev** | `Profiles` → `New` → `Remote` → Paste URL |
| **GUI clients (v2rayA, etc.)** | Import subscription URL in settings |

## What's Inside

- **Protocols:** VLESS, VMess, Trojan, Shadowsocks, Hysteria2
- **Transports:** TCP, WebSocket, gRPC, HTTP/2, HTTPUpgrade, SplitHTTP
- **Security:** TLS, Reality, none
- **Exit countries (default):** Germany 🇩🇪, Finland 🇫🇮, Netherlands 🇳🇱, United Kingdom 🇬🇧, United States 🇺🇸, Turkey 🇹🇷
- **Tested:** every config passes a TCP filter, exit-country check, and several rounds of live URL tests.
- **Daily updates:** on a schedule (default 04:04 `Asia/Tehran`).

## Auto-Update

The subscription advertises an auto-update hint to clients (`SUBSCRIPTION_INTERVAL_HOURS`, default 24). Compatible apps re-fetch the subscription every 24 hours on their own. If your app does not auto-update, just re-import the same URL once a day.

> Profile headers (`profile-title`, `subscription-userinfo`, `profile-update-interval`) are served from the dashboard's `/subscription` route. The raw GitHub file carries the same content but cannot carry those headers.

## Self-Hosting Quick Start

```bash
git clone https://github.com/sinahosseini379/VPN-Subscription-Tester-
cd VPN-Subscription-Tester-
pip install -e ".[dev]"
cp config.env.example config.env
# Set GITHUB_TOKEN (and GITHUB_OWNER / GITHUB_REPO if different) in config.env
vpn-tester
```

- By default this runs a scheduled loop plus a web dashboard at `http://0.0.0.0:30445`.
- Single run: `vpn-tester --once`
- Skip the GitHub push step: `vpn-tester --no-push`
- Requirements: **Python 3.9+**. Xray / sing-box / Hysteria cores are downloaded and updated automatically.

## Dashboard

<!-- Dashboard image: TODO drop a screenshot of the live dashboard on port 30445 here -->
`![Fiddel dashboard](docs/dashboard.png)`

The dashboard shows live progress, streaming logs, published configs, subscription-list management, and schedule editing.

## Privacy

- **No traffic logs:** the tester only checks connectivity; no user traffic passes through our servers.
- **No tracking:** no analytics, no user IDs, no telemetry.
- **Open source:** all code is on GitHub.

## Disclaimer

This project only collects and tests **publicly available** proxy configurations for research and personal use. We do not host, control, or endorse any proxy server. Use at your own risk and in accordance with local laws.

## Support / Star

If this helped you, please ⭐ the GitHub repository:
[github.com/sinahosseini379/VPN-Subscription-Tester-](https://github.com/sinahosseini379/VPN-Subscription-Tester-)

## Documentation

Full technical documentation lives in the [wiki](wiki/Home.md): Architecture, Configuration, Core Management, Pipeline, Incremental Runs, Dashboard API, GitHub Push, Deployment, and Testing.
