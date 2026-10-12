# Dependency scheduling and recovery

Adapted from Matt Pocock's to-tickets and implement-spec. Use this for several
slices with real dependencies, an integration step, or a retained plan. A
settled single-scope task follows workflow.md without creating a graph.

A task delivers one bounded behavior and fits a fresh worker context. Its
blockers name only prerequisites that genuinely gate its implementation. For a
wide mechanical refactor, use expand, bounded migration batches and contract.
Dependent writers may start after prerequisite implementation is handed off;
verification is consolidated after all scoped implementation is stable.
The runner owns authorized integration. Worktrees are optional; branches,
commits, PRs and issue publication stay within existing authorization.

## Create and claim

Create the plan from settled requirements and scout evidence. Use the selected
family/mode and a capacity within the host's actual worker limit:

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" plan claude standard <<'PLAN'
{"goal":"Add tax and use it in order totals","capacity":2,"tasks":[{"id":"tax","title":"Add tax behavior","scope":["orders/tax.py","tests/test_tax.py"],"acceptance":["Tax uses Decimal and validates the rate"],"verify":["python3 -m unittest -q"]},{"id":"totals","title":"Use tax in order totals","blocked_by":["tax"],"scope":["orders/pricing.py","tests/test_pricing.py"],"acceptance":["Order totals include tax"],"verify":["python3 -m unittest -q"]}]}
PLAN
```

Use the literal returned plan path in each following call:

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" graph /tmp/orchestrator-plan-EXAMPLE
```

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" claim /tmp/orchestrator-plan-EXAMPLE tax --owner tax-attempt-1
```

Graph reports a **frontier**: pending tasks with implemented or done blockers and available
capacity/scope. Claim before dispatch; use the returned task's role, acceptance
and scope in its brief. Collect its `verify` entries as candidates for the one
task-wide check plan; the worker does not execute them. Every graph-bound brief also
includes literal PLAN, TASK and ATTEMPT fields from its claim, so execution can
be traced to that task and attempt. For Codex, create the run before claiming and
use its run path as owner. After a Claude Agent dispatch returns its ID, bind it:

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" bind /tmp/orchestrator-plan-EXAMPLE tax --owner returned-agent-id --attempt 1
```

The retained graph now identifies the actual owner. Claims resolve named filesystem paths to prevent symlink aliases from gaining
duplicate ownership. The helper reads path metadata, not file contents.
Resolutions and binding must match the current owner/attempt, so a delayed
result cannot complete a newer retry. Claims are atomic. Dependent or overlapping tasks
stay blocked until their owner is resolved; unrelated work may continue.

## Hand off implementation and complete the task

The implementer reports stable work and a proposed check plan. Release its scope
with `implemented` so a dependent writer can claim it; keep owner and attempt
provenance. This handoff is not graph completion and carries no check result:

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" resolve /tmp/orchestrator-plan-EXAMPLE tax <<'RESULT'
{"status":"implemented","owner":"current-owner-from-graph","attempt":1,"evidence":"Worker report: tax behavior implemented; proposed final check: python3 -m unittest -q"}
RESULT
```

After all implementations are handed off, perform source review and focused
fixes. If a finding reopens an implemented task, confirm its writer stopped,
resolve it to `pending` with `stopped: true`, and claim a new attempt. Then run
one consolidated, scoped verifier plan against final inputs.
Each useful command runs once. Reuse successful receipts while relevant inputs
are unchanged. After an observed failure, fix the cause and rerun only failed or
affected checks. A narrow diagnostic during implementation is allowed only for
an observed frontend error or backend log failure and must name both. Source
review is not a check; docs-only/cosmetic edits require none unless repository
rules do.

Resolve each task `done` only after final verifier results and required review
evidence exist. Evidence fields record those claims; the helper checks presence,
not truth. Quick requires verifier evidence and omits independent review. Keep
the claim while fixing; bind a new owner only after the previous owner stops.
If reclaiming, preserve attempt provenance. Use `blocked` when a real blocker
prevents implementation or verification.

## Resume after interruption

Keep the returned plan path in the handoff. Load graph first: done and
implemented tasks retain their status and provenance, and running claims retain
their owner. Time passing never releases a
claim. Ask the owner or host for its status; capture current partial changes
through a scout. Retry only after the old owner is confirmed stopped:

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" resolve /tmp/orchestrator-plan-EXAMPLE tax <<'RESULT'
{"status":"pending","owner":"current-owner-from-graph","attempt":1,"stopped":true,"evidence":"Host confirmed prior worker stopped; scout located partial edits"}
RESULT
```

Then claim a new attempt and brief it with the original criteria and partial
work. Reuse completed artifacts; preserve user changes. Graph/claim/resolve
work offline and record history. Native family guards still apply to claims
and resolutions. Keep plan state through final review and handoff; the helper
may clean it up after it is no longer needed. Completion is graph.complete plus
accounted-for acceptance criteria and integration verification where required.
