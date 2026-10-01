---
name: orchestrator-codex
description: "Run a task as an orchestrator over Codex processes: a minion executes and, from fast up, a reviewer reviews; the mode (quick, fast, standard, comprehensive) chooses them. Use only when the user asks for /orchestrator-codex."
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
next `/orchestrator-codex` call. When the argument is a mode with no task, or
the remaining argument is empty, with or without `--visible`, reply with one
line naming the mode, the profile it uses and `visible` when it is set, and
wait for the task in the user's next message.

| Mode | Profile | Use for |
| --- | --- | --- |
| `quick` | `roles/profiles/quick.md` | a settled, small change, no review |
| `fast` | `roles/profiles/fast.md` | a settled change, checked by a reviewer |
| `standard` | `roles/profiles/standard.md` | the default: implementation needs judgment |
| `comprehensive` | `roles/profiles/comprehensive.md` | work where a missed defect is expensive |

Every run of this task uses the model and reasoning effort of the current
mode's profile, and no other. On the host path, every `codex exec` passes
these values, metered through Caveman when it is on `PATH`. On the Herdr
path, every `herdr agent start --kind codex` passes the same values.

## Before the first run

Run `git status --short` in the workspace and keep its output as the baseline.
Then read these files. Paths are relative to this skill's directory:

- `roles/profiles/<mode>.md` for the model and reasoning effort of each role;
- `roles/minion.md` and `roles/reviewer.md` (`quick` runs no reviewer) for
  their prompts and sandboxes;
- `references/procedure.md` for the shared Codex workflow;
- `references/examples.md` before writing the first brief: a complete minion
  brief, a reviewer brief, a fix brief, a parallel split and the final report,
  all for a task like yours;
- `references/pitfalls.md` before the first run: every entry of its main
  table is a failure a measured run produced, and its Herdr section is not
  measured yet;
- `references/herdr.md` when `--visible` is set and the gate in the shared
  `herdr.md` passes: every Codex of this task runs as a visible agent in its
  own pane, briefed from a file and followed up in place. This is the Herdr
  path. Otherwise take the host path: run `codex exec` as the procedure says.
- `references/herdr.md` of the `orchestrator-claude` skill when `--visible`
  is set: the shared Herdr procedure that this skill's `herdr.md` extends.
  A path relative to this skill cannot reach another plugin's folder, so
  install the `orchestrator-claude` plugin and read the file from there.

Those files are the sources of truth. Follow the shared procedure through
verification, review, and any accepted fixes. On the host path, when
`caveman` is on `PATH`, keep every run metered through it unless its proxy
cannot start, and report any bypass. On the Herdr path, report every run as
unmeasured, with the reason "herdr-hosted".

## Gotchas

- The orchestrator changes no file in the workspace.
- Only the minion runs tests, typechecks, linters and builds.
- `git status --short` runs before the first run, parallel or not.
- Each writable file belongs to one running minion.
- Without a named scenario from the user, no agent runs, writes or changes an end-to-end test.
- `quick` has no reviewer: run one minion alone.
