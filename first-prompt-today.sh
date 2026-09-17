#!/usr/bin/env bash
# First prompt you typed into the Claude Code CLI today (local time).
# Source: ~/.claude/history.jsonl (global, append-only, one line per typed prompt).
# Excludes CodexBar's /usage probe, which writes into the same file.
jq -rs --arg d "$(date +%F)" '[.[] | select((.project // "" | test("ClaudeProbe") | not) and ((.timestamp/1000 | strflocaltime("%F")) == $d))] | min_by(.timestamp) | if . then "\(.timestamp/1000 | strflocaltime("%F %T"))\t\(.project)\t\(.display | split("\n")[0][0:80])" else "no CLI prompts yet today" end' ~/.claude/history.jsonl
