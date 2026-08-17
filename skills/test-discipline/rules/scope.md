# Scope: what a test must never test (TD10–TD14)

## TD10 — never assert on logs (BLOCKER)

Tests assert observable behaviour: the return value, the state change, the
emitted event, the response. Never that something was logged — no spies on
the logger or console, no stdout/stderr capture, no message matching. A log
assertion breaks on every reworded message and catches no real failure; it is
the purest form of testing the implementation instead of the behaviour.

```text
BEFORE  spy on the logger → call handle(invalidPayload)
        → assert "invalid payload received" was logged
AFTER   result = handle(invalidPayload)
        → assert result is an error
        → assert the store accepted nothing
```

The only exemption: the log line IS the contract, and the task says so
explicitly — an audit trail with a required schema, a structured-logging
format consumed by monitoring, a compliance record. Then test it as the data
contract it is, and say so in the review.

## TD11 — never test a third-party dependency (BLOCKER)

The subject of a test must be code this repo maintains. A test that exercises
a library's own behaviour — a pattern-matching library matching patterns, an
ORM building queries, a date library parsing dates, a validation library
validating its own schema types, the framework's router routing — duplicates
the dependency's own test suite, burns CI time, and catches nothing: when it
fails, the fix is never in this repo.

The litmus test: **would this test pass or fail identically if it lived in
the dependency's own repository?** If yes, delete it. Test YOUR code's use of
the dependency: the decision your code makes with the result, the mapping
your code applies, the branch your code takes.

If you genuinely distrust a dependency's specific behaviour your code relies
on (an edge case you were bitten by), write at most ONE thin, clearly-marked
contract test at the boundary — named so the reader knows it guards an
assumption about the dependency, not project behaviour.

## TD12 — no implementation mirrors (HIGH)

An assertion that restates the code can only fail when someone edits the test
or the internals — it catches no real failure. The classic form: assert that
an internal collaborator was called with exact arguments, instead of
asserting the outcome a caller can observe.

```text
BEFORE  createUser(input)
        → assert repository.save was called with {name: "Jan", role: "admin"}
AFTER   created = createUser(input)
        → assert getUser(created.id) has {name: "Jan", role: "admin"}
```

Call-verification on a double is legitimate only at a real boundary where the
call IS the observable outcome (an outgoing notification, a payment capture)
— and then prefer capturing the payload inside the fake and asserting on the
captured data over verifying call shapes.

## TD13 — snapshots only for data contracts (MEDIUM)

Structure snapshots (rendered components, DOM trees, deep object dumps of
internals) test structure, not behaviour, and break on every refactor.
Snapshots are allowed only for: data contracts (serialized API responses),
complex pure-function output, error-message consistency, generated code.

## TD14 — test count is never a deliverable (HIGH/LOW)

"Added 47 tests" is not a result; 5 tests that each catch a distinct real
failure beat 47 that re-derive the implementation. Consequences:

- No new test file per code file, reflexively — tests follow behaviours, not
  the file tree.
- Coverage is a smell detector for *missing* tests, never a target to hit
  with filler. A test written to color a line green, with no statable real
  failure it catches, gets deleted in review.
- Net test count must be justified by net new behaviour.
