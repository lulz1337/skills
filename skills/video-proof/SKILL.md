---
name: video-proof
description: Record and deliver an agent-browser video that demonstrates a completed bug fix or small user story. Use only when the user explicitly asks for a video, recording, or video proof of completed work, including when the request appears at the start of the task. Do not use for ordinary testing or screenshot-only requests.
license: MIT
metadata:
  version: "2.0.0"
---

# Video Proof

Create a short, trustworthy video demonstration after the requested implementation
and its relevant checks are complete. The video supplements tests; it does not
replace them.

The browser is `agent-browser`: its own Chrome, driven one command at a time,
recorded with `agent-browser record`. It needs no browser extension and no
permission prompt, so the user does not have to do anything for the recording
to start.

## Load agent-browser and preflight early

Before the first agent-browser command:

1. Run `agent-browser skills get core --full` and read its complete output. Do
   not truncate it. It is version-matched to the installed CLI.
2. Pick one session name for the whole proof, for example
   `video-proof-<short-random-id>`, and pass `--session <name>` to every
   command. A named session never touches the default session or another
   agent's browser.
3. Do not use `playwriter`, `terminal-browser`, or `--auto-connect` to drive the
   recording. The first two are other browsers; `--auto-connect` drives the
   user's own Chrome, which can show personal tabs and data.

Check the recording prerequisites early, even when the user requests the video at
the start of a larger task:

- Run `agent-browser doctor` and read its Recording line. `record` pipes frames
  into `ffmpeg`, so a missing `ffmpeg` is a blocker.
- Choose the container from the encoders the installed ffmpeg has:

  ```bash
  ffmpeg -hide_banner -encoders 2>/dev/null | grep -qw libx264 && ext=mp4
  [ -n "${ext:-}" ] || { ffmpeg -hide_banner -encoders 2>/dev/null | grep -qw libvpx && ext=webm; }
  ```

  Prefer `.mp4` (H.264), because it plays everywhere, including QuickTime. Use
  `.webm` (VP8) when ffmpeg has no libx264, as with Fedora's `ffmpeg-free`. If
  neither encoder exists, stop and report it.
- Prove that capture works: create a private temporary directory outside every
  repository, open the target application in the session, run
  `record start <tmpdir>/probe.<ext>`, wait about one second, run `record stop`,
  and check the probe with `ffprobe` (see "Validate the artifact"). Then delete
  only that probe directory. `doctor` alone does not prove that a frame reaches
  the file.
- If ffmpeg is missing, tell the user immediately and ask only for the minimum
  action: install it with the machine's package manager (for example
  `brew install ffmpeg`, `sudo dnf install ffmpeg-free`, or
  `sudo apt install ffmpeg`), then say when it is done.
- Continue implementation and non-video verification while the user fixes the
  prerequisite, when that is practical.

Do not save or present the probe. Do not start the final recording during
preflight.

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

## Prepare the browser session

Prepare authentication, test data, and the initial application state before
recording:

- Set a 16:9 viewport so the video has a predictable size:
  `agent-browser --session <name> set viewport 1280 720`.
- Log in with a project test account, typed into the real login form or through
  `agent-browser auth login`. Never record a login that shows real credentials.
- When the application accepts only the user's own SSO session, ask the user
  first. With consent, export that state once to a file in the private temporary
  directory with `agent-browser --auto-connect state save <tmpdir>/auth.json`,
  load it with `state load`, and delete the file after the proof. Treat the file
  as a secret: it holds session cookies. Never write it inside a repository.
- Make sure the page shows no secrets, notifications, unrelated personal
  information, production customer data, or other sensitive content.

## Record the final demonstration

Record into the private temporary directory, never directly into the target
repository. A failed take then never touches the repository, and only a
validated video is copied into `docs/videos/` (see "Deliver into the
repository").

```bash
agent-browser --session <name> record start "<tmpdir>/take.<ext>" --cursor --contact-sheet
```

`--cursor` draws the pointer and click ripple into the video; Chrome's screencast
does not show the native pointer. `--contact-sheet` writes a timestamped PNG of
the distinct visual changes beside the video, which the validation step uses.
Keep the default 30 fps unless the scenario is a drag or an animation (then 60).
Keep audio out of the proof unless the user explicitly asks for it.

Note the start time (`date +%s`) so each checkpoint can be given as elapsed
seconds.

After recording starts:

- Leave the initial state visible for about two seconds (`wait 2000`).
- Act through user-level commands on refs from a fresh `snapshot -i`: `click`,
  `fill`, `type`, `press`, `select`, `check`, `hover`, `drag`, `upload`,
  `scroll`. Re-snapshot after every navigation or large DOM change; refs go stale.
- Follow observe -> act -> observe. After each action, check `get url`,
  `diff snapshot`, and `errors --json` (plain `errors` prints nothing).
- Assert each expected result from application state with `wait --text`,
  `wait --url`, `is visible`, or `get text`. Do not infer success only from the
  absence of an error.
- Pause about 1.5 seconds on each decisive result (`wait 1500`) so a viewer can
  read it.
- Record each decisive checkpoint label and its elapsed time.

Do not use `eval` to change the DOM or to click. Do not use `network route` to
fake or block responses, `set offline`, or `cookies set` and `storage` writes
during the take. Do not edit the application in memory for the recording.
Project-supported test fixtures are acceptable only when the proof clearly
represents the environment and criterion being demonstrated.

Stop normally and keep the result:

```bash
agent-browser --session <name> record stop --json
```

The JSON reports the saved path, `frames`, and `capturedFrames`. A take whose
`capturedFrames` is 0 or 1 recorded a still image, not the workflow.

## Handle failures and interruptions

After `record start` succeeds, ending the capture becomes mandatory on every exit
path. agent-browser has no maximum recording duration, so nothing stops a
forgotten recording for you.

If an interaction, assertion, command, or connection fails:

1. Treat the current take as failed.
2. Run `agent-browser --session <name> record stop`.
3. If that fails, run `agent-browser --session <name> close` and confirm with
   `agent-browser session list` that the session is gone. The list can still
   name it for a few seconds after `close`, so check again after about three
   seconds. Do not probe the session with another command: any command in a
   closed session launches a new browser.
4. Delete the failed take from the temporary directory, or keep it there solely
   as a clearly identified diagnostic artifact. Never link it as proof.

Never present an incomplete, failed, or unverified take as proof.

## Validate the artifact

Before delivery, verify all of the following:

- `record stop --json` reported the expected path, and `capturedFrames` shows
  more than a single still frame.
- The file exists and has nonzero size.
- A media probe finds a video stream and a positive duration.
- A full decode completes without media errors.
- The contact sheet and frames extracted near the initial state, each decisive
  checkpoint, and the final state show the intended application and result.
- No inspected frame or contact-sheet tile contains secrets or unrelated personal
  content.
- The scenario still satisfies the proof matrix.

```bash
ffprobe -v error \
  -show_entries stream=codec_type,codec_name,width,height:format=duration \
  -of json "$video_path"

ffmpeg -v error -i "$video_path" -f null -

ffmpeg -v error -ss "<checkpoint seconds>" -i "$video_path" -frames:v 1 \
  "<tmpdir>/frame-<label>.png"
```

Inspect the extracted frames and the contact sheet visually. `ffmpeg` is already
required by `record`, so no other tool is needed. If a reliable validation cannot
be completed, report the video as unverified rather than proof.

If a decisive moment is missing, unreadable, incorrect, or too fast, discard only
that take and record a new one.

## Deliver into the repository

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

### Name the video

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

Construct the filename with the extension chosen in preflight:

```text
<branch-slug>__<description-slug>__<YYYYMMDD-HHMMSS>.<ext>
```

For example:

```text
fix-T20-123__ulozeni-profilu__20260914-143022.mp4
```

Reserve the candidate name atomically with a sibling
`<candidate>.video-proof-lock` created with exclusive or noclobber semantics. If
the video or reservation already exists, append `-02`, `-03`, and so on to the
timestamp and try again. Do not delete a reservation created by another process.
Copy the validated take from the temporary directory to the reserved name, then
remove only the reservation created by the current attempt. Never overwrite an
existing file.

Keep the contact sheet, extracted frames, logs, and media-probe output in the
temporary directory. Only the video goes into `docs/videos/`.

### Recheck Git safety

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

## Clean up

- Close the proof session: `agent-browser --session <name> close`.
- Delete the private temporary directory, including any exported auth state.
- Stop only application processes created for this proof, unless the project's
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

If recording or artifact delivery remains unavailable, report the exact blocker,
the work and non-video checks that succeeded, and the minimum user action
required. Do not claim that the video proof exists.
