.PHONY: test validate smoke lint check dev

test:            ## unit + e2e tests
	uv run --group dev pytest

validate:        ## validate plugin manifest and hooks.json
	claude plugin validate . --strict

lint:
	uv run --group dev ruff check .

check: lint validate test

smoke:           ## pipe one fixture through a hook by hand
	@python3 hooks/pre_tool_use.py < tests/fixtures/PreToolUse/bash-rm-root.json; echo "exit=$$?"

dev:             ## start Claude Code with this plugin loaded, debug log to /tmp
	claude --plugin-dir . --debug-file /tmp/wlb-hook-debug.log
