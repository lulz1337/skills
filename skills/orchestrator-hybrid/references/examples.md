# Hybrid orchestration examples

Worked examples for `/orchestrator-hybrid`. The procedure in `procedure.md`
says which parent governs each step; this file shows what good looks like.
The task examples use a small fixture repository: `orders/pricing.py` with
`unittest` tests. The hybrid eval suite has scored
no live run yet, so these examples show the intended shape, not a measured one.

## Choosing a mode

| Request | Mode | Pair |
| --- | --- | --- |
| "Change the host port in docker-compose.yml from 8000 to 8080." | `quick` | `gpt-6-luna` medium executes, no reviewer runs |
| "Rename `calc_total` to `order_total` across the package and its tests." | `fast` | `gpt-6-luna` medium executes, `claude-opus-5-5` high reviews the call sites |
| "Add a 30 percent discount cap to `apply_discount`, with tests." | `standard` | `gpt-6-sol` medium executes, `claude-fable-5-1` medium reviews |
| "Change rounding in `order_total` to `ROUND_HALF_UP`; invoices depend on it." | `comprehensive` | `gpt-6-sol` medium executes, `claude-fable-5-1` high reviews |

When in doubt, `standard`. Escalate to `comprehensive` for money, auth,
migrations and anything the user calls risky. GPT-6 has no `terra` tier, so
`fast` executes on `luna` like `quick` and differs only in the review.

## Answering a bare mode

The user typed `/orchestrator-hybrid fast` and nothing else. Reply in one
line and stop:

```text
Mode fast: gpt-6-luna (medium) executes, claude-opus-5-5 (high) reviews. Send the task.
```

In `quick` there is no reviewer:

```text
Mode quick: gpt-6-luna (medium) executes, no review. Send the task.
```

## Reading the pair

```bash
sed -n '/^minion_/p' "$codex_dir/roles/profiles/fast.md"
sed -n '/^tools:/p; /^model:/p; /^effort:/p' "$skill_dir/agents/reviewer-hybrid-fast.md"
```

where `$skill_dir` is this skill's directory and `$codex_dir` is the
directory of the `orchestrator-codex` skill.

Ignore the profile's `reviewer_*` lines: they belong to `/orchestrator-codex`.

## One minion run

Follow "One minion run, start to finish" in
`references/examples.md` of the `orchestrator-codex` skill for the run
directory, `prompt.md`, the command and the evidence. Only two things
differ. The model and effort come from the `minion_*` lines. The run
directory holds no reviewer files, because the reviewer is not a Codex run.

## The reviewer round

The reviewer is a Claude subagent. Spawn it with the `Agent` tool, never with
`codex exec`:

```text
Agent(
  subagent_type: "reviewer-hybrid-standard",
  description: "Review discount cap diff",
  prompt: <the brief below>
)
```

```text
GOAL:        Review the discount cap change for correctness against the
             request and the repository rules.
SCOPE:       Read-only. The stable diff below; orders/pricing.py and
             tests/test_pricing.py for context.
CONTEXT:     Request: cap apply_discount at 30 percent, reject outside 0..100.
             Baseline was clean. The minion was a Codex process (gpt-6-sol,
             medium), not a Claude subagent.
EVIDENCE:    The verification evidence comes from the minion's final.md, which
             says: `python3 -m unittest tests.test_pricing -q`: OK, 9 tests.
             Nobody else ran it. Diff:
             <git diff output, pasted>
QUESTIONS:   Does the new test fail on the old code, or would a cap of 100
             also pass it?
CONSTRAINTS: Do not run tests or tools that check. Validate every
             correctness-critical claim in final.md against the stable diff.
             CONTEXT.md terms apply.
OUTPUT:      findings most severe first with path:line and the failure each
             causes; what you checked and found sound; what you could not verify.
```

The `Agent` result is the reviewer's report. It also carries the subagent's
token total; keep that number for the final report.

## A fix

The reviewer found that `tests/test_pricing.py:41` also passes with a cap of
50. The fix is a new cold Codex run with the minion body, the mode's
`minion_*` values and the brief from "A follow-up after an accepted finding"
in the Codex examples. Never `codex exec resume`. When the fix is material,
spawn a new `reviewer-hybrid-<mode>` agent with the fix and the new stable
diff, never a `reviewer-<mode>`.

## The final report

```text
Changed
- orders/pricing.py:18-24: apply_discount caps percent at 30; 0..100 still enforced.
- tests/test_pricing.py:38-46: test_discount_cap.

Verification (minion, gpt-6-sol medium): python3 -m unittest tests.test_pricing -q → OK, 9 tests.

Review (reviewer-hybrid-standard, claude-fable-5-1 medium): 2 findings.
- Accepted, fixed in a follow-up run, re-verified: cap test did not pin the cap (tests/test_pricing.py:41).
- Rejected: module constant for the cap; a preference.

Usage: minion 312k in (298k cached) / 4.1k out; follow-up 141k / 1.2k;
reviewer 46k tokens (Agent result).
Caveman measured every Codex run. Nothing committed.
Mode: standard (gpt-6-sol medium executes, claude-fable-5-1 medium reviews).
```

On the Herdr path the usage line reads: minion unmeasured, herdr-hosted;
reviewer not recorded.

## Inside Herdr

With `--visible` set and the gate passing, follow `orchestrator-claude/references/herdr.md` and
`orchestrator-codex/references/herdr.md`. Shell variables do not persist
between Bash calls, so print IDs and paths once and reuse them literally.
For mode `fast`, the minion's values come from the profile and the reviewer's
from its agent frontmatter:

```bash
herdr agent start minion-1 --kind codex --pane <pane-id> -- \
  --model gpt-6-luna -c model_reasoning_effort=medium \
  --sandbox danger-full-access -a never
herdr agent start reviewer --kind claude --pane <pane-id> -- \
  --model claude-opus-5-5 --effort high \
  --permission-mode bypassPermissions --tools "Bash,Read,Glob,Grep"
```

Wait with `herdr agent prompt <name> "…" --wait --timeout <ms>`. The one
exception is the resume after the user answers a dialog, which uses
`herdr agent wait --until idle --until done`. Run the prompt as a background
Bash call, `> <run-dir>/wait.json 2> <run-dir>/wait.err`. The
minion writes `<run-dir>/final.md`; the reviewer writes no file. Read its
report with `herdr agent read reviewer --source recent-unwrapped --lines 300`.
If it is truncated, one short prompt asks for the findings section again.
