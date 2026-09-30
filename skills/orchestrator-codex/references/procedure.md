# Codex orchestration procedure

## Roles and briefs

Delegate all task work: a `minion` handles implementation, exploration, and
verification, and a `reviewer` handles review. The orchestrator only coordinates,
checks small pieces of evidence, adjudicates findings, and reports the result.

Every fresh process starts without this conversation. Combine the applicable
role-definition body with a self-contained brief:

```text
GOAL:        the exact assigned task and its acceptance criteria
SCOPE:       owned files or directories, plus explicit exclusions
CONTEXT:     relevant decisions and baseline state
EVIDENCE:    relevant established facts and results, each with its source
QUESTIONS:   unresolved questions that affect the task
CONSTRAINTS: repository rules, applicable CONTEXT.md terms, and permissions
OUTPUT:      concise evidence and path:line references
VERIFY:      the narrowest affected checks that demonstrate completion
```

Keep `VERIFY` proportional to the changed scope. Name affected test files,
packages, workspaces, lint paths, or typecheck targets when the tooling supports
them. Do not default to a full-repository check.

Reuse current relevant evidence instead of restarting investigation by default.
Recheck when a source changed, evidence is weak or conflicting, or a question is
correctness-critical. Never omit mandatory repository or context instructions.

Record the original request and `git status --short` before delegation. Existing
changes belong to the user. Give each writable file to one minion at a time and
serialize tasks whose ownership overlaps. Use separate worktrees only when
isolation materially helps and the repository state permits safe integration;
they are optional, not the default.

## Parallel processes

Run up to five processes at once when the task splits into independent pieces.
Do not serialize work only because it is safer or easier to track. Before the
first parallel start:

1. Run `git status --short` in the workspace and keep its output as the
   baseline. A parallel start never skips this step.
2. For each process, write down its assignment: one goal, one owned `SCOPE`
   that no running writer shares, and acceptance criteria that it can meet
   alone.
3. For each process, write down its use case: the result that the task needs
   from it, such as a module implemented, a question answered, or a
   subsystem reviewed.

If you cannot state both, do not start the process. Keep the work with a running
process or run it later. Good parallel splits are read-only investigation of
separate questions, implementation in disjoint files or packages, and review of
separate subsystems. Serialize a step that needs another step's result, and
writes that touch a shared file. Do not start a process only to fill a slot.

Give each parallel process its own run directory. Wait for all of them with one
blocking wait, never with a polling loop.

## Who runs checks

The minion is the only role that runs tests, typechecks, linters and builds.
The orchestrator runs none of them: it reads the minion's report, records the
stable diff with `git status --short` and `git diff`, and sends a doubtful
claim back to the minion instead of checking it itself. The reviewer runs none
of them either; it judges the diff and the code and reports a doubtful claim as
unverified. One task therefore runs each check once, plus a rerun of what
failed.

Every `VERIFY` names checks that match the changed files. A Dockerfile, YAML,
Markdown or config change gets that file type's validator or linter when the
repository has one, and no typecheck and no unit tests. A code change gets the
narrowest typecheck, lint and test target that covers the changed modules. A
full-repository check is named only when the repository mandates it or no
targeted command exists.

End-to-end tests are out of scope unless the user asked for them and the brief
names the exact scenario: which flow, which fixture, which assertion. Without
that, an agent that runs, writes or changes an end-to-end test spends the
budget on the wrong thing and can act against live services. When a task seems
to need one, report the need as an open question and stop there.

## Start and track a process

Use an explicit working directory. Create a unique temporary run directory and
write the combined prompt to `prompt.md` with the host's file-writing tool; do
not interpolate prompt text into a shell command. Keep these files per attempt:

- `events.jsonl`: the machine-readable event stream;
- `final.md`: only the agent's final response;
- `stderr.log`: diagnostics.

Build the command from the selected profile and role definition. The
examples wrap `codex exec` in `caveman run --off --`, which meters token spend
through the Caveman proxy. When `caveman` is not on `PATH`, drop that prefix
and run `codex exec` directly; everything else stays the same:

```bash
caveman run --off -- codex exec \
  --skip-git-repo-check \
  --json \
  --output-last-message "$run_dir/final.md" \
  --cd "$working_dir" \
  --model "$model" \
  --config model_reasoning_effort="$reasoning_effort" \
  --config sandbox_mode="$sandbox" \
  - < "$run_dir/prompt.md" > "$run_dir/events.jsonl" 2> "$run_dir/stderr.log"
```

Run it in the background only when the host will wake this same conversation
when the process ends, as an interactive Claude Code session does. A one-shot
run (`claude --print`, a CI job, another agent's subprocess) has no later turn:
a background process there outlives the turn, its result is never read, and
"waiting for it to complete" becomes the final report. In that case run the
command in the foreground with a timeout and wait for it. Never end a turn
while a delegated process is still running, and never wait by polling: a loop
of `sleep 30; check` costs one full-context request per check. Measured on
2026-09-23 in a Codex-hosted orchestration, two such loops re-sent 90k and
200k tokens of context every 40 seconds for over an hour, more than the
minions they were waiting for. One blocking wait with a generous timeout is
the only acceptable form of waiting.
`caveman run --off --` starts the local proxy when needed and meters the run
byte-safe: on Codex the compression saved nothing in every measured run, and
the output shrink once cut the orchestrator's own tool output, so metering
is all we take from it.
If that fails, add `--config model_provider=openai`; this bypasses Caveman, so
record and report the bypass.

Read the `thread.started` event from `events.jsonl` and record its `thread_id`
with the role, ownership, working directory, baseline, and log paths. For
example, when `jq` is available:

```bash
jq -r 'select(.type == "thread.started") | .thread_id' "$run_dir/events.jsonl"
```

Use `final.md` for the normal boundary summary. It must retain relevant files,
decisions, evidence, checks actually run and their results, and unresolved
matters. Inspect selected JSON events or `stderr.log` for lifecycle and failure
evidence. Read the full event log only when diagnosis needs it; do not load a
whole transcript merely to compress it. Keep the run directory through review,
then remove it when its evidence is no longer needed.

## Measure every run

Codex resends the whole transcript on every tool round-trip, so one run's
input tokens grow with the square of its tool calls: a cold `codex exec` starts
near 21k tokens of system prompt, skill catalogue and `AGENTS.md`, and every
later request carries all of that plus every tool result so far. Measured runs
average 100k–140k input tokens per request, about 96% of them cache reads.
Record each run's usage from the `turn.completed` event and put the per-role
totals in the final report:

```bash
jq -c 'select(.type == "turn.completed") | .usage' "$run_dir/events.jsonl"
```

Report `input_tokens`, `cached_input_tokens` (a subset of input) and
`output_tokens` per run and in aggregate. Three levers reduce the bill, in this
order, and each one is a tradeoff to name when used:

- fewer, larger tool calls: a brief with a precise `SCOPE` and the exact
  `VERIFY` commands saves more than any flag;
- `--config tool_output_token_limit=<n>` caps how much of each command output
  enters the transcript, so one verbose test run does not ride along in every
  later request;
- `--config model_auto_compact_token_limit=<n>` compacts the transcript once
  it passes `n` tokens, at the cost of detail the minion may still need.

Do not resend evidence the minion already has. Review is not a lever: every
change goes to the reviewer, because the tests a minion wrote cannot vouch for
the minion.

## Follow up or stop a process

Codex processes cannot receive mid-flight messages. Stop a bad background
process with the host's process-control tool.

Do not resume a session. Under Caveman it is impossible: Caveman
1.3.4 gives every wrapped Codex command a fresh temporary `CODEX_HOME` and
removes it afterward, so the next wrapper cannot find the recorded session.
Instead, write a self-contained cold follow-up that includes the role-definition
body, original requirement and acceptance criteria, the exact accepted finding
and affected location, relevant existing evidence, and the new direction. Do not
replay the full historical brief or unrelated findings. Launch it the same
way as the first run, with the same explicit role settings:

```bash
caveman run --off -- codex exec \
  --skip-git-repo-check \
  --json \
  --output-last-message "$run_dir/final-2.md" \
  --cd "$working_dir" \
  --model "$model" \
  --config model_reasoning_effort="$reasoning_effort" \
  --config sandbox_mode="$sandbox" \
  - < "$run_dir/follow-up.md" \
  > "$run_dir/events-2.jsonl" 2> "$run_dir/stderr-2.log"
```

Record the new `thread_id`; this is a new session, not a continuation. Never use
`resume`, `--last`, or nonexistent `--continue` and `--session` options in this
workflow.

## Verify, review, and complete

After all writers finish, the minion runs one verification phase with the
checks its `VERIFY` names, as "Who runs checks" defines. After a fix it reruns
only what failed and what the fix can affect. Wait until writers have stopped,
then capture a stable diff and current status without running any check.
Brief the reviewer with the
original request, repository decisions, baseline, exact stable changes,
verification evidence, and anything unverified. The report guides navigation,
but is not proof: the reviewer independently validates correctness-critical
claims against actual sources and the stable diff.

Adjudicate each review finding against the request and evidence:

- send accepted findings to a minion that owns the affected files;
- explain why any rejected finding is incorrect, unsupported, out of scope, or
  only a preference;
- rerun affected verification after fixes;
- request another review when fixes are material or could introduce new defects.

Completion means the requested outcome is present, relevant verification has
passed or its limitation is explicit, and no accepted review finding remains
unresolved. A blocker is missing authority, required user input, unavailable
infrastructure, or a reproducible failure that prevents safe progress. Report
its evidence and the smallest next action; do not add arbitrary approval gates.

Report what changed, the review outcome and adjudication, verification that
actually ran, remaining uncertainty, and, when Caveman is in use, whether it
measured every run.
When evaluating context economy later, compare aggregate input tokens, cached
input tokens (a subset of input), and output tokens alongside verification and
review outcomes on comparable tasks. Claim no savings without that evidence;
do not add a collector or benchmark task now.
