---
name: test-discipline
description: >-
  Test hygiene and review when creating, editing, or deleting recognized test
  files, including .spec/.test, Go _test.go and established language test
  names. Also use when explicitly asked to review tests. Do not activate for
  reading tests, running tests, strategy discussion, or source-only changes.
  End activated work with a severity-graded review and behavior gaps.
---

# Test Discipline

## Scope

Load this skill when a task creates, changes, or deletes test code using the
repository's convention: `.spec.*`, `.test.*`, Go `_test.go`, Python `test_*.py`
or `*_test.py`, Java `*Test.java`, and analogous established runner patterns.
Also load it for an explicit request to review tests. A filename mentioned in
the request, a read-only inspection, test execution, strategy discussion, or
source-only change does not activate it. Identify actual changed paths from
tool results or the diff; do not infer a mutation from text in a shell command.

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

After changing a recognized test file or when explicitly asked to review tests,
end with a **Test Review** of the relevant files. If inspection shows the
requested behavior is already covered and no change is needed, explain the
no-op without adding tests or manufacturing a review section.

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
   For JSON fixture/schema work, follow [`rules/fixtures.md`](rules/fixtures.md)
   and validate only files declared in the manifest; do not scan every file
   under a `tests/` directory as executable test code.
3. **Do the semantic review** the checker cannot do: wrong layer, scenario
   duplication across layers, important behavior gaps,
   third-party subjects hidden behind helpers, infrastructure reached through
   indirection. Read the rule files relevant to what you found:
   - [`rules/layers.md`](rules/layers.md) — choosing the layer, duplication,
     e2e budget, load tests, behavior gaps (TD01–TD04)
   - [`rules/scope.md`](rules/scope.md) — what a test must never test: logs,
     third-party dependencies, the implementation itself (TD10–TD14)
   - [`rules/isolation.md`](rules/isolation.md) — what each layer may touch:
     unmocked e2e, fully-supplied integration/functional inputs, UI driven
     as the user drives it (TD20–TD23)
   - [`rules/speed.md`](rules/speed.md) — why suites get slow and how not to:
     type-only imports, shallow module graphs, no sleeps (TD30–TD32)
   - [`rules/failures.md`](rules/failures.md) — what to do with a red test;
     never weaken one to green (TD40–TD41)
   - [`rules/fixtures.md`](rules/fixtures.md) — declared JSON schemas,
     fixtures, and deterministic generated artifacts
4. **Emit the report** in the format below. Mark heuristics as suspicions and
confirm them against behavior and layer before assigning a finding.
5. **Act within scope.** Fix newly written defects. Do not silently delete
   pre-existing security, compatibility, or external-contract tests; explain
   the evidence and recommend a change. Preserve tests guarding different
   failures even when they exercise the same path at different layers.

## Severity

- **BLOCKER** — the test is actively harmful: it passes while the app is
  broken, breaks while the app is fine, or burns machine time for nothing.
  Log assertions (TD10), third-party subjects (TD11), mocked e2e (TD20),
  tests weakened to go green (TD41). Infrastructure findings need a layer
  and isolation review; real isolated resources may be the contract under test.
- **HIGH** — wrong or missing value: implementation mirrors (TD12), the same
  scenario duplicated across layers (TD02), focused/skipped tests left
  committed (TD41), an e2e spec that
  is not a critical journey (TD03), UI driven through internals — structural
  selectors, synthetic events, direct handler calls — instead of the way the
  user drives it (TD23; pure-logic unit tests are exempt).
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
| e2e/checkout.spec.ts | DELETE | TD20 BLOCKER — network mocked inside an e2e journey; the user-visible journey is already covered elsewhere |

**Missing (CREATE):**
- behavior: discounts above the order cap are not shown clamped in any observable outcome (TD04)

**Summary:** 1 BLOCKER, 0 HIGH, 1 MEDIUM. Recommend: fix pricing.test.ts,
recommend review of the pre-existing e2e spec, add coverage for the cap behavior at its narrowest useful layer.
```

Verdicts: **OK** (leave alone), **FIX** (edit — say what), **DELETE** (negative
value — say why), and a **MISSING/CREATE** list for tests that should exist
and don't. Every finding carries rule ID, severity, and file:line where
applicable.

## The layers in one breath

- **unit** — focused behavior with supplied inputs; doubles are usually
  unnecessary. Add tests when they protect meaningful behavior, not once per
  function or branch.
- **integration** (often **functional**) — behavior through public interfaces.
  Usually control external inputs at boundaries. Real isolated infrastructure
  is valid when database constraints, RLS, transaction rollback, migrations,
  or provider behavior is the subject.
- **contract** — compatibility at a producer/consumer or provider boundary;
  keep schema integrity, provider conformance, and business behavior distinct.
  A mock matching a schema does not prove the runtime provider conforms.
- **load** — performance behavior under bounded, representative workload; use
  the load rules in `rules/layers.md`.
- **e2e** — real wiring for critical user journeys. A mocked test is not proof
  of the deployed journey.

**The golden rule:** if a test can be written as an integration/functional
test with supplied inputs, it should be. When in doubt, push DOWN the pyramid,
never up. Details and the classification questions: `rules/layers.md`.

## Self-check before reporting done

- [ ] The Test Review report is in my final message.
- [ ] Every touched test is classified and placed by this repo's convention.
- [ ] No test asserts on logs; no test's subject is a third-party dependency.
- [ ] E2e tests use real wiring; integration/functional tests may use real
      infrastructure when it is isolated and infrastructure behavior is the subject.
- [ ] UI tests locate by role/label/visible text and interact through user
      actions; logic is unit-tested directly, not through the UI.
- [ ] Type-only needs use type-only imports; replace arbitrary waits with
      controls such as fake timers, while retaining justified load think time.
- [ ] Each kept test protects a concrete business rule or external contract
      with an observable outcome; no test-count target or per-function quota.
- [ ] For every kept test I can state the real failure it catches.
- [ ] No scenario is duplicated across layers.
