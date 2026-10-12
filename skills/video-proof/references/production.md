# Narration and composition

Use Python 3 and FFmpeg already required by capture. Reuse an installed speech
provider that offers a natural English female voice and timed captions. Select the
voice explicitly; provider defaults can be male. Prefer a configured local neural
voice for private scripts. Keep generated media outside repositories.

## Speech

A small option when no provider is configured is `edge-tts`, which calls
Microsoft's online speech service without an API key. It sends **narration text**
to that service; use it for non-sensitive narration. It is an unofficial client,
so availability is not guaranteed. Reuse `edge-tts` if installed. Otherwise use
`uv tool run --from edge-tts edge-tts` when `uv` exists, or install `edge-tts` in a
temporary venv. Do not install globally or add it to the application dependencies.

Generate one audio file and SRT per scene, using short sentences:

```bash
uv tool run --from edge-tts edge-tts --voice en-US-AriaNeural --rate=-5% \
  --file "<tmpdir>/scene-01.txt" \
  --write-media "<tmpdir>/scene-01.mp3" \
  --write-subtitles "<tmpdir>/scene-01.srt"
```

Check `--list-voices` if the voice is unavailable. Use an English voice listed as
female, with the same voice/rate for every scene. Kokoro `af_heart`, an installed
English female Piper voice, or a configured commercial provider are alternatives;
do not clone a person's voice. Use provider timestamps where available. Otherwise
align/transcribe the generated audio with an installed tool and correct the
transcript against the script. Word-count estimates are not subtitle timing.
Listen to the sample before recording. A provider error is a blocker, not a reason
to replace natural narration with a robotic voice or silence.

Each SRT cue needs actual start/end times, at most two lines of approximately
42 characters each, and readable duration (aim for no more than 20 characters per
second). Sentence timestamps work for short phrases; shorten long sentences or
use word alignment to break them into timed phrases. Do not distribute a long
sentence's timestamps evenly and call that alignment. Keep subtitle spelling
faithful to the spoken words, with standard spelling for pronounced acronyms.
The renderer trims adjacent provider overlaps of at most 100 ms to the next
measured cue start. Larger overlaps, reversed cues, and missing captions fail.

## Timeline

Save a JSON manifest in the temporary directory. Paths are relative to its folder.
Each scene can select a contiguous interval from the same raw recording, or use
its own successful take for an explicitly announced alternative scenario:

```json
{
  "scenes": [
    {
      "id": "save-confirmation",
      "video": "take.webm",
      "start": 0,
      "end": 9,
      "audio": "scene-01.mp3",
      "captions": "scene-01.srt",
      "voice_start": 0.3,
      "highlights": [
        {"start": 5.0, "end": 8.5, "x": 48, "y": 380, "width": 410, "height": 32}
      ],
      "clicks": [
        {"time": 4.2, "x": 115, "y": 335}
      ]
    }
  ]
}
```

`start`/`end` select seconds in the raw recording; omit them to use the whole take.
Highlight and click times are relative to the **trimmed scene**, before any final
hold. Subtitle times are relative to its audio; the renderer adds `voice_start`.
Do not list `clicks` when the native cursor/ripple is already visible. The fallback
draws a brief circle at the logged real click, not a replacement cursor.

Read `get box <ref> --json` after the target settles, and transfer the actual
`x`, `y`, `width`, `height`. The raw video dimensions must equal the coordinates'
viewport dimensions. Account for iframe offsets when needed. Highlight only
stationary targets; split an interval and remeasure after scrolling or movement.
Have the highlight appear with the corresponding spoken phrase, not an arbitrary
pause. For each action, schedule speech that describes the action before it;
describe a result only when the result is visible.

Allow about 0.3 seconds before speech and 0.8 seconds after it. The helper measures
audio and video; it adds at most two seconds of final-frame hold when needed. A
larger shortfall fails: lengthen the real result hold and rerecord. It never speeds
up actions or cuts off speech. Consecutive scenes retain capture order and state.
Use a clean cut only after the outcome has been readable.

## Render

```bash
python3 "<skill-dir>/scripts/render.py" \
  "<tmpdir>/timeline.json" "<tmpdir>/presentation.webm"
```

Use `.mp4` when `libx264` and `aac` are available, otherwise `.webm` with `libvpx`
and `libopus`. The renderer burns in small white bottom-centered captions with a
dark background, draws thin blue outlines, normalizes each voice scene to about
−16 LUFS / −1.5 dB true peak, and writes `<output>.json` containing measured scene
times for coverage reconciliation. It requires matched frame dimensions, refuses
existing outputs, and decodes the final video. It uses no application dependencies.

Captions overlay the footage. In rehearsal, keep changed fields/results clear of
the bottom caption area. If the product cannot do that, compose a separate caption
footer outside the captured UI with FFmpeg and revalidate dimensions/coordinates;
do not move controls or hide evidence. Inspect the actual output at presentation
size: approximately 24 px captions at 720p (36 px at 1080p), max two lines, with
adequate contrast. Shorten crowded text rather than shrinking it.

Run the helper's dependency-free checks with:

```bash
python3 "<skill-dir>/scripts/render.py" --self-check
```

Checks and decoding do not prove a natural voice, truthful coverage, or smooth
pacing. Watch/listen to the complete final video, inspect caption/highlight frames,
and reconcile the coverage table before delivery. If the agent cannot hear audio,
request a listening check on the concrete artifact and report that gate as pending.
