# wlb-hook

A Claude Code plugin that guards your work-life balance. Once today's work passes your daily
budget (default 9 hours, counted from your first CLI prompt of the day), every prompt is gated by
a native macOS dialog:

- **Stop**: the prompt is dropped. Next prompt gates again.
- **One last prompt**: this prompt runs, the next one gates again.
- **Workaholic**: unlocked until midnight, but you must type an excuse. It goes on your record.

Every gate and choice is appended to `~/.claude/wlb-hook/events.jsonl`, the data a calendar view
of your overwork will read later.

## Install / run

```bash
claude --plugin-dir /path/to/wlb-hook       # load for one session
```

## Configure

`~/.claude/wlb-hook/config.json`:

```json
{ "max_hours": 8 }
```

## Demo (no 9-hour day required)

```bash
make demo    # Claude Code with a fake first prompt 10 hours ago; events go to /tmp
make smoke   # fire the dialog once from the shell, no Claude session needed
make seed    # 6 weeks of fake events for the future calendar -> /tmp/wlb-demo-events.jsonl
```

Overrides read by the hook: `WLB_FIRST_PROMPT_AT` (ISO local time), `WLB_NOW`, `WLB_MAX_HOURS`,
`WLB_EVENTS_FILE`, `WLB_HISTORY_FILE`, `WLB_CONFIG_FILE`, `WLB_DIALOG_RESULT` (tests only:
`stop` | `one_last` | `workaholic:<excuse>` | `timeout`).

## Event log shape

```json
{"ts": "2026-09-17T19:27:34+03:00", "date": "2026-09-17", "kind": "workaholic",
 "worked_hours": 10.0, "budget_hours": 9, "excuse": "the tests were almost green",
 "session_id": "…", "cwd": "/Users/me/Projects/x"}
```

`kind` is `gate` (dialog shown) followed by one of `stop` | `one_last` | `workaholic` with the same
`ts` and `session_id`. A timeout leaves a lone `gate`.

## How it works

```
hooks/hooks.json                UserPromptSubmit -> python3 hooks/user_prompt_submit.py (timeout 28 s)
src/wlb_hook/gate.py            I/O orchestration: Workday -> gate? -> dialog -> log -> hook JSON
src/wlb_hook/core.py            pure logic (first prompt today, budget check, outcome JSON)
src/wlb_hook/store.py           config, event log, history.jsonl, WLB_* overrides
src/wlb_hook/dialog.py          osascript wrapper; wlb_dialog.applescript is the dialog itself
scripts/seed_demo_events.py     demo data generator
```

Workday = first human prompt today in `~/.claude/history.jsonl` (CodexBar probes excluded) to now,
local calendar day. Blocking uses `{"decision": "block", "reason"}`; allowing uses a
`systemMessage`. The hook fails open on internal errors. Glossary in `CONTEXT.md`.

## Develop

```bash
make check       # ruff + plugin validate + pytest
make dev         # claude --plugin-dir . with debug log at /tmp/wlb-hook-debug.log
```
