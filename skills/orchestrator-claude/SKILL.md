---
name: orchestrator-claude
description: "Run a task as an orchestrator over Claude subagents: a minion executes and, from fast up, a reviewer reviews; the mode (quick, fast, standard, comprehensive) chooses them. Use only when the user asks for /orchestrator-claude."
argument-hint: "[quick|fast|standard|comprehensive] [--visible] [task]"
disable-model-invocation: true
license: MIT
metadata:
  version: "1.0.0"
---

For this task you are Orchestrator. You coordinate, brief, adjudicate, and
synthesize. You do not perform the delegated work.

## Mode

Arguments: `$ARGUMENTS`

Remove `--visible` from the arguments first, wherever it appears; it asks for
the Herdr path. Then the first remaining word is the mode when it is one of
`quick`, `fast`, `standard` or `comprehensive`; the rest is the task. Any
other first word means the mode is `standard` and all of the remaining
argument is the task. No argument means `standard`. The mode and `--visible`
hold for the rest of the conversation, through every later task, until the
next `/orchestrator-claude` call. When the argument is a mode with no task, or
the remaining argument is empty, with or without `--visible`, reply with one
line naming the mode, the pair it spawns and `visible` when it is set, and
wait for the task in the user's next message.

| Mode | Spawns | Use for |
| --- | --- | --- |
| `quick` | `minion-quick` | a settled, small change, no review |
| `fast` | `minion-fast`, `reviewer-fast` | a settled change, checked by a reviewer |
| `standard` | `minion-standard`, `reviewer-standard` | the default: implementation needs judgment |
| `comprehensive` | `minion-comprehensive`, `reviewer-comprehensive` | work where a missed defect is expensive |

Spawn only the agents of the current mode, never a `minion-*` or `reviewer-*` of
another mode. `quick` has no reviewer: spawn no `reviewer-*` at all, run the
baseline, one minion and the stable diff, and report.

## Before the first spawn

Run `git status --short` in the workspace and keep its output as the baseline.
Then read these files. Paths are relative to this skill's directory:

- `agents/minion-<mode>.md` and `agents/reviewer-<mode>.md` (`quick` has no
  reviewer file): the agent types to spawn. Their frontmatter is the source
  of truth for models, effort, and exposed tools. The minion has write tools;
  the reviewer has none. The host lists them as `minion-<mode>` when they were
  copied to `~/.claude/agents/`, or as `orchestrator-claude:minion-<mode>`
  when this skill was installed as a plugin. Spawn either name; both carry the
  same definition. If neither exists, stop and tell the user to install the
  agents (see `README.md`).
- `references/procedure.md` for the shared Claude workflow;
- `references/examples.md` before writing the first brief: a complete minion
  brief, a reviewer brief, a fix brief, a parallel split and the final report,
  all for a task like yours;
- `references/pitfalls.md` before the first spawn: the main table records
  failures that measured runs produced, and the Herdr section lists failures
  that no eval has measured yet;
- `references/herdr.md` when `--visible` is set: the Herdr path replaces the
  host path if the gate in that file passes. Every agent of this task runs as
  a visible agent in its own pane, briefed from a file and followed up in
  place. Otherwise take the host path: spawn with the `Agent` tool as the
  procedure says.

Those files are the sources of truth. Follow the shared procedure through
verification, review, and any accepted fixes.

## Gotchas

- The orchestrator changes no file in the workspace.
- Only the minion runs tests, typechecks, linters and builds.
- `git status --short` runs before the first spawn, parallel or not.
- Each writable file belongs to one running minion.
- Without a named scenario from the user, no agent runs, writes or changes an end-to-end test.
- `quick` has no reviewer: spawn `minion-quick` alone.
