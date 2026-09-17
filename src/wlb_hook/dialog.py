"""Native macOS dialog via osascript. Returns (choice, excuse)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("wlb_dialog.applescript")
GIVE_UP = 20  # AppleScript timeout; hook cap on UserPromptSubmit is 30 s
HARD_CAP = 27


def ask(fact: str) -> tuple[str, str | None]:
    """choice in {"stop", "one_last", "workaholic", "timeout"}."""
    fake = os.environ.get("WLB_DIALOG_RESULT")  # tests / CI: skip the real dialog
    if fake:
        choice, _, excuse = fake.partition(":")
        return choice, (excuse or None)
    try:
        p = subprocess.run(
            ["osascript", str(SCRIPT), fact, str(GIVE_UP)],
            capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=HARD_CAP, check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "timeout", None
    if p.returncode != 0:
        if "-128" in p.stderr:  # cancel button / Esc == Stop
            return "stop", None
        print(f"wlb-hook: osascript failed: {p.stderr.strip()}", file=sys.stderr)
        return "timeout", None
    out = p.stdout.rstrip("\n")
    if out == "Stop":
        return "stop", None
    if out == "One last prompt":
        return "one_last", None
    if out.startswith("Workaholic\t"):
        return "workaholic", out.split("\t", 1)[1].strip() or None
    return "timeout", None
