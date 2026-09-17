"""End-to-end: pipe fixture JSON into the real entry script with WLB_* overrides."""
import json
import os
import subprocess
import sys

from conftest import FIXTURES, ROOT

HOOK = ROOT / "hooks" / "user_prompt_submit.py"
PAYLOAD = (FIXTURES / "UserPromptSubmit" / "plain.json").read_text()


def run_hook(tmp_path, stdin=PAYLOAD, **env):
    base = {
        "WLB_EVENTS_FILE": str(tmp_path / "events.jsonl"),
        "WLB_HISTORY_FILE": str(tmp_path / "missing-history.jsonl"),
        "WLB_CONFIG_FILE": str(tmp_path / "missing-config.json"),
        "WLB_NOW": "2026-09-17T19:00:00",
    }
    proc = subprocess.run(
        [sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True, timeout=10,
        check=False, env={**os.environ, **base, **env},
    )
    assert proc.returncode == 0, proc.stderr
    return proc


def events(tmp_path):
    p = tmp_path / "events.jsonl"
    return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []


def test_no_history_is_silent(tmp_path):
    assert run_hook(tmp_path).stdout.strip() == ""
    assert events(tmp_path) == []


def test_under_budget_is_silent(tmp_path):
    proc = run_hook(tmp_path, WLB_FIRST_PROMPT_AT="2026-09-17T11:00:00")
    assert proc.stdout.strip() == ""


def test_over_budget_stop_blocks_and_logs(tmp_path):
    proc = run_hook(tmp_path, WLB_FIRST_PROMPT_AT="2026-09-17T09:00:00", WLB_DIALOG_RESULT="stop")
    out = json.loads(proc.stdout)
    assert out["decision"] == "block" and "10h 00m" in out["reason"]
    assert [e["kind"] for e in events(tmp_path)] == ["gate", "stop"]


def test_stop_hard_blocks_rest_of_day_without_dialog(tmp_path):
    env = dict(WLB_FIRST_PROMPT_AT="2026-09-17T09:00:00")
    run_hook(tmp_path, WLB_DIALOG_RESULT="stop", **env)
    again = run_hook(tmp_path, WLB_DIALOG_RESULT="workaholic:should not be asked", **env)
    assert "stopped for the day" in json.loads(again.stdout)["reason"]
    assert [e["kind"] for e in events(tmp_path)] == ["gate", "stop"]


def test_budget_precedence_config_beats_plugin_option(tmp_path):
    (tmp_path / "config.json").write_text('{"max_hours": 2}')
    env = dict(WLB_FIRST_PROMPT_AT="2026-09-17T16:00:00", WLB_CONFIG_FILE=str(tmp_path / "config.json"),
               WLB_DIALOG_RESULT="stop")
    assert json.loads(run_hook(tmp_path, CLAUDE_PLUGIN_OPTION_MAX_HOURS="12", **env).stdout)["decision"] == "block"
    assert run_hook(tmp_path / "x", CLAUDE_PLUGIN_OPTION_MAX_HOURS="12",
                    WLB_FIRST_PROMPT_AT="2026-09-17T16:00:00").stdout.strip() == ""


def test_wlb_command_sets_budget_and_reports_status(tmp_path):
    env = {**os.environ, "WLB_CONFIG_FILE": str(tmp_path / "config.json"),
           "WLB_EVENTS_FILE": str(tmp_path / "events.jsonl"), "WLB_HISTORY_FILE": str(tmp_path / "none"),
           "WLB_FIRST_PROMPT_AT": "2026-09-17T09:00:00", "WLB_NOW": "2026-09-17T12:00:00"}
    script = str(ROOT / "scripts" / "wlb.py")
    out = subprocess.run([sys.executable, script, "set", "7.5"], capture_output=True, text=True,
                         env=env, check=True).stdout
    assert "7h 30m" in out and json.loads((tmp_path / "config.json").read_text())["max_hours"] == 7.5
    status = subprocess.run([sys.executable, script], capture_output=True, text=True, env=env,
                            check=True).stdout
    assert "worked 3h 00m of 7h 30m" in status and "day state: open" in status


def test_config_budget_respected(tmp_path):
    (tmp_path / "config.json").write_text('{"max_hours": 2}')
    proc = run_hook(tmp_path, WLB_FIRST_PROMPT_AT="2026-09-17T16:00:00",
                    WLB_CONFIG_FILE=str(tmp_path / "config.json"), WLB_DIALOG_RESULT="stop")
    assert json.loads(proc.stdout)["decision"] == "block"


def test_one_last_allows_then_gates_again(tmp_path):
    env = dict(WLB_FIRST_PROMPT_AT="2026-09-17T09:00:00")
    first = run_hook(tmp_path, WLB_DIALOG_RESULT="one_last", **env)
    assert "decision" not in json.loads(first.stdout)
    second = run_hook(tmp_path, WLB_DIALOG_RESULT="stop", **env)
    assert json.loads(second.stdout)["decision"] == "block"
    assert [e["kind"] for e in events(tmp_path)] == ["gate", "one_last", "gate", "stop"]


def test_workaholic_unlocks_rest_of_day(tmp_path):
    env = dict(WLB_FIRST_PROMPT_AT="2026-09-17T09:00:00")
    first = run_hook(tmp_path, WLB_DIALOG_RESULT="workaholic:tests were almost green", **env)
    assert "almost green" in json.loads(first.stdout)["systemMessage"]
    second = run_hook(tmp_path, WLB_DIALOG_RESULT="stop", **env)
    assert second.stdout.strip() == ""
    kinds = [e["kind"] for e in events(tmp_path)]
    assert kinds == ["gate", "workaholic"]
    assert events(tmp_path)[1]["excuse"] == "tests were almost green"


def test_timeout_blocks_without_choice_event(tmp_path):
    proc = run_hook(tmp_path, WLB_FIRST_PROMPT_AT="2026-09-17T09:00:00",
                    WLB_DIALOG_RESULT="timeout")
    assert json.loads(proc.stdout)["decision"] == "block"
    assert [e["kind"] for e in events(tmp_path)] == ["gate"]


def test_malformed_stdin_fails_open(tmp_path):
    out = json.loads(run_hook(tmp_path, stdin="not json{").stdout)
    assert "systemMessage" in out and "decision" not in out


def test_hooks_json_references_existing_scripts():
    cfg = json.loads((ROOT / "hooks" / "hooks.json").read_text())
    for groups in cfg["hooks"].values():
        for group in groups:
            for handler in group["hooks"]:
                for arg in handler.get("args", []):
                    if "${CLAUDE_PLUGIN_ROOT}" in arg:
                        assert (ROOT / arg.replace("${CLAUDE_PLUGIN_ROOT}/", "")).is_file()
