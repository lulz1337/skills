# Repository delivery

Read before writing any final artifact to the target repository.

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

## Deliver the proof

Return:

1. A direct link to the validated video.
2. Concise timestamped coverage of the changed behavior, including the initial
   state, decisive actions, and visible results.
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
