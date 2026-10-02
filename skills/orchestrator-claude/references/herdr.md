# Visible orchestration in Herdr

Use this path only when the user requested --visible. First invoke the runtime's
`visible` operation. It checks HERDR_ENV=1 and herdr status. If unavailable,
report that fact and use the host path. Never control unseen panes from outside
Herdr. The host path remains the default even inside a Herdr pane.

Use `pane layout` to inspect pane IDs and geometry. Use `pane split --direction
right` or `pane split --pane <id> --direction down` to create sibling panes.
The runtime sets the workspace directory and --no-focus. Split the agent area
when a usable sibling already exists; keep the user's pane usable. Respect host
capacity and at most nine live agents, including retained workers and reviewers.

Create the role's run with `new <family> <mode> <role>`, write its brief with
`brief <run>` and a quoted heredoc, then invoke `start <run> --pane <pane-id>`.
The runtime passes model, effort and the exact Claude tool list or Codex sandbox
from role settings. Codex interactive starts include -a never; codex exec
starts do not, because exec does not accept that interactive flag.

Invoke `prompt <run>` in the host's background execution with completion
notification, or a blocking host with sufficient timeout. It sends one prompt
and waits up to 1800000 ms. Never poll. Preserve a nonzero status and its error;
do not interpret a failed wait as a successful result. If the worker is blocked
on a dialog, show its need for input and wait for the user. After the user
answers, invoke `wait <run>`; do not resend the task.

Writable roles write final.md; read it with `report <run>`. Read-only roles
reply in their pane; use `read-pane <run>` (recent-unwrapped, 300 lines). If the
result is truncated, send a focused brief asking only for the missing findings.
For a follow-up, `brief <run>` replaces prompt.md, and `prompt <run>` sends it
to the same living agent. The role body remains attached. Stop a bad run with
`stop <run>` (ctrl+c). Keep artifacts through review; `cleanup <run>` removes
only that run directory. Cleanup does not close user panes or kill agents.

Every Herdr-hosted run is unmeasured: report herdr-hosted as the reason. The
host-path Caveman event stream is unavailable. Visible workflow behavior has
not been evaluated with live agents; do not claim measured costs or correctness.
