# Orchestrator (Hybrid)

An agent skill that turns the current session into an orchestrator over a
mixed pair. It does not do the task itself. It starts a Codex minion that
makes the change and runs the checks, then a Claude reviewer subagent that
reviews the diff without changing anything. Then it rules on each finding
and reports. A reviewer from another model family does not share the
minion's blind spots.

It runs only when you invoke it. The host is Claude Code, because the
reviewer is a Claude subagent. The [Codex CLI](https://github.com/openai/codex)
must be on `PATH`.

This skill is a draft. The author's eval suite for it exists but has scored
no live run yet.

## Modes

| Mode | Minion | Reviewer | Use for |
| --- | --- | --- | --- |
| `quick` | `gpt-6-luna`, medium | none | a settled, small change, no review |
| `fast` | `gpt-6-luna`, medium | `claude-opus-5-5`, high | a settled change, checked by a reviewer |
| `standard` | `gpt-6-sol`, medium | `claude-fable-5-1`, medium | the default: implementation needs judgment |
| `comprehensive` | `gpt-6-sol`, medium | `claude-fable-5-1`, high | work where a missed defect is expensive |

The minion values come from the `minion_*` keys of the profiles in the
`orchestrator-codex` skill. The reviewer values come from the agent files in
`agents/`. To change a model, edit the frontmatter there.

## Installation

This skill carries no copy of the Codex roles and profiles. It reads them,
and the shared procedures, from the `orchestrator-codex` and
`orchestrator-claude` skills, so install those two as well.

Install it as a Claude Code plugin. The plugin also installs the three
reviewer subagents in `agents/`:

```
/plugin marketplace add lulz1337/skills
/plugin install orchestrator-hybrid@skills
/plugin install orchestrator-codex@skills
/plugin install orchestrator-claude@skills
```

The skills CLI installs only the skills, not the subagents. Copy them
yourself:

```bash
npx skills add lulz1337/skills --skill orchestrator-hybrid
npx skills add lulz1337/skills --skill orchestrator-codex
npx skills add lulz1337/skills --skill orchestrator-claude
cp <skill-dir>/agents/reviewer-hybrid-*.md ~/.claude/agents/
```

Caveman, a token-metering proxy, is optional. When `caveman` is on `PATH`,
every Codex run is metered through its proxy.

## Usage

```
/orchestrator-hybrid standard add a 30% cap to apply_discount with a unit test
/orchestrator-hybrid fast --visible rename calc_total to order_total
```

The first word selects the mode. Any other first word means `standard`, and
the whole argument is the task. A mode with no task sets the mode for the rest
of the conversation and waits for the task. The mode and `--visible` hold
until the next `/orchestrator-hybrid` call.

Inside the Herdr terminal multiplexer, `--visible` runs the minion and the
reviewer each in its own pane. The default is the host path, even inside
Herdr.

## What it does

1. **Records a baseline.** It runs `git status --short` before the first run.
2. **Starts a cold Codex minion.** The run gets the Codex minion prompt plus
   a full brief, with the mode's model and effort.
3. **Reviews from fast up.** A Claude reviewer judges the stable diff and is
   told that the minion was a Codex process. `quick` has no reviewer.
4. **Rules on the findings.** An accepted finding becomes a new cold Codex
   run. A rejected finding gets the reason.
5. **Reports usage.** Codex minion tokens and the reviewer's token total,
   separately.

## Structure

- `SKILL.md`: the entry point, the modes, and what to read first.
- `agents/`: one Claude reviewer per mode from `fast` up.
- `references/procedure.md`: which parent procedure governs each step.
- `references/examples.md`: the reviewer brief, the `Agent` call, and a
  final report.
- `references/pitfalls.md`: the failures only the mix can produce.

## License

MIT
