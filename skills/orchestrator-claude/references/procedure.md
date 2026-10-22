# Claude dispatch

Follow [workflow.md](workflow.md). For dependencies or a retained plan, use
[scheduling.md](scheduling.md). For read-only Claude roles (scout, researcher,
reviewer, oracle, sage, critic), use `new claude <mode> <role>`, `brief <run>`,
`start <run>` and `report <run> --final`. Call Claude `start` without
`dangerouslyDisableSandbox`; the guard denies it. Writable Claude roles
(implementer, verifier, runner, browser) and publisher use Agent with the
resolved agent_type and no model override. Start descriptions with the role;
use background execution with host completion notifications and reuse workers
for follow-ups when supported.

Implementation uses worker-<mode>; review uses reviewer-<mode>. All specialist
roles use their resolved definitions. Load [examples.md](examples.md) for dispatch
syntax, [pitfalls.md](pitfalls.md) for an observed failure, or [herdr.md](herdr.md)
for --visible. Claude read-only tool lists do not sandbox Bash; briefs bound
mutation and prohibit nested agents.
