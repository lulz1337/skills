# Hybrid orchestration pitfalls

Both parent lists apply in full:
`../../orchestrator-codex/references/pitfalls.md` for the reviewer and the
other Codex roles, `../../orchestrator-claude/references/pitfalls.md` for the
worker and the orchestrator itself, including their Herdr rows. The rows below are the ones
only the mix can produce. These rows describe failure modes. The limited 2026-10-01 live evaluation
is recorded in agents/evals/ORCHESTRATOR-2026-10-01.md; historical predictions
are not proof that every path has been exercised.

| Pitfall | What would happen | Rule |
| --- | --- | --- |
| Retrying denied coordination | A denied coordination call is a defect report, not a prompt to retry in other spellings or to ask the user for `orchestrator off`. | Load enforcement once, quote the denied command, and stop with the smallest next action. |
| Sage or critic as a substitute | Routing scout, browser or verifier work to sage or critic because their dispatch was blocked breaks the boundary silently; in session a3a8d09c the sage disabled the sandbox twice to take screenshots. | Keep the role boundary; browser work goes to the browser role. |
| Piping the first runtime call | The first runtime call of a session piped through `\| head` or `\| tail` is denied by design. | Run one helper call per command. |
| The profile's reviewer | The orchestrator reads `reviewer_model` from `profiles/<mode>.md` and passes it to Codex, so `comprehensive` reviews on Astra. | The profile's `reviewer_*` half belongs to `/orchestrator-codex`. The hybrid reviewer is the runtime's Sol at high effort in every reviewed mode; `new hybrid <mode> reviewer` resolves it. |
| A Claude confirmer | `reviewer-standard`, `reviewer-hybrid-standard` or `orch-critic-standard` is spawned with Agent because the Claude procedure was read first. | Every confirming role (reviewer, critic, verifier, oracle) is Codex, through the runtime; the guard denies those agent types. Name the resolved model in the report. |
| A Codex worker | `new hybrid <mode> implementer` is started as a Codex process because the codex procedure was read first. | The implementer is the Claude agent `worker-hybrid-<mode>`, Opus at high effort, dispatched with Agent. |
| Asking Codex for terra | `fast` is briefed as "terra" and `gpt-6-terra` is passed to Codex, which rejects it. | There is no GPT-6 terra; `fast` differs from `quick` in the review, not in the worker. |
| A reviewer that does not know its worker | The Codex reviewer treats the implementer's handoff as verified and trusts its claims. | Tell the reviewer the worker was a Claude subagent whose handoff ran no checks, and that verification evidence comes from the verifier's report. Tell it to validate correctness-critical claims against the stable diff. |
| Mixed usage figures | Worker and reviewer usage are added up as one figure, or a Herdr-hosted run is reported as measured. | Report the Claude worker's token total from the `Agent` result and the Codex reviewer's usage from `summary`, separately. On the Herdr path, report a hosted run as unmeasured. |
| A reviewer told to write a file | The read-only reviewer is prompted to write `final.md` and either fails or mutates files through Bash against its prompt. | Only writable roles write `$run_dir/final.md`. Read the reviewer with `report <run> --final`, or `read-pane <run>` under Herdr. |
