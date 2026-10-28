# Isolation: what each layer may touch (TD20–TD23)

The three layers differ in exactly one dimension: **how much of the real
world the test is allowed to reach**. Everything else follows from it.

| Layer | May reach | Must supply |
|-------|-----------|-------------|
| unit | nothing — pure input → output | nothing (no doubles; needing one means it is not a unit test) |
| integration / functional | in-process code and isolated real infrastructure when its semantics matter | data, time, responses, and configuration not under test |
| e2e | everything, for real | nothing may be substituted |

## TD20 — e2e is unmocked, always (BLOCKER)

An e2e test exercises the system exactly as its user drives it: real entry
surface, real composition root, real wiring, real dependencies. No doubles,
no stubbed network, no intercepted routes, no fabricated auth state. A mocked
e2e test goes green while the app is broken — which is the one failure e2e
exists to prevent. Any double inside an e2e spec means: reclassify the spec
as integration (move it), or remove the double.

Seed data and preconditions through the system's own real interfaces (its
API, its CLI), not by reaching into internals. Prefer auto-retrying
assertions over fixed waits; never swallow errors to keep a journey green —
both produce false passes.

## TD21 — isolate infrastructure unless its behavior is the subject

Backends often call this layer **functional tests**; frontends call it
integration. Same contract either way:

- Normally supply external inputs at boundaries: response data, time,
  configuration, and randomness. Use test-owned isolated resources and
  deterministic cleanup.
- Real isolated infrastructure is appropriate when its semantics are under
  test: database constraints, RLS, rollback, migrations, locking, or broker
  delivery. Make isolation, ownership, and cleanup explicit; never mutate
  shared developer or production state.

Prefer supplied inputs for broad edge-case coverage. Do not classify a test
as harmful merely because its path or source mentions a database or server;
verify whether it is isolated and what contract it proves.

This is the workhorse layer for behavior with varied inputs. Keep provider
conformance, schema integrity, and business behavior as separate claims. A
consumer test against a mock proves the consumer's expectation; only a
provider verification or real contract exchange proves provider conformance.
Do not add Pact solely to satisfy this guidance.

See [Pact consumer and provider testing](https://docs.pact.io/).

Go tests use the standard [`testing`](https://pkg.go.dev/testing) package and
follow the repository's package and legal import placement. Prefer meaningful
table cases when they clarify distinct business outcomes. Exercise real domain
aggregates; fix business time explicitly and use doubles only at external
boundaries. Use isolated real infrastructure when its behavior is the subject.

## TD22 — double the boundary, never the internals (HIGH)

Mock/fake/stub only at the module's external boundary (network, persistence,
clock, randomness, third-party services) — never internal functions or
collaborators of the unit under test; that produces implementation mirrors
(TD12). Further discipline that keeps doubles honest:

- Every double is a claim about a contract that can silently drift. Where a
  producer and consumer are both in reach, prefer one shared contract test
  over two independent fantasies.
- Build fixtures with factory functions: sensible defaults + explicit
  overrides, so test data stays complete and each test states only what it
  cares about. Keep payloads minimal and purpose-built.
- Define the happy path once for the suite; override per-test only for
  errors and edge cases; reset doubles between tests — shared mutable double
  state is a top flake source.
- A green suite built on doubles proves behaviour, not wiring — wiring proof
  is the e2e layer's job, don't fake it here.

## TD23 — drive the UI as the user does (HIGH)

Applies to every test that renders or drives a user interface, at any layer
(integration/functional UI tests and e2e alike):

- **Locate elements the way the user perceives them**: by role, then by
  visible label/text, with a dedicated test identifier as the last resort.
  Structural selectors (CSS classes, XPath, DOM paths, component internals)
  need a stated justification — they break on every markup refactor without
  any behaviour changing.
- **Interact through user actions**: click the button the user sees, type
  into the field, submit the form. Never call an internal handler directly
  or fire synthetic events on internal nodes — that tests wiring you
  imagined, not the interface the user gets.
- **Assert what the user sees or receives**, not the component's internal
  state.

Why: what you cannot find by role or label, the user (and their screen
reader) cannot find either — the test guards accessibility for free, and it
keeps passing across markup refactors because it is coupled to behaviour,
not structure.

**The exception is logic.** A pure function extracted from a component —
formatting, validation, calculation, a state reducer — is unit-tested
directly through its inputs and outputs (TD04): no rendering, no queries,
no user simulation. This rule governs tests OF the interface; it must not
push logic testing up into the UI.
