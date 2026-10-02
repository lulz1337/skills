# Hybrid dispatch

Follow [workflow.md](workflow.md). For dependencies or a retained plan, use
[scheduling.md](scheduling.md). Codex owns implementation, discovery,
research, browser work and diagnosis. Claude owns reviewer, sage and critic.
The runtime's resolved role metadata selects the family and model.

For Codex roles use `new hybrid <mode> <role>`, `brief <run>`, `start <run>` and
`report <run>` as [examples.md](examples.md) shows. For Claude roles use Agent
with the resolved agent_type and no model override. The reviewer is
reviewer-hybrid-<mode>. Quick has no reviewer or critic.

Disclose proxy bypasses and keep detailed usage in coordination state. Keep
Claude and Codex usage separate in the aggregate line. A different review
family does not guarantee independent reasoning. Load [pitfalls.md](pitfalls.md)
for an observed failure or [herdr.md](herdr.md) for --visible. Live evidence and
unverified paths are recorded in agents/evals/ORCHESTRATOR-2026-10-01.md.

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
