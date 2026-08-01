# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# System deps + latest Xray from GitHub releases
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends curl ca-certificates unzip; \
    mkdir -p /opt/xray; \
    curl -sL "https://api.github.com/repos/XTLS/Xray-core/releases/latest" \
      -o /tmp/release.json; \
    XRAY_URL=$(python3 -c \
      "import json;d=json.load(open('/tmp/release.json'));print(next(a['browser_download_url'] for a in d['assets'] if a['name']=='Xray-linux-64.zip'))"); \
    curl -sL "$XRAY_URL" -o /tmp/xray.zip; \
    unzip /tmp/xray.zip -d /opt/xray; \
    chmod +x /opt/xray/xray; \
    rm -rf /tmp/*.json /tmp/*.zip /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY pyproject.toml .
COPY src/ src/
RUN pip install .

COPY subscriptions.txt config.env.example ./

# Mount a real config.env + output volume at runtime:
#   docker compose run / -v ./config.env:/app/config.env:ro
VOLUME ["/app"]

ENV XRAY_BIN=/opt/xray/xray

# Run forever (90-min loop inside). For a single run: add --once
CMD ["vpn-tester"]

# Trivial healthcheck: process alive check
HEALTHCHECK --interval=5m --timeout=10s --start-period=30s --retries=3 \
  CMD pgrep -f vpn-tester || exit 1
