# Orchestrator (Claude)

A Claude Code skill that turns the main session into an orchestrator. It
does not do the task itself. It briefs a minion subagent that makes the
change and runs the checks, then a reviewer subagent that reviews the diff
without changing anything. Then it rules on each finding and reports.

It runs only when you invoke it.

## Modes

| Mode | Minion | Reviewer | Use for |
| --- | --- | --- | --- |
| `quick` | `claude-sonnet-5-5`, medium | `claude-opus-5-5`, medium | a settled, small change with a light review |
| `fast` | `claude-sonnet-5-5`, medium | `claude-opus-5-5`, high | a settled change, such as a mechanical refactor, checked harder |
| `standard` | `claude-opus-5-5`, medium | `claude-fable-5-1`, high | the default: implementation needs judgment |
| `comprehensive` | `claude-opus-5-5`, high | `claude-fable-5-1`, xhigh | work where a missed defect is expensive |

The agent files in `agents/` are the source of truth for these values. To
change a model, edit the frontmatter there.

## Installation

Install it as a Claude Code plugin. The plugin also installs the eight
subagents in `agents/`:

```
/plugin marketplace add lulz1337/skills
/plugin install orchestrator-claude@skills
```

The skills CLI installs only the skill, not the subagents. Copy them
yourself:

```bash
npx skills add lulz1337/skills --skill orchestrator-claude
cp <skill-dir>/agents/minion-*.md <skill-dir>/agents/reviewer-*.md ~/.claude/agents/
```

Without the subagents the skill stops and tells you to install them.

## Usage

```
/orchestrator-claude fast rename OrderLine.qty to quantity across the orders package
/orchestrator-claude comprehensive
```

The first word selects the mode. Any other first word means `standard`, and
the whole argument is the task. A mode with no task sets the mode for the rest
of the conversation and waits for the task.

## What it does

1. **Records a baseline.** It runs `git status --short` before the first
   spawn, so your uncommitted work stays yours.
2. **Delegates with a full brief.** Each minion gets a self-contained brief:
   goal, owned scope, context, evidence, constraints, and the exact checks.
   Independent pieces with separate files run in parallel, up to five.
3. **Runs each check once.** Only the minion runs tests, typechecks, and
   linters. It uses the narrowest target that covers the changed files.
4. **Reviews every change.** The reviewer judges the stable diff against the
   repository's `AGENTS.md`, `CLAUDE.md`, and `CONTEXT.md` files.
5. **Rules on the findings.** It accepts a finding and sends it back to a
   minion as a fix, or it rejects the finding and gives the reason.

## Structure

- `SKILL.md`: the entry point, the modes, and what to read first.
- `agents/`: one minion and one reviewer per mode.
- `references/procedure.md`: the workflow, from brief to final report.
- `references/examples.md`: complete briefs and a final report.
- `references/pitfalls.md`: failures from measured runs, and the rule that
  prevents each one.

## License

MIT
