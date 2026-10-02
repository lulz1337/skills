# Hybrid orchestration pitfalls

Both parent lists apply in full:
`../../orchestrator-codex/references/pitfalls.md` for the worker and
`../../orchestrator-claude/references/pitfalls.md` for the reviewer and the
orchestrator itself, including their Herdr rows. The rows below are the ones
only the mix can produce. These rows describe failure modes. The limited 2026-10-01 live evaluation
is recorded in agents/evals/ORCHESTRATOR-2026-10-01.md; historical predictions
are not proof that every path has been exercised.

| Pitfall | What would happen | Rule |
| --- | --- | --- |
| The profile's reviewer | The orchestrator reads `reviewer_model` from `profiles/<mode>.md` and runs a Codex reviewer. | The profile's `reviewer_*` half belongs to `/orchestrator-codex`. The reviewer here is always the Claude agent `reviewer-hybrid-<mode>`. |
| The parent's reviewer | `reviewer-standard` (fable, high) is spawned on a `standard` task instead of `reviewer-hybrid-standard` (fable, medium). | Spawn `reviewer-hybrid-<mode>` and nothing else; name it in the report. |
| A Claude worker | A `worker-<mode>` agent is spawned because the Claude procedure was read first. | The worker is Codex, always: `codex exec` on the host path, `--kind codex` in Herdr. |
| Asking Codex for terra | `fast` is briefed as "terra" and `gpt-6-terra` is passed to Codex, which rejects it. | There is no GPT-6 terra; `fast` executes on `gpt-6-luna` at medium and differs from `quick` in the review. |
| A reviewer that does not know its worker | The Claude reviewer treats `final.md` as its own host's subagent report and trusts the verification claims. | Tell the reviewer the worker was a Codex process and that its evidence comes from `final.md`. Tell it to validate correctness-critical claims against the stable diff. |
| Mixed usage figures | Worker and reviewer usage are added up as one figure, or a Herdr-hosted run is reported as measured. | On the host path, report Codex worker usage from `turn.completed` and the reviewer's token total from the `Agent` result, separately. On the Herdr path, report the worker as unmeasured, herdr-hosted, and the reviewer's usage as not recorded. |
| A reviewer told to write a file | The Herdr reviewer is prompted to write `final.md`, has no write tool, and either fails or mutates files through Bash against its prompt. | Only the worker writes `$run_dir/final.md`. Read the reviewer's report with `herdr agent read reviewer --source recent-unwrapped --lines 300`. |
