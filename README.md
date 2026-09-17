# wlb-hook

Claude Code hook plugin boilerplate. Layout follows Anthropic's shipped hook plugins
(`hookify`, `security-guidance`) and the plugins reference; see
[docs/research/claude-code-hooks-boilerplate.md](docs/research/claude-code-hooks-boilerplate.md)
for the cited research.

```
.claude-plugin/plugin.json   manifest
hooks/hooks.json             event -> matcher -> command (exec form, ${CLAUDE_PLUGIN_ROOT})
hooks/<event>.py             thin entry points: stdin -> core -> stdout
src/wlb_hook/core.py         pure decision logic, no I/O (unit-tested directly)
src/wlb_hook/shim.py         JSON adapter; fails open with a systemMessage on internal error
tests/fixtures/<Event>/      one stdin payload per scenario
tests/test_core.py           unit tests
tests/test_hooks_e2e.py      subprocess tests: fixture -> script, assert exit code + JSON
```

## Develop

```bash
make test        # pytest (unit + e2e)
make validate    # claude plugin validate . --strict
make smoke       # pipe a fixture through a hook by hand
make dev         # claude --plugin-dir . --debug-file /tmp/wlb-hook-debug.log
```

Inside the dev session run `/hooks` to confirm registration, `Ctrl+O` to see hook stderr in
the transcript, and `grep -i hook /tmp/wlb-hook-debug.log` for stdout that is otherwise hidden.

## Contract cheatsheet

- Exit `0` with JSON on stdout to decide. Exit `2` blocks unconditionally. Exit `1` does **not**
  block, and a missing script fails open. Timed-out `PreToolUse` hooks let the tool run.
- `PreToolUse` decides via `hookSpecificOutput.permissionDecision` (`allow|deny|ask|defer`).
  `PostToolUse`, `Stop`, `UserPromptSubmit` use top-level `decision: "block"` + `reason`.
- `hookSpecificOutput.hookEventName` is required. `suppressOutput` is a documented no-op.
- Default command timeout is 600 s. Set `timeout` explicitly (this repo uses 5 to 10 s).

## Add a hook

1. Add a decider `def <event>(payload) -> dict | None` in `src/wlb_hook/core.py`.
2. Copy `hooks/pre_tool_use.py` to `hooks/<event>.py`, point it at the new decider.
3. Register it in `hooks/hooks.json`. Add fixtures under `tests/fixtures/<Event>/` and tests.
4. `make check`.
