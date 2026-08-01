"""Data model for a single proxy config under test."""

from __future__ import annotations

from dataclasses import dataclass, field


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

    def display_name(self) -> str:
        if self.flag:
            return f"{self.country_name or self.country} {self.flag}".strip()
        return self.name or self.uri[:50]
