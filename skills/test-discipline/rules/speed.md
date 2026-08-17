# Speed: a slow suite stops being run (TD30–TD32)

A test suite's value is proportional to how often it runs. A suite that takes
minutes runs on CI only; a suite that takes hours effectively never runs. The
three rules below target the usual causes.

## TD30 — type-only needs use type-only imports (MEDIUM)

In statically typed languages, a test often needs a name **only as a type**
— for an annotation, a signature, a fixture's shape. Importing it as a value
drags the module's entire runtime dependency graph into every test process:
the module initializes, its imports initialize, transpilation/compilation
covers all of it. In a large codebase this is the difference between a suite
that runs in seconds and one that runs in hours.

The rule: if a name is used only in type positions, import it in the
language's type-only form (in TypeScript, `import type { X } from '…'`; other
typed ecosystems have their equivalents — dedicated type imports, interface
references, header-only includes). If the language offers no type-only form,
depend on the narrowest module that declares the shape, not on the package
root.

The wider principle: **keep the test's module graph shallow.** Import the
unit under test, not the application's composition root; never initialize a
framework, a dependency-injection container, or a plugin system in a unit or
integration test unless that container IS the unit under test.

## TD31 — no sleeps, no real timers (MEDIUM)

A hardcoded sleep is a race condition with a trophy for showing up late: too
short → flake, long enough → the suite crawls, and it is always both across
machines. Replace every sleep and real-timer wait with:

- **event-based waiting** — await the promise/future/channel, wait for the
  condition or element, subscribe to the completion signal;
- **a controlled clock** — for debounce, throttle, scheduling, and timeout
  logic, inject or fake time and advance it explicitly. Time is an input;
  integration/functional tests supply their inputs (TD21).

The same applies to retry-with-backoff loops around assertions: they hide the
missing completion signal instead of awaiting it.

## TD32 — build the world once, or not at all (MEDIUM)

Per-test world building — reconstructing the application, reloading fixtures,
re-running migrations on a fresh in-memory store for every single test — is
almost always accidental, inherited from a copied setup block. Discipline:

- Share expensive **immutable** setup at the suite level; keep per-test setup
  for the mutable slice the test actually changes.
- Render/construct the smallest unit that exhibits the behaviour, not the
  whole application shell.
- If a single test's setup dwarfs its assertions, the test is probably at the
  wrong layer — usually one below where it belongs (see TD01).

Abstraction guidance at this layer: explicit inline setup beats deep helper
towers; abstract only on real repetition (5+ occurrences), domain meaning, or
genuinely shared fixtures.
