---
name: orchestrator-hybrid
description: "Run a task as an orchestrator over a mixed pair: a Claude Opus worker implements and, from fast up, a Codex Sol reviewer reviews; the mode (quick, fast, standard, comprehensive) chooses the rest. Use only when the user asks for /orchestrator-hybrid."
argument-hint: "[quick|fast|standard|comprehensive] [--visible] [task]"
disable-model-invocation: true
disallowed-tools: Read, Edit, Write, NotebookEdit, Glob, Grep
compatibility: "Needs the shared orchestrator runtime installed, codex and caveman on PATH, and Claude Code for implementation. herdr is optional."
license: MIT
metadata:
  version: "2.2.0"
---

Coordinate the requested task with Claude implementation and Codex review. The main thread owns decisions,
briefs, dispatch and adjudication; workers own repository, web and browser work.

## Select the mode

Arguments: `$ARGUMENTS`

Remove --visible wherever it appears. It selects Herdr hosting. The first
remaining word selects quick, fast, standard or comprehensive; otherwise use
standard and treat the whole argument as the task. No argument means standard.
With no task, reply in one line naming the mode and pair/profile, include visible
when selected, and wait. Keep the settings across later tasks until the next
invocation or the user's exact `orchestrator off` message.

| Mode | Claude worker | Codex reviewer | Use for |
| --- | --- | --- | --- |
| `quick` | `worker-hybrid-quick` | none | a settled, small change, no review |
| `fast` | `worker-hybrid-fast` | Sol, high effort | a settled change, checked by a reviewer |
| `standard` | `worker-hybrid-standard` | Sol, high effort | the default: implementation needs judgment |
| `comprehensive` | `worker-hybrid-comprehensive` | Sol, high effort | work where a missed defect is expensive |

One frontier implements and the other confirms. Every Claude worker is the
latest Opus at high effort. Reviewer and critic are the newest visible Sol at
or above gpt-6.1-sol at high effort, resolved by the runtime; verifier and
oracle are Codex roles from `profiles/<mode>.md`, as are scout, researcher
and browser. Runner (Opus, medium), sage (advice) and publisher stay Claude.

Every mode finishes scoped implementation and source review/fixes before final
verification. Quick has no independent reviewer. Specialist roles are chosen
for an actual question or outcome.

## Load coordination instructions

Run each helper call separately, using the selected mode in place of standard:

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" instructions hybrid standard
```

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" instructions hybrid standard procedure
```

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" instructions hybrid standard workflow
```

The helper supplies [role contracts](references/roles.md),
[tool boundaries](references/tools.md) and resolved settings. Follow the shared
workflow through its completion criteria. Load examples for uncertain dispatch
syntax, pitfalls for an observed failure, and herdr only for --visible, through
`instructions hybrid <mode> <reference>`. Metadata and reports use the helper;
repository facts, source changes, diffs and checks use workers.

For dependent slices or a retained plan, load scheduling through the helper and
follow its claim, verification and recovery rules. Single-scope work follows
the shared workflow directly.
