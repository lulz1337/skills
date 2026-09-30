# Codex orchestration pitfalls

Each entry is a failure that a measured run produced and the rule that
prevents it. The general pitfalls of the `orchestrator-claude` skill apply too;
these are the Codex-specific ones. The Caveman rows apply only when `caveman`
is on `PATH`.

| Pitfall | What happened | Rule |
| --- | --- | --- |
| Polling for a process | Two `sleep 30; check` loops re-sent 90k and 200k tokens of context every 40 seconds for over an hour, more than the minions they waited for (2026-09-23). | One blocking wait with a generous timeout. In a one-shot host, run in the foreground. |
| Ending the turn with a process running | In `claude --print` a background `codex exec` outlived the turn; "waiting for it to complete" became the final report. | Never end a turn while a delegated process runs. |
| The prompt in the command line | The brief was interpolated into a shell string; quoting broke on the first backtick. | Write `prompt.md` with the file tool and feed it on stdin (`- < prompt.md`). The check fails a command that contains `GOAL:`. |
| The wrong profile | The model and effort of another mode, or the defaults, on one of the runs. | Every `codex exec` of the task uses the current mode's four values. The check compares model, effort and sandbox against `profiles/<mode>.md`. |
| Resuming a Caveman-wrapped session | `codex exec resume` could not find the session: Caveman 1.3.4 gives each wrapped command a fresh temporary `CODEX_HOME`. | A follow-up is a new cold run with the role body and a focused brief. Never `resume`, `--last`, `--continue`, `--session`. |
| A silent Caveman bypass | `--config model_provider=openai` made the run work and dropped the metering without a word. | Keep `caveman run --off --`; if it fails, bypass and say so in the report. The check fails an unmeasured run unless the report names the bypass. |
| Running the checks yourself | Every Codex orchestrator ran the unit suite itself 2–3× before the "who runs checks" rule. | The minion runs checks, once, inside its turn. The orchestrator reads `final.md` and the diff. |
| `&&` as parallel | Two runs chained with `&&` were reported as concurrent. | Concurrent means `run a & run b & wait` from one command, or a `for` loop whose body ends in `&`. |
| Transcript reading | The whole `events.jsonl` was loaded into the orchestrator's context to "summarize" it. | Read `final.md`; inspect selected events with `jq`; read the full log only for diagnosis. |
| Ignoring usage | The report gave no token figures, so the mode's cost could not be compared. | Record `turn.completed` usage per run and report input, cached input and output tokens per role. |

## Cost notes

- A cold `codex exec` starts near 21k tokens of system prompt and `AGENTS.md`;
  every tool round-trip resends the whole transcript, so input tokens grow
  with the square of the tool calls. A brief with an exact `SCOPE` and `VERIFY`
  is the first lever; `--config tool_output_token_limit=<n>` the second.
- Codex rows spend ChatGPT subscription quota that the harness cannot meter;
  measure one condition at a time before adding trials.
