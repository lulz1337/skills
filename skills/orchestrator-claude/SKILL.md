---
name: orchestrator-claude
description: "Run a task as an orchestrator over Claude subagents: a worker executes and, from fast up, a reviewer reviews; the mode (quick, fast, standard, comprehensive) chooses them. Use only when the user asks for /orchestrator-claude."
argument-hint: "[quick|fast|standard|comprehensive] [--visible] [task]"
disable-model-invocation: true
disallowed-tools: Read, Edit, Write, NotebookEdit, Glob, Grep
license: MIT
metadata:
  version: "2.0.0"
---

Coordinate the requested task with Claude workers. The main thread owns decisions,
briefs, dispatch and adjudication; workers own repository, web and browser work.

## Select the mode

Arguments: `$ARGUMENTS`

Remove --visible wherever it appears. It selects Herdr hosting. The first
remaining word selects quick, fast, standard or comprehensive; otherwise use
standard and treat the whole argument as the task. No argument means standard.
With no task, reply in one line naming the mode and pair/profile, include visible
when selected, and wait. Keep the settings across later tasks until the next
invocation or the user's exact `orchestrator off` message.

| Mode | Spawns | Use for |
| --- | --- | --- |
| `quick` | `worker-quick` | a settled, small change, no review |
| `fast` | `worker-fast`, `reviewer-fast` | a settled change, checked by a reviewer |
| `standard` | `worker-standard`, `reviewer-standard` | the default: implementation needs judgment |
| `comprehensive` | `worker-comprehensive`, `reviewer-comprehensive` | work where a missed defect is expensive |

Quick uses discovery, one implementation scope and verification, with no reviewer
or critic. Specialist roles are chosen for an actual question or outcome.

## Load coordination instructions

Run each helper call separately, using the selected mode in place of standard:

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" instructions claude standard
```

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" instructions claude standard procedure
```

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" instructions claude standard workflow
```

The helper supplies [role contracts](references/roles.md),
[tool boundaries](references/tools.md) and resolved settings. Follow the shared
workflow through its completion criteria. Load examples for uncertain dispatch
syntax, pitfalls for an observed failure, and herdr only for --visible, through
`instructions claude <mode> <reference>`. Metadata and reports use the helper;
repository facts, source changes, diffs and checks use workers.

For dependent slices or a retained plan, load scheduling through the helper and
follow its claim, verification and recovery rules. Single-scope work follows
the shared workflow directly.
