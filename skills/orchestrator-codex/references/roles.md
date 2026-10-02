# Worker roster

Adapted from martinslaby70/agents-skills, `skills/orchestrator/SKILL.md` and
`agents/orch-*.md` (MIT; see `agents/LICENSE.orchestrator`). Local model IDs
replace upstream's private gateway IDs. The orchestrator is always the main
thread. Workers never inherit its coordination role or delegate further.

| Role | Contract | Route when |
| --- | --- | --- |
| scout | Locate files, symbols, call sites; return path:line evidence | Any repository lookup, baseline instructions or stable diff |
| verifier | Run the exact VERIFY commands; report output and exit codes | Implementation is stable; rerun only affected or failed checks |
| runner | Execute the named mechanical sequence; report end state | Closed command lists, Git operations, generated artifacts, server lifecycle |
| researcher | Synthesize evidence across files, docs or the web | A lookup alone cannot answer the question |
| browser | Drive the requested UI flow; return screenshots, console and network evidence | Browser observation is required |
| implementer | Make the bounded change inside owned SCOPE | The approach and acceptance criteria are settled |
| reviewer | Independently inspect the stable diff and surrounding code | Every implementation in fast, standard or comprehensive; never quick |
| oracle | Diagnose a failure that resisted a fix; recommend a cause-based fix | At least one attempted fix failed |
| sage | Assess design alternatives; recommend one approach | The user asks, or a real design uncertainty remains |
| critic | Independently critique a change beyond its author's assumptions | Shared code, CI, auth or money, in a mode with review |

Use the lowest configured tier that covers the contract. Scout, verifier and
runner have closed briefs. Do not give them open research or design work.
Researcher and browser use the current worker tier. Implementer uses the
mode's worker model; reviewer uses its reviewer model. Oracle, sage and critic
use the stronger configured tier. `instructions <family> <mode>` prints every
resolved model, effort, agent type and tool list; those values are authoritative.

Claude implementation uses `worker-<mode>` and review uses `reviewer-<mode>`.
Other contracts use `orch-<role>-<mode>`. Codex combines `<role>.md` (implementer
is `worker.md`) with `profiles/<mode>.md`; scout and verifier use the quick profile; runner uses the
standard worker tier in every mode after lower-tier state-report failures. Oracle, sage and critic use the comprehensive reviewer tier.
Hybrid uses Codex for execution, discovery, research, browser work and diagnosis;
review uses `reviewer-hybrid-<mode>`, and sage and critic use Claude
`orch-<role>-<mode>`. Thus hybrid critique can come from another model family.
Claude uses latest-family aliases (Sonnet for closed contracts, Opus for
implementation, Fable for the strongest reasoning roles). Codex queries its live
model/list catalog and selects the newest visible version in the configured GPT
tier, with gpt-6.1-sol as the minimum Sol version. The runtime reports live, cached
or fallback metadata; cache and fallback cannot prove the latest release and
are never used for dispatch. A Codex start requires a fresh live catalog. No private gateway,
obfuscated model ID or silent cross-family fallback is copied from upstream.

Quick keeps discovery, implementation and verification but skips reviewer and
critic. Other modes retain the existing review requirement. Do not add sage,
oracle or critic merely to fill a slot. Reviewers and critics must not review
work they authored. Every writable file belongs to one running worker.

A status question that existing coordination state answers needs no dispatch.
A new repository fact requires a scout or researcher. Judge contradictory
reports from their cited evidence; ask a worker to resolve a source question.
Execution and absence claims need completed tool receipts. Worker summaries
must account for every requested item; brevity cannot remove required evidence.
One failed discovery retry escalates to a stronger research/diagnosis role.
