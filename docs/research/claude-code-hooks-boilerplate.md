# Claude Code hooks: project boilerplate research

Researched 2026-09-17 against the live docs at code.claude.com (the old `docs.anthropic.com/en/docs/claude-code/hooks*` URLs 301-redirect there; verified with curl) and against Anthropic's first-party repos. Local CLI at time of writing: Claude Code 2.1.274.

Legend: **[P]** primary (Anthropic docs / Anthropic repo), **[S]** secondary (community, structure ideas only), **UNVERIFIED** could not confirm from a primary source.

---

## TL;DR

**Recommendation:** build the hook as a *plugin* from day one (`.claude-plugin/plugin.json` + `hooks/hooks.json` + `scripts/`), keep the decision logic in a pure function that is separate from the stdin/stdout shim, test it with fixture JSON piped to stdin, and gate CI on `claude plugin validate --strict` plus the unit tests. Anthropic's own guidance is "start with standalone configuration in `.claude/` for quick iteration, then convert to a plugin when you're ready to share" [P: https://code.claude.com/docs/en/plugins]; if the goal is distribution, skipping straight to the plugin layout costs nothing because `claude --plugin-dir ./my-plugin` loads it without installation [P: https://code.claude.com/docs/en/plugins].

### Recommended directory tree

```text
wlb-hook/
├── .claude-plugin/
│   └── plugin.json              # {"name","version","description","author"}  [P plugins-reference]
├── hooks/
│   └── hooks.json               # {"description"?, "hooks": {Event: [{matcher, hooks:[handler]}]}}  [P plugins-reference]
├── scripts/                     # hook entry points, one per event; thin stdin->decision->stdout shims
│   ├── pre-tool-use.sh          # (or .py / .ts) -- referenced as "${CLAUDE_PLUGIN_ROOT}/scripts/..."
│   └── lib/                     # pure decision logic, no I/O (unit-tested directly)
├── tests/
│   ├── fixtures/                # one stdin JSON per event/scenario, e.g. PreToolUse.bash-rm.json
│   ├── expected/                # golden stdout JSON (optional)
│   ├── unit/                    # tests for scripts/lib
│   └── e2e/                     # pipe fixture -> script, assert exit code + stdout JSON
├── .claude/
│   └── settings.local.json      # optional: local dev wiring while iterating (gitignored)
├── README.md
├── CHANGELOG.md
└── LICENSE
```

The `hooks/`, `scripts/`, etc. directories must sit at the plugin root; only `plugin.json` goes inside `.claude-plugin/` [P: https://code.claude.com/docs/en/plugins]. Anthropic's own hook plugins follow exactly this shape: `hookify` (`.claude-plugin/plugin.json`, `hooks/hooks.json`, `hooks/*.py`, `core/`, `matchers/`, `utils/`, `examples/`) and `security-guidance` (`.claude-plugin/plugin.json`, `hooks/hooks.json`, `hooks/*.py`, `hooks/sg-python.sh`) [P: https://github.com/anthropics/claude-code/tree/main/plugins/hookify, https://github.com/anthropics/claude-code/tree/main/plugins/security-guidance]. Note both put scripts inside `hooks/` next to `hooks.json`; the reference layout in the docs uses a separate `scripts/` directory [P: https://code.claude.com/docs/en/plugins-reference]. Either works.

### Recommended toolchain

| Concern | Pick | Why |
| --- | --- | --- |
| Language | bash + `jq` for trivial hooks; Python 3 (stdlib only) for anything with real logic | Docs' Bash examples all use `jq`; the troubleshooting page says "If you see `jq: command not found`, install `jq` or use Python/Node.js for JSON parsing" [P: hooks-guide]. Anthropic's two shipped hook plugins are Python 3 stdlib (`hookify`, `security-guidance`) [P: GitHub]. |
| Interpreter dispatch | `bash "${CLAUDE_PLUGIN_ROOT}/hooks/py.sh" "${CLAUDE_PLUGIN_ROOT}/hooks/x.py"` shim, or exec form `"command": "python3", "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/x.py"]` | Anthropic's `security-guidance` uses a `sg-python.sh` probe shim so the Windows Store `python3` stub falls through to a real interpreter [P: https://github.com/anthropics/claude-code/blob/main/plugins/security-guidance/hooks/sg-python.sh]. Exec form avoids shell quoting entirely [P: hooks reference]. |
| Local verification | `echo '<fixture>' \| ./script; echo $?` then `claude --plugin-dir . --debug-file /tmp/claude.log` | Both prescribed by the docs [P: hooks-guide, hooks reference]. |
| Config validation | `claude plugin validate . --strict --json` | Validates `plugin.json` and `hooks/hooks.json`; `--strict` makes warnings fail [P: plugins-reference]. |
| Tests | bats-core (bash), pytest (Python), `bun test`/vitest (TS) | Runner choice is not prescribed by Anthropic (UNVERIFIED as a recommendation); `cchooks` uses pytest with `tests/contexts/test_*.py` + `tests/fixtures/` [S], johnlindquist's template uses `bun test` [S]. |
| Types (TS only) | `@anthropic-ai/claude-agent-sdk` exports `PreToolUseHookInput`, `HookJSONOutput`, etc. | SDK types share the CLI's hook JSON schema [P: https://code.claude.com/docs/en/agent-sdk/hooks]. |

---

## 1. The hook JSON contract

### 1.1 Configuration structure

Three levels: event -> matcher group -> handler [P: https://code.claude.com/docs/en/hooks#configuration].

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/pre-tool-use.sh",
            "args": [],
            "timeout": 10,
            "statusMessage": "Checking command..."
          }
        ]
      }
    ]
  }
}
```

The same `"hooks": {...}` object is used in settings files and in a plugin's `hooks/hooks.json`; plugin `hooks.json` may additionally carry a top-level `"description"` [P: https://code.claude.com/docs/en/plugins#convert-existing-configurations-to-plugins, hookify/hooks.json]. (The `plugin-dev` skill in anthropics/claude-code claims settings files use the events directly at top level with no `hooks` wrapper; that contradicts the hooks reference and guide, which show `"hooks": {...}` in `.claude/settings.json`. Follow the docs.) [P: hooks-guide "Register the hook" step]

**Handler types** (`type`): `command`, `http`, `mcp_tool`, `prompt`, `agent`. Agent hooks are experimental [P: hooks#hook-handler-fields].

**Common handler fields** [P: hooks#hook-handler-fields]:
- `type` (required)
- `if`: one permission rule such as `"Bash(git *)"` or `"Edit(*.ts)"`; only evaluated on `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`, `PermissionDenied`; on other events a hook with `if` never runs. Best-effort for Bash (`$VAR cmd` runs the hook anyway); "use the permission system rather than a hook to enforce a hard allow or deny".
- `timeout` (seconds): defaults **600** for `command`/`http`/`mcp_tool`, 30 for `prompt`, 60 for `agent`; lowered to 30 on `UserPromptSubmit`, `PreModelSwitch`, `PostModelSwitch`, 10 on `MessageDisplay`; `SessionEnd` shares a 1.5 s budget (raised to the max per-hook timeout, capped at 60 s). Not enforced on `async: true`.
- `statusMessage`: spinner text.
- `once`: remove after first success; only honored in skill frontmatter.

**Command handler fields** [P: hooks#command-hook-fields]: `command`, `args` (presence switches to *exec form*: no shell, direct spawn, placeholders substituted as plain strings), `async`, `asyncRewake` (background, wakes Claude on exit 2), `shell` (`bash`/`powershell`). Shell form runs via `sh -c` on Unix, so quote placeholders with spaces: `"\"${CLAUDE_PROJECT_DIR}\"/.claude/hooks/x.sh"`. `security-guidance` also uses `rewakeMessage` / `rewakeSummary` alongside `asyncRewake` [P: security-guidance/hooks.json]; those two fields are not in the reference tables I read (UNVERIFIED as documented API).

**Prompt/agent handler fields**: `prompt` with `$ARGUMENTS` placeholder for the input JSON, optional `model`, prompt hooks also `continueOnBlock`; response schema `{"ok": true|false, "reason": "...", "impossible": true|false}` [P: hooks#prompt-based-hooks, #agent-based-hooks].

### 1.2 Matcher syntax

`"*"`, `""`, or omitted matches everything. A string of only letters/digits/`_`/`-`/spaces/`|`/`,` is an exact match on alternatives (`"Edit|Write"`; `"Edit, Write"` from v2.1.191). Anything else is a JavaScript RegExp tested unanchored (`"mcp__.*"`, `"^my-plugin:reviewer$"`). Matchers are case-sensitive. What the matcher compares against depends on the event: tool name for tool events; `startup|resume|clear|compact|fork` for `SessionStart`; `clear|resume|logout|prompt_input_exit|other` for `SessionEnd`; notification type for `Notification`; agent type for `SubagentStart/Stop`; `manual|auto` for `PreCompact/PostCompact`; literal filenames for `FileChanged`; etc. MCP tools are named `mcp__<server>__<tool>` [P: hooks#matcher-patterns, hooks-guide "Hook not firing"].

### 1.3 Events

Full current list (reference page, 2026-09): `SessionStart`, `Setup`, `InstructionsLoaded`, `UserPromptSubmit`, `UserPromptExpansion`, `MessageDisplay`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `PermissionDenied`, `Notification`, `SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted`, `Stop`, `StopFailure`, `TeammateIdle`, `ConfigChange`, `CwdChanged`, `DirectoryAdded`, `FileChanged`, `WorktreeCreate`, `WorktreeRemove`, `PreCompact`, `PostCompact`, `PreModelSwitch`, `PostModelSwitch`, `SessionEnd`, `Elicitation`, `ElicitationResult` [P: https://code.claude.com/docs/en/hooks#hook-events; same table in plugins-reference#hooks].

Agent SDK support differs: Python SDK only exposes `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `UserPromptSubmit`, `Stop`, `SubagentStart`, `SubagentStop`, `PreCompact`, `PermissionRequest`, `Notification`; TypeScript exposes all of them. `SessionStart`/`SessionEnd` are TS-only in the SDK [P: https://code.claude.com/docs/en/agent-sdk/hooks#available-hooks].

### 1.4 stdin input

Common fields (all events; stdin for command hooks, POST body for http) [P: hooks#common-input-fields]: `session_id`, `prompt_id` (v2.1.196+), `transcript_path` (written asynchronously, may lag; use `last_assistant_message` on Stop instead), `cwd`, `scratchpad_dir` (v2.1.257+), `permission_mode` (`default|plan|acceptEdits|auto|dontAsk|bypassPermissions`; not on every event), `effort` (`{"level": ...}` on tool-context events), `hook_event_name`. Inside subagents / `--agent`: `agent_id`, `agent_type`. Only `SessionStart` can receive `model`.

Event-specific:
- `PreToolUse`: `tool_name`, `tool_input`, `tool_use_id`. File-tool `tool_input.file_path` is always absolute, with native separators (backslashes on Windows; normalize with `${FILE_PATH//\\//}`) [P: hooks#pretooluse-input].
- `PermissionRequest`: `tool_name`, `tool_input`, optional `permission_suggestions[]`; no `tool_use_id` [P: hooks#permissionrequest-input].
- `PostToolUse`: `tool_input`, `tool_response` (shape depends on tool; `Bash` returns `{stdout, stderr, interrupted, isImage}`), `tool_use_id`, optional `duration_ms`, and `tool_response.bashEditDiff` for Bash on v2.1.269+ [P: hooks#posttooluse-input].
- `PostToolUseFailure`: `tool_name`, `tool_use_id`, `error`, optional `is_interrupt` [P: hooks#posttoolusefailure].
- `UserPromptSubmit`: `prompt` [P: hooks#userpromptsubmit-input].
- `Stop`/`SubagentStop`: `stop_hook_active`, `last_assistant_message`, `background_tasks[]`, `session_crons[]` [P: hooks#stop-input].
- `SessionStart`: `source` (`startup|resume|clear|compact|fork`), sometimes `model`; env `CLAUDE_ENV_FILE` available [P: hooks#sessionstart].
- `SessionEnd`: `reason` [P: hooks#sessionend-input].
- `PreCompact`: `trigger` (`manual|auto`), `custom_instructions`; `PostCompact`: `trigger` [P: hooks#precompact, #postcompact].
- `Notification`: `message`, `title`, `notification_type` [P: hooks#notification].

Example `PreToolUse` stdin, quoted from the reference:

```json
{
  "session_id": "abc123",
  "prompt_id": "550e8400-e29b-41d4-a716-446655440000",
  "transcript_path": "/home/user/.claude/projects/.../transcript.jsonl",
  "cwd": "/home/user/my-project",
  "scratchpad_dir": "/tmp/claude-1000/-home-user-my-project/abc123/scratchpad",
  "permission_mode": "default",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": {
    "command": "npm test",
    "description": "Run test suite",
    "timeout": 120000,
    "run_in_background": false
  },
  "tool_use_id": "toolu_01ABC123..."
}
```

### 1.5 Exit codes

[P: https://code.claude.com/docs/en/hooks#exit-code-output]

- **0**: success; intended code when printing JSON. For most events stdout goes to the debug log only, *not* the transcript. Exceptions where plain-text stdout is injected as context Claude can see: `UserPromptSubmit`, `UserPromptExpansion`, `SessionStart`, `PostModelSwitch`. Stderr on exit 0 goes to the debug log only; Claude never sees it.
- **2**: blocking error, cannot be overridden by JSON (even `permissionDecision: "allow"`). Blocking message = JSON decision reason if present, else stderr. Per event: `PreToolUse` blocks the tool; `UserPromptSubmit` erases the prompt; `Stop`/`SubagentStop` prevents stopping and feeds stderr to Claude; `PostToolUse`/`PostToolUseFailure` cannot block but *show stderr to Claude*; `PermissionRequest` ignores exit 2 (use the `decision` object); `Notification`, `StopFailure`, `Setup` ignore exit code and stderr; `SessionStart`, `SessionEnd`, `SubagentStart`, `PostCompact`, `CwdChanged`, `FileChanged` show stderr to the user only; `PreCompact` blocks compaction; `WorktreeCreate`/`WorktreeRemove` fail on *any* nonzero.
- **Other (1, 3, 127, ...)**: non-blocking for most events. If stdout is a schema-valid JSON object, the exit code is ignored and the JSON decides. Otherwise the transcript shows `<hook name> hook error` + first stderr line prefixed `Failed with non-blocking status code:`. A missing/non-executable script lands here (exit 127), so "a mistyped path in `settings.json` leaves the gate silently disabled". Explicit warning: exit 1 does **not** block; "If your hook is meant to enforce a policy, use `exit 2`."
- **Timeout**: output discarded, no decision; on `PreToolUse` a timed-out command hook lets the tool proceed ("don't count on a stalled hook to act as a gate"). SDK callback timeouts on `PreToolUse` block instead.

JSON detection: stdout (trimmed) must start with `{` and end with `}`; otherwise treated as plain text. Parse or schema failure on exit 0 is a non-blocking error shown in the transcript (since v2.1.248) [P: hooks#exit-code-0].

### 1.6 stdout JSON output

[P: https://code.claude.com/docs/en/hooks#json-output]

Universal top-level fields: `continue` (default true; `false` stops Claude entirely, takes precedence over event decisions), `stopReason`, `suppressOutput` (**"Has no effect: Claude Code accepts the field but doesn't act on it"**), `systemMessage` (warning shown to the user), `terminalSequence` (allowlisted OSC/BEL escapes). Strings are capped at 10,000 chars.

Decision patterns per event (from the reference's Decision control table):

| Events | Pattern | Fields |
| --- | --- | --- |
| `UserPromptSubmit`, `UserPromptExpansion`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `Stop`, `SubagentStop`, `ConfigChange`, `PreCompact` | top-level | `decision: "block"`, `reason` (only value is `"block"`; omit to allow) |
| `PreToolUse` | `hookSpecificOutput` | `permissionDecision: allow\|deny\|ask\|defer`, `permissionDecisionReason`, `updatedInput` (replaces the whole input object), `additionalContext` |
| `PermissionRequest` | `hookSpecificOutput.decision` | `behavior: allow\|deny`, `updatedInput`, `updatedPermissions[]`, `message`, `interrupt` |
| `PostToolUse` extra | `hookSpecificOutput` | `additionalContext`, `updatedToolOutput` (must match tool output shape), `classifierContext` |
| `Stop`/`SubagentStop` extra | `hookSpecificOutput` | `additionalContext` (continues conversation as "Stop hook feedback" instead of a hook error) |
| `UserPromptSubmit` extra | `hookSpecificOutput` | `additionalContext`, `sessionTitle`; top-level `suppressOriginalPrompt` |
| `SessionStart` | `hookSpecificOutput` | `additionalContext`, `initialUserMessage`, `watchPaths`, `sessionTitle`, `reloadSkills` |
| `SessionEnd`, `Notification`, `PostCompact`, `Setup`, ... | none | side effects only; JSON fields discarded |

`hookSpecificOutput` **requires** `hookEventName`. `permissionDecision` at top level parses fine but is silently ignored; find those in the debug log under `Hook JSON output had unrecognized keys` [P: hooks-guide#hook-json-has-no-effect]. PreToolUse's old top-level `decision: approve|block` is deprecated and maps to `allow|deny` [P: hooks#pretooluse-decision-control]. Multiple `PreToolUse` decisions resolve `deny > defer > ask > allow`. `PreToolUse` hooks fire in every permission mode, so a hook `deny` holds even under `--dangerously-skip-permissions`; an `allow` cannot override settings deny rules [P: hooks-guide#limitations-and-troubleshooting].

Canonical examples:

```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Database writes are not allowed"}}
```
```json
{"decision":"block","reason":"Test suite must pass before proceeding"}
```
```json
{"hookSpecificOutput":{"hookEventName":"PermissionRequest","decision":{"behavior":"allow","updatedInput":{"command":"npm run lint"}}}}
```

### 1.7 Environment and placeholders

`${CLAUDE_PROJECT_DIR}` (project root; stays at the original root inside worktrees, use `cwd` from input for the worktree), `${CLAUDE_PLUGIN_ROOT}` (plugin install dir), `${CLAUDE_PLUGIN_DATA}` (persistent dir surviving updates, for venvs/node_modules) are substituted in `command`/`args`, HTTP `url`/`headers`, MCP `input`, prompt text, and also exported as env vars. Also `CLAUDE_ENV_FILE` (SessionStart, Setup, CwdChanged, FileChanged only: append `export X=Y` lines to persist env for later Bash calls), `CLAUDE_EFFORT`, `CLAUDE_CODE_REMOTE`, `CLAUDE_PLUGIN_OPTION_<KEY>`. `OTEL_*` is stripped from hook processes [P: hooks#reference-scripts-by-path, hooks#persist-environment-variables, plugins-reference#environment-variables].

### 1.8 Settings locations and precedence

Hook locations: `~/.claude/settings.json` (all projects), `.claude/settings.json` (project, commit it), `.claude/settings.local.json` (personal; Claude Code adds `**/.claude/settings.local.json` to global git excludes the first time *it* writes the file, otherwise gitignore it yourself), managed policy settings, plugin `hooks/hooks.json`, skill frontmatter, subagent frontmatter [P: hooks#hook-locations, settings]. Precedence highest-first: managed, `--settings` CLI, project local, shared project, user [P: https://code.claude.com/docs/en/settings#settings-precedence]. Hook entries **merge** across levels rather than replace; same handler in multiple settings files runs once; a plugin's copy stays separate [P: hooks#hook-locations, #hook-handler-fields]. `disableAllHooks: true` follows precedence and cannot disable managed hooks; `allowManagedHooksOnly` blocks user/project/local/plugin hooks [P: hooks#disable-or-remove-hooks].

Settings are file-watched and hooks reload live: "Claude Code watches your settings files and reloads them when they change ... including edits to `permissions`, `hooks`" [P: https://code.claude.com/docs/en/settings]. The older "hooks are snapshotted at startup; review in `/hooks`" behavior does **not** appear in the current reference (grep for "snapshot" returns nothing); the troubleshooting page instead says "File edits are normally picked up automatically. If they haven't appeared after a few seconds ... restart your session" [P: hooks-guide#hooks-shows-no-hooks-configured]. Treat the snapshot claim as historical.

### 1.9 Agent SDK types

`options.hooks` is `{ [HookEvent]: HookCallbackMatcher[] }`, `HookCallbackMatcher = { matcher?: string; hooks: HookCallback[]; timeout?: number }` (TS) / `HookMatcher(matcher=..., hooks=[...])` (Python). Callbacks receive `(input, tool_use_id, context)` and return the same JSON shape (`hookSpecificOutput.permissionDecision`, `continue`, `systemMessage`, ...). SDK matchers "follow the same rules as matchers in settings files". Callback timeouts on `PreToolUse`/`UserPromptSubmit` fail *closed* (block), unlike command hooks [P: https://code.claude.com/docs/en/agent-sdk/hooks]. The TS package exports `PreToolUseHookInput`, `PreToolUseHookSpecificOutput`, `SyncHookJSONOutput`, etc., which the johnlindquist template imports for typed stdin parsing [S: https://github.com/johnlindquist/claude-session-hooks-template/blob/main/scripts/PreToolUse.ts]. The `$schema` URL that template references (`anthropics/claude-agent-sdk/main/schemas/hooks.json`) returns 404 -- no published JSON Schema for hooks.json found (UNVERIFIED that one exists).

---

## 2. Project layout and language choice

### 2.1 Plugin vs plain `.claude/`

| | Standalone `.claude/settings.json` + `.claude/hooks/*.sh` | Plugin |
| --- | --- | --- |
| Best for | "Personal workflows, project-specific customizations, quick experiments" | "Sharing with teammates, distributing to community, versioned releases, reusable across projects" |
| Hooks live in | `settings.json` `hooks` key | `hooks/hooks.json` (same object) |
| Path variable | `${CLAUDE_PROJECT_DIR}` | `${CLAUDE_PLUGIN_ROOT}` |
| Install | copy files | `claude plugin install x@marketplace`, `--plugin-dir`, or drop into `~/.claude/skills/<name>/` (auto-loads as `<name>@skills-dir`) |

[P: https://code.claude.com/docs/en/plugins#when-to-use-plugins-vs-standalone-configuration, #develop-a-plugin-in-your-skills-directory]

Minimal `plugin.json` is `{"name": "..."}`; the manifest is optional but `claude plugin validate` warns on missing `version`, `description`, `author` (observed locally). `version` matters: "users only receive updates when you bump this field" [P: plugins-reference, plugins]. Scaffold with `claude plugin init my-hook --with hooks` [P: plugins-reference#plugin-init].

Example `hooks/hooks.json` for a PreToolUse gate on Bash, exec form:

```json
{
  "description": "wlb-hook: guard Bash commands",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3",
            "args": ["${CLAUDE_PLUGIN_ROOT}/scripts/pre_tool_use.py"],
            "timeout": 10,
            "statusMessage": "wlb-hook: checking command"
          }
        ]
      }
    ]
  }
}
```

Equivalent standalone `.claude/settings.json` (from the guide, shell form with quoting):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/protect-files.sh" }
        ]
      }
    ]
  }
}
```
[P: https://code.claude.com/docs/en/hooks-guide#block-edits-to-protected-files]

### 2.2 Language choices

What Anthropic actually ships:
- **bash + jq**: every inline example in the docs (`jq -r '.tool_input.file_path' | xargs npx prettier --write`, `jq -nc --arg ...` to build output) [P: hooks-guide, hooks#emit-terminal-notifications]. The docs recommend building JSON output with `jq` rather than string concatenation so quotes/backslashes are escaped [P: hooks-guide#hook-error-in-output].
- **Python 3 stdlib**: `examples/hooks/bash_command_validator_example.py` (reads `json.load(sys.stdin)`, prints issues to stderr, `sys.exit(2)` to block, exit 1 on bad JSON) [P: https://github.com/anthropics/claude-code/blob/main/examples/hooks/bash_command_validator_example.py]; `hookify` (`python3 ${CLAUDE_PLUGIN_ROOT}/hooks/pretooluse.py`, `timeout: 10`, always exits 0 and prints `{"systemMessage": ...}` on internal error so the hook never blocks by accident) [P: hookify/hooks/pretooluse.py]; `security-guidance` (bash shim -> python3) [P].
- **Node/TS**: docs show `"command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/scripts/format.js"]` as the exec-form example and note `.cmd`/`.bat` on Windows require exec form [P: hooks#exec-form-and-shell-form]. Community: `bun run ${CLAUDE_PLUGIN_ROOT}/scripts/X.ts` per event [S: johnlindquist template].
- **uv single-file scripts**: `uv run $CLAUDE_PROJECT_DIR/.claude/hooks/pre_tool_use.py` for every event [S: https://github.com/disler/claude-code-hooks-mastery/blob/main/.claude/settings.json]. Not used in any Anthropic first-party hook.

**Startup latency**: Anthropic's docs do not publish per-language startup numbers (UNVERIFIED). What they do say: hooks run on every matching event, all matching hooks run in parallel, `UserPromptSubmit` "runs before every prompt and blocks model processing until it completes, a stuck hook stalls the session" [P: hooks#userpromptsubmit], `MessageDisplay` holds each batch until the hook returns [P], and `SessionEnd` only gets 1.5 s total [P]. The `plugin-dev` linter flags hooks that could exceed 60 s [P: plugin-dev/skills/hook-development/scripts/hook-linter.sh]. Practical ordering (general knowledge, UNVERIFIED against Anthropic measurements): `sh`+`jq` (single fork, ~ms) < `python3` stdlib (tens of ms) < `bun` (tens of ms) < `node` (~50-100 ms) < `uv run` with dependency resolution / `npx` (hundreds of ms to seconds cold). Whatever you pick, set an explicit small `timeout` (hookify uses 10) and avoid importing heavy deps on the hot path; use `${CLAUDE_PLUGIN_DATA}` for a pre-built venv/node_modules if you need deps [P: plugins-reference#environment-variables].

### 2.3 Shim + pure core pattern

Keep the entry script tiny: read stdin, `json.load`, call `decide(payload) -> Decision`, serialize, exit. Anthropic's `hookify` separates `hooks/pretooluse.py` (I/O) from `core/rule_engine.py` (logic) [P: hookify tree]; `cchooks` separates per-event context classes from output utils and tests each context with fixtures [S: https://github.com/GowayLee/cchooks]. This is what makes step 4 (unit tests without a subprocess) possible.

---

## 3. Fast local verification

1. **Pipe a fixture to the script** (docs' own recipe):
   ```bash
   echo '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | ./my-hook.sh
   echo $?  # Check the exit code
   ```
   [P: https://code.claude.com/docs/en/hooks-guide#hook-error-in-output]. Anthropic's `plugin-dev` skill ships `scripts/test-hook.sh` that does exactly this plus sets `CLAUDE_PROJECT_DIR`, `CLAUDE_PLUGIN_ROOT`, `CLAUDE_ENV_FILE`, times the run, maps exit 0/2/124, and pretty-prints JSON stdout; `--create-sample PreToolUse` emits a fixture [P: https://github.com/anthropics/claude-code/blob/main/plugins/plugin-dev/skills/hook-development/scripts/test-hook.sh]. (Its samples are dated: they use `tool_result`/`user_prompt` where the reference says `tool_response`/`prompt`; build fixtures from the reference, not from that script.)
2. **Load the plugin without installing**: `claude --plugin-dir ./wlb-hook` (also accepts a `.zip` or a folder of plugins; `/reload-plugins` after edits) [P: https://code.claude.com/docs/en/plugins#test-your-plugins-locally].
3. **Confirm registration**: `/hooks` lists events with counts, matcher, type, command and source (`User Settings`, `Project Settings`, `Local Settings`, `Plugin Hooks`, `Session Hooks`); read-only [P: hooks#the-hooks-menu, hooks-guide].
4. **Debug log**: `claude --debug-file /tmp/claude.log` then `tail -f` in another terminal, or `claude --debug` (log at `~/.claude/debug/<session-id>.txt`; `--debug` does not print to the terminal), or `/debug` mid-session. Shows which hooks matched, exit codes, stdout/stderr, JSON parse/validation results, `Hook JSON output had unrecognized keys`. `CLAUDE_CODE_DEBUG_LOG_LEVEL=verbose` adds matcher counts [P: https://code.claude.com/docs/en/hooks#debug-hooks, hooks-guide#debug-techniques].
5. **Transcript view**: `Ctrl+O` opens the transcript; a successful hook shows nothing, a blocking error shows the reason/stderr, a non-blocking error shows `<hook name> hook error`. Async completion notices need verbose mode (`Ctrl+O` or `--verbose`) [P: hooks-guide#debug-techniques, hooks#run-hooks-in-the-background]. Ctrl+R was not mentioned on either page (UNVERIFIED).
6. **Validate config**: `claude plugin validate ./wlb-hook [--strict] [--json]` checks `plugin.json`, `hooks/hooks.json`, and skill/agent/command frontmatter; exit 0 pass, 1 fail, 2 could not run [P: https://code.claude.com/docs/en/plugins-reference#plugin-validate]. Observed on 2.1.274: an unknown event name (`BogusEvent`) is reported as a *warning* ("unknown hook event; entry ignored at runtime") and the run still exits 0 without `--strict`; a `command` handler with no `command` field was not flagged at all. So `--strict` is mandatory in CI and the validator is not a substitute for tests.

---

## 4. Testing approach

Anthropic prescribes *that* you test (fixtures piped to stdin, then `claude --debug`) but not a test framework; the runner choices below are conventions, marked [S] or UNVERIFIED where noted.

### 4.1 Fixtures

One JSON file per event and scenario, built from the reference's input examples. Example `tests/fixtures/PreToolUse.bash-rm-rf.json`:

```json
{
  "session_id": "test-session",
  "transcript_path": "/tmp/transcript.jsonl",
  "cwd": "/tmp/test-project",
  "permission_mode": "default",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": { "command": "rm -rf /tmp/build", "description": "clean" },
  "tool_use_id": "toolu_test_001"
}
```

Include a fixture for each: allowed input, denied input, non-matching tool (should exit 0 with no output), malformed JSON stdin, empty stdin, Windows-style `file_path` with backslashes (docs call this out as a common miss) [P: hooks#pretooluse-input], and `stop_hook_active: true` for Stop hooks (docs require early exit to avoid the 8-block cap) [P: hooks-guide#stop-hook-hits-the-block-cap].

### 4.2 Three layers

1. **Unit tests on the pure core** (no subprocess): `decide(payload)` returns a typed decision. pytest for Python, `bun test`/vitest for TS, bats + a sourced function for bash.
2. **Contract tests on the shim**: spawn the script, feed the fixture on stdin with `CLAUDE_PLUGIN_ROOT`/`CLAUDE_PROJECT_DIR` set, assert (a) exit code, (b) stdout is either empty or a single JSON object that starts with `{` and ends with `}`, (c) `hookSpecificOutput.hookEventName` equals the event, (d) no stray stdout on the allow path, (e) block reasons go to stderr when using exit 2. Golden files under `tests/expected/` compared with `jq -S` (sorted keys) keep this deterministic.
3. **Config tests**: `claude plugin validate . --strict --json` passes; every `command`/`args` path referenced in `hooks.json` exists and is executable (the docs list "Script not executable" as the top "hooks not firing" cause and note a bad path fails *open*) [P: plugins-reference#common-issues, hooks#other-exit-codes].

Example pytest contract test:

```python
import json, os, subprocess, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]

def run_hook(fixture: str):
    payload = (ROOT / "tests/fixtures" / fixture).read_text()
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(ROOT), "CLAUDE_PROJECT_DIR": "/tmp/test-project"}
    return subprocess.run(["python3", ROOT / "scripts/pre_tool_use.py"],
                          input=payload, text=True, capture_output=True, env=env, timeout=10)

def test_rm_rf_is_denied():
    r = run_hook("PreToolUse.bash-rm-rf.json")
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

def test_ls_has_no_opinion():
    r = run_hook("PreToolUse.bash-ls.json")
    assert r.returncode == 0 and r.stdout.strip() == ""
```

Example bats test (bash hooks):

```bash
@test "denies rm -rf via exit 2 with stderr reason" {
  run bash -c "cat tests/fixtures/PreToolUse.bash-rm-rf.json | CLAUDE_PLUGIN_ROOT=$PWD scripts/pre-tool-use.sh"
  [ "$status" -eq 2 ]
  [[ "$output" == *"Blocked"* ]]
}
```

Example invocations: `pytest -q`, `bats tests/e2e`, `bun test`, `./plugin-dev/.../test-hook.sh -v scripts/pre-tool-use.sh tests/fixtures/PreToolUse.bash-rm-rf.json`.

Reference implementations: `cchooks` has `tests/contexts/test_<event>.py` per event plus `tests/fixtures/sample_data.py` and `tests/integration/` [S: https://github.com/GowayLee/cchooks]; johnlindquist's template wires `"test": "bun test"` and `"typecheck": "bunx tsc --noEmit"` [S: https://github.com/johnlindquist/claude-session-hooks-template/blob/main/package.json].

### 4.3 CI

- Run the unit + contract tests on Linux and macOS (path/`sh` differences), and Windows if you claim support (backslash paths, `python3` Store stub -- Anthropic hit this and shipped `sg-python.sh` for it [P]).
- Install Claude Code in CI and run `claude plugin validate . --strict` (the docs explicitly position `--strict` for CI) [P: plugins-reference#plugin-validate].
- Lint shell with shellcheck; Anthropic's `hook-linter.sh` checks: shebang, `set -euo pipefail`, reads stdin, uses `jq`, quoted variables, no hardcoded `/home|/usr|/opt`, explicit `exit 0|2`, errors to `>&2`, input validation [P: plugin-dev hook-linter.sh].
- Optional: `claude plugin eval` for behavioral evaluation against prompts (docs mention it for plugins generally) [P: plugins#test-your-plugins-locally]. Whether it is useful for pure hook plugins is UNVERIFIED.
- For an end-to-end smoke test, `claude -p` with `--plugin-dir` runs hooks non-interactively; note `-p`/SDK sessions treat the folder as trusted so repo hooks run without a dialog [P: hooks#workspace-trust].

---

## 5. Pitfalls documented by Anthropic

- **Timeout default is 600 s, not 60 s**, for command hooks (30 s on `UserPromptSubmit`, 1.5 s budget on `SessionEnd`). Set your own small `timeout`; a timed-out `PreToolUse` command hook lets the tool run [P: hooks#hook-handler-fields, #timeouts].
- **Exit 1 does not block.** Only exit 2 (or valid JSON decision fields) does [P: hooks#other-exit-codes].
- **Missing/non-executable script fails open** with a `Failed with non-blocking status code: ... No such file or directory` notice; `chmod +x`, use `${CLAUDE_PLUGIN_ROOT}`/`${CLAUDE_PROJECT_DIR}`, prefer exec form (`"args": []`) to avoid quoting [P: hooks#other-exit-codes, hooks-guide#hook-error-in-output].
- **Parallel execution and non-deterministic order**: all matching hooks run in parallel; if several `PreToolUse` hooks return `updatedInput`, the last to finish wins -- do not have two hooks rewrite the same tool's input [P: hooks-guide#limitations-and-troubleshooting].
- **Dedup**: same handler across multiple settings files runs once; plugin/skill copies stay separate; async hooks are never deduplicated across firings [P: hooks#hook-handler-fields, #limitations].
- **stdout visibility**: on exit 0, stdout is invisible in the transcript except on `UserPromptSubmit`, `UserPromptExpansion`, `SessionStart`, `PostModelSwitch`, where it becomes context. `suppressOutput` does nothing. Stderr on exit 0 goes only to the debug log [P: hooks#exit-code-0, #json-output].
- **stderr on exit 2 is fed to Claude** on `PreToolUse`, `Stop`, `SubagentStop`, `PostToolUse`, `PostToolUseFailure`; shown to the user only on `SessionStart`, `SessionEnd`, `UserPromptSubmit`, etc.; ignored on `PermissionRequest`, `Notification`, `StopFailure` [P: hooks#exit-code-2-behavior-per-event].
- **stdout must be *only* the JSON object**; a shell profile `echo` prepended to it makes the whole thing plain text and the decision is silently dropped. Wrap profile echoes in `if [[ $- == *i* ]]` [P: hooks-guide#hook-json-has-no-effect].
- **Field placement**: `permissionDecision`/`additionalContext` at top level are ignored without error; `hookSpecificOutput` needs `hookEventName` [P: hooks-guide, hooks#json-output].
- **Build JSON with an encoder** (`jq -n --arg`, `json.dumps`) not string concatenation [P: hooks-guide#hook-error-in-output].
- **Stop hook loop**: check `stop_hook_active`; Claude Code overrides after 8 consecutive blocks; raise with `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` [P: hooks-guide#stop-hook-hits-the-block-cap].
- **Do not read `transcript_path` for the current turn**; it lags. Use `last_assistant_message` [P: hooks#common-input-fields].
- **`Edit|Write` matchers miss Bash-driven file changes**; use `FileChanged` or a `Stop`-time `git status --porcelain` sweep [P: hooks-guide, hooks#posttooluse].
- **`@`-referenced files bypass `PreToolUse` Read hooks**; use a `Read` deny rule [P: hooks#pretooluse].
- **Windows paths** arrive with backslashes even under Git Bash; normalize before matching [P: hooks#pretooluse-input].
- **`additionalContext` phrasing**: write factual statements ("This repo uses `bun test`"), not imperative system commands, or prompt-injection defenses surface the text to the user instead [P: hooks#add-context-for-claude].
- **Security**: "Command hooks execute shell commands with your full user permissions." Validate/sanitize input, always quote `"$VAR"`, block `..` traversal, use absolute paths, skip `.env`/`.git/`/keys. Settings-file hooks wait for workspace trust in interactive sessions, but `-p`/SDK sessions run repo hooks with no dialog -- review `.claude/` or pass `--settings '{"disableAllHooks": true}'` before scripting `claude -p` on an untrusted repo [P: hooks#security-considerations].
- **`if` filtering is best-effort**; enforce hard policy with permission rules, not hooks [P: hooks#hook-handler-fields].
- **`claude plugin validate` without `--strict` passes unknown events with a warning** and did not flag a `command`-less handler (observed locally, 2.1.274).

---

## Sources

Primary (Anthropic):
- Hooks reference: https://code.claude.com/docs/en/hooks (redirect target of https://docs.anthropic.com/en/docs/claude-code/hooks)
- Hooks guide: https://code.claude.com/docs/en/hooks-guide (redirect target of https://docs.anthropic.com/en/docs/claude-code/hooks-guide)
- Settings: https://code.claude.com/docs/en/settings
- Create plugins: https://code.claude.com/docs/en/plugins
- Plugins reference: https://code.claude.com/docs/en/plugins-reference
- Agent SDK hooks: https://code.claude.com/docs/en/agent-sdk/hooks (+ TS/Python type refs via Context7 `/websites/code_claude_en_agent-sdk`)
- Bash command validator example: https://github.com/anthropics/claude-code/blob/main/examples/hooks/bash_command_validator_example.py
- hookify plugin: https://github.com/anthropics/claude-code/tree/main/plugins/hookify
- security-guidance plugin: https://github.com/anthropics/claude-code/tree/main/plugins/security-guidance
- plugin-dev hook-development skill (SKILL.md, scripts/test-hook.sh, validate-hook-schema.sh, hook-linter.sh, references/patterns.md): https://github.com/anthropics/claude-code/tree/main/plugins/plugin-dev/skills/hook-development
- Official marketplace index (39 plugins incl. hookify, security-guidance, plugin-dev): https://github.com/anthropics/claude-plugins-official/tree/main/plugins
- Local CLI checks: `claude --version` (2.1.274), `claude plugin validate --help`, validate smoke test on a temp plugin

Secondary (structure ideas only):
- disler/claude-code-hooks-mastery: https://github.com/disler/claude-code-hooks-mastery (uv single-file Python hooks per event in `.claude/hooks/`)
- johnlindquist/claude-session-hooks-template: https://github.com/johnlindquist/claude-session-hooks-template (plugin layout, `bun run scripts/<Event>.ts`, SDK types, `bun test`)
- GowayLee/cchooks: https://github.com/GowayLee/cchooks (Python SDK; per-event context classes; pytest with `tests/contexts/`, `tests/fixtures/`, `tests/integration/`)
- hgeldenhuys/claude-hooks-sdk (TypeScript hooks SDK; surfaced via Context7, repo tree not fetched)
