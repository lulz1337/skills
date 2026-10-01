# Hybrid orchestration procedure

`/orchestrator-hybrid` runs the Codex procedure for everything the minion
does and the Claude procedure for everything the reviewer does. This file
does not repeat either; it says which one governs each step and what the mix
changes. Read the two parents:

- `references/procedure.md` of the `orchestrator-codex` skill (Codex);
- `references/procedure.md` of the `orchestrator-claude` skill (Claude).

Where the two agree, which is most of the text, there is one rule. The brief
shape, the baseline, the ownership rule, the parallel rules, who runs checks,
the end-to-end prohibition, adjudication and completion are identical in both
and apply as written.

## Step by step

| Step | Governed by | What the mix changes |
| --- | --- | --- |
| Mode and baseline | this skill's `SKILL.md` | the pair is `minion_*` of `roles/profiles/<mode>.md` plus `reviewer-hybrid-<mode>`; `quick` has the minion alone |
| Minion brief | Codex: `prompt.md` is the body of `roles/minion.md` of `orchestrator-codex` plus the brief | nothing |
| Minion run | Codex: `caveman run --off -- codex exec …` with the mode's minion model, effort and `danger-full-access`, `final.md` through `--output-last-message` | the `reviewer_*` values of the profile are never used |
| Parallel minions | Codex: several runs started in the background from one command, one blocking `wait` | nothing |
| Measurement | Codex: `turn.completed` usage per minion run; Claude: the token total in the `Agent` result | on the Herdr path, see "Inside Herdr" |
| Stable diff | both: `git status --short` and `git diff`, no checks | nothing |
| Reviewer brief | Skipped in `quick`. Otherwise Claude: the `Agent` tool with `subagent_type: reviewer-hybrid-<mode>` and the reviewer brief from this skill's `examples.md` | the brief says the minion was a Codex process and the verification evidence comes from its `final.md`; the reviewer validates correctness-critical claims against the stable diff |
| Adjudication | both | nothing |
| Fix brief | Codex: a new cold run with the role body and a focused `follow-up.md`, never `resume` | nothing |
| Second review | Claude: a new `reviewer-hybrid-<mode>` agent with the fix and the new stable diff | nothing |
| Report | both | name the mode, both models with their efforts, minion usage, the reviewer's token total, and whether every Codex run was measured |

## Inside Herdr

With `--visible` set and the gate passing, the shared Herdr procedure in
`orchestrator-claude/references/herdr.md` applies to both agents. The minion
is started as the Codex side of `orchestrator-codex/references/herdr.md`
describes, from the profile's `minion_*` values. The reviewer is started as a
Claude agent from the `reviewer-hybrid-<mode>.md` frontmatter, with
`--tools` set to the frontmatter's read-only tools. `examples.md` shows both
start commands.

- Reports: the minion writes `$run_dir/final.md`. The reviewer writes no
  file, because it has no write tools and its prompt forbids mutating files
  through Bash. Read its report with
  `herdr agent read reviewer --source recent-unwrapped --lines 300`. If the
  report is truncated, send one short prompt that asks the reviewer to repeat
  only its findings section.
- Waiting: wait with `herdr agent prompt <name> "…" --wait --timeout <ms>`.
  The one exception is the resume after the user answers a dialog, which uses
  `herdr agent wait --until idle --until done`. Run the prompt as a background
  Bash call with `> wait.json 2> wait.err`. A foreground Bash call stops at 2
  or 10 minutes.
- Shell variables do not persist between Bash calls. Print the pane IDs and
  the run directory, and reuse them literally.
- A fix brief goes to the living minion, and a second review to the living
  reviewer.
- Usage: the minion is unmeasured, herdr-hosted. The reviewer's usage is not
  recorded. Report both so.

## Why a Claude reviewer for a Codex minion

The tests a minion writes cannot vouch for the minion, and a reviewer of the
same family tends to share its assumptions about what a function is for. A
reviewer from the other family reads the diff without those assumptions. That
is the hypothesis this draft exists to test; until the hybrid eval suite
scores a live run against `/orchestrator-codex` on the shared cases, it is a
hypothesis.
