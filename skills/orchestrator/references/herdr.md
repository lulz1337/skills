# Visible Codex reviewer and critic in Herdr

Use this path only when the user passed `--visible` and the family is hybrid
or `--codex`. It replaces steps 4 and 5 of [codex.md](codex.md); steps 1 to 3
and 6 stay the same. The Herdr subcommands (`visible`, `pane`, `prompt`,
`read-pane`, `wait`, `stop`) and `start` may need `dangerouslyDisableSandbox:
true` for the Herdr socket.

1. Invoke the runtime's `visible` operation. It checks `HERDR_ENV=1` and
   `herdr status`. When it fails, say so in one line and use the host path in
   codex.md. Never control unseen panes from outside Herdr.
2. Inspect the panes with `pane layout`. Create a sibling with `pane split
   --direction right`, or `pane split --pane <id> --direction down`. Keep the
   user's pane usable. The runtime sets the workspace directory and
   `--no-focus`.
3. Start the run in the pane: `start <run> --pane <pane-id>`. Use the literal
   pane ID that `pane` returned.
4. Invoke `prompt <run>` in background execution with completion
   notification. It sends one prompt and waits up to 1800000 ms. Never poll.
   Keep a nonzero status and its error; a failed wait is not a result.
5. The reviewer and the critic reply in their pane. Read the reply with
   `read-pane <run>`. When it is truncated, write a focused brief that asks
   only for the missing findings, then `prompt <run>` again.

A run that waits on a dialog needs the user. Show the need, wait for the
answer, then invoke `wait <run>`; do not resend the task. Stop a bad run with
`stop <run>`. `cleanup <run>` removes only that run directory; it closes no
pane and stops no agent.

Every Herdr-hosted run is unmeasured: report its usage as unmeasured, with
herdr-hosted as the reason. Visible review has not been evaluated with live
agents; claim no measured cost or correctness for it.
