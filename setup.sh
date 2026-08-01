#!/usr/bin/env bash
# setup.sh — install Python deps, download xray, verify config, install cron/systemd.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON="${PYTHON:-python3}"

echo "=== 1/5 Python dependencies ==="
"$PYTHON" -m venv .venv
if [[ "$(uname -s)" == MINGW* || "$(uname -s)" == MSYS* ]]; then
  source .venv/Scripts/activate
else
  source .venv/bin/activate
fi
pip install --upgrade pip
pip install -e ".[dev]"

echo "=== 2/5 Xray binary ==="
if ! command -v xray >/dev/null 2>&1 && [[ -z "${XRAY_BIN:-}" ]]; then
  echo "  Downloading latest Xray-core to /opt/xray ..."
  sudo mkdir -p /opt/xray
  XRAY_URL=$(curl -sL https://api.github.com/repos/XTLS/Xray-core/releases/latest | \
    python3 -c "import json,sys;d=json.load(sys.stdin);print(next(a['browser_download_url'] for a in d['assets'] if a['name']=='Xray-linux-64.zip'))")
  curl -sL "$XRAY_URL" -o /tmp/xray.zip
  sudo unzip -o /tmp/xray.zip -d /opt/xray
  sudo chmod +x /opt/xray/xray
  rm -f /tmp/xray.zip
  echo "  export XRAY_BIN=/opt/xray/xray" 
else
  echo "  xray already available."
fi

echo "=== 3/5 config.env ==="
if [[ ! -f config.env ]]; then
  cp config.env.example config.env
  echo "  Created config.env from example — fill in GITHUB_TOKEN before running."
elif grep -qE "^GITHUB_TOKEN= *$" config.env; then
  echo "  WARNING: GITHUB_TOKEN is empty in config.env"
fi

echo "=== 4/5 subscriptions.txt ==="
if [[ ! -f subscriptions.txt ]]; then
  cp subscriptions.txt.example subscriptions.txt 2>/dev/null || true
fi

echo "=== 5/5 smoke test ==="
python -c "import vpn_tester; print('OK vpn_tester', vpn_tester.__version__)"
pytest -q >/dev/null && echo "  tests OK"

echo ""
echo "Done. Run a single cycle with:  ./run --once"
echo "Or keep it alive forever with:  nohup python -m vpn_tester.main > vpn_tester.log 2>&1 &"
