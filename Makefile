.PHONY: test validate smoke lint check dev demo seed

test:            ## unit + e2e tests
	uv run --group dev pytest

validate:        ## validate plugin manifest and hooks.json
	claude plugin validate .  # not --strict: CLAUDE.md at root is a dev-context warning

lint:
	uv run --group dev ruff check .

check: lint validate test

smoke:           ## fire the real Gate dialog once, from the shell (events go to /tmp)
	@WLB_FIRST_PROMPT_AT=$$(date -v-10H +%Y-%m-%dT%H:%M:%S) WLB_EVENTS_FILE=/tmp/wlb-demo-events.jsonl \
	  python3 hooks/user_prompt_submit.py < tests/fixtures/UserPromptSubmit/plain.json; echo "exit=$$?"

demo:            ## Claude Code with the plugin loaded and a fake 10-hour-old first prompt (events -> /tmp)
	WLB_FIRST_PROMPT_AT=$$(date -v-10H +%Y-%m-%dT%H:%M:%S) WLB_EVENTS_FILE=/tmp/wlb-demo-events.jsonl \
	  claude --plugin-dir . --debug-file /tmp/wlb-hook-debug.log

seed:            ## generate 6 weeks of fake events for the future calendar
	python3 scripts/seed_demo_events.py /tmp/wlb-demo-events.jsonl

dev:             ## start Claude Code with this plugin loaded, debug log to /tmp
	claude --plugin-dir . --debug-file /tmp/wlb-hook-debug.log
