# VPN Subscription Tester 🚀

اسکریپت پایتون برای دانلود، URL-test واقعی و فیلتر کانفیگ‌های Xray/Sing-box با پوش خودکار به GitHub.

---

## نحوه کار (Real URL Test)

برخلاف ابزارهای ساده که فقط TCP ping می‌زنند، این اسکریپت:

1. برای **هر کانفیگ** یک پروسه Xray مجزا اجرا می‌کند
2. یک پورت SOCKS5 محلی منحصربه‌فرد به آن می‌دهد  
3. درخواست‌های HTTP واقعی را از طریق آن پروکسی به ۵ هدف می‌فرستد
4. تأخیر end-to-end واقعی را اندازه می‌گیرد

---

## ساختار فایل‌ها

```
vpn-sub-tester/
├── run.py              # نقطه ورود اصلی
├── vpn_tester.py       # هسته: دانلود + URL-test + فیلتر
├── github_push.py      # پوش خودکار به GitHub
├── subscriptions.txt   # لیست لینک‌های سابسکریپشن (حداکثر ۱۰)
├── config.env          # تنظیمات GitHub
├── requirements.txt    # وابستگی‌های پایتون
├── setup.sh            # نصب + راه‌اندازی cron
└── best_configs.txt    # خروجی نهایی (بعد از اجرا ساخته می‌شود)
```

---

## پیش‌نیاز اصلی — نصب Xray-core

اسکریپت به باینری `xray` نیاز دارد:

### لینوکس / macOS
```bash
# روش ۱: اسکریپت رسمی
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# روش ۲: دانلود مستقیم و قرار دادن در پوشه پروژه
# https://github.com/XTLS/Xray-core/releases/latest
# فایل xray را در کنار vpn_tester.py بگذارید
```

### مسیر سفارشی
```bash
export XRAY_BIN=/path/to/your/xray
```

---

## نصب و راه‌اندازی

```bash
# ۱. نصب وابستگی‌ها و cron
chmod +x setup.sh && ./setup.sh

# ۲. لینک‌های سابسکریپشن
nano subscriptions.txt

# ۳. اطلاعات GitHub
nano config.env

# ۴. اجرای دستی
python3 run.py
```

---

## جریان کار

```
دانلود همه سابسکریپشن‌ها (حداکثر ۱۰)
            ↓
    حذف URI های تکراری
            ↓
  Round 1 — هر کانفیگ:
    ├── اجرای Xray روی پورت محلی
    ├── ارسال HTTP به Google, YouTube, Cloudflare, Spotify, X
    └── حذف کانفیگ‌هایی با خطای بیش از ۱۰٪
            ↓
  Round 2, 3, 4 — تکرار برای دقت بیشتر
            ↓
  مرتب‌سازی بر اساس میانگین تأخیر
            ↓
  ذخیره ۱۵ کانفیگ برتر → best_configs.txt
            ↓
  git commit + push به GitHub
```

---

## اهداف تست

| سرویس | URL |
|---|---|
| Google | http://www.gstatic.com/generate_204 |
| YouTube | https://www.youtube.com/generate_204 |
| Cloudflare | http://cp.cloudflare.com/ |
| Spotify | https://spclient.wg.spotify.com/ |
| X.com | https://x.com/ |

---

## تنظیمات قابل تغییر در `vpn_tester.py`

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `TOP_N` | 15 | تعداد کانفیگ نهایی |
| `MAX_ERROR_RATE` | 0.10 | حداکثر نرخ خطا در Round 1 |
| `EXTRA_ROUNDS` | 3 | راندهای اضافی تأخیر |
| `MAX_CONCURRENT` | 10 | تعداد Xray process های همزمان |
| `CONNECT_TIMEOUT` | 10.0 | تایم‌اوت اتصال (ثانیه) |
| `REQUEST_TIMEOUT` | 15.0 | تایم‌اوت کامل درخواست (ثانیه) |
| `XRAY_STARTUP_WAIT` | 1.5 | زمان انتظار بعد از اجرای Xray |

> ⚠️ اگر تعداد کانفیگ‌ها زیاد است، `MAX_CONCURRENT` را کاهش دهید تا از مصرف بیش از حد RAM جلوگیری شود.

---

## کرون‌جاب (هر روز ساعت ۴ صبح)

```bash
crontab -l   # مشاهده
crontab -e   # ویرایش / حذف
```

---

## استفاده از فایل خروجی

`best_configs.txt` یک سابسکریپشن base64 استاندارد است. این لینک raw را در کلاینت وارد کنید:

```
https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/best_configs.txt
```

سازگار با: **v2rayNG، Hiddify، Shadowrocket، Nekoray، Streisand**
