"""File I/O: config, event log, history. Demo/test overrides via WLB_* env vars."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from wlb_hook.core import DEFAULT_BUDGET_HOURS

HOME = Path(os.environ.get("HOME", "~")).expanduser()
DATA_DIR = HOME / ".claude" / "wlb-hook"


def config_path() -> Path:
    return Path(os.environ.get("WLB_CONFIG_FILE", DATA_DIR / "config.json"))


def events_path() -> Path:
    return Path(os.environ.get("WLB_EVENTS_FILE", DATA_DIR / "events.jsonl"))


def history_path() -> Path:
    return Path(os.environ.get("WLB_HISTORY_FILE", HOME / ".claude" / "history.jsonl"))


def now() -> datetime:
    override = os.environ.get("WLB_NOW")
    dt = datetime.fromisoformat(override) if override else datetime.now()
    return dt.astimezone()


def budget_hours() -> float:
    if "WLB_MAX_HOURS" in os.environ:
        return float(os.environ["WLB_MAX_HOURS"])
    try:
        return float(json.loads(config_path().read_text()).get("max_hours", DEFAULT_BUDGET_HOURS))
    except (OSError, ValueError, AttributeError):
        return DEFAULT_BUDGET_HOURS


def first_prompt_override() -> datetime | None:
    v = os.environ.get("WLB_FIRST_PROMPT_AT")
    return datetime.fromisoformat(v).astimezone() if v else None


def history_lines() -> list[str]:
    try:
        return history_path().read_text().splitlines()
    except OSError:
        return []


def events_today(today: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        lines = events_path().read_text().splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("date") == today:
            out.append(rec)
    return out


def append_event(event: dict[str, Any]) -> None:
    path = events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(event) + "\n")
