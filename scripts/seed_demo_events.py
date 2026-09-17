#!/usr/bin/env python3
"""Seed a deterministic demo ``events.jsonl`` for the work-life-balance hook.

Usage:
    python3 scripts/seed_demo_events.py <out_path> [--weeks 6] [--seed 42] [--end YYYY-MM-DD]

One JSON object per line. Event shape (shared with the hook):

    {"ts": "<ISO-8601 local time with offset>", "date": "YYYY-MM-DD",
     "kind": "gate" | "stop" | "one_last" | "workaholic",
     "worked_hours": <float, 1dp>, "budget_hours": 9,
     "excuse": "<str, workaholic only>", "session_id": "<uuid4>", "cwd": "<str>"}

Semantics:
  * A ``gate`` event is written every time the hook intercepts a prompt because
    worked_hours > budget_hours. It is always followed by exactly one of
    ``stop`` / ``one_last`` / ``workaholic`` with the same ``ts`` + ``session_id``.
  * Workaholic day: one gate+workaholic pair, then nothing more.
  * Stop day: 1-3 gate+stop pairs a few minutes apart.
  * One-last day: gate+one_last, then ~5 min later gate+stop or gate+workaholic.
  * Weekdays only. ~70% of weekdays are normal (no events); the rest split
    ~40% stop / ~30% one_last / ~30% workaholic.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys
import uuid
from pathlib import Path

BUDGET_HOURS = 9

PROJECTS = [
    "/Users/demo/Projects/invoice-ninja-clone",
    "/Users/demo/Projects/side-hustle-api",
    "/Users/demo/Projects/dotfiles",
    "/Users/demo/Projects/llm-playground",
    "/Users/demo/Projects/kubernetes-but-worse",
]

EXCUSES = [
    "It's deploy Friday and someone has to watch the dashboards.",
    "The tests were almost green. Almost.",
    "Just one more rebase, I promise.",
    "The CI runner is slow; I'm basically waiting, not working.",
    "If I stop now I'll lose the entire mental model of this bug.",
    "Prod is fine. Prod is probably fine. Let me just check prod.",
    "I only need to rename one variable. Across 47 files.",
    "The standup is in 12 hours and I have nothing to say yet.",
    "This isn't work, this is a hobby that happens to be my job.",
    "My rubber duck told me to keep going.",
    "Flaky test. Definitely flaky. Re-running it a ninth time.",
    "I'll sleep when the linter is happy.",
    "The PR has 1 unresolved comment and it's haunting me.",
    "Docker is building; closing the laptop now would be rude.",
    "I opened the file, so legally I have to finish the refactor.",
    "The bug only reproduces after 8pm. Science demands I stay.",
    "I'm not overworking, I'm pair programming with the future me.",
    "Someone force-pushed to main and now it's personal.",
    "Just going to add one tiny feature flag. What's the worst that can happen?",
    "The coffee is still warm. That's a sign.",
]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("out_path", type=Path, help="Where to write events.jsonl")
    parser.add_argument("--weeks", type=int, default=6, help="Number of weeks to generate (default 6)")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default 42)")
    parser.add_argument(
        "--end",
        type=dt.date.fromisoformat,
        default=None,
        help="Last calendar day to generate, YYYY-MM-DD (default: today)",
    )
    args = parser.parse_args(argv)
    if args.weeks < 1:
        parser.error("--weeks must be >= 1")
    return args


def local_tz() -> dt.tzinfo:
    tz = dt.datetime.now().astimezone().tzinfo
    return tz if tz is not None else dt.timezone.utc


def iso_local(d: dt.date, t: dt.time, tz: dt.tzinfo) -> str:
    return dt.datetime.combine(d, t).replace(tzinfo=tz).isoformat(timespec="seconds")


def make_event(
    *,
    when: dt.datetime,
    kind: str,
    worked_hours: float,
    session_id: str,
    cwd: str,
    excuse: str | None = None,
) -> dict:
    event = {
        "ts": when.isoformat(timespec="seconds"),
        "date": when.date().isoformat(),
        "kind": kind,
        "worked_hours": round(worked_hours, 1),
        "budget_hours": BUDGET_HOURS,
    }
    if kind == "workaholic":
        event["excuse"] = excuse
    event["session_id"] = session_id
    event["cwd"] = cwd
    return event


def pair(when, kind, worked_hours, session_id, cwd, excuse=None) -> list[dict]:
    """A gate event followed by its outcome, sharing ts and session_id."""
    common = dict(when=when, worked_hours=worked_hours, session_id=session_id, cwd=cwd)
    return [
        make_event(kind="gate", **common),
        make_event(kind=kind, excuse=excuse, **common),
    ]


def day_events(rng: random.Random, day: dt.date, tz: dt.tzinfo) -> list[dict]:
    roll = rng.random()
    if roll < 0.70:
        return []
    # remaining 30% -> 40/30/30 split
    r = (roll - 0.70) / 0.30
    day_type = "stop" if r < 0.40 else "one_last" if r < 0.70 else "workaholic"

    # First over-budget prompt lands somewhere in the evening.
    start_minutes = rng.randint(17 * 60 + 15, 20 * 60 + 30)
    when = dt.datetime.combine(day, dt.time(0, 0)).replace(tzinfo=tz) + dt.timedelta(
        minutes=start_minutes, seconds=rng.randint(0, 59)
    )
    worked = BUDGET_HOURS + rng.uniform(0.1, 2.4)
    cwd = rng.choice(PROJECTS)
    session_id = str(uuid.UUID(int=rng.getrandbits(128), version=4))

    events: list[dict] = []

    if day_type == "workaholic":
        events += pair(when, "workaholic", worked, session_id, cwd, excuse=rng.choice(EXCUSES))
        return events

    if day_type == "stop":
        for i in range(rng.randint(1, 3)):
            if i > 0:
                gap = rng.randint(2, 8)
                when += dt.timedelta(minutes=gap, seconds=rng.randint(0, 59))
                worked += gap / 60
            events += pair(when, "stop", worked, session_id, cwd)
        return events

    # one_last
    events += pair(when, "one_last", worked, session_id, cwd)
    gap = rng.randint(4, 7)
    when += dt.timedelta(minutes=gap, seconds=rng.randint(0, 59))
    worked += gap / 60
    if rng.random() < 0.6:
        events += pair(when, "stop", worked, session_id, cwd)
    else:
        events += pair(when, "workaholic", worked, session_id, cwd, excuse=rng.choice(EXCUSES))
    return events


def generate(weeks: int, seed: int, end: dt.date) -> list[dict]:
    rng = random.Random(seed)
    tz = local_tz()
    start = end - dt.timedelta(days=weeks * 7 - 1)
    events: list[dict] = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            events += day_events(rng, day, tz)
        day += dt.timedelta(days=1)
    return events


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    end = args.end or dt.date.today()
    events = generate(args.weeks, args.seed, end)
    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    with args.out_path.open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(f"wrote {len(events)} events to {args.out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
