# Failures: a red test is information (TD40–TD41)

## TD40 — decide which side is broken before touching anything

"Fix the tests" never means "make it green by any means". A red test has
exactly three states; identify which one before editing:

- **The code is wrong** — the test caught a real regression. Fix the code;
  the test just did its job. Do not touch the test.
- **The test is wrong** — it asserts behaviour that was intentionally
  changed. Update it, and justify every changed assertion by the intended
  behaviour change or spec, stated in your report.
- **Unclear** — investigate until it becomes one of the two. Never guess,
  never split the difference, never adjust the expectation to whatever the
  code currently returns without understanding why.

A legitimately red test you cannot resolve is a **finding to report to the
user**, not a blocker to silence.

## TD41 — never weaken a test to make it pass (BLOCKER)

Weakening converts a working alarm into a decoration. All of these count:

- deleting or loosening assertions (exact match → truthiness, narrow matcher
  → broad matcher);
- skipping or deferring (skip/todo/fixme annotations, commenting the test
  out);
- wrapping the failing step in error swallowing;
- widening timeouts to mask a race instead of fixing the race (TD31);
- adding retries to hide flake instead of removing the flake's cause;
- committing a focused test (an "only"-style marker), which silently disables
  the rest of the suite.

Any of these already present in the codebase is a review finding; any of them
introduced to get a task over the line is a BLOCKER on your own work.
