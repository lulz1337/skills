# Orchestrator

Run a task in one main agent loop with an independent review. The main thread
scopes, implements and verifies the change itself. After all writing stops, a
reviewer from the chosen family reviews the final diff. Every file edit after a
review needs a fresh review.

Version 3 replaces orchestrator-claude, orchestrator-codex and
orchestrator-hybrid. An evaluation on the shared 20-case suite found the same
outcome at 2.8× lower cost and 2.4× less time than the delegating
orchestrators: [fold evaluation](https://github.com/lulz1337/.dotfiles/blob/main/agents/evals/FOLD-EVAL-2026-10-26.md).

## Installation

From a clone of this repository:

```bash
python3 orchestrator/install.py
```

The installer copies the skill, the Claude reviewer agents, the Codex reviewer
and critic roles, and the runtime into `~/.agents` and `~/.claude`. It also removes a version 2 installation: the three old skills,
their retired agents and roles, and the session guard with its hooks in Claude
settings and Codex `hooks.json`. Restart Claude Code afterwards.

The skill can also be added with `npx skills add lulz1337/skills --skill
orchestrator` or `/plugin install orchestrator@skills`. The default Codex
reviewer still needs the runtime from the command above. The
[runtime guide](../../orchestrator/README.md) covers prerequisites and tests.

## Usage

```text
/orchestrator fast rename OrderLine.qty to quantity
/orchestrator --claude comprehensive migrate the billing schema
```

The first word selects the mode; otherwise the mode is standard. A mode
without a task sets the mode and waits. Only the exact message
`orchestrator off` clears it.

| Mode | Reviewer | Use for |
| --- | --- | --- |
| `quick` | none | a settled, small change |
| `fast` | fast reviewer | a settled change, checked by a reviewer |
| `standard` | standard reviewer | the default: the change needs judgment |
| `comprehensive` | comprehensive reviewer | a missed defect is expensive |

The default family is hybrid: this thread implements and a Codex run reviews.
`--codex` names the same family. `--claude` uses the Claude reviewer agents.
`--visible` hosts the Codex runs in a Herdr pane.

## Package

- `SKILL.md` — the loop: scope, implement, verify, review, report.
- `references/` — Codex run commands and Herdr hosting.
- `agents/` — the Claude reviewer agents, `reviewer-<mode>`.
- `roles/` — Codex reviewer and critic roles with per-mode profiles.

## License

MIT
