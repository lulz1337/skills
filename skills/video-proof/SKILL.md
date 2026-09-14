---
name: video-proof
description: Record and deliver a Playwriter video that demonstrates a completed bug fix or small user story. Use only when the user explicitly asks for a video, recording, or video proof of completed work, including when the request appears at the start of the task. Do not use for ordinary testing or screenshot-only requests.
license: MIT
metadata:
  version: "1.0.0"
---

# Video Proof

Create a short, trustworthy video demonstration after the requested implementation
and its relevant checks are complete. The video supplements tests; it does not
replace them.

## Load Playwriter and preflight early

Before the first Playwriter command:

1. Load the `playwriter` skill.
2. Run `playwriter skill` and read its complete output. Do not truncate it.
3. Use an extension-backed Playwriter session. Do not use direct CDP, headless, or
   cloud mode: these modes do not support `recording.start` and `recording.stop`.
4. Do not use `playwriter recorder start`. That command records human actions for
   skill generation; it does not create the requested video.

Check the recording prerequisite early, even when the user requests the video at
the start of a larger task:

- Create a dedicated Playwriter session.
- Acquire a page owned by that session according to the Playwriter instructions
  and navigate it to the target application as soon as the application can run.
- Check `recording.isRecording({ page: state.page })`. If it reports an existing
  recording on that page, do not disturb it; use a different page or report the
  conflict.
- Prove capture permission by starting a recording to a unique path inside a
  private temporary directory, with `audio: false` and `maxDurationMs: 10000`.
  Immediately call `recording.cancel({ page: state.page })`, confirm that
  `recording.isRecording` is false, and delete only that probe directory. Merely
  calling `recording.isRecording` is insufficient: it does not verify Chrome's
  `activeTab` capture permission.
- If Chrome is not running, start it using the platform-appropriate command from
  the Playwriter documentation.
- If Playwriter reports that the extension is disconnected or the tab is not
  enabled, tell the user immediately. Ask only for the minimum action: open the
  target tab in Chrome, click the Playwriter extension icon on that tab, approve
  current-tab capture if Chrome asks, and tell the agent when it is ready.
- Continue implementation and non-video verification while the user fixes the
  connection when practical.

Do not save or present the discarded preflight capture. If the final scenario
uses a different tab, or navigation may have revoked the tab permission, repeat
the capture probe on the final tab before creating any project output. Do not
start the final recording during preflight.

## Derive the proof scenario

Read the ticket, acceptance criteria, project instructions, and relevant
`CONTEXT.md` files.

Create a small internal proof matrix with one row per acceptance criterion:

- criterion;
- initial visible state;
- decisive user action;
- expected visible result;
- evidence method: video, automated check, or both.

The recorded scenario must contain:

1. The relevant initial state.
2. The shortest sequence of real user actions that exercises the behavior.
3. A stable, readable view of the expected result.

For a bug, reproduce the original triggering situation against the fixed
application. Demonstrate that the same trigger now produces the correct result.
Do not manufacture a separate, easier scenario that avoids the bug.

Mark criteria that cannot be established by a browser video, such as persistence
after a backend restart, authorization boundaries, database state, performance,
or an internal API contract. Verify them with suitable tests or diagnostics and
list them separately in the final report. Never treat the video as a substitute
for those checks.

## Run the correct application

Identify the target project's Git worktree and application start procedure from
its own documentation and existing scripts.

Before starting the application, record:

```bash
git rev-parse --show-toplevel
git rev-parse HEAD
git symbolic-ref --quiet --short HEAD || true
git status --short
```

Run build, migration, seed, and start commands from that exact worktree. Use
project-supported test data or fixtures only when they represent the acceptance
environment honestly.

After the last source change:

1. Run the relevant automated checks.
2. Rebuild or restart anything that could contain an older bundle.
3. Start a new application process from the target worktree.
4. Prefer a new, known port instead of reusing an unidentified server.
5. Record the command, process identifier, working directory, port, and build
   output needed to connect the running application to the current worktree.
6. Verify that the browser URL reaches that process and not an old server,
   another worktree, or a previously built deployment.

Do not stop or replace an unrelated process merely because it occupies the usual
port. Choose another port or report the conflict.

If the current build cannot be tied to the current worktree with reasonable
evidence, do not record it as proof.

Any source change after recording invalidates the video. Run the relevant checks
again and record a new proof.

## Prepare the output safely

The output repository is always the Git checkout of the project being fixed. It
is not the repository that contains this skill unless that repository is itself
the target project.

Require a Git working tree:

```bash
video_repo_root=$(git rev-parse --show-toplevel)
```

Save videos only below:

```text
<video_repo_root>/docs/videos/
```

Before creating that directory, a reservation file, a video, or any other output,
inspect the index:

```bash
git -C "$video_repo_root" ls-files -- docs/videos/
```

Remember the result. Ignore rules do not protect files that are already tracked.
Do not delete existing files, remove them from the index, modify their staged
state, or conceal them.

Check whether an ignore rule already applies:

```bash
git -C "$video_repo_root" check-ignore -v --no-index -- \
  docs/videos/.video-proof-ignore-probe
```

If no rule applies, append this exact rule to the repository's local exclude file:

```text
/docs/videos/
```

Resolve the effective exclude file through Git:

```bash
video_exclude_file=$(
  git -C "$video_repo_root" rev-parse \
    --path-format=absolute --git-path info/exclude
)
```

This is important for linked worktrees. Do not construct `.git/info/exclude`
manually and do not assume that `.git` is a directory. Preserve existing exclude
content and ensure the new rule starts on a new line. Do not modify the tracked
`.gitignore` unless the user separately asks for that repository change.

Verify the effective rule before the first output write:

```bash
git -C "$video_repo_root" check-ignore -v --no-index -- \
  docs/videos/.video-proof-ignore-probe
```

Stop if the check still does not identify an ignore rule.

Only then create `docs/videos/`.

## Name the video

Read the full local branch name with:

```bash
git -C "$video_repo_root" symbolic-ref --quiet --short HEAD
```

Use the entire returned name as the branch input, not only the text after its last
slash. Normalize it as follows:

1. Apply Unicode NFKD normalization and remove combining marks.
2. Replace every slash with `-`.
3. Replace each remaining run outside `A-Z`, `a-z`, `0-9`, `.`, `_`, and `-`
   with `-`.
4. Collapse repeated `-`.
5. Remove leading `.` or `-` and trailing `.`, `_`, or `-`.
6. Preserve ASCII letter case.
7. Limit the result to 80 characters. If truncation is necessary, append `-`
   and the first 12 hexadecimal characters of a SHA-256 hash of the exact,
   unnormalized full branch name.
8. If normalization produces an empty string, use `branch-` followed by that
   12-character hash.

For detached HEAD, do not invent a branch name. Use:

```text
detached-<first 12 hexadecimal characters of HEAD>
```

Normalize the short scenario description with the same rules, convert it to
lowercase, and limit it to 48 characters. Use `proof-<12-character hash>` if it
would otherwise be empty.

Construct the filename as:

```text
<branch-slug>__<description-slug>__<YYYYMMDD-HHMMSS>.mp4
```

For example:

```text
fix-T20-123__ulozeni-profilu__20260914-143022.mp4
```

Never pass an existing path to `recording.start`.

Reserve the candidate name atomically with a sibling
`<candidate>.video-proof-lock` created with exclusive or noclobber semantics. If
the video or reservation already exists, append `-02`, `-03`, and so on to the
timestamp and try again. Do not delete a reservation created by another process.
Remove only the reservation created by the current attempt, after recording has
stopped.

Keep temporary screenshots, extracted frames, logs, and media-probe output in a
temporary directory outside the repository.

## Record the final demonstration

Prepare authentication, test data, and the initial application state before
recording. Use a dedicated tab. Ensure that the tab shows no secrets,
notifications, unrelated personal information, production customer data, or
other sensitive content.

Use the native Playwriter API documented by `playwriter skill`:

```js
await recording.start({
  page: state.page,
  outputPath: "/absolute/path/to/docs/videos/the-proof.mp4",
  frameRate: 30,
  audio: false,
  videoBitsPerSecond: 2500000,
  aspectRatio: { width: 16, height: 9 },
  maxDurationMs: 5 * 60 * 1000,
})

state.videoProof = {
  active: true,
  startedAt: Date.now(),
  checkpoints: [],
}
```

Use absolute output paths. Keep audio disabled unless the user explicitly asks
for audio and the audio is safe to disclose.

After recording starts:

- Leave the initial state visible briefly.
- Use Playwriter locator and mouse interactions so the ghost cursor shows the
  workflow.
- Follow Playwriter's observe -> act -> observe loop.
- After each action, inspect the URL, a fresh snapshot, and
  `getLatestLogs({ page: state.page, sinceLastCall: true })`.
- Assert each expected result from application state. Do not infer success only
  from the absence of an exception.
- Pause briefly at the initial state and each decisive result so a viewer can
  read them.
- Record each decisive checkpoint label and its elapsed time from
  `state.videoProof.startedAt`.

Do not modify the DOM, invoke `element.click()` through `page.evaluate`, force
interactions through blockers, intercept responses, or inject fake success data.
Do not edit the application in memory for the recording. Project-supported test
fixtures are acceptable only when the proof clearly represents the environment
and criterion being demonstrated.

Stop normally and retain the full result:

```js
state.recordingResult = await recording.stop({ page: state.page })
state.videoProof.active = false
```

## Handle failures and interruptions

After `recording.start` succeeds, ending the capture becomes mandatory on every
exit path.

If an interaction, assertion, command, or connection fails:

1. Treat the current take as failed.
2. In the next available Playwriter call, check
   `recording.isRecording({ page: state.page })`.
3. If it is active, call `recording.stop({ page: state.page })`.
4. If a normal stop cannot complete, retry once after restoring the extension
   connection, then call `recording.cancel({ page: state.page })` if available.
5. Confirm that `recording.isRecording` is false.
6. Delete only the failed video and reservation created by the current attempt,
   or retain the video solely as a clearly identified diagnostic artifact.
   Never link it as proof.

The bounded `maxDurationMs` is a final safety net, not the normal stop mechanism.
If capture state cannot be confirmed, report that the recording may remain active
until that limit expires.

Never present an incomplete, failed, auto-truncated, or unverified take as proof.

## Validate the artifact

Before delivery, verify all of the following:

- `recording.stop` returned a path and a duration greater than zero.
- The expected file exists and has nonzero size.
- A media probe finds a video stream and a positive duration.
- A full decode completes without media errors.
- Frames extracted near the initial state, each decisive checkpoint, and the
  final state contain the intended application and result.
- No inspected frame contains secrets or unrelated personal content.
- The scenario still satisfies the proof matrix.

Prefer the installed `ffprobe` and `ffmpeg`:

```bash
ffprobe -v error \
  -show_entries stream=codec_type,codec_name,width,height:format=duration \
  -of json "$video_path"

ffmpeg -v error -i "$video_path" -f null -
```

Extract checkpoint frames into a temporary directory and inspect them visually.
If these tools are unavailable, use an existing trusted media probe and decoder.
Do not install a new dependency merely to finish the proof. If no reliable
validation method is available, report the video as unverified rather than proof.

If a decisive moment is missing, unreadable, incorrect, or too fast, discard only
that attempt and record a new take.

## Recheck Git safety

For every video or task-created artifact, verify the ignore rule again:

```bash
git -C "$video_repo_root" check-ignore -v --no-index -- \
  "<path-relative-to-video_repo_root>"
```

Check the index separately:

```bash
git -C "$video_repo_root" ls-files --error-unmatch -- \
  "<path-relative-to-video_repo_root>"
```

The second command must fail for every task-created output. Also inspect the
staged paths under `docs/videos/` and compare them with the preflight result.
Never alter pre-existing tracked or staged files to make this check pass.

Never stage, commit, force-add, or place videos or helper artifacts in Git LFS.

Stop only application processes created for this proof, unless the project's
normal workflow explicitly requires them to remain running.

## Deliver the proof

Return:

1. A direct link to the validated video.
2. One or two sentences that identify the initial state, decisive actions, and
   visible result.
3. The checks used for acceptance criteria that video cannot prove.
4. A concise list of anything still unverified.

When the agent and user share the filesystem, link the absolute video path using
the environment's normal clickable local-file syntax.

When the agent runs remotely, use the environment's existing private artifact
attachment or transfer mechanism and verify that the delivered artifact is
reachable. Do not upload the video publicly, commit it, or claim that a remote
filesystem path is accessible to the user. If no private transfer mechanism is
available, state that delivery is incomplete and give the minimum concrete action
needed to retrieve the file.

If extension capture or artifact delivery remains unavailable, report the exact
blocker, the work and non-video checks that succeeded, and the minimum user action
required. Do not claim that the video proof exists.
