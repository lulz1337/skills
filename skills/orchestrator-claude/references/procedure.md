# Claude orchestration procedure

## Roles and briefs

Delegate all task work: the minion agent handles implementation, exploration,
and verification, and the reviewer agent handles review. The orchestrator only
coordinates, checks small pieces of evidence, adjudicates findings, and reports
the result. The skill that loaded this procedure names the two agent types to
spawn; their frontmatter is the source of truth for models, effort, and exposed
tools.

The tool lists reduce accidental mutation and nesting, but do not enforce
either rule: Bash can change files or invoke another agent process. Both agent
prompts prohibit nested delegation, and the reviewer prompt prohibits mutation.
Treat these as behavioral constraints, not sandbox guarantees.

A subagent starts without this conversation, so give it a self-contained brief:

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

Record the original request and `git status --short` first. Existing changes
belong to the user. Give each writable file to one minion at a time and serialize
overlapping scopes. Separate worktrees are optional and only justified when
isolation materially helps and the repository state permits safe integration.

A loaded mode skill does not automatically reach a subagent. Put any required
skill path and mode in `CONSTRAINTS`.

## Parallel agents

Run up to nine agents at once when the task splits into independent pieces. Do
not serialize work only because it is safer or easier to track. Before the
first parallel spawn:

1. Run `git status --short` in the workspace and keep its output as the
   baseline. A parallel spawn never skips this step.
2. For each agent, write down its assignment: one goal, one owned `SCOPE`
   that no running writer shares, and acceptance criteria that it can meet
   alone.
3. For each agent, write down its use case: the result that the task needs
   from it, such as a module implemented, a question answered, or a
   subsystem reviewed.

If you cannot state both, do not spawn the agent. Keep the work with a running
agent or run it later. Good parallel splits are read-only investigation of
separate questions, implementation in disjoint files or packages, and review of
separate subsystems. Serialize a step that needs another step's result, and
writes that touch a shared file. Do not spawn an agent only to fill a slot.

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

## Coordination

On the host path, spawn each agent with the `Agent` tool and run it in the
background. The host notifies you when an agent finishes, so do not poll. Use
the host's message mechanism to add context to a running minion, and its stop
mechanism to abort a bad run. Describe the actual coordination actions in the
final report when they materially affected the outcome.

When `--visible` is set and the gate passes, take the Herdr path that
`herdr.md` describes. It
changes where agents run, how a brief reaches them, how you wait, how you stop
a run and how a follow-up reaches the same agent. It does not change the roles,
the brief shape, who runs checks, the parallel rules, adjudication or the
report.

Compress reports at boundaries: retain relevant files, decisions, evidence,
checks actually run and their results, and unresolved matters, not tool noise.
If an agent reports success without verification evidence, treat verification as
missing.

## Verify, review, and complete

The `quick` mode has no reviewer. After the minion's one verification phase,
capture the stable diff, read the minion's report, and report. Skip the review
brief and every step below that needs a reviewer.

For an accepted finding, brief the fixing minion with the original requirement
and acceptance criteria, the exact finding and affected location, relevant
existing evidence, and the new direction. Do not replay the full historical
brief or unrelated findings.

After all writers finish, the minion runs one verification phase with the
checks its `VERIFY` names, as "Who runs checks" defines. After a fix it reruns
only what failed and what the fix can affect. Wait until writers have stopped,
then capture a stable diff and current status without running any check.
Brief the reviewer with the original request, repository decisions, baseline,
exact stable changes, verification evidence, and anything unverified. The
report guides navigation, but is not proof: the reviewer independently
validates correctness-critical claims against actual sources and the stable
diff.

Adjudicate every review finding against the request and evidence:

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
actually ran, and remaining uncertainty. Claim a token saving only with
measured input, cached input (a subset of input) and output tokens, next to
verification and review outcomes, on comparable tasks.
