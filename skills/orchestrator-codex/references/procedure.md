# Codex dispatch

Follow [workflow.md](workflow.md). For dependencies or a retained plan, use
[scheduling.md](scheduling.md). Create one run per owned outcome:

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" new codex standard implementer
```

Use the selected mode and role. Send `brief <run>` with a quoted heredoc, then
`start <run>`. The runtime resolves the live model, effort and sandbox, feeds
prompt.md on stdin and records events.jsonl, final.md and stderr.log. Read
`report <run>` after completion. Use background execution only when the host
notifies this conversation on completion; a one-shot host waits for the result.
Independent starts may be separate concurrent tool calls.

Dispatch requires the live catalog. Completed reports remain readable offline.
If the Caveman proxy cannot start, `start <run> --bypass-caveman` is available;
disclose automatic or explicit bypasses. Retain evidence through review, then
`cleanup <run>`. Writable runtime output does not authorize edits beyond SCOPE.

A follow-up is a cold run carrying original criteria, the accepted finding and
pointers to current evidence. Separate Caveman wrappers have fresh CODEX_HOME
folders, so cross-wrapper session resume is unavailable. Load
[examples.md](examples.md) for syntax, [pitfalls.md](pitfalls.md) for an observed
failure, or [herdr.md](herdr.md) for --visible.

## Independent runtime batch

Use one call for independent runs; separate foreground calls run sequentially:

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" start-many /tmp/orchestrator-A /tmp/orchestrator-B --capacity 2
```

Replace both paths with literal returned run paths. For implementer or runner
runs, first create and claim a scheduling plan with each run path as owner,
then add `--plan /tmp/orchestrator-plan-P` to the batch call. Read-only batches
need no plan. Collect every report; use `summary` with every run path before
reporting counts or usage.
