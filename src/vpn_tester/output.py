"""Write the final base64 subscription and its metadata JSON."""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings
from .models import Config

log = logging.getLogger(__name__)


def write_subscription(configs: list[Config], settings: Settings) -> dict:
    """Write best_configs.txt (base64) + .meta.json. Returns the metadata dict."""
    uris = [c.uri for c in configs]
    payload = "\n".join(uris)
    encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")

    out_path = Path(settings.output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(encoded, encoding="utf-8")
    log.info("Subscription written -> %s (%d configs)", out_path, len(configs))

    meta = build_metadata(configs, settings)
    meta_path = Path(settings.metadata_file)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Metadata written -> %s", meta_path)
    return meta


def build_metadata(configs: list[Config], settings: Settings) -> dict:
    """Pure metadata builder, kept separate for testability."""
    avg_lat = _avg([c.avg_latency for c in configs if c.latencies])
    err_rate = _avg([c.error_rate for c in configs]) if configs else 1.0
    by_country: dict[str, int] = {}
    for c in configs:
        key = c.country or "?"
        by_country[key] = by_country.get(key, 0) + 1

    weights = {label: w for label, _url, w in settings.test_urls}

    return {
        "version": "2.3.0",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(configs),
        "avg_latency_ms": _round2(avg_lat),
        "avg_error_rate": _round2(err_rate),
        "by_country": by_country,
        "targets": [
            {"label": label, "url": url, "weight": weight}
            for label, url, weight in settings.test_urls
        ],
        "items": [
            {
                "name": c.display_name(),
                "protocol": c.protocol,
                "country": c.country,
                "error_rate": _round2(c.error_rate),
                "weighted_error_rate": _round2(c.weighted_error_rate(weights)),
                "avg_latency_ms": _round2(c.avg_latency) if c.latencies else None,
                "p50_ms": _round2(c.p50) if c.latencies else None,
                "p95_ms": _round2(c.p95) if c.latencies else None,
                "samples": c.total,
                "per_target": c.target_stats,
            }
            for c in configs
        ],
    }


def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _round2(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None
