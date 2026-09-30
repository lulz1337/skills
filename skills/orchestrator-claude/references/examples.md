# Claude orchestration examples

Worked examples for `/orchestrator-claude`. The procedure in `procedure.md`
says what to do; this file shows what good looks like. Every example uses a small
fixture repository: `orders/pricing.py` with `unittest` tests.

## Choosing a mode

| Request | Mode | Why |
| --- | --- | --- |
| "Change the host port in docker-compose.yml from 8000 to 8080." | `quick` | one settled line, review can be shallow |
| "Rename `calc_total` to `order_total` across the package and its tests." | `fast` | mechanical, but a missed call site breaks the build, so the reviewer works harder than the minion |
| "Add a 30 percent discount cap to `apply_discount`, with tests." | `standard` | the implementation needs judgment about edge cases and terms |
| "Change rounding in `order_total` to `ROUND_HALF_UP`; invoices depend on it." | `comprehensive` | a missed defect reaches money; the strongest reviewer at `xhigh` |

When in doubt, `standard`. Escalate to `comprehensive` for money, auth,
migrations and anything the user calls risky. Drop to `quick` only when the
diff is small and the user would accept it after a glance.

## Answering a bare mode

The user typed `/orchestrator-claude fast` and nothing else. Reply in one
line and stop:

```text
Mode fast: minion-fast executes, reviewer-fast reviews. Send the task.
```

Do not explore the repository, do not spawn, do not list questions.

## A complete minion brief

Task: "Add a discount cap to `orders/pricing.py`: `apply_discount` never takes
more than 30 percent off. Cover it in `tests/test_pricing.py`."

```text
GOAL:        apply_discount(total, percent) caps percent at 30: a percent above
             30 applies 30, not an error. Percents outside 0..100 still raise
             ValueError. One new unit test covers the cap.
SCOPE:       orders/pricing.py, tests/test_pricing.py. Nothing else.
CONTEXT:     Baseline `git status --short` is clean. Money is Decimal.
EVIDENCE:    apply_discount is at orders/pricing.py:18 and validates 0..100
             at line 20 (read by the orchestrator).
QUESTIONS:   none.
CONSTRAINTS: CONTEXT.md terms: order, customer, discount. Never purchase,
             cart, user, rebate, coupon. Follow AGENTS.md. Do not commit.
OUTPUT:      what changed with path:line, the test name, the verify result.
VERIFY:      python3 -m unittest tests.test_pricing -q
```

What makes it good: the goal states acceptance criteria, the scope names the
only two files, evidence carries its source, and `VERIFY` names the one test
module, not the whole repository.

## A reviewer brief

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
CONSTRAINTS: Do not run tests or tools that check. Judge the diff and code.
             CONTEXT.md terms apply.
OUTPUT:      findings most severe first with path:line and the failure each
             causes; what you checked and found sound; what you could not verify.
```

## Adjudicating findings

The reviewer returned two findings:

1. `tests/test_pricing.py:41` asserts `apply_discount(D('100'), D('50')) ==
   D('70')`; a cap of 50 would also pass. Accepted: the test does not pin the
   cap. Fix brief to the minion that owns the file:

   ```text
   GOAL:        Make the cap test fail if the cap is not 30: assert that
                percent 50 and percent 31 both give the 30 percent result.
   SCOPE:       tests/test_pricing.py only.
   CONTEXT:     Review finding on tests/test_pricing.py:41 (text above).
   EVIDENCE:    Previous verify: OK, 8 tests.
   CONSTRAINTS: as before.
   OUTPUT:      the changed assertion with path:line and the verify result.
   VERIFY:      python3 -m unittest tests.test_pricing -q
   ```

2. "Consider a module constant `DISCOUNT_CAP`." Rejected: a preference, the
   value already has a name in the function and appears once.

After the fix, request a second review only if the fix is material. A changed
assertion in one test is not; report it as re-verified instead.

## A parallel split

Task: "First, make `line_total` reject quantity zero. Second, add
`orders/tax.py` with `add_vat` and `tests/test_tax.py`."

Before spawning, the assignments:

- Minion A: goal zero-quantity rejection; scope `orders/pricing.py`,
  `tests/test_pricing.py`; done when the suite passes with a new test.
- Minion B: goal `add_vat`; scope `orders/tax.py`, `tests/test_tax.py` (new
  files); done when `tests.test_tax` passes.

No file appears in both scopes, so both start in one message, in the
background. Each brief names the other's files as excluded:

```text
SCOPE: orders/pricing.py, tests/test_pricing.py. Excluded: orders/tax.py and
       tests/test_tax.py, owned by another minion running now.
```

One reviewer reviews the combined stable diff after both minions finish.

## The final report

```text
Changed
- orders/pricing.py:18-24: apply_discount caps percent at 30; 0..100 still enforced.
- tests/test_pricing.py:38-46: test_discount_cap (percent 31 and 50 give the 30 percent result).

Verification (minion): python3 -m unittest tests.test_pricing -q → OK, 9 tests.

Review (reviewer-standard): 2 findings.
- Accepted, fixed, re-verified: cap test did not pin the cap (tests/test_pricing.py:41).
- Rejected: module constant for the cap; a preference, the value appears once.

Not done: nothing committed; the diff is yours to review.
Mode: standard (minion-standard, reviewer-standard).
```

No transcript, no restated brief, no claim about a check that did not run.
