"""Data model for a single proxy config under test."""

from __future__ import annotations

from dataclasses import dataclass, field

# Offset from ASCII 'A' to the Unicode "Regional Indicator Symbol" block. Two of
# these letters in a row are what terminals and phones render as a flag emoji.
_REGIONAL_INDICATOR_A = 0x1F1E6


def flag_from_country_code(cc: str) -> str:
    """Build a flag emoji from a 2-letter ISO country code (``"DE"`` -> 🇩🇪).

    Returns ``""`` for anything that is not a plausible country code, so callers
    can safely use ``config_flag or flag_from_country_code(cc)`` as a fallback.
    """
    if not cc or len(cc) != 2 or not cc.isalpha():
        return ""
    return "".join(chr(_REGIONAL_INDICATOR_A + ord(ch) - ord("A")) for ch in cc.upper())


@dataclass
class Config:
    uri: str
    name: str = ""
    protocol: str = "unknown"
    server: str = ""
    port: int = 0
    latencies: list[float] = field(default_factory=list)
    errors: int = 0
    total: int = 0
    country: str = ""
    country_name: str = ""
    flag: str = ""
    index: int = 0  # global output number (1-based), set before publishing
    target_stats: dict[str, dict[str, int]] = field(default_factory=dict)

    # -- Stealth / ISP-resilience fields ------------------------------------
    # Populated by ``parsers.extract_stealth_info`` right after parsing.
    transport: str = ""  # ws, grpc, h2, tcp, httpupgrade, splithttp
    security: str = ""  # tls, reality, none
    fingerprint: str = ""  # uTLS fingerprint (chrome, firefox, …)
    stealth_score: float = 0.0  # 0.0 (easily blocked) – 1.0 (very stealthy)

    def record(self, label: str, ok: bool) -> None:
        """Record one probe result against a named test target."""
        stats = self.target_stats.setdefault(label, {"ok": 0, "fail": 0})
        stats["ok" if ok else "fail"] += 1

    def weighted_error_rate(self, weights: dict[str, float]) -> float:
        """Error rate where each target contributes its configured weight."""
        total_w = 0.0
        fail_w = 0.0
        for label, stats in self.target_stats.items():
            w = weights.get(label, 1.0)
            total_w += w * (stats["ok"] + stats["fail"])
            fail_w += w * stats["fail"]
        return fail_w / total_w if total_w else 1.0

    @property
    def avg_latency(self) -> float:
        return sum(self.latencies) / len(self.latencies) if self.latencies else float("inf")

    @property
    def error_rate(self) -> float:
        return self.errors / self.total if self.total else 1.0

    @property
    def p50(self) -> float:
        return self._percentile(50)

    @property
    def p95(self) -> float:
        return self._percentile(95)

    def _percentile(self, q: float) -> float:
        if not self.latencies:
            return float("inf")
        ordered = sorted(self.latencies)
        k = (len(ordered) - 1) * q / 100.0
        lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)

    def flag_emoji(self) -> str:
        """Flag for this config: the explicit one, else derived from the code."""
        return self.flag or flag_from_country_code(self.country)

    def display_name(self) -> str:
        flag = self.flag_emoji()
        if self.index:
            flag_part = f"{flag} " if flag else ""
            return f"{flag_part}{self.country_name or self.country} | {self.index:02d}"
        if flag:
            return f"{self.country_name or self.country} {flag}".strip()
        return self.name or self.uri[:50]
