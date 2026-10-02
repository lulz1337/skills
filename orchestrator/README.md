# Shared orchestrator runtime

This bundle supplies all three orchestrator skills. It contains the execution
runtime, worker definitions, model profiles, session guard and free tests.
It runs independently of the author's dotfiles checkout.

## Install from this repository

Use Python 3.10 or newer on Linux or macOS. Authenticate Claude Code and Codex
separately. Codex execution uses `caveman` when installed; an explicitly reported
direct run can use the runtime's `--bypass-caveman` option. Herdr is optional.

From the repository root:

```bash
python3 orchestrator/install.py
```

The installer copies the three skills, Claude workers, Codex roles and runtime
into the user's agent directories. It merges session guards into Claude settings
and Codex hooks, preserving other hooks and skills. Restart Claude Code. In native
Codex, start with `codex --enable hooks` and review and trust the new hooks in
`/hooks`. Hook enforcement requires enabled, trusted hooks.

The skills CLI and Claude plugins install skill packages, but the shared runtime
still needs the command above. If another checkout manages a destination through
a symlink, update that owning checkout; the installer refuses to write through
changed symlink targets. `--home <directory>` supports an isolated installation;
`--codex-home <directory>` selects a separate Codex configuration directory.

## Roles and models

| Role | Duty |
| --- | --- |
| scout | Locate instructions, sources, callers and evidence |
| researcher | Reconcile sources and answer research questions |
| implementer | Make the bounded change in owned files |
| runner | Execute a prescribed mechanical sequence |
| verifier | Run exact checks and report their output and exit status |
| browser | Observe a named UI flow |
| reviewer | Review the stable final revision |
| oracle | Diagnose an unresolved failure |
| sage | Advise on an architectural decision |
| critic | Challenge a material claim independently |

Each role has quick, fast, standard and comprehensive variants. Quick excludes
reviewer and critic. Claude uses Claude workers; Codex uses Codex workers. Hybrid
uses Codex execution and Claude reviewer, sage and critic roles.

Claude model aliases follow the newest model in their configured family. Codex
profiles set minimum versions and resolve the newest account-visible model in
the same tier through live `model/list`. Sol starts at `gpt-6.1-sol`; dispatch
stops when a fresh eligible model cannot be verified. The runner uses Sol in
every mode; specialist routing remains defined by the runtime.

## Execution and tools

The controller briefs, dispatches, decides and reports. Workers read and search
the repository, edit owned files and inspect external sources. The verifier owns
tests, typechecks, lint and builds. The session guard enforces this separation on
local tool hooks while orchestration is active; hosted tools remain governed by
instructions. This guard is a workflow boundary, not a security sandbox.

`start-many` joins independent Codex executions and checks retained ownership for
writable batches. Reports preserve complete receipts, and `summary` reports
actual intervals and usage. Worker configuration is isolated from host hooks.
Only the exact user message `orchestrator off` clears persistent orchestration.

## Verification

```bash
python3 -m unittest discover -s orchestrator/tests
```

These tests use stub processes and disposable homes. They spend no model budget.
They cover all supported role contracts, model selection, guards, batching,
evidence preservation and installation. CI runs the same command.

The imported [session evaluation](evidence/ORCHESTRATOR-SESSION-2026-10-02.md)
and [score summary](evidence/ORCHESTRATOR-SESSION-2026-10-02.json) were measured in
the dotfiles repository at commit `b7d6d0f`. They are historical evidence, not a
fresh paid evaluation of this packaging change. Rejected prompt rewrites remain
rejected; this repository carries the approved original worker definitions.
