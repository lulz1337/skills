# Orchestrating inside Herdr

Herdr is the terminal multiplexer the user runs their agents in. When the
user passes `--visible` and the orchestrator itself runs in a Herdr pane,
every minion and reviewer runs as a visible, interactive agent in a sibling
pane instead of a hidden subagent.
This is the Herdr path; the `Agent` tool is the host path.

This file is the orchestration layer over the `herdr` CLI. The installed
binary's help is the authority for command syntax, as
the `herdr` skill says: read it with `herdr <group>` or
`herdr <group> <command> --help`, and never run bare `herdr`, which opens the
TUI. Every command below exists in `herdr` 0.9.3.

The herdr skill triggers only when the user mentions Herdr. This skill uses
Herdr only when the user asks for it with `--visible` and the gate below
passes. The default is the host path, even inside Herdr: the `Agent` tool
returns reports as data and is the path every eval measures, while the Herdr
path is unscored, costs about ten tool calls per agent, and reads the
reviewer's report from a wrapped pane (the minion writes `final.md`). It earns its place when the user
wants to watch or take over the agents.

The Codex-specific commands are in `references/herdr.md` of the
`orchestrator-codex` skill; everything else here applies
to Codex agents too.

## Gate

Take the Herdr path only when `--visible` is set and this check passes:

```bash
test "${HERDR_ENV:-}" = 1 && herdr status >/dev/null 2>&1
```

When `--visible` is set and this check fails, Herdr is not hosting you. Say
in one line that the Herdr path is unavailable, take the host path the
procedure describes, and run no `herdr` command: controlling a Herdr session
from outside it acts on panes you cannot see. The eval suites run under
`claude --print` with no Herdr, so they exercise the host path only. The
Herdr path is unmeasured. Name the path you used in the final report.

## What the Herdr path changes, and what it does not

The Herdr path changes five things:

- where agents run: one sibling pane per agent, which the user can watch and
  take over;
- how a brief reaches an agent: a file in the run directory, submitted with a
  one-line prompt;
- how you wait: one background `herdr agent prompt --wait` per prompt, never a
  loop;
- how you stop a run: `herdr agent send-keys <name> ctrl+c`;
- what a follow-up gives: continuity. The agent is still alive with its
  context, so a fix brief or a second review round goes to the same agent
  instead of a new one.

It changes nothing else. The roles, the brief shape, who runs checks, the
mode's models and efforts, the baseline, the hands-off rule, the parallel
rules, adjudication and the report are what the procedure says.

## Shell state

Shell variables do not persist from one Bash call to the next, so a variable
set in one call is empty in the next. An empty `$pane` or `$run_dir` does not
fail loudly: the command runs against the wrong target or the wrong path.
Three rules follow:

- print every pane ID and path a command returns (`echo`, or `jq -r` to
  stdout), and write the literal value into every later call;
- keep steps that share a variable in one Bash call;
- never `cd` into a run directory, and use absolute paths instead: the host
  can keep the working directory between calls, and `--cwd "$PWD"` and
  `git status --short` must still point at the workspace.

The snippets below use literal example values, such as `w1:p4` and
`/tmp/orchestrator.k3Qx1a`. Use the values your own commands printed.

## Live agents and names

At most nine agents are live at once, reviewers included. When a review
follows, that leaves at most eight parallel minions. A live agent is one whose
pane is still open, so a minion kept for a follow-up still counts.

Run `herdr agent list` before the first start and pick free names. Name
minions `minion-1`, `minion-2` and so on. Name the reviewer `reviewer`, or
`reviewer-1`, `reviewer-2` and so on when more than one reviewer runs. Names
are unique among live agents and follow the pane occupant.

## Layout

Give each agent its own pane, a sibling in the current tab, with the workspace
as its working directory, and never take the user's focus. Read the shape of
the panes first:

```bash
herdr pane layout --current | jq -c '.result.layout.panes[] | {pane_id, rect}'
```

Split a pane `right` only when its `rect.width` is at least 160 columns, so
each half keeps about 80 columns, which an agent's pane needs to be readable.
Split any narrower pane `down`. `rect.width` from `herdr pane layout` is in
terminal columns.

The first agent splits the calling pane, by the calling pane's shape:

```bash
herdr pane split --current --direction right --cwd "$PWD" --no-focus | jq -r '.result.pane.pane_id'
```

Each further agent splits the largest pane the orchestrator created, by that
pane's own shape, read again with `herdr pane layout --pane w1:p4`:

```bash
herdr pane split w1:p4 --direction down --cwd "$PWD" --no-focus | jq -r '.result.pane.pane_id'
```

Never split the user's pane a second time, and never split the newest pane by
habit: both halve the same pane again and again. Do not create a workspace,
tab or worktree, and do not change the working directory: that topology is
the user's to ask for, and overlapping writers are serialized, not isolated.

## Run directory and brief

Give each agent its own run directory and print its path:

```bash
mktemp -d "${TMPDIR:-/tmp}/orchestrator.XXXXXX"
```

Write `prompt.md` into it with the host's file-writing tool: the role body
below the agent file's frontmatter, a blank line, then the brief in the
procedure's shape. An interactive `claude` does not load the agent file, so
the role body reaches it only through this file. Then ask the agent to read
it. The brief is never the argument of `herdr agent prompt`: a
brief there breaks on the first backtick, lands in shell history, and is what
the Codex pitfall "the prompt in the command line" already forbids.

## Report channel

A minion writes its report to `final.md` in its run directory and replies
with the path only. This deviates on purpose from the herdr skill, which says
not to request file output in the initial prompt. A terminal viewport is
wrapped, scrolled and truncated, and a minion's report carries the
verification evidence the orchestrator must read whole. `final.md` is the
boundary summary, exactly as `--output-last-message` is on the Codex host
path.

A reviewer never writes a file. Its tools have no Write and no Edit, and the
reviewer prompt forbids changing files. Read its report from the pane:

```bash
herdr agent read reviewer --source recent-unwrapped --lines 300
```

When that output is truncated, send one short prompt that asks the reviewer
to repeat only its findings section, and read the pane again.

## Start a Claude agent

The mode's agent file is the source of truth for the model, the effort and
the tools. Read all three from its frontmatter and start the agent in the
same Bash call. Replace `<mode>` with the current mode and `$skill_dir`
with this skill's directory:

```bash
f="$skill_dir/agents/minion-<mode>.md"
model="$(sed -n 's/^model: //p' "$f")"
effort="$(sed -n 's/^effort: //p' "$f")"
tools="$(sed -n 's/^tools: //p' "$f" | tr -d ' ')"
echo "model=$model effort=$effort tools=$tools"
herdr agent start minion-1 --kind claude --pane w1:p4 -- \
  --model "$model" --effort "$effort" --permission-mode bypassPermissions \
  --tools "$tools"
```

`claude --agent <name>` exists and was not adopted: a test run applied the
file's model but listed Bash, Read, Write and Edit without its Glob and Grep,
and reported no effort.

Start a reviewer the same way from `agents/reviewer-<mode>.md`, in
its own pane. Its `tools:` line has no Write and no Edit, so `--tools` leaves
it without editing tools. `--tools` is an allowlist: without it an
interactive `claude` also gets `Agent`, `WebFetch` and every other built-in
tool, which the agent file deliberately leaves out. `claude --help` describes
`--tools` as the built-in set only, so MCP tools configured for the user can
still appear.

Bash still reaches the reviewer and can mutate files; the reviewer prompt
forbids it, as on the host path. This is a behavioral constraint, not a
sandbox.

`agent start` returns when Herdr sees the agent ready for input. If it returns
`agent_not_ready`, read the pane: a first-run confirmation is the user's to
answer, not yours. Show them the text and wait.

## Prompt and wait

Wait with `herdr agent prompt --wait --timeout <ms>`. The one exception is the
resume after the user answers a dialog, which uses
`herdr agent wait --until idle --until done`. Never follow a
prompt with a bare `herdr agent wait`: an agent that is still idle when the
wait starts satisfies it at once, before the turn has begun.

Give a minion 30 minutes (`--timeout 1800000`) and a reviewer 15
(`--timeout 900000`); the timeout includes submission. A foreground Bash call
stops after at most 10 minutes, so run the waiting call with
`run_in_background: true` and a Bash `timeout` above the herdr timeout:
1900000 for a minion, 1000000 for a reviewer. The host wakes the conversation
when the command ends. Capture stdout and stderr in separate files and print
the exit status:

```bash
herdr agent prompt minion-1 \
  "Read /tmp/orchestrator.k3Qx1a/prompt.md and carry it out. Write your final report to /tmp/orchestrator.k3Qx1a/final.md and reply only with that path." \
  --wait --timeout 1800000 \
  > /tmp/orchestrator.k3Qx1a/wait.json 2> /tmp/orchestrator.k3Qx1a/wait.err
echo "minion-1 exit=$?"
```

Parallel minions are prompted from one background Bash call, and each job's
exit status is checked on its own:

```bash
herdr agent prompt minion-1 "Read /tmp/orchestrator.k3Qx1a/prompt.md …" --wait --timeout 1800000 \
  > /tmp/orchestrator.k3Qx1a/wait.json 2> /tmp/orchestrator.k3Qx1a/wait.err & p1=$!
herdr agent prompt minion-2 "Read /tmp/orchestrator.Hd7w2m/prompt.md …" --wait --timeout 1800000 \
  > /tmp/orchestrator.Hd7w2m/wait.json 2> /tmp/orchestrator.Hd7w2m/wait.err & p2=$!
wait "$p1"; echo "minion-1 exit=$?"
wait "$p2"; echo "minion-2 exit=$?"
```

A bare `wait` returns 0 whatever the jobs returned, so it hides a failure.
Never wait with `sleep` and `herdr agent get` in a loop: every iteration
resends your whole context, which is the measured failure the Codex pitfalls
record.

## Read the result

A nonzero exit status means the command failed. `wait.err` then holds the
server's JSON error, and `wait.json` can be empty. On exit 0, read the state
from `wait.json`, then `final.md` for a minion's report or the pane for a
reviewer's.

When the state is `blocked`, the agent is at an approval or question dialog:

```bash
herdr agent read minion-1 --source recent-unwrapped --lines 60
herdr notification show "minion-1 needs input" --body "approval dialog in its pane" --sound request
```

Show the user the dialog text and stop until they answer it in the pane.
Never answer a dialog yourself, not with `agent send-keys` and not with
`agent prompt`. After the user says they answered, resume in a background
Bash call:

```bash
herdr agent wait minion-1 --until idle --until done --timeout 1800000 \
  > /tmp/orchestrator.k3Qx1a/wait-resume.json 2> /tmp/orchestrator.k3Qx1a/wait-resume.err
echo "minion-1 exit=$?"
```

This is the only use of `agent wait`. The `--until` states leave out
`blocked`, so the wait does not return on the dialog the user just closed.

When a minion's `final.md` is missing after `idle` or `done`, read the pane
with `agent read --lines 200` and ask the minion, in one short prompt, to
write the report file. A `timeout` or `agent_prompt_stalled` result does not
prove the prompt was never delivered; inspect `agent get` and the pane before
deciding anything, and do not resend the brief blindly.

The report rules do not change: a report without verification evidence means
verification is missing, and only `git status --short` and `git diff` are
yours to run.

## Stop a bad run

To abort a run that went wrong, interrupt the agent:

```bash
herdr agent send-keys minion-1 ctrl+c
```

This stops the agent's turn and leaves it alive in its pane, ready for a
corrected brief or for closing. Use it only to stop a run, never to answer a
dialog.

## Follow up on the same agent

This is what the Herdr path buys. A fix brief goes to the minion that owns
the files and is still alive in its pane; a second review round goes to the
same reviewer. Write `follow-up.md` to the agent's run directory with the
requirement, the exact accepted finding and its location, the relevant
evidence and the new direction, nothing more, and prompt in a background Bash
call:

```bash
herdr agent prompt minion-1 \
  "Read /tmp/orchestrator.k3Qx1a/follow-up.md and carry it out. Write your report to /tmp/orchestrator.k3Qx1a/final-2.md and reply only with that path." \
  --wait --timeout 1800000 \
  > /tmp/orchestrator.k3Qx1a/wait-2.json 2> /tmp/orchestrator.k3Qx1a/wait-2.err
echo "minion-1 exit=$?"
```

A reviewer's second round asks for a reply, not a file, and is read from the
pane as before. The agent keeps the files it has read. A Codex agent also keeps its system
prompt in its session, but it resends its whole transcript with every request.
The token cost of a follow-up is therefore unmeasured and can exceed a cold
start. The gain is continuity. A follow-up still carries the
whole finding: the agent's memory is a convenience, not a substitute for the
brief.

## Finish

After the final report, close the panes you created, and only those, with the
literal IDs you printed:

```bash
herdr pane close w1:p4
```

Leave a pane open when the user said they want to inspect the agent, and say
so in the report. Remove the run directories with the panes. When the task
took longer than a few minutes, tell the user it is over:

```bash
herdr notification show "Orchestrator: done" --body "<one line of outcome>" --sound done
```

Never close a pane, tab or workspace you did not create, never stop the
server, and never kill the Herdr process.
