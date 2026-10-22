# Claude coordination examples

## A bare invocation

`/orchestrator-claude fast` selects fast and waits for the task. It dispatches
nothing until actionable work arrives. Quick has no review; the other modes
retain the configured reviewer. Role names and tools are in roles.md and tools.md.

## Discover and brief

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" instructions claude fast
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

After all writers stop, review the final source against the request and
behavioral contracts in fast and higher modes. Resolve accepted findings with
focused edits, then collect a fresh source review. Quick skips independent
review. Once implementation and source review are stable, brief the verifier
with one consolidated, scope-matched command list. It runs each useful command
once and reports exit codes and output. After a final failure, rerun only failed
or affected checks after the focused fix. A shared-code change gets critic;
oracle gets a failure only after a fix failed.

## Codex process or a visible role

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" new claude fast implementer
```

Use the printed absolute run path in `brief <run> <<'BRIEF'` as tools.md shows.
For Codex or read-only Claude roles, invoke `start <run>` and later `report <run> --final`.
For Claude implementer, verifier, runner, browser and publisher, dispatch the
printed agent_type with Agent and the brief.

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
