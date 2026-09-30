# Orchestrator (Codex)

An agent skill that turns the current session into an orchestrator over
`codex exec` processes. It does not do the task itself. It starts a Codex
minion that makes the change and runs the checks, then a read-only Codex
reviewer that reviews the diff. Then it rules on each finding and reports
token usage per role.

It runs only when you invoke it. The host can be Claude Code or Codex. The
[Codex CLI](https://github.com/openai/codex) must be on `PATH`.

## Modes

| Mode | Minion | Reviewer | Use for |
| --- | --- | --- | --- |
| `quick` | `gpt-6-luna`, medium | `gpt-6-luna`, medium | a settled, small change with a light review |
| `fast` | `gpt-6-luna`, medium | `gpt-6-sol`, high | a settled change, such as a mechanical refactor, checked harder |
| `standard` | `gpt-6-sol`, medium | `gpt-6-sol`, high | the default: implementation needs judgment |
| `comprehensive` | `gpt-6-sol`, medium | `gpt-6-astra`, medium | work where a missed defect is expensive |

The profiles in `roles/profiles/` are the source of truth for these values.
To change a model, edit the frontmatter there.

## Installation

Install with the skills CLI:

```bash
npx skills add lulz1337/skills --skill orchestrator-codex
```

Or install it as a Claude Code plugin:

```
/plugin marketplace add lulz1337/skills
/plugin install orchestrator-codex@skills
```

Or copy this folder into the skill directory of your agent harness.

Caveman, a token-metering proxy, is optional. When
`caveman` is on `PATH`, every run is metered through its proxy. Without it,
the skill runs `codex exec` directly.

## Usage

```
/orchestrator-codex standard add a 30% cap to apply_discount with a unit test
$orchestrator-codex quick bump the base image in Dockerfile to node:22-slim
```

The first word selects the mode. Any other first word means `standard`, and
the whole argument is the task.

## What it does

1. **Records a baseline.** It runs `git status --short` before the first run.
2. **Starts cold, self-contained runs.** Each `codex exec` gets the role
   prompt plus a full brief on stdin, with the mode's model, effort, and
   sandbox. The minion has full access. The reviewer is read-only.
3. **Waits without polling.** It uses one blocking wait, because each poll
   resends the whole context.
4. **Reviews every change and rules on the findings.** An accepted finding
   becomes a new cold follow-up run, never a resumed session.
5. **Reports usage.** Input, cached input, and output tokens per role, read
   from the `turn.completed` events.

## Structure

- `SKILL.md`: the entry point, the modes, and what to read first.
- `roles/minion.md`, `roles/reviewer.md`: the role prompts and sandboxes.
- `roles/profiles/`: the model and effort of each role, per mode.
- `references/procedure.md`: the workflow and the exact `codex exec` command.
- `references/examples.md`: complete briefs, commands, and a final report.
- `references/pitfalls.md`: failures from measured runs, and the rule that
  prevents each one.

## License

MIT
