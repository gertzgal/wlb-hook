---
name: wlb
description: Work-life balance status and settings. `/wlb` shows today's hours vs budget; `/wlb set 8` sets the daily budget in hours.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wlb.py *)
---

The user ran `/wlb $ARGUMENTS`.

Run exactly one command with the Bash tool and relay its single output line to the user verbatim, nothing else:

- No arguments or `status`: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/wlb.py" status`
- `set <hours>` (a number, e.g. `set 8` or `set 7.5`): `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/wlb.py" set <hours>`

If the arguments match neither form, reply with: `usage: /wlb [status | set <hours>]`.
The budget takes effect on the next prompt; no restart needed.
