# VPN Subscription Tester — راهنمای به‌روزرسانی‌شده

این پروژه اسکریپتی برای دانلود سابسکریپشن‌ها، تست واقعی URL‌ها از طریق هر کانفیگ (با اجرای یک پروسه Xray برای هر کانفیگ)، فیلتر و انتخاب بهترین کانفیگ‌ها و در نهایت پوش خودکار خروجی به GitHub است.

نسخه فعلی ویژگی‌های زیر را انجام می‌دهد:

- محدود کردن تعداد سابسکریپشن‌های دانلودی به اولین ۱۰ لینک موجود در `subscriptions.txt`.
- استخراج کانفیگ‌های Xray/Sing-box/Clash/SS/Trojan از محتواهای base64 یا JSON.
- یک فیلتر TCP پیش‌فرض: برای هر سرور ۵ تلاش TCP انجام می‌شود و فقط کانفیگ‌هایی که حداقل ۴ اتصال موفق داشته باشند نگه داشته می‌شوند.
- اجرای Xray برای هر کانفیگ به‌صورت محلی و گرفتن IP خروجی، سپس نگهداری فقط کانفیگ‌هایی که IP خروجی مربوط به کشورهای مجاز است: آلمان (DE)، فنلاند (FI)، هلند (NL)، بریتانیا (GB)، آمریکا (US)، کانادا (CA). نام کانفیگ‌ها به «نام کشور + ایموجی پرچم» تغییر می‌کند.
- تکرار تست URLها (`Google`, `YouTube`, `Cloudflare`, `X.com`) پنج بار برای هر کانفیگ و محاسبه درصد اختلال (drop%).
- مرتب‌سازی بر اساس کمترین درصد اختلال سپس میانگین تأخیر و انتخاب `TOP_N` کانفیگ نهایی (پیش‌فرض 10).
- نوشتن خروجی فشرده‌شده در `best_configs.txt` و یک فایل متادیتا `best_configs.txt.meta.json` شامل زمان تولید، تعداد آیتم‌ها، میانگین تأخیر و نرخ افت.
- پوش خودکار به GitHub با استفاده از `github_push.py` (خواندن مقادیر از `config.env` یا متغیرهای محیطی).
- اجرای مداوم: اسکریپت به‌صورت خودکار هر 90 دقیقه حلقه‌اش را تکرار می‌کند (بنابراین برای اجرای دائمی، کافیست آن را در پس‌زمینه یا به‌عنوان سرویس قرار دهید).

---

**فایل‌ها**

```
VPN-Subscription-Tester/
├── run.py              # wrapper / entry (اجرا از این فایل ممکن است)
├── vpn_tester.py       # هسته اصلی (تست، فیلتر، خروجی)
├── github_push.py      # پوش به GitHub
├── subscriptions.txt   # لیست لینک‌های سابسکریپشن (حداکثر ۱۰)
├── config.env          # تنظیمات GitHub و گزینه‌های اختیاری
├── requirements.txt    # وابستگی‌های پایتون
├── setup.sh            # نصب وابستگی‌ها و راه‌اندازی (اختیاری)
└── best_configs.txt    # خروجی نهایی (بعد از اجرا ساخته می‌شود)
```

---

پیش‌نیازها
- Python 3.9+
- کتابخانه‌های موجود در `requirements.txt` (با `pip install -r requirements.txt` نصب می‌شوند)
- باینری `xray` در PATH یا تنظیم شده در `XRAY_BIN` در `config.env` (یا متغیر محیطی)

نصب سریع
```bash
# نصب وابستگی‌ها (در virtualenv توصیه می‌شود)
python -m venv .venv
source .venv/bin/activate    # یا on Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
```

تنظیمات `config.env` (نمونه)
```
# TOKEN با دسترسی نوشتن به ریپو
GITHUB_TOKEN=ghp_xxx...
GITHUB_OWNER=your_github_user
GITHUB_REPO=your_repo_name
GITHUB_BRANCH=main
OUTPUT_FILE=best_configs.txt
REPO_DIR=./repo
# مسیر اختیاری xray
# XRAY_BIN=/home/you/bin/xray
```

اجرا دستی
```bash
python vpn_tester.py
```
یا اگر می‌خواهید از run.py (در صورت وجود wrapper) استفاده کنید:
```bash
python run.py
```

اسکریپت خودش بعد از هر بار اجرا منتظر `90` دقیقه می‌ماند و مجدداً مراحل را از ابتدا تکرار می‌کند؛ بنابراین کافیست آن را یکبار اجرا کنید و به‌صورت پس‌زمینه نگه دارید.

اجرای در پس‌زمینه (نمونه برای لینوکس)
```bash
# با nohup
nohup python vpn_tester.py >/var/log/vpn_tester.log 2>&1 &

# یا با tmux/screen
tmux new -s vpntester 'python vpn_tester.py'
```

راه‌اندازی به‌عنوان سرویس systemd (پیشنهاد شده برای سرور)
1. فایل سرویس: `/etc/systemd/system/vpn-tester.service`
```
[Unit]
Description=VPN Subscription Tester
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/VPN-Subscription-Tester
ExecStart=/path/to/python /path/to/VPN-Subscription-Tester/vpn_tester.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```
2. فعال‌سازی و استارت:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vpn-tester.service
sudo journalctl -u vpn-tester -f
```

کرون‌جاب
از آن‌جایی که اسکریپت یک حلقه 90 دقیقه‌ای داخلی دارد، بهترین روش این است که آن را با `@reboot` در کرون اجرا کنید تا پس از ریبوت سرور خودکار بالا بیاید، یا از systemd استفاده کنید. اگر می‌خواهید هر 90 دقیقه کرون را جداگانه اجرا کنید، کرون مستقیماً 90 دقیقه را پشتیبانی نمی‌کند؛ دو گزینه دارید:

گزینه A — اجرا در بوت و نگهداری دائمی (پیشنهادی):
```bash
# ویرایش crontab کاربر
crontab -e

# اضافه کنید (شروع در بوت و اجرای در پس‌زمینه):
@reboot sleep 30 && /usr/bin/nohup /usr/bin/python /path/to/VPN-Subscription-Tester/vpn_tester.py >/path/to/vpn_tester.log 2>&1 &
```

گزینه B — استفاده از systemd timer برای زمان‌بندی 90 دقیقه‌ای (دقیق‌تر):
1. فایل سرویس `/etc/systemd/system/vpn-tester-run.service` (موقتی، اجرا یکبار):
```
[Unit]
Description=One-shot run of VPN tester

[Service]
Type=oneshot
User=youruser
WorkingDirectory=/path/to/VPN-Subscription-Tester
ExecStart=/path/to/python /path/to/VPN-Subscription-Tester/vpn_tester.py
```

2. فایل تایمر `/etc/systemd/system/vpn-tester-run.timer`:
```
[Unit]
Description=Run VPN tester every 90 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=90min
Unit=vpn-tester-run.service

[Install]
WantedBy=timers.target
```

3. فعال‌سازی:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vpn-tester-run.timer
sudo systemctl status vpn-tester-run.timer
```

نکته: اگر از تایمر استفاده کنید، اسکریپت نباید وارد حلقه داخلی شود (یا باید حالت oneshot اضافه شود). در نسخه فعلی اسکریپت یک حلقه 90 دقیقه‌ای داخلی دارد؛ بنابراین از `@reboot` یا systemd service استفاده کنید تا فقط یک نمونه همیشه اجرا شود.

پوش به GitHub
برای پوش خودکار نیاز است `config.env` یا متغیرهای محیطی حاوی `GITHUB_TOKEN`, `GITHUB_OWNER`, `GITHUB_REPO` باشد. `github_push.py` از این مقادیر استفاده می‌کند تا ریپو را clone/pull کرده، `best_configs.txt` را کپی کند و commit/push بزند.

نمونه قدم‌ها برای ست‌آپ اولیه GitHub:
```bash
# 1. مقداردهی در config.env
nano config.env

# 2. اجرای دستی برای تست
python github_push.py
```

تذکرات ایمنی
- مقدار `GITHUB_TOKEN` را با دقت نگه دارید و در مخزن عمومی قرار ندهید.
- اگر سرور شما فایروال یا محدودیت اتصال دارد، ممکن است TCP-ping یا تست URL ناکام بماند — مقادیر `PING_TRIES`, `PING_MIN_SUCCESS`, `MAX_CONCURRENT` را مطابق نیاز تغییر دهید.

پایان
اگر مایل هستید من می‌توانم:
- یک نمونه `config.env.example` بسازم با توضیحات.
- systemd unit/timer نمونه را برای مسیرهای شما تولید کنم.
- `setup.sh` را بررسی و طوری ویرایش کنم که virtualenv بسازد و سرویس را ثبت کند.

مواردی که من اصلاح کردم در کد فعلی:
- فیلتر TCP (۵ تلاش، حداقل ۴ موفق).
- فیلتر کشور خروجی و تغییر نام کانفیگ‌ها به نام کشور + ایموجی.
- حذف تست Spotify و متمرکز شدن روی Google, YouTube, Cloudflare, X.com.
- اضافه شدن متادیتا (`best_configs.txt.meta.json`).
- حلقه داخلی ۹۰ دقیقه‌ای و پوش خودکار به GitHub پس از نوشتن خروجی.

