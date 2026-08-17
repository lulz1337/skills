# Isolation: what each layer may touch (TD20–TD22)

The three layers differ in exactly one dimension: **how much of the real
world the test is allowed to reach**. Everything else follows from it.

| Layer | May reach | Must supply |
|-------|-----------|-------------|
| unit | nothing — pure input → output | nothing (no doubles; needing one means it is not a unit test) |
| integration / functional | in-process code up to the boundary | **every input**: data, time, network responses, configuration |
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

## TD21 — integration/functional tests supply everything, reach nothing (BLOCKER)

Backends often call this layer **functional tests**; frontends call it
integration. Same contract either way:

- **Every input is supplied by the test**: the database is replaced by
  fixtures, fakes, or an in-memory substitute; every external response is
  stubbed at the boundary; the clock is fixed; configuration is explicit.
- **The test never reaches real infrastructure**: no live database, no
  network call leaving the process, no message broker, no third-party
  service, no shared filesystem state (temp dirs owned by the test are
  fine). A test that needs infrastructure standing up is either an e2e test
  in the wrong folder or a flake generator.

Why so strict: supplied inputs are what make this layer deterministic, fast,
and parallel-safe — the properties that let it host hundreds of edge-case
scenarios that would be unaffordable at e2e. Every infrastructure touch
trades all three away and gains nothing the e2e layer doesn't already cover.

This is the workhorse layer: error branches, permission failures, retries,
empty states, validation, calculated fields — anything that benefits from
simulating **varied inputs deterministically**.

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
