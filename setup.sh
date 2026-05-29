#!/usr/bin/env bash
# setup.sh — نصب وابستگی‌ها و راه‌اندازی cronjob
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

echo "=== Installing Python dependencies ==="
$PYTHON -m pip install -r "$SCRIPT_DIR/requirements.txt" --break-system-packages 2>/dev/null \
  || $PYTHON -m pip install -r "$SCRIPT_DIR/requirements.txt"

echo ""
echo "=== Checking config.env ==="
if grep -q "ghp_xxx" "$SCRIPT_DIR/config.env" 2>/dev/null; then
  echo "⚠️  config.env هنوز پر نشده — قبل از اجرا مقادیر واقعی را وارد کنید."
fi

echo ""
echo "=== Installing cron job (every day at 04:00) ==="

CRON_CMD="0 4 * * * cd \"$SCRIPT_DIR\" && $PYTHON run.py >> vpn_tester.log 2>&1"

# آیا قبلاً نصب شده؟
if crontab -l 2>/dev/null | grep -qF "run.py"; then
  echo "Cron job already installed — skipping."
else
  # اضافه کردن به crontab موجود
  (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
  echo "✅  Cron job added:"
  echo "    $CRON_CMD"
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "مراحل بعدی:"
echo "  1. فایل subscriptions.txt را باز کنید و لینک‌های سابسکریپشن را وارد کنید"
echo "  2. فایل config.env را باز کنید و اطلاعات GitHub را وارد کنید"
echo "  3. برای اجرای دستی: python3 run.py"
echo "  4. اسکریپت هر روز ساعت 4 صبح به‌صورت خودکار اجرا می‌شود"
