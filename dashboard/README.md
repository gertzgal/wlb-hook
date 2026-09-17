# wlb dashboard

Calendar view of your work-life-balance record with Claude Code.

```bash
cd dashboard && npm install
WLB_EVENTS_FILE=/tmp/wlb-demo-events.jsonl npm run dev   # demo data (run `make seed` first)
npm run dev                                                # your real ~/.claude/wlb-hook/events.jsonl
```

Opens on http://localhost:5178. The page polls the file every 2 s, so a gate answered in a
running `make demo` session shows up on today's cell. Drop any `events.jsonl` onto the page to
read a different record.
