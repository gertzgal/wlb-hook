#!/usr/bin/env python3
"""/wlb command backend: `wlb.py status` | `wlb.py set <hours>`. Writes ~/.claude/wlb-hook/config.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from wlb_hook import core, store


def status() -> str:
    now = store.now()
    first = store.first_prompt_override() or core.first_prompt_today(store.history_lines(), now)
    worked = core.worked_hours(first, now)
    budget = store.budget_hours()
    state = core.day_state(store.events_today(now.date().isoformat()))
    started = first.strftime("%H:%M") if first else "no prompts yet"
    return (f"wlb: started {started}, worked {core.fmt_hours(worked)} of {core.fmt_hours(budget)} "
            f"budget, day state: {state}. Config: {store.config_path()}")


def set_hours(raw: str) -> str:
    hours = float(raw)
    if not 0 < hours <= 24:
        raise ValueError("hours must be between 0 and 24")
    cfg = store.read_config()
    cfg["max_hours"] = hours
    store.write_config(cfg)
    return f"wlb: daily budget set to {core.fmt_hours(hours)} ({store.config_path()})"


def main(argv: list[str]) -> int:
    try:
        if len(argv) >= 2 and argv[0] == "set":
            print(set_hours(argv[1]))
        elif not argv or argv[0] == "status":
            print(status())
        else:
            print("usage: wlb.py [status | set <hours>]", file=sys.stderr)
            return 2
    except ValueError as exc:
        print(f"wlb: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
