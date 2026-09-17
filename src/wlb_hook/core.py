"""Pure decision functions. Input: parsed hook stdin dict. Output: stdout JSON dict (or None).

Keep this module free of I/O so it can be unit-tested directly.
Contract: https://code.claude.com/docs/en/hooks#json-output
"""
from __future__ import annotations

import re
from typing import Any

# Example policy: deny obviously destructive shell commands.
DENY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\s+/(\s|$)", "recursive delete of /"),
    (r"\bgit\s+push\b.*(--force\b|\s-f\b)", "force push"),
)


def pre_tool_use(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return a PreToolUse decision, or None to stay silent (allow by default)."""
    if payload.get("tool_name") != "Bash":
        return None
    command = str(payload.get("tool_input", {}).get("command", ""))
    for pattern, label in DENY_PATTERNS:
        if re.search(pattern, command):
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"wlb-hook: blocked {label}: {command!r}",
                }
            }
    return None


def user_prompt_submit(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Example: inject context when the prompt mentions a keyword."""
    prompt = str(payload.get("prompt", ""))
    if "wlb" in prompt.lower():
        return {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "wlb-hook is active in this session.",
            }
        }
    return None
