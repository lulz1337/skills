# Enforcement and limitations

Claude's `orchestrator-guard.py` activates on the three slash commands or the
matching Skill call and stays active across turns and resumes. It denies the
main thread's repository tools and unknown tools, and accepts Bash only for a
single validated runtime call or `git status --short`. Runtime help is allowed.
Agent dispatch must use the selected roster: Claude roles for Claude, no Claude
Agent calls for Codex, and only Claude reviewer/sage/critic for hybrid. New runs
and launch/prompt actions must match the selected family, including retained runs. It exempts actual
subagents by the hook's `agent_id`, not by `agent_type` (a main thread can also
have an agent type). Only the user's exact message `orchestrator off` clears
this session's state. No global deny rules restrict workers or ordinary sessions.
The guard is a workflow boundary, not a security sandbox against malicious
workers or arbitrary modifications to the installed helper.

Claude honors frontmatter `disallowed-tools` during the invocation turn; its
documentation says this restriction clears on the next user message. The
runtime hook enforces the boundary across turns. The same guard runs in native
Codex with `--provider codex`, through UserPromptSubmit and PreToolUse hooks
merged into ~/.codex/hooks.json. Native activation recognizes an explicit
$orchestrator-* token anywhere in the user prompt, or a slash call at its start. Codex requires the new hook definitions to be
reviewed and trusted in `/hooks`; disabled or untrusted hooks do not enforce it.
For vetted automated tests only, `--dangerously-bypass-hook-trust` activates
those hooks for that invocation. Do not add that flag to ordinary workflows.

Native Codex denies local shell reads, apply_patch, MCP and other local task
tools while orchestration is active. Its runtime launches independent worker
sessions, which are not activated by the main thread's session state. Native
spawn_agent is not an alternate dispatch route. Coordination uses the helper,
update_plan and request_user_input. Hosted tools such as WebSearch do not pass
through Codex tool hooks; their prohibition remains instructional. Some
specialized paths can also bypass the hook path. This is a workflow guard,
not complete tool isolation. Codex worker sandboxes limit read-only roles;
verifier, runner and browser need writable runtime output and rely on their
contract to prohibit source edits.

Official references checked 2026-10-01: Claude hooks
https://code.claude.com/docs/en/hooks, skill tool restrictions
https://code.claude.com/docs/en/skills#frontmatter-reference and model aliases
https://code.claude.com/docs/en/model-config; Codex model/list
https://learn.chatgpt.com/docs/app-server#list-models-modellist, native hooks
https://learn.chatgpt.com/docs/hooks and Sol
https://developers.openai.com/api/docs/models/gpt-6.1-sol.
