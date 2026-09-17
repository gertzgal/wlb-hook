"""Unit tests for the pure Gate logic."""
import json
from datetime import datetime, timedelta

from wlb_hook import core

NOW = datetime(2026, 9, 17, 19, 30).astimezone()


def hist(*whens, project="/Users/x/proj"):
    return [json.dumps({"timestamp": int(w.timestamp() * 1000), "project": project})
            for w in whens]


def test_first_prompt_today_picks_earliest_today_and_skips_probe_and_yesterday():
    lines = hist(NOW - timedelta(hours=9), NOW - timedelta(hours=2), NOW - timedelta(days=1))
    lines += hist(NOW - timedelta(hours=12), project="/x/CodexBar/ClaudeProbe")
    lines += ["garbage", ""]
    assert core.first_prompt_today(lines, NOW) == NOW - timedelta(hours=9)


def test_no_prompts_today_means_zero_hours():
    assert core.first_prompt_today(hist(NOW - timedelta(days=1)), NOW) is None
    assert core.worked_hours(None, NOW) == 0.0


def test_should_gate_only_when_over_budget_and_not_unlocked():
    assert core.should_gate(9.5, 9, unlocked=False)
    assert not core.should_gate(8.9, 9, unlocked=False)
    assert not core.should_gate(12, 9, unlocked=True)


def test_workaholic_event_unlocks_day():
    assert core.is_unlocked([{"kind": "gate"}, {"kind": "workaholic"}])
    assert not core.is_unlocked([{"kind": "gate"}, {"kind": "one_last"}])


def test_outcomes():
    assert core.outcome("stop", None, 9.5, 9)["decision"] == "block"
    assert core.outcome("timeout", None, 9.5, 9)["decision"] == "block"
    assert "decision" not in core.outcome("one_last", None, 9.5, 9)
    wk = core.outcome("workaholic", "deploy friday", 9.5, 9)
    assert "decision" not in wk and "deploy friday" in wk["systemMessage"]


def test_fmt_hours():
    assert core.fmt_hours(9.5) == "9h 30m"
    assert core.fmt_hours(0.25) == "15m"
