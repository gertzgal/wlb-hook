"""stdin -> core -> stdout adapter shared by every hook entry point.

Policy (mirrors Anthropic's hookify plugin): never crash the user's session.
Internal errors exit 0 with a systemMessage instead of a blocking exit 2.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any

Decider = Callable[[dict[str, Any]], dict[str, Any] | None]


def run(decide: Decider, stdin=None, stdout=None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    try:
        raw = stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        result = decide(payload)
    except Exception as exc:  # fail open by design
        result = {"systemMessage": f"wlb-hook internal error: {type(exc).__name__}: {exc}"}
    if result is not None:
        stdout.write(json.dumps(result))
        stdout.write("\n")
    return 0
