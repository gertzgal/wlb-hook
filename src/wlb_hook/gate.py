"""UserPromptSubmit decider with I/O: compute Workday, gate if over Budget, record the Choice."""
from __future__ import annotations

from typing import Any

from wlb_hook import core, dialog, store


def user_prompt_submit(payload: dict[str, Any]) -> dict[str, Any] | None:
    now = store.now()
    today = now.date().isoformat()
    budget = store.budget_hours()
    first = store.first_prompt_override() or core.first_prompt_today(store.history_lines(), now)
    worked = core.worked_hours(first, now)
    events = store.events_today(today)
    if not core.should_gate(worked, budget, core.is_unlocked(events)):
        return None

    base = {
        "ts": now.isoformat(timespec="seconds"),
        "date": today,
        "worked_hours": round(worked, 1),
        "budget_hours": budget,
        "session_id": payload.get("session_id"),
        "cwd": payload.get("cwd"),
    }
    store.append_event({**base, "kind": "gate"})
    choice, excuse = dialog.ask(core.gate_fact(worked, budget))
    if choice in ("stop", "one_last", "workaholic"):
        event = {**base, "kind": choice}
        if choice == "workaholic":
            event["excuse"] = excuse or ""
        store.append_event(event)
    return core.outcome(choice, excuse, worked, budget)
