# Dependency scheduling and recovery

Adapted from Matt Pocock's to-tickets and implement-spec. Use this for several
slices with real dependencies, an integration step, or a retained plan. A
settled single-scope task follows workflow.md without creating a graph.

A task delivers one complete, independently verifiable behavior and fits a
fresh worker context. Its blockers name only prerequisites that genuinely gate
it. For a wide mechanical refactor, use expand, bounded migration batches and
contract; claim green intermediate states only when the verifier observed them.
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

Graph reports a **frontier**: pending tasks with completed blockers and available
capacity/scope. Claim before dispatch; use the returned task's role, acceptance,
scope and checks in its brief. Every graph-bound implementation brief also
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

## Complete a slice

The implementer reports stable work, then the verifier checks it. In a reviewed
mode, request a fresh reviewer. Resolve only after each acceptance criterion is
supported and accepted findings are fixed. Every fix after review needs new
verification and a fresh reviewer before done, even when only a regression
assertion changes. Keep the claim while fixing; bind the new owner only after
the previous owner has stopped. If you release and reclaim, the new attempt
needs its own verification and review. Earlier review cannot complete it:

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" resolve /tmp/orchestrator-plan-EXAMPLE tax <<'RESULT'
{"status":"done","owner":"current-owner-from-graph","attempt":1,"evidence":"Worker report: each tax criterion accounted for","verification":"Verifier report: python3 -m unittest -q, exit 0","review":"Reviewer: no remaining accepted findings"}
RESULT
```

Quick still requires verifier evidence but omits review. Evidence fields are
coordination assertions: the helper checks their presence, not their truth.
A process exit or implementation report alone does not complete a slice. Use
status blocked with cited evidence when a prerequisite or check prevents
completion. Recompute graph after each resolution; dispatch only its frontier.

## Resume after interruption

Keep the returned plan path in the handoff. Load graph first: done tasks stay
done, and running claims retain their owner. Time passing never releases a
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
