# Video Proof

An agent skill that records a short browser video proving a finished fix or
story actually works. It drives the real application through the `playwriter`
skill, validates the resulting file, and keeps the video out of Git.

It supplements tests. It never replaces them, and it says out loud which
acceptance criteria a video cannot establish.

## Installation

Install with the skills CLI:

```bash
npx skills add lulz1337/skills --skill video-proof
```

Or install it as a Claude Code plugin:

```
/plugin marketplace add lulz1337/skills
/plugin install video-proof@skills
```

Or copy this folder into the skill directory of your agent harness.

## Requirements

- The `playwriter` skill and an extension-backed Playwriter session. Direct
  CDP, headless, and cloud modes do not support recording.
- Chrome with the Playwriter extension enabled on the target tab.
- `ffprobe` and `ffmpeg`, or another trusted media probe and decoder, for
  artifact validation.

## Usage

Ask for it explicitly. It never triggers on ordinary testing or screenshot
requests:

```
Fix the profile save bug and record a video proof
```

```
Nahraj video, že to funguje
```

The request may come at the start of the task. The skill then checks capture
permission early and continues implementation while you reconnect the
extension if needed.

## What it guarantees

- **Capture works before it matters.** A discarded probe recording proves
  Chrome's `activeTab` permission, because `recording.isRecording` alone does
  not.
- **The video shows the code you just wrote.** It records the worktree, commit,
  branch, start command, and port, and refuses to present a recording it
  cannot tie to the current build.
- **The demonstration is honest.** Real user actions through the ghost cursor,
  results asserted from application state, no DOM edits, no forced clicks, no
  injected success data. For a bug, the original trigger against the fixed
  application.
- **The artifact is verified.** Non-zero duration, a full decode without
  errors, and extracted frames inspected at the initial state, every decisive
  checkpoint, and the result — also for leaked secrets.
- **Nothing lands in Git.** Videos go to `docs/videos/` under a rule written to
  the effective `info/exclude` (resolved through Git, so linked worktrees work),
  verified before the first write and again per artifact. Never staged, never
  committed, never LFS.

## Structure

- `SKILL.md` — the whole skill: preflight, proof matrix, build provenance,
  naming and reservation, recording, failure handling, artifact validation,
  Git safety, and delivery.

## License

MIT
