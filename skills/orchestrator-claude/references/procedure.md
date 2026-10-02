# Claude dispatch

Follow [workflow.md](workflow.md). For dependencies or a retained plan, use
[scheduling.md](scheduling.md). Use Agent with the runtime's resolved
agent_type and no model override. Start descriptions with the role, such as
`[scout] Locate pricing`. Use background execution when the host supplies
completion notifications; reuse workers for follow-ups when supported.

Implementation uses worker-<mode>; review uses reviewer-<mode>. All specialist
roles use their resolved definitions. Load [examples.md](examples.md) for dispatch
syntax, [pitfalls.md](pitfalls.md) for an observed failure, or [herdr.md](herdr.md)
for --visible. Claude read-only tool lists do not sandbox Bash; briefs bound
mutation and prohibit nested agents.
