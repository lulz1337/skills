---
name: test-discipline
description: >-
  Test hygiene and test-pyramid discipline for every test in any language,
  framework, or runner. Load this skill EVERY time tests are involved in any
  way: writing, editing, moving, reviewing, fixing, deleting, or generating
  tests; questions about test strategy, hygiene, coverage, flaky tests, or
  slow suites; "write tests", "fix the tests", "napiš testy", "oprav testy",
  "review testů"; and any touch of a test file (*.test.*, *.spec.*, *_test.*,
  test_*, *Test.*). Do not skip it because the change looks small — it always
  ends with a severity-graded review (BLOCKER/HIGH/MEDIUM/LOW) that marks
  each test OK / FIX / DELETE and names the tests that are MISSING.
---

# Test Discipline

Agents write too many tests at the wrong layer, and the failure mode is always
the same: the agent writes tests **for itself** — to prove its own
implementation passes — instead of tests **for the user** — to catch real
regressions after the agent is gone. This skill is the correction. It is
stack-agnostic on purpose: every rule is about behaviour and cost, never about
a particular runner, library, or language. If a TDD skill is also active, it
governs the *process* (red → green → refactor); this skill governs *what to
test, at which layer, what a finished test may look like — and it always ends
with a review*.

## The one question every test must answer

> **"What real application failure does this test catch when my
> implementation is no longer in front of me?"**

If the honest answer is "none — it just re-states what my code does",
the test has negative value: pure maintenance cost. Delete it.

## Non-negotiable outcome: the review

Every activation of this skill ends with a **Test Review** — even when the
task was "write tests" (review your own new tests before reporting done), and
even when the user only asked a hygiene question (review what exists). Never
end a test-touching task with just "done, tests pass".

The workflow:

1. **Discover repo conventions.** Existing test files, test config, CI
   scripts. The repo decides where tests live and what they are called; this
   skill decides what they may contain. Never impose a foreign layout.
2. **Run the checker** on the relevant test files:

   ```bash
   python3 scripts/review_tests.py <files-or-dirs> [--e2e-pattern REGEX]
   ```

   It is a dependency-free heuristic pre-pass: it flags findings with
   severity, rule ID, and file:line, and gives each file a provisional
   verdict. Findings marked "verify" are suspicions, not convictions —
   confirm or dismiss them yourself.
3. **Do the semantic review** the checker cannot do: wrong layer, scenario
   duplication across layers, missing unit tests for changed business logic,
   third-party subjects hidden behind helpers, infrastructure reached through
   indirection. Read the rule files relevant to what you found:
   - [`rules/layers.md`](rules/layers.md) — choosing the layer, duplication,
     e2e budget, mandatory unit tests (TD01–TD04)
   - [`rules/scope.md`](rules/scope.md) — what a test must never test: logs,
     third-party dependencies, the implementation itself (TD10–TD14)
   - [`rules/isolation.md`](rules/isolation.md) — what each layer may touch:
     unmocked e2e, fully-supplied integration/functional inputs (TD20–TD22)
   - [`rules/speed.md`](rules/speed.md) — why suites get slow and how not to:
     type-only imports, shallow module graphs, no sleeps (TD30–TD32)
   - [`rules/failures.md`](rules/failures.md) — what to do with a red test;
     never weaken one to green (TD40–TD41)
4. **Emit the report** in the format below.
5. **Act on the verdicts** within the task's scope: fix and create freely;
   delete tests you wrote in this session freely; for pre-existing tests,
   recommend deletion with the rule and reasoning and let the user confirm —
   they may know a contract you cannot see.

## Severity

- **BLOCKER** — the test is actively harmful: it passes while the app is
  broken, breaks while the app is fine, or burns machine time for nothing.
  Log assertions (TD10), third-party subjects (TD11), mocked e2e (TD20),
  infrastructure reached from integration/functional tests (TD21), tests
  weakened to go green (TD41).
- **HIGH** — wrong or missing value: implementation mirrors (TD12), the same
  scenario duplicated across layers (TD02), business logic without a unit
  test (TD04), focused/skipped tests left committed (TD41), an e2e spec that
  is not a critical journey (TD03).
- **MEDIUM** — real cost without necessity: value imports where type imports
  suffice (TD30), sleeps and real timers (TD31), per-test world building
  (TD32), snapshot misuse (TD13).
- **LOW** — drift and inflation: placement/naming against repo convention
  (TD01), assertion filler, test count as a deliverable (TD14).

## Report format

ALWAYS use this exact structure (prose around it is fine):

```markdown
## Test review

| File | Verdict | Findings |
|------|---------|----------|
| src/pricing.test.ts | FIX | TD10 BLOCKER line 42 — asserts a log message; TD30 MEDIUM line 3 — value import used only as a type |
| src/api/orders.spec.ts | OK | — |
| e2e/checkout.spec.ts | DELETE | TD20 BLOCKER — network mocked inside an e2e journey; scenario already covered at integration layer |

**Missing (CREATE):**
- unit: `calculateDiscount` — branches for negative quantity and max-cap are untested (TD04)

**Summary:** 1 BLOCKER, 0 HIGH, 1 MEDIUM. Recommend: fix pricing.test.ts,
delete e2e/checkout.spec.ts (needs confirmation — pre-existing), add 1 unit test.
```

Verdicts: **OK** (leave alone), **FIX** (edit — say what), **DELETE** (negative
value — say why), and a **MISSING/CREATE** list for tests that should exist
and don't. Every finding carries rule ID, severity, and file:line where
applicable.

## The layers in one breath

- **unit** — pure input → output, no I/O, no doubles. The only layer with no
  budget; every function with decisions inside gets one.
- **integration** (backends often call this **functional**) — a module's
  behaviour through its public interface with **every input supplied by the
  test**: database replaced by fixtures/fakes, network stubbed at the
  boundary, clock fixed. It never reaches real infrastructure. This is the
  workhorse layer for edge cases and error branches.
- **e2e** — few, sacred, unmocked. Real system, real wiring, critical user
  journeys only. A mocked e2e test is a lie.

**The golden rule:** if a test can be written as an integration/functional
test with supplied inputs, it should be. When in doubt, push DOWN the pyramid,
never up. Details and the classification questions: `rules/layers.md`.

## Self-check before reporting done

- [ ] The Test Review report is in my final message.
- [ ] Every touched test is classified and placed by this repo's convention.
- [ ] No test asserts on logs; no test's subject is a third-party dependency.
- [ ] Nothing labelled e2e contains a double; nothing labelled
      integration/functional touches real infrastructure.
- [ ] Type-only needs use type-only imports; no sleeps; suites stay fast.
- [ ] Every changed pure business-logic function has a unit test.
- [ ] For every kept test I can state the real failure it catches.
- [ ] No scenario is duplicated across layers.
