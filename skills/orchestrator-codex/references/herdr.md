# Orchestrating Codex inside Herdr

This file is the Herdr path of `/orchestrator-codex`. The shared Herdr
procedure is `references/herdr.md` of the `orchestrator-claude` skill: the gate, the
layout, the run directory, the prompt-by-file rule, the waiting rules,
blocked handling, the shell-state rules, follow-ups and cleanup apply to
Codex agents too. This file holds what differs when the agents in the panes
are Codex.

The snippets below use `w1:p3` and `w1:p4` for the panes and
`/tmp/orchestrator.Zq8n2c` for the minion's run directory; replace them with
the values your own calls printed.

## Start a Codex agent

The mode's profile stays the source of truth. Read the role's two values
from `roles/profiles/<mode>.md` of this skill in the same call that starts
the agent, and pass them as native Codex arguments after `--`. The minion
reads the `minion_*` keys and gets the full-access sandbox. Replace
`$skill_dir` with this skill's directory:

```bash
profile="$skill_dir/roles/profiles/<mode>.md"
model="$(sed -n 's/^minion_model: //p' "$profile")"
effort="$(sed -n 's/^minion_reasoning_effort: //p' "$profile")"
herdr agent start minion-1 --kind codex --pane w1:p3 -- \
  --model "$model" -c model_reasoning_effort="$effort" \
  --sandbox danger-full-access -a never
```

The reviewer reads the `reviewer_*` keys and gets the read-only sandbox:

```bash
profile="$skill_dir/roles/profiles/<mode>.md"
model="$(sed -n 's/^reviewer_model: //p' "$profile")"
effort="$(sed -n 's/^reviewer_reasoning_effort: //p' "$profile")"
herdr agent start reviewer --kind codex --pane w1:p4 -- \
  --model "$model" -c model_reasoning_effort="$effort" \
  --sandbox read-only -a never
```

`-a never` keeps an unattended agent from stopping at an approval dialog.
The sandbox is the permission, as it is on the host path. `-a` exists only in
interactive `codex`, which is what Herdr starts; `codex exec` rejects it.

## Prompt and wait

Wait with `herdr agent prompt --wait --timeout <ms>`. The one exception is the
resume after the user answers a dialog, which uses
`herdr agent wait --until idle --until done`. Run the prompt as a
background Bash call (`run_in_background: true`) with a tool timeout above
the Herdr timeout. A foreground Bash call stops at 120000 ms by default and at
600000 ms at most, which is shorter than a minion's turn. Redirect stdout and
stderr to absolute paths in the run directory, and print the exit status.
Parallel prompts check each job with its own `wait "$pid"`, as the shared
procedure shows:

```bash
herdr agent prompt minion-1 \
  "Read /tmp/orchestrator.Zq8n2c/prompt.md and carry it out. Write your final report to /tmp/orchestrator.Zq8n2c/final.md and reply only with that path." \
  --wait --timeout 1800000 \
  > /tmp/orchestrator.Zq8n2c/wait.json 2> /tmp/orchestrator.Zq8n2c/wait.err
echo "minion-1 exit=$?"
```

Herdr writes a server error as JSON to stderr and exits with status 1. A
nonzero exit therefore means `wait.err` holds the reason, and `wait.json` is
not a result. When `wait.json` shows `blocked`, show the user the dialog and
stop until they answer. After their answer, wait again, also in the
background:

```bash
herdr agent wait minion-1 --until idle --until done --timeout 1800000 \
  > /tmp/orchestrator.Zq8n2c/wait-resume.json 2> /tmp/orchestrator.Zq8n2c/wait-resume.err
echo "minion-1 exit=$?"
```

## Read the result

A minion writes its report to `final.md` in its run directory, because its
`danger-full-access` sandbox allows the write. `--output-last-message` exists
only for `codex exec` and is not used here.

A reviewer never writes a file. Its read-only sandbox blocks the write, and
with `-a never` the failure goes back to the model, so no report file would
ever appear. Ask the reviewer to reply in its pane, and read the report from
there:

```bash
herdr agent read reviewer --source recent-unwrapped --lines 300
```

When the read cuts the report off, send the reviewer one short prompt that
asks it to repeat only its findings section, and read the pane again.

## Follow up or stop

A follow-up goes to the living agent. Write `follow-up.md` to the run
directory with the file tool, and prompt the agent to read it, with the same
background wait as above. The gain is continuity: the minion keeps the files
it has read and its understanding of the brief, so the follow-up needs no
re-briefing. The gain is not tokens. Codex resends its whole transcript with
every request, so a long-lived minion's follow-up can cost more per request
than a cold start on the host path. Nobody has measured the difference.

Stop an agent with `herdr agent send-keys minion-1 ctrl+c`.

## What a Herdr-hosted Codex run loses

Herdr starts the bare `codex` executable, so `caveman run --off --` cannot
wrap it. A Herdr-hosted Codex run is not metered, and there is no
`events.jsonl` to read `turn.completed` usage from. Report every such run as
unmeasured, with "herdr-hosted" as the reason, the way the host path reports
a `model_provider=openai` bypass. When the task is a cost comparison or an
eval, use the host path, which measures.
