# Orchestrator session fixes — 2026-10-02

Keep the runtime and completion-gate fixes. Reject the worker prompt rewrites:
they did not improve both quality and clarity. All worker definitions and model
profiles are restored to the baseline commit, `50cedb8`.

## Audited session

Claude session `25b9b7ed-94a5-4899-9930-b25c904a52fe` selected
`/orchestrator-hybrid fast`. Hosting in Claude did not make this a Claude-only
dispatch. Its 23 Codex runs comprised eight scouts, two researchers, six browser
workers, four implementers and three verifiers; Claude supplied one reviewer.
Every Codex execution was sequential, although the controller claimed parallelism.
The final answer incorrectly counted 19 runs. Two discovery reports described
unattempted listings as empty output. A material repair received no final review.
The controller also ignored the requested `docs/adr/` destination and considered
removing newly appearing unrelated work.

## Changes retained

1. `start-many` starts independent Codex runs concurrently, joins every child and
   reports individual failures. Writable batches require retained plan claims;
   dispatch rejects rebound scopes and conflicts with every active owner.
2. Briefing and execution share an execution lock. Started runs cannot overwrite
   their original prompt or events. Reports recover full output or a specific
   completed receipt. Missing completed receipts fail batch evidence checks even
   after an exit-zero process.
3. Each host Codex child receives a disposable authentication-only configuration.
   Host hooks, plugins and skill discovery are disabled; project instructions and
   the Caveman wrapper's provider routing remain available. The brief requires
   collecting a yielded command's session before reporting its result.
4. Completion scoring requires every writer to finish before final verification
   and review. Trusted background completion notifications count; launch
   acknowledgments and forged notifications do not. A resumed agent needs a new
   completion notification. Batch concurrency requires overlapping timestamps.
5. Shared workflow instructions retain explicit user paths, preserve unrelated
   new files, route prescribed commands to runner, bound discovery retries and
   require review after material repairs. Usage summaries deduplicate runs and
   keep cached input within input totals.

## Evidence

| Check | Before | Final | Interpretation |
| --- | --- | --- | --- |
| Targeted runtime/scorer regressions | 0/13 | 13/13 | Deterministic acceptance checks against `50cedb8` and the candidate |
| Live batch: correct fixture locations | 0/2 | 2/2 | Both `alpha` and `beta` found at `README.md:1` after isolation |
| Live batch: completed command receipts | 0 | 2 | One completed command per final worker; peak concurrency 2 |
| Free tests | 172 in the previous published report | 186, four expected failures | Stub tools; no model calls |
| Scoring mutations | 37/37 caught | 37/37 caught | Updated the background-completion mutation target |
| Repository orchestrator checks | — | 20 passed, zero failed | Includes free tests and scoring mutations |

The 13 regression cases are intentionally selected for these fixes. Four baseline
cases fail behavioral assertions; the other nine fail because the old runtime
lacks the new interfaces or evidence fields. This measures acceptance of the
fixes, not general model quality. Both live batch attempts use the same fixture
content; the first is an early candidate, not the baseline commit, which had no
batch command. The final batch is rerun after restoring the worker prompts.

Raw role evaluations and blind judgments remain under ignored
`results/orchestrator-session-fix-{baseline,qualified,final,tuned,promoted}-2026-10-02/`.
The directory named `promoted` records an experiment that was subsequently
rejected; its name does not indicate installation. Final installed-runtime
evidence is in `results/orchestrator-session-fix-runtime-2026-10-02/`.
Authentication files are never retained with evidence.
The [committed summary](ORCHESTRATOR-SESSION-2026-10-02.json) contains the exact
test names, source hashes, quality averages and final batch receipts and usage.
Installation succeeded; Linux preflight reported zero blocking problems and four
warnings (sudo, Caveman integration, graphical keymap and the absent private
Kubernetes configuration).

## Prompt experiment: rejected

The rejected prompt experiment ran all 36 scout, verifier and researcher family
× mode cells live. After tuning, its 32 changed variants passed their
deterministic role contracts at 100/100.
An unchanged Claude quick researcher still failed citation-line validation,
also observed in its paired baseline. No quota failure was scored as performance.

The blind judge was `gpt-6.1-sol`, high effort. It compared 32 completed matched
pairs: 12 scout, 12 verifier and eight Codex-family researcher variants. Unchanged
Claude researchers were excluded. Both weighted quality and clarity must improve;
structural contract checks cannot override a factual defect.

| Role | Quality before → candidate (out of 5) | Clarity before → candidate (out of 5) | Decision |
| --- | --- | --- | --- |
| Scout | 4.633 → 4.567 | 4.500 → 4.500 | Reject: lower quality, no clarity gain |
| Verifier | 4.742 → 4.717 | 4.667 → 4.833 | Reject: lower quality |
| Researcher | 4.850 → 4.787 | 5.000 → 4.875 | Reject: both lower; one new factual blocker |

Three Claude researcher tuning attempts did not reliably enforce the requested
report limit and evidence shape. The doubtful assumption was that more prompt
wording would reliably fix those behaviors. Tuning stopped, and all role prompt
rewrites were reverted. The installed runtime improvements do not claim a role
quality or clarity gain from those rejected prompts.

## Limits and follow-up

1. Run a paired controller scenario for explicit destinations, concurrent
   unrelated edits, discovery escalation and long research dossiers. Current
   workflow wording is a requirement, not proof that a controller follows it.
2. Test real interactive Claude background notifications and Herdr dispatch.
   Lifecycle parsing uses the audited session's trusted metadata and regression
   fixtures; streamed-host compatibility has not been qualified here.
3. Reassess the unchanged Claude quick researcher's inaccurate source line with
   a focused fixture. Do not promote another rewrite without stronger evidence.

Receipt checks detect the audited empty-output patterns, invented receipt IDs and
incomplete started actions. They do not semantically verify arbitrary reports.
The normal wrapper can fall back to direct provider traffic: metering requested
is not metering observed, and token counts are not a measured dollar cost.

The upstream Codex `quick_validate.py` rejects the existing Claude frontmatter
keys (`argument-hint`, `disable-model-invocation`, `disallowed-tools`, and hybrid
`compatibility`). Those keys were not changed; the repository's own checks
validate the intended multi-host layout. Installed CLI help documents
`--ignore-user-config`; the fetched official CLI reference did not list it.
Only explicit direct bypass uses that flag, so normal wrapper routing is retained.
