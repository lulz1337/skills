# Layers: choosing, budgeting, not duplicating (TD01–TD04)

## TD01 — classify before writing; the repo decides placement

Five questions, asked before the first line of a new test:

1. Am I testing a **user journey** or a **component's behaviour**?
2. Do I need the **real running system** to learn something meaningful?
3. Can every needed input be **supplied by the test** (fixtures, fakes, stubs)?
4. Do I expect **many edge cases / error scenarios**?
5. Is **fast, reliable feedback** important here?

Component-scoped + suppliable inputs + many scenarios → **integration/functional**.
User journey + real system → **e2e**. Pure input→output logic → **unit**.

**The golden rule:** if a test can be written at a lower layer, write it
there. e2e → integration → unit; never push up.

Placement and naming belong to the repo, not to this skill. Before writing,
find how THIS repo lays tests out — existing test files, test configuration,
CI scripts — and match its folders, names, helpers, and fixtures exactly.
Only when the repo has no convention yet, propose one explicitly: e2e in one
dedicated folder at the application root; integration/functional and unit
tests named and placed the way the dominant language community expects.

## TD02 — one scenario, one layer

The same flow tested at e2e AND integration AND unit is triple maintenance
for single information. Keep each scenario at the lowest layer that can catch
its failure; e2e keeps only the single happy-path skeleton.

```text
BEFORE  e2e: login happy path, wrong password, locked account
        integration: login happy path, wrong password
AFTER   e2e: login happy path (the single walking skeleton)
        integration: wrong password, locked account, rate-limited
        unit: password-validation edge cases
```

A unit test of a pure function's own edge cases is NOT duplication of a
journey that merely passes through that function — duplication means the same
*scenario*, not the same code path.

When moving an existing test down: if the e2e covers a critical journey, keep
it AND add the detailed scenarios at integration — smoke and detail are
complementary. Fully replace (delete) the e2e only when the behaviour has no
multi-step workflow and no cross-system dependency.

## TD03 — e2e is a budgeted, product-level decision

An application has a handful of critical journeys — flows whose breakage
means the system is unusable ("user can log in", "user can complete a
purchase"). Every e2e spec must be one of them: one happy-path spec per
journey; variants and edge cases live at integration.

- Adding a new e2e spec is a product decision, not an implementation detail.
  If the repo keeps a journey manifest, every spec maps to an entry; propose
  additions instead of silently writing specs.
- A journey is not browser-specific: for a service, CLI, or library it is a
  sequence of real calls against a running instance, same rules.
- Heuristic: a flow spanning many steps and transitions is a journey; a
  handful of actions against one screen or endpoint is an integration test
  wearing an e2e costume.
- If the e2e folder outgrows what you can list from memory, it is wrong.

## TD04 — every business-logic function gets a unit test

Business logic means **decisions inside**: branches, calculations,
thresholds, rules. Every pure function that carries them must have a unit
test — the cheapest, highest-value test there is: trivial to write, instant
to run, precise about what broke. "It's covered by an integration test above
it" is not an exemption: the integration test says *that* something broke,
the unit test says *what*.

Trivial mapping and pure delegation are exempt — there, the one question at
the top of SKILL.md decides. The unit layer is the only one with no budget:
edge cases, property cases, exhaustive branches are all welcome, as long as
each test can fail for a reason other than "the test was edited".
