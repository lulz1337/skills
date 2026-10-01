# Orchestration pitfalls

Each entry is a failure that a measured run produced, the rule that prevents
it, and the check that catches it. The author's eval suite
scores every one of them.

| Pitfall | What happened | Rule |
| --- | --- | --- |
| Doing the work yourself | The baseline without the skill edited `orders/pricing.py` with an inline `open(..., "w")` script, then reported success. | The orchestrator changes no file in the workspace. Not with Edit, not with a heredoc, not with `sed -i`. A prompt file in a run directory outside the workspace is fine. |
| Running checks from the orchestrator | Before the "who runs checks" rule, every Claude run executed the unit suite from the orchestrator (1–2×), the minion (2–3×) and the reviewer (1–2×): one task, up to seven test runs. | Only the minion runs tests, typechecks, linters and builds, once after the last edit and again only for what failed. The orchestrator reads the report and records `git status --short` and `git diff`. The reviewer judges the diff. |
| The wrong pair | An orchestrator that skims the argument spawns the default pair on a `quick` or `comprehensive` task and still passes every outcome check. | Spawn `minion-<mode>` and `reviewer-<mode>` and nothing else; in `quick`, spawn `minion-quick` alone and no reviewer. Name the mode in the final report. |
| Skipping the baseline before a parallel spawn | In 5 of 6 trials the earlier soft orchestrator went straight to two concurrent minions without `git status --short`; a lost user edit would have had no evidence. | `git status --short` runs before the first spawn, parallel or not. |
| Serializing independent work | Two disjoint changes ran one after the other "to be safe". | Independent pieces with disjoint scopes run together, up to nine. Serialize only a step that needs another's result, or writes to a shared file. |
| Two hands on one file | Two parallel briefs both named `orders/pricing.py`. | Each writable file belongs to one running minion. Name the other minion's files as excluded in each brief. |
| Parallel for its own sake | A single-scope task (one function, one test file) split across two minions. | If you cannot write one goal, one owned scope and acceptance criteria per agent, do not spawn it. |
| The end-to-end temptation | "Make sure the checkout flow still works end to end" made the baseline run `tests/e2e`, which changes orders on staging. | Without a named scenario from the user, no agent runs, writes or changes an end-to-end test. Report the request as an open question. |
| A full test run for a YAML change | A one-line `docker-compose.yml` change triggered the Python unit suite and a typecheck. | Match checks to the changed files: a YAML change gets a YAML or compose validator, or none, and says so. |
| Treating "done" as proof | A minion reported success with no command output. | A report without verification evidence means verification is missing. Send it back. |
| Replaying history | A fix brief carried the whole original brief plus every finding. | A fix brief carries the requirement, the exact finding with its location, the relevant evidence and the new direction. |
| Reporting what did not run | The report said "all tests pass" on a task whose test module did not exist. | State blockers, unverified claims and limits plainly. The check marks a false claim as a hard fail. |
| Touching the user's work | The user's uncommitted edit was in the same file the minion changed. | Existing changes belong to the user. Preserve them, keep them unstaged, never stash, reset or commit. |
| Ponytail pressure | With `/ponytail` active, "code first, shortest diff" invites the orchestrator to write the one-liner itself. | Ponytail governs what the minion builds, not who builds it. Put `ponytail` and its level in the brief's `CONSTRAINTS`; the orchestrator still delegates. |

## Herdr pitfalls

No eval measures the Herdr path (`herdr.md`) yet. The rows below are not
measured failures. They are the failures that the `herdr` skill, the Codex
pitfalls and a review of `herdr.md` predict for it, so each one says what
would happen.

| Pitfall | What would happen | Rule |
| --- | --- | --- |
| Herdr from outside Herdr | `herdr pane split` with `HERDR_ENV` unset acts on a session the orchestrator cannot see. | The gate: `--visible`, `HERDR_ENV=1` and `herdr status`. Otherwise the host path, and no `herdr` command at all. |
| A variable from an earlier call | `$pane` or `$run_dir` is empty in the next Bash call, so the command targets the wrong pane or path without an error. A `cd` into a run directory can outlive its call and move `--cwd "$PWD"` and `git status --short` off the workspace. | Print every ID and path and write the literal value into later calls, or keep dependent steps in one call. Use absolute paths, never `cd`. |
| The brief as the prompt argument | A brief passed to `herdr agent prompt` breaks on the first backtick and lands in shell history. | `prompt.md` in the run directory; the prompt is one line that names it. |
| The viewport as a minion's report | `herdr agent read` returns a wrapped, scrolled, truncated screen, and the verification evidence is cut off. | The minion writes `final.md`. A reviewer writes no file; read its report with `--lines 300` and ask once for the findings section when it is truncated. |
| A foreground wait | A 30-minute `--wait` in a foreground Bash call is stopped after at most 10 minutes. | Run the waiting call with `run_in_background: true` and a Bash timeout above the herdr timeout. |
| A lost error | A failed prompt leaves `wait.json` empty. Without `2> wait.err` its reason is not kept, and a bare `wait` after parallel jobs reports 0 for it. | Capture `> wait.json 2> wait.err` and print each job's exit status with its own `wait "$pid"`. |
| Polling the agent | `sleep 30; herdr agent get` in a loop resends the whole context on every turn. | One background `agent prompt --wait` per prompt; parallel prompts from one call, each job checked with `wait "$pid"`. |
| A bare wait after a prompt | `herdr agent wait` right after a prompt returns on the idle state from before the turn. | Wait with `agent prompt --wait`. Use `agent wait --until idle --until done` only to resume after the user answered a dialog. |
| An unrestricted agent | Without `--tools`, an interactive `claude` gets `Agent`, `WebFetch` and every other built-in tool that the agent file leaves out. | Pass `--tools` with the agent file's `tools:` line, next to its model and effort. |
| Answering a dialog | A `blocked` agent receives `send-keys enter` from the orchestrator. | Read the pane, show the user the dialog, wait for their answer. `send-keys ctrl+c` only stops a bad run. |
| The user's pane | An agent starts in the calling pane, the split takes focus, or the user's pane is split twice. | Own sibling pane per agent, `--cwd "$PWD"`, `--no-focus`; further agents split the largest pane the orchestrator created. |
| A tenth live agent | The reviewer starts while nine minions are still alive. | At most nine live agents, reviewers included: at most eight parallel minions when a review follows. |
| Leftover agents | Minions stay alive after the final report. | Close the panes you created, and only those, after the report. |
| A cold follow-up | A fix brief starts a new agent while the owning minion is still alive. | The follow-up goes to the same agent through `follow-up.md`. |

## Cost notes

- The reviewer's extra effort can cost what a cheaper minion saves: on the
  three-case run of 2026-09-23 the medium-minion, xhigh-reviewer pair cost
  $1.07 against $1.03 for the standard pair. Choose a mode for the review
  depth the task needs, not for price.
- A Claude row on the small fixture costs $0.1–0.5 and grows with the task.
  A precise `SCOPE` and an exact `VERIFY` command save more than any other
  lever.
