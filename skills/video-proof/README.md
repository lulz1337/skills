# Video Proof

An agent skill that records a short browser video proving a finished fix or
story actually works. It drives the real application through
[`agent-browser`](https://github.com/vercel-labs/agent-browser), records the
session with `agent-browser record`, validates the resulting file, and keeps
the video out of Git.

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

- `agent-browser` on `PATH` (`npm install -g agent-browser`). It launches its
  own Chrome, so no extension and no permission prompt is needed.
- `ffmpeg` and `ffprobe`. `agent-browser record` pipes frames into ffmpeg; the
  skill records `.mp4` where ffmpeg has libx264 and falls back to `.webm`
  (VP8) where it only has libvpx, such as Fedora's `ffmpeg-free`.

`agent-browser doctor` reports both.

## Usage

Ask for it explicitly. It never triggers on ordinary testing or screenshot
requests:

```
Fix the profile save bug and record a video proof
```

```
Nahraj video, že to funguje
```

The request may come at the start of the task. The skill then checks the
recording prerequisites early and continues implementation while you install
ffmpeg if it is missing.

## What it guarantees

- **Capture works before it matters.** A discarded probe recording proves that
  a frame reaches the file, because `agent-browser doctor` alone does not.
- **Nothing else is touched.** Every command runs in a named `--session`, so
  the proof never drives your own Chrome, another agent's browser, or the
  default session.
- **The video shows the code you just wrote.** It records the worktree, commit,
  branch, start command, and port, and refuses to present a recording it
  cannot tie to the current build.
- **The demonstration is honest.** Real user actions with the recorded cursor,
  results asserted from application state, no DOM edits, no forced clicks, no
  injected success data. For a bug, the original trigger against the fixed
  application.
- **The artifact is verified.** Non-zero duration, a full decode without
  errors, and extracted frames inspected at the initial state, every decisive
  checkpoint, and the result — also for leaked secrets. Takes are recorded
  outside the repository, so a failed take never lands in it.
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
