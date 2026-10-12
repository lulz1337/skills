---
name: video-proof
description: Record and deliver a narrated feature walkthrough of completed work, with a female English voice, bottom subtitles, changed-field highlights, and visible clicks. Use when the user explicitly requests a feature demo, video, recording, or video proof, including at the start of an implementation task. Do not use for ordinary testing or screenshot-only requests.
license: MIT
metadata:
  version: "3.0.0"
---

# Video Proof

Present the finished change through the real application: the starting situation,
the complete user scenario, and the verified result. The default is a smooth
video with a female English voice, small bottom subtitles, highlights on every
changed section or field, and a visible pointer and ripple on every click.
Preserve an explicit request for another language, voice, or a silent recording.
The video supplements tests; a polished presentation still needs evidence.
For an explicitly silent video, skip speech/caption gates and compose highlights
on the raw capture with FFmpeg; the bundled renderer requires narrated scenes.

## Establish coverage and prerequisites

Read the task, acceptance criteria, project instructions, applicable `CONTEXT.md`,
and the implementation diff, including new files. Identify the comparison base
from the task or branch; `HEAD` alone may not contain the whole change. Separate
unrelated user edits from this task.

Make a coverage table in a private temporary directory outside repositories:

| Change / criterion | Initial state and action | Visible result | Scene / highlight | Other verification |
| --- | --- | --- | --- | --- |

Account for **every task change**, not only the headline feature. Each changed
field and section needs an identifiable highlighted moment. Group changes into
the user's workflow rather than narrating filenames. Cover validation, empty/error
states, persistence, and responsive layouts when changed. Exercise the original
bug trigger against the fixed app. Describe historical behavior only when
supported by evidence; an old-version recording is optional.

Internal changes get a concise narration beat and a named check. Label them as
verified by that check, or unverified. Browser footage alone cannot establish
database state, authorization boundaries, or performance. Keep failing or
unreachable criteria open; a complete presentation cannot conceal them.

Before browser work, read `agent-browser --help` and its installed core guide
(`agent-browser skills get core`). Consult `record --help` for capture details.
Use one named `--session video-proof-<id>` throughout, including cleanup. Record
in its private Chrome, without auto-connect, profile reuse, or personal tabs.

Read [production.md](references/production.md) before generating speech or the
timeline. Resolve helpers from this skill's directory, not the target app. Check
`agent-browser doctor`, FFmpeg video/audio encoders, `ffprobe`, the `subtitles`
filter, and a speech provider for the requested voice/language. Prefer installed tools. Resolve
missing prerequisites within existing authorization or report the exact blocker
while continuing independent work. Do not silently substitute a silent,
uncaptioned, or incomplete video.

Prove the pipeline with a disposable capture and voice sample: composite a
subtitle and highlight, probe both streams, decode, inspect a frame, and listen.
Delete the probe. Tool inventory alone is not capture proof.

## Use the finished build

Record the target worktree, HEAD, branch, and working-tree status. Run the
project's checks and documented build/start procedure there after the last source
change. Use project-supported fixtures and a test account. Record the start
command, process ID, directory, port, and build evidence; verify that the browser
reaches this process. Choose another port instead of stopping an unrelated server.
A deployed URL needs equivalent provenance.

Rebuild stale bundles and restart task-owned processes when needed. Source changes
after recording invalidate affected proof: rerun its checks and rerecord it.
Uncertain build provenance means the recording cannot be called proof.

Authenticate and prepare initial data before capture. Keep credentials, cookies,
real customer data, notifications, and personal information out of frames and
narration. Follow the environment's authorized authentication method. Exporting
personal SSO state needs consent unless already authorized; any export stays in
the private temporary directory and is deleted during cleanup.

## Script and rehearse

Write scene beats as **context → action → visible result**. Open on the useful
screen with one sentence explaining the change. End on the demonstrated outcome.
Add scenes for other workflow steps or branches. Length follows complete coverage;
never drop changes to meet an arbitrary duration.

Narrate concrete behavior: "Saving now shows a confirmation and keeps your entries."
Read product labels exactly and explain why a result matters. Use a calm female
voice around 130–160 words per minute. Keep sentences short; remove filler, sales
language, generic praise, and unsupported claims. Speak about the product, not the
automation. Keep one voice, accent, and level. Music, effects, and an avatar are
absent unless requested.

Generate speech and its actual timestamps before the final take. Pace actions and
holds against them. Captions reflect the spoken words, with standard product
spelling. Listen for names, numbers, acronyms, and pronunciation. New audio
invalidates old timings.

Rehearse the whole scenario. Use a consistent viewport, preferably 1280×720 or
1920×1080, and readable UI. Record 30 fps; use 60 only when motion needs it.
Use `--input-mode smooth` for pointer movement. Check scrolling in rehearsal:
ease with native support where available, otherwise use small increments rather
than a large jump. Keep context visible around highlighted fields.

## Capture real actions and direct attention

Prefer one continuous successful scenario:

```bash
agent-browser --session <name> --input-mode smooth record start \
  "<tmpdir>/take.<mp4-or-webm>" --cursor --contact-sheet
```

`--cursor` captures the pointer and click ripple. Verify both in the probe;
every click, including checkbox and select interactions, must be visible.
Rehearsed dependent sequences can use `batch --bail` to avoid command gaps.
Install a cleanup trap for unattended sequences; stopping capture is mandatory
on every exit path after it starts.

Use fresh snapshot refs and real UI commands: observe → act → assert the expected
state. Resnapshot after navigation or large changes. Assert with `wait --text`,
`wait --url`, `is visible`, or `get text`; fixed waits serve viewer readability
only. Hold the initial state for about 1–2 seconds and decisive results for at
least 1.5 seconds, longer when speech or reading requires it. Check meaningful
page state and `errors --json` (plain `errors` prints nothing).

Log clip boundaries, clicks, and checkpoints against the **recording clock**.
Use `get box <ref> --json` for each changed target's viewport coordinates.
Apply timed thin outlines in postproduction, one target at a time, while that
target is discussed. Clear outlines before scrolling/layout movement and
remeasure afterward. Coordinates must match the captured resolution. Measure
result positions again after layout-changing actions.

Keep the original capture untouched. Highlights and subtitles are presentation
annotations. They must leave labels and results readable. Do not modify the app's
DOM/data, inject success, fake network responses, or replace user actions with
hidden API calls. If a native click ripple is missing, add a timed annotation
from the logged real click; never invent a click to imply an action occurred.

On an interaction/assertion failure, stop and discard the take. If stopping fails,
close the named session and confirm its disappearance from `session list`; avoid
commands that relaunch it. Fix and rehearse again. After three failed fixes, name
the doubtful assumption before another attempt. Never hide a failed outcome in an
edit. Stop with `record stop --json`; `capturedFrames` of 0 or 1 is a still image,
not a captured workflow.

## Compose, evaluate, and deliver

Follow [production.md](references/production.md) and use `scripts/render.py` for
narration, bottom subtitles, and highlights. Keep UI actions at real speed.
Trim preparation and idle gaps only; preserve the trigger, relevant loading
behavior, state continuity, and decisive result. Announce resets or alternate
scenarios. Cut at stable boundaries; transitions must not obscure evidence.
The renderer allows a brief final-frame hold, but refuses a long freeze used to
cover rushed footage. Rerecord at the correct pace instead.

Evaluate the **final rendered file**, not just the raw take:

1. Probe dimensions, positive duration, video/audio streams; decode the whole file
   with `ffmpeg -v error -i <file> -f null -`.
2. Watch and listen from start to finish. Confirm smooth motion, visible real
   clicks, the requested voice/language (female English by default), pronunciation, volume,
   complete sentences, and synchronization. If playback or listening is
   unavailable, say so; the presentation remains unverified.
3. Inspect extracted frames at the start, every changed target, each click/result,
   seams, caption intervals, and the end. Check readable text, contrast,
   unobstructed controls, outline position, caption presence, and sensitive data.
4. Reconcile every coverage row with a final-video timestamp and its separate
   check. Missing, unreadable, rushed, or unsupported beats fail the presentation.
5. Read [delivery.md](references/delivery.md) before any output write to the target
   repository; it governs ignore rules, branch naming, atomic reservation, Git
   safety, and private artifact delivery. Deliver only after verification passes.

Only the finished video goes into `docs/videos/`. Keep raw footage, scripts,
audio, subtitles, coverage notes, frames, and renderer reports in the private
temporary directory. Close the browser, delete temporary material including auth
exports, and stop only processes started for this proof.

Return the video link, concise timestamped change coverage, nonvisual checks, and
anything unverified. Call an incomplete deliverable incomplete. Research behind
this workflow is in [sources.md](references/sources.md); read it when revising the
skill rather than for each recording.
