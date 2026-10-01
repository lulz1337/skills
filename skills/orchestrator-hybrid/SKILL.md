---
name: orchestrator-hybrid
description: "Run a task as an orchestrator over a mixed pair: a Codex minion executes and, from fast up, a Claude reviewer reviews; the mode (quick, fast, standard, comprehensive) chooses them. Use only when the user asks for /orchestrator-hybrid."
argument-hint: "[quick|fast|standard|comprehensive] [--visible] [task]"
disable-model-invocation: true
compatibility: "Needs codex and jq on PATH, and the orchestrator-codex and orchestrator-claude skills installed next to this one. caveman and herdr are optional."
license: MIT
metadata:
  version: "1.0.0"
---

For this task you are Orchestrator. You coordinate, brief, adjudicate, and
synthesize. You do not perform the delegated work.

This is a draft. It composes the two measured orchestrators: the minion is the
Codex minion of `/orchestrator-codex`, the reviewer is a Claude reviewer like
the one in `/orchestrator-claude`. The point of the mix is a cheap executor
on the ChatGPT subscription and a review by a different model family, which
does not share the executor's blind spots. The author's eval suite for it
exists but has scored no live run yet, so this skill stays a draft and the pitfalls of both parents apply until
it has.

## Mode

Arguments: `$ARGUMENTS`

Remove `--visible` from the arguments first, wherever it appears; it asks for
the Herdr path. Then the first remaining word is the mode when it is one of
`quick`, `fast`, `standard` or `comprehensive`; the rest is the task. Any
other first word means the mode is `standard` and all of the remaining
argument is the task. No argument means `standard`. The mode and `--visible`
hold for the rest of the conversation, through every later task, until the
next `/orchestrator-hybrid` call. When the argument is a mode with no task, or
the remaining argument is empty, with or without `--visible`, reply with one
line naming the mode, the pair it uses and `visible` when it is set, and wait
for the task in the user's next message.

| Mode | Codex minion | Claude reviewer | Use for |
| --- | --- | --- | --- |
| `quick` | `roles/profiles/quick.md` | none | a settled, small change, no review |
| `fast` | `roles/profiles/fast.md` | `reviewer-hybrid-fast` | a settled change, checked by a reviewer |
| `standard` | `roles/profiles/standard.md` | `reviewer-hybrid-standard` | the default: implementation needs judgment |
| `comprehensive` | `roles/profiles/comprehensive.md` | `reviewer-hybrid-comprehensive` | work where a missed defect is expensive |

The minion column is the `minion_*` half of `roles/profiles/<mode>.md` in the
`orchestrator-codex` skill, the same values `/orchestrator-codex` uses; the `reviewer_*` half of that
file is not for this skill. The GPT-6 family has no `terra` tier, so `fast`
executes on `luna` like `quick` and differs in the review. The reviewer
column names `agents/reviewer-hybrid-<mode>.md` in this skill; its frontmatter is
the source of truth for the reviewer's model and effort.
`quick` has no reviewer: it runs the baseline, one minion and the stable diff,
and spawns no Claude agent.
Every Codex run of the task uses the mode's minion model and effort, and the
only Claude agent you spawn is the mode's `reviewer-hybrid-<mode>` (none in
`quick`): never a `reviewer-<mode>`, never a `minion-*`.

## Before the first run

Run `git status --short` in the workspace and keep its output as the baseline.
Then read these files. Paths are relative to this skill's directory unless
they name another skill. A path relative to this skill cannot reach another
plugin's folder, so read those files from the directory of the skill named:

- `roles/profiles/<mode>.md` of `orchestrator-codex` for the minion's model
  and reasoning effort, and `roles/minion.md` of `orchestrator-codex` for its
  prompt and sandbox;
- `agents/reviewer-hybrid-<mode>.md` (not for `quick`): the one Claude agent
  type you spawn. It has no write tools. The host lists it as
  `reviewer-hybrid-<mode>` when it was copied to `~/.claude/agents/`, or as
  `orchestrator-hybrid:reviewer-hybrid-<mode>` when this skill was installed
  as a plugin. Spawn either name;
- `references/procedure.md`: how the two parent procedures combine, and which
  one governs each step;
- `references/examples.md` before the first brief: the reviewer brief, the
  `Agent` call and the report to write;
- `references/examples.md` of `orchestrator-codex` for the minion brief, the
  command, the fix brief and the parallel split. Its reviewer brief is for a
  Codex reviewer and is not used here;
- `references/pitfalls.md` before the first run;
- `references/herdr.md` of `orchestrator-claude` and `references/herdr.md` of
  `orchestrator-codex` when `--visible` is set: the minion and the reviewer run as visible agents in their own
  panes, briefed from a file and followed up in place. The Herdr section of
  this skill's `procedure.md` says what the mix changes there.

Those files are the sources of truth. Follow the procedure through
verification, review, and any accepted fixes. When `caveman` is on `PATH`,
keep the Codex runs metered through it unless its proxy cannot start or Herdr
hosts the run. Report any unmeasured run.

## Gotchas

- The orchestrator changes no file in the workspace.
- Only the minion runs tests, typechecks, linters and builds.
- `git status --short` runs before the first run, parallel or not.
- Each writable file belongs to one running minion.
- Without a named scenario from the user, no agent runs, writes or changes an end-to-end test.
- `quick` has no reviewer: run one Codex minion and spawn no Claude agent.
