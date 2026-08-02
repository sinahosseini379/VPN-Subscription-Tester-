"""Write the final base64 subscription and its metadata JSON."""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .config import Settings
from .models import Config
from .parsers import set_fragment

log = logging.getLogger(__name__)


def _encode_configs(configs: list[Config]) -> str:
    """Rewrite each URI's fragment to the display name, then base64-encode all."""
    uris = [set_fragment(c.uri, c.display_name()) for c in configs]
    payload = "\n".join(uris)
    return base64.b64encode(payload.encode("utf-8")).decode("ascii")


def country_output_path(output_file: str, country: str) -> Path:
    """Per-country filename derived from the main one: best.txt + DE -> best-DE.txt."""
    p = Path(output_file)
    # ``.with_stem`` keeps any parent dir and the original suffix (e.g. .txt).
    return p.with_name(f"{p.stem}-{country}{p.suffix}")


def write_subscription(configs: list[Config], settings: Settings) -> dict:
    """Write the base64 subscription + .meta.json (+ per-country files).

    Returns the metadata dict. The list of every file written this run (main,
    metadata, and any per-country files) is stored on ``meta["written_files"]``
    so the caller can hand them to the GitHub push step.
    """
    out_path = Path(settings.output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_encode_configs(configs), encoding="utf-8")
    log.info("Subscription written -> %s (%d configs)", out_path, len(configs))

    meta = build_metadata(configs, settings)
    meta_path = Path(settings.metadata_file)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Metadata written -> %s", meta_path)

    written = [str(out_path), str(meta_path)]
    if settings.per_country_output:
        written += write_per_country(configs, settings)
    meta["written_files"] = written
    return meta


def write_per_country(configs: list[Config], settings: Settings) -> list[str]:
    """Write one base64 file per country, preserving allow-list order.

    A country's file holds exactly that country's configs (already the best N,
    since selection ran upstream). Returns the paths written.
    """
    by_country: dict[str, list[Config]] = {}
    for c in configs:
        by_country.setdefault(c.country or "XX", []).append(c)

    # Order countries by the allow-list, then any extras alphabetically.
    ordered = [cc for cc in settings.allowed_countries if cc in by_country]
    ordered += sorted(cc for cc in by_country if cc not in settings.allowed_countries)

    written: list[str] = []
    for cc in ordered:
        path = country_output_path(settings.output_file, cc)
        path.write_text(_encode_configs(by_country[cc]), encoding="utf-8")
        written.append(str(path))
        log.info("Country subscription written -> %s (%d configs)", path, len(by_country[cc]))
    return written


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
        "version": __version__,
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
                "index": c.index,
                "protocol": c.protocol,
                "country": c.country,
                "country_name": c.country_name,
                "flag": c.flag_emoji(),
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
