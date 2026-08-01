<div dir="rtl">

# Fiddel — اشتراک VPN

اشتراک خودکار و زنده که بهترین سرورها را از میان ده‌ها کشور انتخاب و مرتب می‌کند.
نام اشتراک **Fiddel** است و هر **۲۴ ساعت** یک‌بار خودش را به‌روزرسانی می‌کند.

---

## نحوه اتصال (راهنمای کاربر)

### ۱. لینک اشتراک را کپی کنید

لینک اشتراک را از این ریپو (یا صفحه داشبورد سرور) کپی کنید.

### ۲. در اپ موبایل خود اضافه کنید

| اپلیکیشن | پلتفرم | روش |
|---|---|---|
| **Hiddify** | اندروید / iOS | «Add from clipboard» |
| **v2rayNG** | اندروید | دکمه `+` ← «Import config from Clipboard» |
| **Nekoray** | اندروید / دسکتاپ | «Import from clipboard» |
| **Streisand** | iOS | «Add Subscription» ← لینک را بچسبانید |
| **sing-box / SFA** | اندروید | «Import» ← لینک اشتراک |

در بیشتر اپ‌ها کافیست **لینک را کپی کنید و در اپ بچسبانید**؛ اشتراک خودکار دانلود می‌شود.

### ۳. از سرعت لذت ببرید 🌐

سرورها به‌صورت خودکار با نام **«کشور | شماره»** (مثل `Germany | 01`) مرتب شده‌اند
و فقط سالم‌ترین‌ها نگه داشته می‌شوند.

---

## سوالات متداول

**اشتراک چند وقت یک‌بار به‌روز می‌شود؟**
هر ۲۴ ساعت به‌صورت خودکار بررسی و اگر سروری از کار افتاده باشد با سرور سالم جایگزین می‌شود.

**چرا بعضی سرورها حذف می‌شوند؟**
سرورهایی که تست زنده را پاس نکنند (قطع، کند یا کشور نامجاز) از لیست حذف می‌شوند.

**چطور نام سرورها را تشخیص دهم؟**
هر سرور با فرمت `کشور | شماره` نام‌گذاری شده؛ شماره‌ها سراسری و ۰۱ به بعد هستند.

</div>

---

<div dir="ltr">

# Fiddel — VPN Subscription

An automated, live subscription that picks and ranks the best servers across many
countries. The profile name is **Fiddel** and it auto-updates every **24 hours**.

---

## How to connect (user guide)

### 1. Copy the subscription link

Copy the subscription URL from this repo (or from the dashboard page on the server).

### 2. Add it in your mobile app

| App | Platform | How |
|---|---|---|
| **Hiddify** | Android / iOS | "Add from clipboard" |
| **v2rayNG** | Android | `+` button → "Import config from Clipboard" |
| **Nekoray** | Android / Desktop | "Import from clipboard" |
| **Streisand** | iOS | "Add Subscription" → paste the link |
| **sing-box / SFA** | Android | "Import" → subscription link |

In most apps you just **copy the link and paste it**; the subscription is fetched automatically.

### 3. Enjoy high-speed connections 🌐

Servers are named **"Country | Number"** (e.g. `Germany | 01`) and only the
healthiest ones are kept — dead or slow servers are swapped out automatically.

---

## FAQ

**How often does the subscription update?**
Every 24 hours the tester re-verifies the servers; if one goes offline it is
replaced by a healthy config automatically.

**Why do some servers get removed?**
Servers that fail the live test (down, too slow, or an unallowed exit country)
are dropped from the list.

**How do I read the server names?**
Each server is labeled `Country | Number` with a global 01..NN numbering.

</div>

---

## For administrators / developers

This repository is the **technical home** of the project: download subscriptions,
live-test every config through real proxy cores (Xray / sing-box / Hysteria2),
filter by TCP reachability + exit country, score by error-rate / latency, and
publish the best configs to GitHub automatically — with a built-in web dashboard.

Technical docs (architecture, deployment, configuration, security, Docker) live
in the [project wiki](../../wiki). End users only need the subscription link above.

### Quick start (server)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp config.env.example config.env   # fill GITHUB_TOKEN + settings
python -m vpn_tester.main           # scheduled loop + dashboard on :30445
```

Run tests: `pytest -q` · Lint: `ruff check src tests && ruff format src tests`

</div>
