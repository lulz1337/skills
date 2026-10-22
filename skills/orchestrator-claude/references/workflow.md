# Shared workflow

Adapted from Matt Pocock's writing-for-agents and agent-brief guidance.
Family dispatch belongs in procedure.md; role settings come from the runtime.

## 1. Establish the scope

Record the request and run `baseline` before dispatch. Ask a scout for applicable
instructions, CONTEXT.md terms, affected paths and available checks. Reuse
current evidence. Keep the user's explicit output paths and constraints as
acceptance criteria. An explicit user instruction overrides conflicting local
guidance; identify the conflict and follow the authorized request.
Request research or design advice only for an unresolved
question. For a bug, ask the verifier to reproduce the exact reported input
before implementation; distinguish unrelated environment failures. This phase
is done when the owned scope, desired behavior and checks
are known, or a cited blocker explains what is missing.
When the request includes a push, PR, deploy or other external action, a worker
checks the needed credentials during scoping, for example with `gh auth status`.
Send a blocker that only the user can clear, such as a login, a token or an
approval, to the user at once with the exact command, for example
`! gh auth login`. Independent work continues meanwhile.

Accept execution claims only with completed tool receipts. An unattempted lookup
is not an empty result or an access failure. For Codex, read
`report <run> --final`, which prints final.md, each receipt's command and exit
code without output, the execution summary and, for a failed or flagged run, a
stderr tail. Inspect its exit codes and evidence issues, recover a receipt's
output with `report <run> --receipt <id>` when that output is evidence you need,
and recover everything with `--full`. A rejected discovery report gets one
bounded retry; if it still misses its outcome, escalate to oracle for diagnosis,
then resume one source lookup bounded by that diagnosis.

## 2. Brief the owner

Every worker receives one outcome and a bounded brief:

```text
GOAL: current behavior, desired behavior, checkable acceptance criteria
SCOPE: owned paths and exclusions; read-only where applicable
CONTEXT: settled decisions, baseline and pointers to relevant artifacts
EVIDENCE: established facts with source references
QUESTIONS: decisions still reserved for the orchestrator
CONSTRAINTS: applicable instructions, terms and permissions
OUTPUT: changed paths or findings, evidence and remaining uncertainty
VERIFY: exact affected commands and expected outcomes; verifier executes them
```

Include the five-year code-maintainability requirement from roles.md in the
CONSTRAINTS of every brief that writes, reviews or recommends code.
Keep durable requirements in the acceptance criteria. A scout supplies current
paths for dispatch ownership. Workers preserve user edits and one another's
changes. Commits, pushes and external publication require existing authorization.
Use runner for a closed, prescribed command sequence; scout discovers locations.
Integration (commit, push, PR, deploy) starts only after the verifier passes on
the final revision and the required review is done. One runner brief never
combines checks with integration.
Preserve new unrelated files as well as baseline files. A clean baseline and
recent timestamp do not establish ownership or authorize deletion. Verify only
the owned scope; unrelated concurrent edits are not a failed acceptance check.
Scout briefs set VERIFY to read-only evidence collection. Implementer briefs
reserve check execution for the verifier. Briefs must not permit scout or
implementer checks, including one self-check. Repository check requirements
apply to the task; the verifier executes them. Verifier briefs name the exact checks
and exclude unrelated suites. Briefing is done when one owner can satisfy each
criterion within its scope.

## 3. Implement and review the source

Give each writable file to one running worker. For dependent slices or retained state, follow scheduling.md.
Concurrent work needs independent
outcomes and disjoint scopes; honor host capacity, at most nine. Each implementer
returns stable edits and one consolidated, scoped check plan. Do not run checks
during implementation. For dependent slices, record an `implemented` handoff so
a downstream writer can start; it releases ownership without marking the graph
complete or claiming verification. After every writer stops, review the final
source against the request and required behavior/contracts, resolve accepted
findings with focused edits, and collect fresh source review. This phase ends
when all scoped implementation and source fixes are stable.

For independent Codex or read-only Claude runs, use one `start-many <run-a> <run-b> --capacity 2`
call. It waits for every execution and reports each exit code. Writable batches
require `--plan <plan>` with matching active claims; use scheduling.md.
Separate foreground `start` calls are sequential even if requested in the same
model response. For writable Claude roles and publisher use independent Agent
calls with background dispatch in an interactive host, then collect every result. Only claim concurrency when
execution intervals overlap; an unavailable concurrent host is a stated limit.

## 4. Final verification

Only after all writers and source review/fixes are complete, the verifier runs
the consolidated check plan once against final inputs and reports commands,
exit codes and relevant output. Run each useful command once; add no checks
beyond task scope or repository requirements. Preserve a successful receipt
while its relevant source, tests, configuration, dependencies and environment
inputs are unchanged. After an observed final failure, make a focused fix and
rerun only failed or affected checks. An observed frontend error or backend log
failure may justify one named, narrowly scoped diagnostic during implementation;
record the error and diagnostic explicitly. Local/source-only review is not a
check. Docs-only and cosmetic edits need no checks unless repository rules do.
Choose YAML/Compose validation for configuration changes;
run Python unit tests or typechecks only when the changed code or a repository
rule requires them. Apply repository rules to the paths and conditions they
name; a rule for orders/ or tests/ does not apply to docker-compose.yml.
Explicit user constraints take precedence. An
end-to-end test needs an exact user-requested scenario and permitted environment.
Without both, keep it out of every brief and VERIFY plan; do not ask a worker
to run it, even to show that it skips.
Re-check the exact reproduced input after a fix.
Send failed checks to the implementer; use oracle after a failed fix attempt.

Quick has no independent reviewer. Other modes use a fresh source reviewer
before final verification to inspect the stable diff against the request,
baseline and required behavior/contracts; the author's narrative is optional.
Add critic for shared code, CI, auth or money. Reviewers and critics do not run
checks. Resolve factual disputes
through workers; adjudicate each finding against scope and cited evidence.
Decide each finding on its own: accept it with a reason, reject it with a
reason, or settle the fact through a worker. Check each accepted fix against
earlier accepted fixes and user-approved decisions.
Final completion requires observed verifier results and required review
evidence. A material fix after final verification invalidates affected receipts;
rerun only affected checks and refresh source review. Do not replace factual
review with heading, word-count or keyword checks.
When the second review of the same slice still reports a blocking finding, stop
the fix loop. Give oracle the findings and fix history to find a cause, and tell
the user that the slice is stuck, with the open findings.

## 5. Report

Wait for every started worker before the final response. Use foreground dispatch in a one-shot CLI controller. If a worker was already
started in the background, collect its runtime `report` or Agent TaskOutput when available;
the controller cannot rely on receiving a later conversation turn.
Use completion notifications or the host's blocking wait in interactive hosts. Answer status from
existing coordination state. For a completed task, state changed behavior,
verification actually run, review disposition and material uncertainty.
A report claims that something works only with evidence from the path the user
uses: a live run, the deployed environment, or a test that exercises that path.
Static checks (typecheck, lint, unit tests, review) support only "checks pass".
The report names what nobody observed. Use at
most 120 words in quick or 180 in other modes unless detail was requested.
Explain rejected findings briefly. Keep raw reports and token tables in the
coordination record; give at most one aggregate usage line. A blocked task needs
cited evidence and the smallest next action. Completion requires every requested
acceptance criterion to be accounted for; unresolved criteria stay explicit.
Before reporting, account for each requested criterion, final verifier result,
final revision review and outstanding worker. Use `summary <run-a> <run-b> ...`
for all Codex run counts and usage, including unsuccessful runs. Cached tokens
are part of input tokens; do not add them again. Keep Claude usage separate and
do not infer a cost from tokens. Missing telemetry stays unmeasured.
