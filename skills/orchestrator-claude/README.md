# Orchestrator (Claude)

Run a task through delegated workers when explicitly invoked. Claude workers only. The four modes select Claude model aliases and effort; specialist roles have their own definitions.

## Installation

From a clone of this repository, install the shared runtime, roles and guards:

```bash
python3 orchestrator/install.py
```

Restart Claude Code. For native Codex, enable hooks and trust them in `/hooks`.
The [runtime guide](../../orchestrator/README.md) covers prerequisites, model
selection, tool boundaries and installation into a separate home.

The skill can also be discovered with `npx skills add lulz1337/skills --skill
orchestrator-claude`, or installed as a Claude Code plugin with `/plugin install
orchestrator-claude@skills` after adding the `lulz1337/skills` marketplace. Both
still require the shared runtime installation above. No dotfiles checkout is
required.

## Usage

```text
/orchestrator-claude fast rename OrderLine.qty to quantity
```

The first word selects quick, fast, standard or comprehensive; otherwise the
mode is standard and the argument is the task. A mode without a task sets the
mode and waits. `--visible` selects Herdr hosting when available.

## Workflow

The controller decides, briefs, dispatches and reports. Workers handle repository,
web and browser work. The verifier runs checks; the reviewer judges the final
revision from fast upward. Independent Codex or read-only Claude runs of one kind use a joined batch with
actual execution intervals. Writable Codex batches retain exclusive ownership claims.

The eleven roles are scout, researcher, implementer, runner, verifier, browser,
reviewer, oracle, sage, critic and publisher. Publisher builds an Artifact page
from supplied files using Claude. Quick excludes reviewer and critic. Only the
exact user message `orchestrator off` clears persistent mode.

## Package

`agents/` contains worker, reviewer and specialist definitions, including the four publisher modes. `references/` contains the shared workflow and Claude dispatch instructions.

Runtime code and role definitions are shared through the `orchestrator/` bundle
in this repository. See its guide for free tests and historical evaluations.

## License

MIT
