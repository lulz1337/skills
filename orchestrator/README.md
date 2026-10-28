# Orchestrator runtime

This bundle supplies the [orchestrator skill](../skills/orchestrator/): the
installer, the Codex run runtime and its free tests. It runs without the
author's dotfiles checkout.

## Install from this repository

Use Python 3.10 or newer on Linux or macOS. The default and `--codex` reviewers
need the `codex` CLI, authenticated. `--claude` needs only Claude Code. Herdr is
optional and used only with `--visible`.

From the repository root:

```bash
python3 orchestrator/install.py
```

The installer copies:

| Source | Destination |
| --- | --- |
| `skills/orchestrator/` | `~/.agents/skills/orchestrator`, `~/.claude/skills/orchestrator` |
| `skills/orchestrator/agents/*.md` | `~/.claude/agents/` |
| `skills/orchestrator/roles/` | `~/.agents/codex-agents/` |
| `orchestrator/orchestrator-runtime.py` | `~/.agents/orchestrator-runtime.py` |

It also removes a version 2 installation: the orchestrator-claude, -codex and
-hybrid skills, their retired agents and roles, `~/.agents/orchestrator-guard.py`
and the guard handlers in `~/.claude/settings.json` and Codex `hooks.json`.
Other hooks, skills and agents stay. Restart Claude Code afterwards.

If another checkout manages a destination through a symlink, update that
checkout; the installer refuses to write or delete through a symlink and
changes nothing. `--home <directory>` installs into a separate home;
`--codex-home <directory>` selects a separate Codex configuration directory.

## Runtime

`orchestrator-runtime.py` creates, starts and reads Codex reviewer and critic
runs: `instructions`, `new`, `brief`, `start`, `report <run> --final` and
`summary`. The skill's [Codex reference](../skills/orchestrator/references/codex.md)
lists the exact commands. The reviewer and the critic use Sol at high effort in
every reviewed mode. The runtime resolves the newest account-visible model in
that tier through `model/list` and falls back to the profile model when the
check fails, saying so in `model_source`.

## Verification

```bash
python3 -m unittest discover -s orchestrator/tests
```

The tests use stub processes and disposable homes and spend no model budget.
They cover run creation, model selection, reports, receipts, installation and
the removal of version 2. CI runs the same command.
