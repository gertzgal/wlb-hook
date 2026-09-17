"""Unit tests for the pure decision logic (no subprocess, no I/O)."""
from wlb_hook import core


def test_safe_bash_is_silent(fixture):
    assert core.pre_tool_use(fixture("PreToolUse", "bash-safe")) is None


def test_rm_root_is_denied(fixture):
    out = core.pre_tool_use(fixture("PreToolUse", "bash-rm-root"))
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == "deny"
    assert "recursive delete" in hso["permissionDecisionReason"]


def test_force_push_is_denied(fixture):
    out = core.pre_tool_use(fixture("PreToolUse", "bash-force-push"))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_non_bash_tool_is_ignored():
    assert core.pre_tool_use({"tool_name": "Edit", "tool_input": {"command": "rm -rf /"}}) is None


def test_prompt_mentioning_wlb_gets_context(fixture):
    out = core.user_prompt_submit(fixture("UserPromptSubmit", "mentions-wlb"))
    assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "additionalContext" in out["hookSpecificOutput"]


def test_plain_prompt_is_silent(fixture):
    assert core.user_prompt_submit(fixture("UserPromptSubmit", "plain")) is None
