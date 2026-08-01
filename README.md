# Fiddel VPN — Free Config Subscription

A free, daily-updated VPN configuration subscription optimized for users in Iran and worldwide.

## Quick Links

| Protocol | Direct Link |
|----------|-------------|
| **Base64 (all apps)** | `https://raw.githubusercontent.com/sinahosseini379/VPN-Subscription-Tester-/main/felfelconfig.txt` |
| **Sing-box / SFA** | `https://raw.githubusercontent.com/sinahosseini379/VPN-Subscription-Tester-/main/felfelconfig.txt` |
| **Clash / Meta** | `https://raw.githubusercontent.com/sinahosseini379/VPN-Subscription-Tester-/main/felfelconfig.txt` |
| **V2Ray / NekoBox / Shadowrocket** | `https://raw.githubusercontent.com/sinahosseini379/VPN-Subscription-Tester-/main/felfelconfig.txt` |

> **Tip**: All links point to the same file. Most modern VPN apps (SFA, NekoBox, Clash Meta, v2rayNG, Shadowrocket, Streisand, etc.) accept a single base64 subscription URL.

---

## How to Use

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
| **Clash Verge / Clash Verge Rev** | `Profiles` → `New` → `Remote` → Paste URL |
| **GUI clients (v2rayA, etc.)** | Import subscription URL in settings |

---

## What's Inside

- **Protocols**: VLESS (TCP/WS/gRPC/XHTTP), VMess, Trojan, Shadowsocks, **Hysteria2**
- **Transports**: TCP, WebSocket, gRPC, XHTTP, HTTP/2, HTTP/3 (QUIC)
- **Security**: TLS, Reality, mTLS, none
- **Obfuscation**: Salamander (Hysteria2), UTLS, HTTPUpgrade
- **Countries**: Germany 🇩🇪, Netherlands 🇳🇱, USA 🇺🇸, Finland 🇫🇮, UK 🇬🇧, Turkey 🇹🇷
- **Daily auto-update**: Every 24 hours at 04:04 Tehran time
- **Tested**: Each config is live-tested through real Xray/Sing-box/Hysteria processes

---

## Auto-Update

The subscription includes an **auto-update hint** (`update_interval_hours=24`). Compatible apps (SFA, NekoBox, Shadowrocket, Streisand, Hiddify, etc.) will automatically re-fetch the subscription every 24 hours.

If your app doesn't auto-update, just re-import the same URL once a day.

---

## Status & Stats

- **Generated**: Daily at 04:04 Asia/Tehran
- **Source**: 2 public subscription sources, ~1000+ raw configs
- **Filtered**: TCP reachable → Correct exit country → Live URL tests (5 rounds × 4 targets)
- **Output**: Top 2 configs per country (max 12 total)
- **Metadata**: [felfelconfig.txt.meta.json](https://raw.githubusercontent.com/sinahosseini379/VPN-Subscription-Tester-/main/felfelconfig.txt.meta.json) (latency, error rate, country, protocol)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Invalid subscription" | Make sure you copied the **raw** GitHub URL (not the HTML page) |
| Configs don't connect | Try a different protocol (VLESS-Reality works best in Iran) |
| Slow speeds | Pick configs with lower latency (shown in app) |
| App crashes on import | Update your VPN app to latest version |

---

## Privacy & Security

- **No logs**: The tester only checks connectivity; no traffic passes through our servers
- **Open source**: All code at [github.com/sinahosseini379/VPN-Subscription-Tester-](https://github.com/sinahosseini379/VPN-Subscription-Tester-)
- **No tracking**: No analytics, no user IDs, no telemetry

---

## Support the Project

If this helps you, please ⭐ the [GitHub repo](https://github.com/sinahosseini379/VPN-Subscription-Tester-). It's free, open source, and community-driven.

---

## Disclaimer

This project provides **publicly available** proxy configurations for research and personal use. We do not host, control, or endorse any proxy server. Use at your own risk and in accordance with local laws.

---

## Persian / فارسی

### لینک‌های مستقیم اشتراک

| پروتکل | لینک مستقیم |
|--------|-------------|
| **Base64 (همه اپلیکیشن‌ها)** | `https://raw.githubusercontent.com/sinahosseini379/VPN-Subscription-Tester-/main/felfelconfig.txt` |
| **Sing-box / SFA** | `https://raw.githubusercontent.com/sinahosseini379/VPN-Subscription-Tester-/main/felfelconfig.txt` |
| **Clash / Meta** | `https://raw.githubusercontent.com/sinahosseini379/VPN-Subscription-Tester-/main/felfelconfig.txt` |
| **V2Ray / NekoBox / Shadowrocket** | `https://raw.githubusercontent.com/sinahosseini379/VPN-Subscription-Tester-/main/felfelconfig.txt` |

> **نکته**: همه لینک‌ها به یک فایل اشاره دارند. اکثر اپلیکیشن‌های مدرن VPN (SFA، NekoBox، Clash Meta، v2rayNG، Shadowrocket، Streisand و...) یک URL اشتراک Base64 را می‌پذیرند.

### نحوه استفاده

| اپلیکیشن | روش اضافه کردن |
|----------|----------------|
| **SFA / Sing-box** | `Profiles` → `Add` → `Remote` → URL را چسبانید |
| **NekoBox** | `Profile` → `Import from URL` → URL را چسبانید |
| **v2rayNG** | `+` → `Import from clipboard` (بعد از کپی URL) |
| **Kitsunebi** | `+` → `Import from URI` → URL را چسبانید |
| **Hiddify** | `Config` → `Add Subscription` → URL را چسبانید |
| **Shadowrocket (iOS)** | `+` → `Subscribe` → URL را چسبانید |
| **Streisand (iOS)** | `Subscriptions` → `Add` → URL را چسبانید |
| **v2rayN (Windows)** | `Subscription` → `Add` → URL را چسبانید |
| **Clash Verge Rev** | `Profiles` → `New` → `Remote` → URL را چسبانید |

### چه چیزهایی در اشتراک هست؟

- **پروتکل‌ها**: VLESS (TCP/WS/gRPC/XHTTP)، VMess، Trojan، Shadowsocks، **Hysteria2**
- **ترنسبورت‌ها**: TCP، WebSocket، gRPC، XHTTP، HTTP/2، HTTP/3 (QUIC)
- **امنیت**: TLS، Reality، mTLS، none
- **ماسکینگ**: Salamander (Hysteria2)، UTLS، HTTPUpgrade
- **کشورها**: آلمان 🇩🇪، هلند 🇳🇱، آمریکا 🇺🇸، فنلاند 🇫🇮، انگلستان 🇬🇧، ترکیه 🇹🇷
- **بروزرسانی روزانه خودکار**: هر ۲۴ ساعت یک بار ساعت ۰۴:۰۴ وقت تهران
- **تست شده**: هر کانفیگ از طریق پروسه‌های واقعی Xray / Sing-box / Hysteria تست زنده شده

### بروزرسانی خودکار

اشتراک شامل یک **راهنمای بروزرسانی خودکار** است (`update_interval_hours=24`). اپلیکیشن‌های سازگار (SFA، NekoBox، Shadowrocket، Streisand، Hiddify و...) به‌طور خودکار هر ۲۴ ساعت یک‌بار اشتراک را مجدداً دریافت می‌کنند.

اگر اپلیکیشن‌تان بروزرسانی خودکار ندارد، کافیست یک‌بار در روز همان URL را مجدداً ایمپورت کنید.

### عیب‌یابی

| مشکل | راه‌حل |
|-------|--------|
| «اشتراک نامعتبر» | مطمئن شوید **URL مستقیم (Raw)** گیت‌هاب را کپی کرده‌اید (نه صفحه HTML) |
| کانفیگ‌ها وصل نمی‌شوند | پروتکل دیگری امتحان کنید (VLESS-Reality در ایران بهترین نتیجه را می‌دهد) |
| سرعت پایین | کانفیگ‌های با تاخیر (latency) کمتر را انتخاب کنید |
| اپلیکیشن هنگام ایمپورت کرش می‌کند | اپلیکیشن VPN را به آخرین نسخه بروزرسانی کنید |

### حریم خصوصی و امنیت

- **بدون لاگ**: تستر فقط اتصال را چک می‌کند؛ هیچ ترافیکی از سرورهای ما نمی‌گذرد
- **متن‌باز**: کل کد در [گیت‌هاب](https://github.com/sinahosseini379/VPN-Subscription-Tester-) موجود است
- **بدون ردیابی**: هیچ آنالیتیکس، شناسه کاربری، یا تلِمتری وجود ندارد

### حمایت از پروژه

اگر این اشتراک برایتان مفید بود، لطفاً ریپوی [گیت‌هاب](https://github.com/sinahosseini379/VPN-Subscription-Tester-) را ⭐ کنید. این پروژه رایگان، متن‌باز و جامعه‌محور است.

### سلب مسئولیت

این پروژه تنها **کانفیگ‌های عمومی** پروکسی را برای تحقیق و استفاده شخصی جمع‌آوری می‌کند. ما هیچ سرور پروکسی را میزبانی، کنترل یا تایید نمی‌کنیم. استفاده به عهده کاربر و طبق قوانین محلی است.