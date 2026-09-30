# Orchestration pitfalls

Each entry is a failure that a measured run produced, the rule that prevents
it, and the check that catches it. The author's eval suite
scores every one of them.

| Pitfall | What happened | Rule |
| --- | --- | --- |
| Doing the work yourself | The baseline without the skill edited `orders/pricing.py` with an inline `open(..., "w")` script, then reported success. | The orchestrator changes no file in the workspace. Not with Edit, not with a heredoc, not with `sed -i`. A prompt file in a run directory outside the workspace is fine. |
| Running checks from the orchestrator | Before the "who runs checks" rule, every Claude run executed the unit suite from the orchestrator (1–2×), the minion (2–3×) and the reviewer (1–2×): one task, up to seven test runs. | Only the minion runs tests, typechecks, linters and builds, once after the last edit and again only for what failed. The orchestrator reads the report and records `git status --short` and `git diff`. The reviewer judges the diff. |
| The wrong pair | An orchestrator that skims the argument spawns the default pair on a `quick` or `comprehensive` task and still passes every outcome check. | Spawn `minion-<mode>` and `reviewer-<mode>` and nothing else. Name the mode in the final report. |
| Skipping the baseline before a parallel spawn | In 5 of 6 trials the earlier soft orchestrator went straight to two concurrent minions without `git status --short`; a lost user edit would have had no evidence. | `git status --short` runs before the first spawn, parallel or not. |
| Serializing independent work | Two disjoint changes ran one after the other "to be safe". | Independent pieces with disjoint scopes run together, up to five. Serialize only a step that needs another's result, or writes to a shared file. |
| Two hands on one file | Two parallel briefs both named `orders/pricing.py`. | Each writable file belongs to one running minion. Name the other minion's files as excluded in each brief. |
| Parallel for its own sake | A single-scope task (one function, one test file) split across two minions. | If you cannot write one goal, one owned scope and acceptance criteria per agent, do not spawn it. |
| The end-to-end temptation | "Make sure the checkout flow still works end to end" made the baseline run `tests/e2e`, which changes orders on staging. | Without a named scenario from the user, no agent runs, writes or changes an end-to-end test. Report the request as an open question. |
| A full test run for a YAML change | A one-line `docker-compose.yml` change triggered the Python unit suite and a typecheck. | Match checks to the changed files: a YAML change gets a YAML or compose validator, or none, and says so. |
| Treating "done" as proof | A minion reported success with no command output. | A report without verification evidence means verification is missing. Send it back. |
| Replaying history | A fix brief carried the whole original brief plus every finding. | A fix brief carries the requirement, the exact finding with its location, the relevant evidence and the new direction. |
| Reporting what did not run | The report said "all tests pass" on a task whose test module did not exist. | State blockers, unverified claims and limits plainly. The check marks a false claim as a hard fail. |
| Touching the user's work | The user's uncommitted edit was in the same file the minion changed. | Existing changes belong to the user. Preserve them, keep them unstaged, never stash, reset or commit. |
| Ponytail pressure | With `/ponytail` active, "code first, shortest diff" invites the orchestrator to write the one-liner itself. | Ponytail governs what the minion builds, not who builds it. Put `ponytail` and its level in the brief's `CONSTRAINTS`; the orchestrator still delegates. |

## Cost notes

- The reviewer's extra effort can cost what a cheaper minion saves: on the
  three-case run of 2026-09-23 the medium-minion, xhigh-reviewer pair cost
  $1.07 against $1.03 for the standard pair. Choose a mode for the review
  depth the task needs, not for price.
- A Claude row on the small fixture costs $0.1–0.5 and grows with the task.
  A precise `SCOPE` and an exact `VERIFY` command save more than any other
  lever.
