# Codex reviewer

Use this path for the hybrid and `--codex` families. The runtime helper
`~/.agents/orchestrator-runtime.py` creates, starts and reads each run. Run
one helper call per command, without a pipe, and use the literal run path that
`new` prints. Every helper call runs in the foreground: `start` and
`start-many` block until the Codex run ends and then print its summary. Never
run them in the background, never poll for a result with `sleep`, `until` or
`pgrep` (a `pgrep -f orchestrator-runtime` matches the polling shell itself
and never ends), and never read a background task file to collect a run.

## Dispatch

1. Once per session, before the first run, load the resolved settings:

   ```bash
   python3 "$HOME/.agents/orchestrator-runtime.py" instructions hybrid standard
   ```

2. Create one run per role. Use the selected mode in place of standard, and
   path and the resolved model, effort and sandbox; name that model in the
   report.

   ```bash
   python3 "$HOME/.agents/orchestrator-runtime.py" new hybrid standard reviewer
   ```

3. Write the step 4 brief with a quoted heredoc:

   ```bash
   python3 "$HOME/.agents/orchestrator-runtime.py" brief /tmp/orchestrator-EXAMPLE <<'BRIEF'
   GOAL: ...
   SCOPE: ...
   CONTEXT: ...
   EVIDENCE: ...
   QUESTIONS: ...
   CONSTRAINTS: ...
   OUTPUT: ...
   BRIEF
   ```

   In CONTEXT, say that the main thread wrote the change and ran the listed
   checks. Tell the run to validate correctness-critical claims against the
   stable diff itself.

4. Start the run with `dangerouslyDisableSandbox: true` on the Bash call.
   Codex cannot start inside the Claude sandbox; the run applies its own
   read-only sandbox.

   ```bash
   python3 "$HOME/.agents/orchestrator-runtime.py" start /tmp/orchestrator-EXAMPLE
   ```


5. Read the result. The reviewer is read-only: never tell it
   to write a file.

   ```bash
   python3 "$HOME/.agents/orchestrator-runtime.py" report /tmp/orchestrator-EXAMPLE --final
   ```

6. Before the report, sum the usage of every run once:

   ```bash
   python3 "$HOME/.agents/orchestrator-runtime.py" summary /tmp/orchestrator-A /tmp/orchestrator-B
   ```

   Report Codex usage as tokens, separate from Claude usage. Never convert it
   to dollars.

A fresh review is a new run from step 2, not a follow-up prompt to the old run.

## Failures

| Failure | Rule |
| --- | --- |
| `new` or `start` fails: codex missing, no live model catalog, no login | Report it as a blocker with the exact command and the error. Do not switch to a Claude reviewer silently; offer `--claude`. |
| The model comes from `profiles/<mode>.md` | The `reviewer_*` lines of a profile do not select this reviewer. Use the model that `new` prints. |
| A model name such as `gpt-6-terra` | There is no GPT-6 terra. Pass no model; the runtime resolves it. |
| A nonzero exit from `start` or `start-many` | Keep the status and the error. A failed run is not a review; the review stays open. |
