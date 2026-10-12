# Video Proof

Present a finished feature through the real application. The video covers the
complete user scenario with a female English voice, small bottom subtitles,
highlights on changed fields and sections, and visible pointer movement and clicks.
It supplements tests and identifies behavior the video cannot prove.

## Install

```bash
npx skills add lulz1337/skills --skill video-proof
```

For Claude Code:

```text
/plugin marketplace add lulz1337/skills
/plugin install video-proof@skills
```

You can also copy this entire folder into your agent's skill directory. Include
`references/` and `scripts/`; copying only `SKILL.md` loses the production helpers.

## Requirements

- Python 3, `agent-browser`, Chrome, `ffmpeg`, and `ffprobe`.
- FFmpeg's `subtitles` filter and either `libx264`/`aac` for MP4 or
  `libvpx`/`libopus` for WebM. Fedora's FFmpeg can use the WebM path.
- A natural female English speech provider with caption timestamps. Reuse an
  installed provider; `edge-tts` through `uv` is a small option without an API key.
  It sends narration text to Microsoft's online service. Use a local neural
  voice for private scripts.

The skill probes the actual capture, speech, caption, and highlight pipeline
before recording. Missing capabilities are reported; silent or uncaptioned output
is not presented as the requested narrated video.

## Use

```text
Use $video-proof to present the completed profile changes. Show the full scenario,
including validation. Explain every change with a female English voice, bottom
subtitles, changed-field highlights, and visible clicks.
```

A video request can precede the implementation. The skill preflights early and
records after the work and checks finish. Explicit voice/language preferences or
a silent-video request override the defaults. Ordinary testing and screenshot
requests do not activate it.

## What it checks

- Every task change maps to a scene and timestamp, or a named nonvisual check.
- The real application comes from the finished worktree/build. User actions and
  asserted results remain intact; captions and highlights are presentation layers.
- Speech timing controls pacing. Captions use measured boundaries, not word-count
  estimates. Changed targets receive timed outlines without hiding their labels.
- The final render decodes and contains video/audio. A full watch/listen and frame
  review check caption visibility, click markers, pacing, pronunciation, and coverage.
- Media stays outside Git. Only the finished video goes into locally ignored
  `docs/videos/`, with branch-based names and overwrite protection.

Listening or playback that cannot be completed stays explicitly unverified.
Rendering a file alone does not establish presentation quality.

## Files

`SKILL.md` defines coverage, capture, and acceptance. `references/production.md`
explains speech and the timeline. `scripts/render.py` composes scenes using only
Python's standard library and FFmpeg. `references/delivery.md` preserves Git and
artifact delivery rules; `references/sources.md` records the research.

Check the helper with:

```bash
python3 skills/video-proof/scripts/render.py --self-check
```

The [version 3 evaluation](references/evaluation.md) records the real browser
exercise, bugs found and fixed, and the remaining listening/playback limits.

MIT — see the repository license.
