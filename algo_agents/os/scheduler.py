"""AGENTIC-OS daily schedule helpers (stdlib only)."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from algo_agents.config import Settings
from algo_agents.os.artifacts import read_scheduler_state, write_scheduler_state

_WEEKDAY_MAP = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


def parse_weekdays(spec: str) -> set[int]:
    text = spec.strip().lower()
    if text in ("*", "all", "daily"):
        return set(range(7))
    if text in ("mon-fri", "weekdays"):
        return {0, 1, 2, 3, 4}
    days: set[int] = set()
    for part in text.split(","):
        token = part.strip()
        if not token:
            continue
        if token in _WEEKDAY_MAP:
            days.add(_WEEKDAY_MAP[token])
    return days or {0, 1, 2, 3, 4}


def is_scheduled_now(settings: Settings, now: datetime | None = None) -> bool:
    if not settings.agentic_schedule_enabled:
        return False
    tz = ZoneInfo(settings.agentic_schedule_tz)
    current = now.astimezone(tz) if now else datetime.now(tz)
    if current.weekday() not in parse_weekdays(settings.agentic_schedule_weekdays):
        return False
    return (
        current.hour == settings.agentic_schedule_hour
        and current.minute == settings.agentic_schedule_minute
    )


def should_run_daily(settings: Settings, now: datetime | None = None) -> bool:
    if not is_scheduled_now(settings, now):
        return False
    tz = ZoneInfo(settings.agentic_schedule_tz)
    current = now.astimezone(tz) if now else datetime.now(tz)
    day_key = current.date().isoformat()
    state = read_scheduler_state() or {}
    if state.get("last_daily_date") == day_key:
        return False
    return True


def mark_daily_ran(settings: Settings, now: datetime | None = None) -> None:
    tz = ZoneInfo(settings.agentic_schedule_tz)
    current = now.astimezone(tz) if now else datetime.now(tz)
    write_scheduler_state({"last_daily_date": current.date().isoformat()})
