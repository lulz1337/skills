# Coordination boundary

| Work | Owner |
| --- | --- |
| Clarify, decide, brief, dispatch, adjudicate, report | Orchestrator |
| Locate sources, instructions and checks; capture a stable diff | scout or reviewer |
| Edit owned source; perform authorized integration | implementer or runner |
| Run tests, lint, typecheck and build | verifier |
| Investigate sources or drive a UI | researcher or browser |
| Build and publish an Artifact page from supplied files | publisher (Claude: Bash, Read, Write, Glob, Skill, Artifact); unavailable to the codex family |

Use the runtime helper for orchestration definitions, baseline status, literal
briefs, task graphs, concurrent dispatch, receipts and usage summaries. Use the selected family's workers for task work,
including repository reads and searches. The same boundary applies through
shell interpreters, CodeGraph, tgrep, MCP tools and connectors.

Runtime calls run inside the host sandbox. Only `start` and `start-many` for
Codex-only runs, and the herdr subcommands (`visible`, `pane`, `prompt`,
`read-pane`, `wait`, `stop`), which may need the herdr socket, may run with the
sandbox disabled. Codex cannot start inside the Claude sandbox and applies each
run's own sandbox mode. Claude `start` and any `start-many` containing Claude
runs must omit `dangerouslyDisableSandbox`; the guard denies it.

Run one helper call per command. Use the literal returned run path. Write a
brief, plan or resolution with a quoted heredoc:

```bash
python3 "$HOME/.agents/orchestrator-runtime.py" brief /tmp/orchestrator-EXAMPLE <<'BRIEF'
GOAL: ...
SCOPE: ...
CONTEXT: ...
EVIDENCE: ...
QUESTIONS: ...
CONSTRAINTS: ...
OUTPUT: ...
VERIFY: ...
BRIEF
```

`start-many` is a single foreground coordination call that runs independent
Codex or read-only Claude runs concurrently and joins all of them. Writable
Codex runs need active claims in its `--plan`; writable Claude roles and
publisher use Agent with the resolved agent_type. `report --receipt <id>`
recovers one complete recorded tool result; `report --full` recovers the full
report and command outputs. `summary` counts the named runs once and sums
recorded usage. These commands read coordination artifacts, not source files.

Host Codex workers use a disposable authentication-only configuration. Hooks,
plugins and host skill discovery are disabled; project instructions still apply.
The Caveman wrapper can supply its own routing configuration. Metering requested
is not evidence of measured traffic: retain a reported direct fallback as a limit.
Workers collect yielded command sessions before reporting. Missing completed
receipts fail the batch evidence check even when the process exits zero.

Only the user's exact message `orchestrator off` ends the persistent mode.
For hook activation, trust, tool coverage or a denied coordination call, load
[enforcement.md](enforcement.md). Native hosted tools remain instruction-only;
these hooks provide a workflow boundary, not a security sandbox.
