"""Pure decision logic for the work-life-balance Gate. No I/O here.

Terms (see CONTEXT.md): Workday, Budget, Gate, Choice (stop | one_last | workaholic), Excuse.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

DEFAULT_BUDGET_HOURS = 9.0
PROBE_MARKER = "ClaudeProbe"  # CodexBar's /usage probe also writes to history.jsonl

Choice = str  # "stop" | "one_last" | "workaholic" | "timeout"


def first_prompt_today(history_lines: list[str], now: datetime) -> datetime | None:
    """Earliest human CLI prompt on `now`'s local calendar day (~/.claude/history.jsonl lines)."""
    today = now.date()
    tz = now.tzinfo
    earliest: datetime | None = None
    for raw in history_lines:
        line = raw.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if PROBE_MARKER in str(rec.get("project", "")):
            continue
        ts = rec.get("timestamp")
        if not isinstance(ts, (int, float)):
            continue
        when = datetime.fromtimestamp(ts / 1000, tz=tz)
        if when.date() != today:
            continue
        if earliest is None or when < earliest:
            earliest = when
    return earliest


def worked_hours(first_prompt: datetime | None, now: datetime) -> float:
    if first_prompt is None:
        return 0.0
    return max(0.0, (now - first_prompt).total_seconds() / 3600)


def is_unlocked(events_today: list[dict[str, Any]]) -> bool:
    """Workaholic mode: any workaholic Choice today unlocks the rest of the Workday."""
    return any(e.get("kind") == "workaholic" for e in events_today)


def should_gate(worked: float, budget: float, unlocked: bool) -> bool:
    return not unlocked and worked > budget


def fmt_hours(hours: float) -> str:
    h, m = int(hours), round((hours % 1) * 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def gate_fact(worked: float, budget: float) -> str:
    return (
        f"You've been working for {fmt_hours(worked)} today. "
        f"Your budget is {fmt_hours(budget)}.\n\nYou are overworking. What now?"
    )


def outcome(choice: Choice, excuse: str | None, worked: float, budget: float) -> dict[str, Any]:
    """Hook JSON for a Choice made at the Gate."""
    over = fmt_hours(worked - budget)
    if choice == "one_last":
        return {
            "systemMessage": f"wlb-hook: one last prompt granted ({over} over budget). "
            "The next one will be gated again.",
        }
    if choice == "workaholic":
        return {
            "systemMessage": f"wlb-hook: workaholic mode until midnight. Excuse on record: "
            f"“{excuse}”",
        }
    if choice == "stop":
        return {
            "decision": "block",
            "reason": f"wlb-hook: you chose to stop after {fmt_hours(worked)}. Prompt dropped. "
            "Close the laptop.",
        }
    return {
        "decision": "block",
        "reason": "wlb-hook: no answer at the overwork dialog. Prompt dropped; "
        "resend it to choose again.",
    }
