# Hybrid coordination examples

## A bare invocation

`/orchestrator-hybrid fast` selects fast and waits for the task. It dispatches
nothing until actionable work arrives. Quick has no review; the other modes
retain the configured reviewer. Role names and tools are in roles.md and tools.md.

## Discover and brief

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" instructions hybrid fast
```

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" baseline
```

Dispatch scout with this self-contained brief in a runtime-created run
for either Claude or Codex:

```text
GOAL: Locate order_total and all call sites; identify applicable instructions and narrow verification commands.
SCOPE: Read-only discovery of orders/ and tests/; no writes or check execution.
CONTEXT: The user requested renaming calc_total to order_total. Preserve baseline changes.
EVIDENCE: The baseline is the recorded status output; no code fact is established yet.
QUESTIONS: Report missing paths or conflicting vocabulary; do not choose an API redesign.
CONSTRAINTS: Read AGENTS.md, CLAUDE.md and every covering CONTEXT.md. Use CodeGraph if indexed.
OUTPUT: path:line locations, mandatory rules, affected check commands; at most 250 words.
VERIFY: Confirm each location against source. Do not run tests, lint or builds.
```

Decide the exact edit from scout evidence, then brief implementer with its owned
files, accepted names, acceptance criteria and exclusions. Say explicitly that
other workers and the user's existing edits must be preserved. Independent
files can be implemented concurrently; overlapping writes run sequentially.

When implementer finishes, brief verifier with the exact affected commands and
expected exit code 0. A failing command returns its exit code and relevant error
lines. Implementer fixes an accepted defect; verifier reruns the affected check.
Do not ask implementer, reviewer or the main thread to rerun it too.

In fast and higher modes, brief a fresh reviewer with the request, baseline,
implementation report, verifier evidence and source paths. The reviewer captures
the stable diff itself. Accept concrete failures and explain rejected findings.
A shared-code change gets critic; oracle gets a failure only after a fix failed.

## Codex process or a visible role

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" new hybrid fast implementer
```

Use the printed absolute run path in `brief <run> <<'BRIEF'` as tools.md shows.
For Codex roles, including the reviewer, and for read-only Claude roles,
invoke `start <run>` and later `report <run> --final`. For the Claude implementer
(`worker-hybrid-<mode>`), runner and publisher, dispatch the printed
agent_type with Agent and the brief.

For --visible, invoke `visible`, then `pane layout` and `pane split --direction
right`. Use the returned pane ID in `start <run> --pane w1:p4`, and invoke
`prompt <run>` with background execution and completion notification. Read
`report <run> --final` for a writable role or `read-pane <run>` for a read-only role.
These are separate runtime calls, not shell pipelines. Replace example paths
and pane IDs with the literal returned values.

## Report

Changed the named behavior in the assigned files. Verification: the named
checks passed, with the verifier's evidence. Review: no unresolved accepted
finding (or skipped in quick). State any unverified platform and any Caveman
bypass or Herdr-hosted unmeasured run. Do not paste full reports or claim a
result while a worker is pending.

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
