"""End-to-end: pipe fixture JSON into the real entry scripts, assert exit code + stdout JSON.

This is exactly what Claude Code does at runtime (exec form, python3 <script>).
"""
import json
import subprocess
import sys

import pytest

from conftest import FIXTURES, ROOT

HOOKS = ROOT / "hooks"


def run_hook(script: str, stdin: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOKS / script)],
        input=stdin, capture_output=True, text=True, timeout=10, check=False,
    )


@pytest.mark.parametrize("name,expect_decision", [
    ("bash-safe", None),
    ("bash-rm-root", "deny"),
    ("bash-force-push", "deny"),
])
def test_pre_tool_use_e2e(name, expect_decision):
    payload = (FIXTURES / "PreToolUse" / f"{name}.json").read_text()
    proc = run_hook("pre_tool_use.py", payload)
    assert proc.returncode == 0, proc.stderr
    if expect_decision is None:
        assert proc.stdout.strip() == ""
    else:
        out = json.loads(proc.stdout)
        assert out["hookSpecificOutput"]["permissionDecision"] == expect_decision


def test_user_prompt_submit_e2e():
    payload = (FIXTURES / "UserPromptSubmit" / "mentions-wlb.json").read_text()
    proc = run_hook("user_prompt_submit.py", payload)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"


def test_malformed_stdin_fails_open():
    proc = run_hook("pre_tool_use.py", "not json{")
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert "systemMessage" in out
    assert "hookSpecificOutput" not in out


def test_empty_stdin_is_silent():
    proc = run_hook("pre_tool_use.py", "")
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_hooks_json_references_existing_scripts():
    cfg = json.loads((HOOKS / "hooks.json").read_text())
    for groups in cfg["hooks"].values():
        for group in groups:
            for handler in group["hooks"]:
                assert handler["type"] == "command"
                assert "command" in handler
                for arg in handler.get("args", []):
                    if "${CLAUDE_PLUGIN_ROOT}" in arg:
                        path = ROOT / arg.replace("${CLAUDE_PLUGIN_ROOT}/", "")
                        assert path.is_file(), f"missing {path}"
