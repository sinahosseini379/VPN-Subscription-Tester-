#!/usr/bin/env python3
"""VPN Subscription Tester — professional edition.

Reasons this version is better than v1:
- Secure GitHub push via the Contents API (token never lands in a git URL or .git/config).
- Every knobby value is configurable via config.env / environment variables.
- Country check is also concurrency-limited (no process storm).
- Xray readiness is polled (no wasted fixed sleep); processes are cleaned up on exit.
- HTTP responses are validated (only 2xx/3xx count as success).
- Geo-IP lookup has multiple fallback providers + caching.
- Unsupported protocols are reported, not silently dropped.
- Full pytest + ruff coverage and a CI workflow.
- Containerized with healthcheck; logging rotates.
"""

__version__ = "2.1.0"
