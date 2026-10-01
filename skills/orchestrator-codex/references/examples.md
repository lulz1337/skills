# Codex orchestration examples

Worked examples for `/orchestrator-codex`. The procedure in `procedure.md`
says what to do; this file shows what good looks like. The task examples use
a small fixture repository: `orders/pricing.py` with `unittest` tests.

## Choosing a mode

| Request | Mode | Why |
| --- | --- | --- |
| "Change the host port in docker-compose.yml from 8000 to 8080." | `quick` | one settled line; luna executes and no reviewer runs |
| "Rename `calc_total` to `order_total` across the package and its tests." | `fast` | mechanical for luna; sol at `high` catches the missed call site |
| "Add a 30 percent discount cap to `apply_discount`, with tests." | `standard` | sol writes it, sol at `high` reviews it |
| "Change rounding in `order_total` to `ROUND_HALF_UP`; invoices depend on it." | `comprehensive` | a missed defect reaches money; astra reviews |

When in doubt, `standard`. Escalate to `comprehensive` for money, auth,
migrations and anything the user calls risky.

## Answering a bare mode

The user typed `/orchestrator-codex fast` and nothing else. Reply in one line
and stop:

```text
Mode fast: gpt-6-luna (medium) executes, gpt-6-sol (high) reviews. Send the task.
```

In `quick` there is no reviewer:

```text
Mode quick: gpt-6-luna (medium) executes, no review. Send the task.
```

## Reading the profile

```bash
sed -n '2,5p' "$skill_dir/roles/profiles/fast.md"
```

where `$skill_dir` is this skill's directory, not the workspace,
gives the four values every command of this task uses:

```text
minion_model: gpt-6-luna
minion_reasoning_effort: medium
reviewer_model: gpt-6-sol
reviewer_reasoning_effort: high
```

## One minion run, start to finish

1. Run directory and prompt. Write `prompt.md` with the host's file tool: the
   body of `roles/minion.md` (below its frontmatter), a
   blank line, then the brief:

   ```text
   GOAL:        apply_discount(total, percent) caps percent at 30: a percent
                above 30 applies 30, not an error. Percents outside 0..100
                still raise ValueError. One new unit test covers the cap.
   SCOPE:       orders/pricing.py, tests/test_pricing.py. Nothing else.
   CONTEXT:     Baseline `git status --short` is clean. Money is Decimal.
   EVIDENCE:    apply_discount is at orders/pricing.py:18 and validates
                0..100 at line 20 (read by the orchestrator).
   QUESTIONS:   none.
   CONSTRAINTS: CONTEXT.md terms: order, customer, discount. Never purchase,
                cart, user, rebate, coupon. Follow AGENTS.md. Do not commit.
                You have one turn: finish, verify, report.
   OUTPUT:      what changed with path:line, the test name, the verify result.
   VERIFY:      python3 -m unittest tests.test_pricing -q
   ```

2. The command, in the foreground, with one blocking wait. This is the
   default in every host, including an interactive one: it ends when the
   minion ends, and nothing is left running when the turn ends.

   ```bash
   run_dir=$(mktemp -d /tmp/orch-minion-XXXXXX)
   timeout 1500 caveman run --off -- codex exec \
     --skip-git-repo-check --json \
     --output-last-message "$run_dir/final.md" \
     --cd "$PWD" \
     --model gpt-6-luna \
     --config model_reasoning_effort="medium" \
     --config sandbox_mode="danger-full-access" \
     - < "$run_dir/prompt.md" > "$run_dir/events.jsonl" 2> "$run_dir/stderr.log"
   ```

   A background start is allowed only when the host will wake this same
   conversation when the process ends, and then only with a task
   notification you have seen work in this session. `claude --print`, CI and
   another agent's subprocess never do: the turn ends, the process is
   orphaned, and "waiting for it" becomes the report. Unsure means
   foreground.

3. Afterwards, the evidence:

   ```bash
   jq -r 'select(.type == "thread.started") | .thread_id' "$run_dir/events.jsonl"
   jq -c 'select(.type == "turn.completed") | .usage' "$run_dir/events.jsonl"
   cat "$run_dir/final.md"
   git status --short && git diff
   ```

## The reviewer run

Same shape, the reviewer body from `roles/reviewer.md`, the
brief below it, `--model gpt-6-sol --config model_reasoning_effort="high"`
and `sandbox_mode="read-only"`:

```text
GOAL:        Review the discount cap change for correctness against the
             request and the repository rules.
SCOPE:       Read-only. The stable diff below; orders/pricing.py and
             tests/test_pricing.py for context.
CONTEXT:     Request: cap apply_discount at 30 percent, reject outside 0..100.
             Baseline was clean.
EVIDENCE:    Minion ran `python3 -m unittest tests.test_pricing -q`: OK, 8
             tests. Diff:
             <git diff output, pasted>
QUESTIONS:   Does the new test fail on the old code, or would a cap of 100
             also pass it?
CONSTRAINTS: Do not run tests. Judge the diff and the code. One turn.
OUTPUT:      findings most severe first with path:line and the failure each
             causes; what you checked and found sound; what you could not verify.
```

## A follow-up after an accepted finding

Codex cannot be messaged mid-flight and a Caveman-wrapped session cannot be
resumed, so the fix is a new cold run with the minion body and this brief:

```text
GOAL:        Make the cap test fail if the cap is not 30: assert that percent
             50 and percent 31 both give the 30 percent result.
SCOPE:       tests/test_pricing.py only.
CONTEXT:     Review finding on tests/test_pricing.py:41: the assertion also
             passes with a cap of 50.
EVIDENCE:    Previous verify: OK, 8 tests.
CONSTRAINTS: as before; one turn.
OUTPUT:      the changed assertion with path:line and the verify result.
VERIFY:      python3 -m unittest tests.test_pricing -q
```

## Two minions at once

Independent pieces with disjoint scopes start from one shell command, each
with its own run directory, and one `wait` in the same command. The command
as a whole still runs in the foreground:

```bash
start() { # $1 run dir, model and effort from the profile
  caveman run --off -- codex exec --skip-git-repo-check --json \
    --output-last-message "$1/final.md" --cd "$PWD" \
    --model gpt-6-sol --config model_reasoning_effort="medium" \
    --config sandbox_mode="danger-full-access" \
    - < "$1/prompt.md" > "$1/events.jsonl" 2> "$1/stderr.log"
}
start /tmp/orch-a & start /tmp/orch-b & wait
```

`a && b` runs them one after another and is not parallel. One reviewer
reviews the combined stable diff after both finish.

## The final report

```text
Changed
- orders/pricing.py:18-24: apply_discount caps percent at 30; 0..100 still enforced.
- tests/test_pricing.py:38-46: test_discount_cap.

Verification (minion, gpt-6-sol medium): python3 -m unittest tests.test_pricing -q → OK, 9 tests.

Review (gpt-6-sol high): 2 findings.
- Accepted, fixed in a follow-up run, re-verified: cap test did not pin the cap (tests/test_pricing.py:41).
- Rejected: module constant for the cap; a preference.

Usage: minion 312k in (298k cached) / 4.1k out; follow-up 141k / 1.2k; reviewer 188k / 2.3k.
Caveman measured every run. Nothing committed. Mode: standard.
```

## The same task on the Herdr path

`--visible` is set, the gate passes and the mode is `standard`. Shell variables do not persist
between Bash calls, so every step prints what the next step needs, and the
next step uses the literal value.

1. Read the profile. `sed -n '2,5p' "$skill_dir/roles/profiles/standard.md"`
   gives `gpt-6-sol` at `medium` for the minion and `gpt-6-sol` at `high` for
   the reviewer.
2. Make two panes and one run directory per agent. The first layout read
   shows the calling pane at width 200, which is at least 160 columns, so the
   first split is `right` and prints `w1:p3`. The second read shows `w1:p3` at
   width 100, so the second split is `down` and prints `w1:p4`. The run
   directories print `/tmp/orchestrator.Zq8n2c` for the minion and
   `/tmp/orchestrator.Rv82pd` for the reviewer:

   ```bash
   herdr pane layout --current | jq -c '.result.layout.panes[] | {pane_id, rect}'
   herdr pane split --current --direction right --cwd "$PWD" --no-focus | jq -r '.result.pane.pane_id'
   herdr pane layout --pane w1:p3 | jq -c '.result.layout.panes[] | {pane_id, rect}'
   herdr pane split w1:p3 --direction down --cwd "$PWD" --no-focus | jq -r '.result.pane.pane_id'
   mktemp -d "${TMPDIR:-/tmp}/orchestrator.XXXXXX"
   mktemp -d "${TMPDIR:-/tmp}/orchestrator.XXXXXX"
   ```

3. Write `/tmp/orchestrator.Zq8n2c/prompt.md` with the file tool: the minion
   body and the brief from "One minion run, start to finish".
4. Start both agents with the profile's values:

   ```bash
   herdr agent start minion-1 --kind codex --pane w1:p3 -- \
     --model gpt-6-sol -c model_reasoning_effort=medium --sandbox danger-full-access -a never
   herdr agent start reviewer --kind codex --pane w1:p4 -- \
     --model gpt-6-sol -c model_reasoning_effort=high --sandbox read-only -a never
   ```

5. Prompt the minion in a background Bash call with a 1900000 ms tool timeout:

   ```bash
   herdr agent prompt minion-1 "Read /tmp/orchestrator.Zq8n2c/prompt.md and carry it out. Write your final report to /tmp/orchestrator.Zq8n2c/final.md and reply only with that path." \
     --wait --timeout 1800000 \
     > /tmp/orchestrator.Zq8n2c/wait.json 2> /tmp/orchestrator.Zq8n2c/wait.err
   echo "minion-1 exit=$?"
   ```

6. When the call wakes the conversation, read `wait.json` and `wait.err`. Exit
   0 with an `idle` or `done` state means the turn settled. Then read
   `final.md` and run `git status --short && git diff`.
7. Write `/tmp/orchestrator.Rv82pd/prompt.md` with the file tool: the
   reviewer body and the reviewer brief from "The reviewer run", with
   `OUTPUT` asking for the report in the pane and no file. Prompt the reviewer
   the same way, with `--timeout 900000` and a 1000000 ms tool timeout, into
   that directory's `wait.json` and `wait.err`, then read the report:

   ```bash
   herdr agent read reviewer --source recent-unwrapped --lines 300
   ```

8. The cap finding is accepted. Write `follow-up.md` with the fix brief from
   "A follow-up after an accepted finding", asking for the report in
   `final-2.md`. Prompt `minion-1` to read it, with the same background wait
   into `wait-2.json` and `wait-2.err`. The minion still knows the brief and
   the files. The follow-up is not cheaper in tokens, because Codex resends
   the transcript.
9. Finish: `herdr pane close w1:p3`, `herdr pane close w1:p4`, and remove
   `/tmp/orchestrator.Zq8n2c` and `/tmp/orchestrator.Rv82pd`.

The report ends with:

```text
Usage: unmeasured (herdr-hosted) for the minion, its follow-up and the reviewer.
Nothing committed. Mode: standard.
```
