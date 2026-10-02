# Orchestrator (Codex)

Run a task through delegated workers when explicitly invoked. Codex workers only. The runtime resolves the newest account-visible model in each configured tier; Sol profiles require at least `gpt-6.1-sol`. It stops dispatch if live model selection cannot be verified.

## Installation

From a clone of this repository, install the shared runtime, roles and guards:

```bash
python3 orchestrator/install.py
```

Restart Claude Code. For native Codex, enable hooks and trust them in `/hooks`.
The [runtime guide](../../orchestrator/README.md) covers prerequisites, model
selection, tool boundaries and installation into a separate home.

The skill can also be discovered with `npx skills add lulz1337/skills --skill
orchestrator-codex`, or installed as a Claude Code plugin with `/plugin install
orchestrator-codex@skills` after adding the `lulz1337/skills` marketplace. Both
still require the shared runtime installation above. No dotfiles checkout is
required.

## Usage

```text
/orchestrator-codex standard add a 30% discount cap
```

The first word selects quick, fast, standard or comprehensive; otherwise the
mode is standard and the argument is the task. A mode without a task sets the
mode and waits. `--visible` selects Herdr hosting when available.

## Workflow

The controller decides, briefs, dispatches and reports. Workers handle repository,
web and browser work. The verifier runs checks; the reviewer judges the final
revision from fast upward. Independent Codex runs use a joined batch with actual
execution intervals. Writable batches retain exclusive ownership claims.

The ten roles are scout, researcher, implementer, runner, verifier, browser,
reviewer, oracle, sage and critic. Quick excludes reviewer and critic. Only the
exact user message `orchestrator off` clears persistent mode.

## Package

`roles/` contains all ten role contracts and the four model profiles. `references/` contains the shared workflow and Codex dispatch instructions.

Runtime code and role definitions are shared through the `orchestrator/` bundle
in this repository. See its guide for free tests and historical evaluations.

## License

MIT
