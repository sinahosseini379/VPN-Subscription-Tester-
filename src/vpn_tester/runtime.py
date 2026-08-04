"""Shared runtime state between the pipeline, scheduler and web dashboard.

Everything here is event-loop-safe by construction (single asyncio loop, no
`await` inside the state mutations), so no locks are needed.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import logging
import time
from collections import deque
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

STAGE_DOWNLOAD = "downloading"
STAGE_TCP = "tcp-ping"
STAGE_STEALTH = "stealth-filter"
STAGE_COUNTRY = "country-check"
STAGE_URL_TESTS = "url-tests"
STAGE_FINALIZE = "finalizing"
STAGE_PUSH = "pushing"


def seconds_until_next_run(
    schedule_time: str,
    now: datetime.datetime | None = None,
    tz_name: str = "Asia/Tehran",
) -> float:
    """Seconds until the next occurrence of HH:MM in the given timezone.

    `now` defaults to the current UTC instant; a naive `now` is treated as
    UTC. Raises ValueError for malformed times or unknown timezones. If the
    time already passed in that timezone, the target is the same time tomorrow.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        raise ValueError(f"Unknown timezone {tz_name!r}") from None

    try:
        hour, minute = (int(p) for p in schedule_time.split(":", 1))
    except (ValueError, TypeError):
        raise ValueError(f"Invalid SCHEDULE_TIME {schedule_time!r}: expected 'HH:MM'") from None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid SCHEDULE_TIME {schedule_time!r}: hour 0-23, minute 0-59")

    now_tz = now.astimezone(tz)
    target = now_tz.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now_tz:
        target = (target + datetime.timedelta(days=1)).astimezone(tz)
    return (target - now_tz).total_seconds()


class Reporter:
    """In-process progress + log buffer for the dashboard."""

    def __init__(self, max_logs: int = 1000):
        self.status = "idle"  # idle | running | done | failed
        self.stage = ""
        self.message = ""
        self.progress = 0.0
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.last_meta: dict | None = None
        self._log_seq = 0
        self._logs: deque[tuple[int, str]] = deque(maxlen=max_logs)

    # -- lifecycle -----------------------------------------------------------
    def begin_run(self, message: str = "") -> None:
        self.status = "running"
        self.stage = "starting"
        self.message = message or "Starting…"
        self.progress = 0.0
        self.started_at = time.time()
        self.finished_at = None
        self.last_meta = None
        self.log(f"[run] {message or 'starting'}")

    def set_stage(self, stage: str, message: str = "") -> None:
        self.stage = stage
        if message:
            self.message = message
            self.log(f"[{stage}] {message}")

    def set_progress(self, stage: str, current: int, total: int, lo: float, hi: float) -> None:
        """Advance progress inside a stage, mapping current/total onto [lo, hi]."""
        frac = (current / total) if total else 1.0
        self.stage = stage
        self.progress = lo + (hi - lo) * min(1.0, max(0.0, frac))
        self.message = f"{stage}: {current}/{total}"

    def finish(self, ok: bool, meta: dict | None = None) -> None:
        self.status = "done" if ok else "failed"
        self.finished_at = time.time()
        self.progress = 1.0
        if meta is not None:
            self.last_meta = meta
        self.log(f"[run] finished ({self.status})")

    # -- logs ----------------------------------------------------------------
    def log(self, line: str) -> None:
        self._log_seq += 1
        self._logs.append((self._log_seq, line))

    def logs_after(self, after: int) -> tuple[int, list[str]]:
        """Return (newest_seq, lines) for entries strictly newer than `after`."""
        lines = [line for seq, line in self._logs if seq > after]
        return self._log_seq, lines

    def snapshot(self) -> dict:
        return {
            "status": self.status,
            "stage": self.stage,
            "message": self.message,
            "progress": round(self.progress, 4),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "log_seq": self._log_seq,
        }


class LogCapture(logging.Handler):
    """Mirrors every log record into the shared reporter."""

    def __init__(self, reporter: Reporter):
        super().__init__(level=logging.DEBUG)
        self._reporter = reporter

    def emit(self, record: logging.LogRecord) -> None:
        with contextlib.suppress(Exception):
            self._reporter.log(record.getMessage())


class RunCoordinator:
    """Single-flight runs + scheduler wakeups, driven from the dashboard."""

    def __init__(self, settings: Any, run_once_fn: Callable[..., Any]):
        self.settings = settings
        self._run_once = run_once_fn
        self._task: asyncio.Task | None = None
        self.schedule_changed = asyncio.Event()

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def request_schedule_change(self) -> None:
        self.schedule_changed.set()

    def trigger_run(self, *, do_push: bool = True) -> bool:
        """Start a manual run in the background. Returns False if one is active."""
        if self.is_running():
            return False
        self._task = asyncio.create_task(self._run_once(self.settings, do_push=do_push))
        return True


reporter = Reporter()
