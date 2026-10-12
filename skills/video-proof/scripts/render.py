#!/usr/bin/env python3
"""Compose real browser scenes with measured narration, SRT and annotations."""

import argparse
import json
import math
import re
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def probe(path):
    return json.loads(run("ffprobe", "-v", "error", "-show_streams",
                          "-show_format", "-of", "json", str(path),
                          capture_output=True).stdout)


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Expected a finite number, got {value!r}")
    return float(value)


def stamp(value):
    ms = round(value * 1000)
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    seconds, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"


def seconds(value):
    h, m, s, ms = map(int, re.split("[:,]", value))
    if m > 59 or s > 59:
        raise ValueError(f"Invalid subtitle timestamp: {value}")
    return h * 3600 + m * 60 + s + ms / 1000


def captions(source, offset, audio_duration):
    blocks = re.split(r"\n\s*\n", source.strip().replace("\r\n", "\n"))
    result, last_end = [], 0
    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].strip().isdigit():
            raise ValueError("Expected nonempty numbered SRT cues")
        match = re.fullmatch(r"(\d{2,}:\d{2}:\d{2},\d{3}) --> (\d{2,}:\d{2}:\d{2},\d{3})", lines[1])
        if not match:
            raise ValueError(f"Invalid SRT cue: {lines[1]}")
        start, end = map(seconds, match.groups())
        # Encoders may round duration a few milliseconds below the last boundary.
        if start < last_end:
            if last_end - start > 0.1 or start <= result[-1][0]:
                raise ValueError("Subtitle times overlap substantially or reverse")
            # Edge sentence boundaries may overlap by ~50ms. End the previous
            # cue at the next measured start, without estimating speech timing.
            result[-1][1] = start
        if end <= start or end > audio_duration + 0.1:
            raise ValueError("Subtitle times reverse or exceed the speech")
        text = " ".join(" ".join(lines[2:]).split())
        if not text or any(c in text for c in "{}\\<>"):
            raise ValueError("Captions must be plain, nonempty text without markup")
        wrapped = textwrap.wrap(text, 42, break_long_words=False, break_on_hyphens=False)
        if len(wrapped) > 2 or any(len(line) > 42 for line in wrapped):
            raise ValueError("Caption exceeds two readable lines; shorten or align phrases")
        result.append([start, end, wrapped])
        last_end = end
    cues = []
    for start, end, wrapped in result:
        if len(" ".join(wrapped)) / (end - start) > 20:
            raise ValueError("Caption exceeds 20 characters/second; slow or shorten speech")
        cues.append(f"{len(cues)+1}\n{stamp(start+offset)} --> {stamp(end+offset)}\n" + "\n".join(wrapped))
    return "\n\n".join(cues) + "\n\n"


def ass_captions(srt, scene, width, height, duration):
    """Set explicit ASS resolution so caption size is actual frame pixels."""
    def clock(value):
        return stamp(value)[:-1].replace(",", ".")

    font = round(height / 30)
    margin = round(height / 30)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,DejaVu Sans,{font},&H00FFFFFF,&H00FFFFFF,&H40000000,&H40000000,0,0,0,0,100,100,0,0,3,1,0,2,24,24,{margin},1
Style: Click,DejaVu Sans,24,&HFF000000,&HFF000000,&H00F8BD38,&HFF000000,0,0,0,0,100,100,0,0,1,2,0,5,0,0,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for block in srt.strip().split("\n\n"):
        lines = block.splitlines()
        start, end = (seconds(v) for v in lines[1].split(" --> "))
        text = r"\N".join(lines[2:])
        events.append(f"Dialogue: 1,{clock(start)},{clock(end)},Caption,,0,0,0,,{text}")
    circle = "m 18 0 b 28 0 36 8 36 18 b 36 28 28 36 18 36 b 8 36 0 28 0 18 b 0 8 8 0 18 0"
    for click in scene.get("clicks", []):
        t, x, y = (number(click[k]) for k in ("time", "x", "y"))
        if not (0 <= t < duration and 0 <= x <= width and 0 <= y <= height):
            raise ValueError("Click falls outside the captured scene or frame")
        effect = rf"{{\an5\pos({x},{y})\p1\fad(50,150)}}"
        events.append(f"Dialogue: 0,{clock(t)},{clock(min(t+0.45,duration))},Click,,0,0,0,,{effect}{circle}")
    return header + "\n".join(events) + "\n"


def annotation_filters(scene, duration, width, height):
    filters = []
    for box in scene.get("highlights", []):
        start, end = number(box["start"]), number(box["end"])
        x, y, w, h = (number(box[k]) for k in ("x", "y", "width", "height"))
        if not (0 <= start < end <= duration and 0 <= x < x+w <= width and 0 <= y < y+h <= height):
            raise ValueError("Highlight falls outside the captured scene or frame")
        filters.append(f"drawbox=x={x}:y={y}:w={w}:h={h}:color=0x38BDF8:t=3:enable='between(t,{start},{end})'")
    return filters


def render(manifest, output):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise ValueError("FFmpeg and ffprobe are required")
    report_path = Path(str(output) + ".json")
    if output.exists() or report_path.exists():
        raise ValueError("Output or timing report already exists; choose a fresh name")
    encoders = run("ffmpeg", "-hide_banner", "-encoders", capture_output=True).stdout
    if output.suffix == ".mp4" and "libx264" in encoders and re.search(r"\baac\b", encoders):
        codec = ["-c:v", "libx264", "-crf", "20", "-preset", "medium", "-c:a", "aac", "-b:a", "160k"]
    elif output.suffix == ".webm" and "libvpx " in encoders and "libopus" in encoders:
        codec = ["-c:v", "libvpx", "-crf", "10", "-b:v", "2M", "-c:a", "libopus", "-b:a", "128k"]
    else:
        raise ValueError("Choose MP4 with libx264/aac or WebM with libvpx/libopus")
    data = json.loads(manifest.read_text())
    scenes = data["scenes"]
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Timeline needs at least one scene")
    report, dimensions, total = [], None, 0
    with tempfile.TemporaryDirectory(prefix="video-proof-render-") as tmp:
        work = Path(tmp)
        for i, scene in enumerate(scenes):
            video, audio, srt = ((manifest.parent / scene[k]).resolve() for k in ("video", "audio", "captions"))
            vp, ap = probe(video), probe(audio)
            stream = next(s for s in vp["streams"] if s["codec_type"] == "video")
            if not any(s["codec_type"] == "audio" for s in ap["streams"]):
                raise ValueError("Narration has no audio stream")
            size = (stream["width"], stream["height"])
            if dimensions is not None and size != dimensions:
                raise ValueError("Scene dimensions differ; capture with one viewport")
            if any(v % 2 for v in size):
                raise ValueError("Capture dimensions must be even for yuv420p")
            dimensions = size
            vd, ad = float(vp["format"]["duration"]), float(ap["format"]["duration"])
            start, end = number(scene.get("start", 0)), number(scene.get("end", vd))
            offset = number(scene.get("voice_start", 0.3))
            if not (0 <= start < end <= vd + 0.05 and ad > 0 and offset >= 0):
                raise ValueError("Invalid trim, speech duration, or speech offset")
            footage = end - start
            duration = math.ceil(max(footage, offset + ad + 0.8) * 30) / 30
            if duration - footage > 2:
                raise ValueError(f"Scene {i+1} needs over 2s of freeze; rerecord slower")
            shifted = captions(srt.read_text(encoding="utf-8-sig"), offset, ad)
            (work / "captions.ass").write_text(ass_captions(shifted, scene, *size, footage))
            hold = max(0, duration - footage)
            vf = ["setpts=PTS-STARTPTS", "fps=30", f"tpad=stop_mode=clone:stop_duration={hold:.6f}"]
            vf += annotation_filters(scene, footage, *size)
            vf += ["subtitles=captions.ass", "format=yuv420p"]
            delay = round(offset * 1000)
            af = f"asetpts=PTS-STARTPTS,loudnorm=I=-16:TP=-1.5:LRA=7,aresample=48000,adelay={delay}:all=1,apad"
            clip = f"scene-{i:03}{output.suffix}"
            run("ffmpeg", "-v", "error", "-nostdin", "-n", "-ss", str(start), "-t", str(footage), "-i", str(video),
                "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-vf", ",".join(vf), "-af", af,
                "-t", str(duration), "-ac", "2", *codec, clip, cwd=work)
            actual = float(probe(work / clip)["format"]["duration"])
            report.append({"id": scene.get("id", f"scene-{i+1}"), "start": total, "end": total+actual,
                           "speech_start": total+offset, "speech_end": total+offset+ad,
                           "source": str(video), "source_start": start, "source_end": end})
            total += actual
        (work / "concat.txt").write_text("\n".join(f"file 'scene-{i:03}{output.suffix}'" for i in range(len(scenes))))
        assembled = work / ("presentation" + output.suffix)
        flags = ["-movflags", "+faststart"] if output.suffix == ".mp4" else []
        run("ffmpeg", "-v", "error", "-nostdin", "-n", "-f", "concat", "-safe", "0", "-i", "concat.txt",
            "-c", "copy", *flags, str(assembled), cwd=work)
        run("ffmpeg", "-v", "error", "-nostdin", "-i", str(assembled), "-f", "null", "-")
        final = probe(assembled)
        if not {"video", "audio"}.issubset({s["codec_type"] for s in final["streams"]}):
            raise ValueError("Final video is missing video or narration")
        # Exclusive creation protects a competing render after the initial check.
        with output.open("xb") as dest, assembled.open("rb") as src:
            shutil.copyfileobj(src, dest)
        with report_path.open("x") as dest:
            json.dump({"duration": float(final["format"]["duration"]), "scenes": report}, dest, indent=2)
        print(f"Rendered {output} ({total:.2f}s); inspect and listen before delivery")


def self_check():
    assert stamp(3661.9996) == "01:01:02,000"
    assert seconds("00:01:02,345") == 62.345
    cue = "1\n00:00:00,100 --> 00:00:02,000\nProfile saved.\n"
    assert "00:00:00,400 --> 00:00:02,300" in captions(cue, 0.3, 2)
    overlapping = cue + "\n2\n00:00:01,950 --> 00:00:03,000\nYour entries stay.\n"
    assert "00:00:00,100 --> 00:00:01,950" in captions(overlapping, 0, 3)
    ass = ass_captions(captions(cue, 0.3, 2), {"clicks": [{"time": 1, "x": 50, "y": 60}]}, 1280, 720, 2)
    assert "PlayResY: 720" in ass and "Caption,DejaVu Sans,24," in ass
    assert r"\pos(50.0,60.0)\p1" in ass
    for bad in ("", cue.replace("02,000", "00,050"), cue.replace("Profile saved.", "{hidden}"),
                cue.replace("Profile saved.", "A " * 60), cue.replace("Profile saved.", "W" * 43), cue+"\n"+cue):
        try:
            captions(bad, 0, 2)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid captions accepted")
    assert "drawbox" in annotation_filters({"highlights": [{"start": 0, "end": 1, "x": 1, "y": 1, "width": 20, "height": 20}]}, 2, 100, 100)[0]
    for scene in ({"highlights": [{"start": 0, "end": 1, "x": 90, "y": 1, "width": 20, "height": 20}]},
                  {"highlights": [{"start": 0, "end": 3, "x": 1, "y": 1, "width": 20, "height": 20}]}):
        try:
            annotation_filters(scene, 2, 100, 100)
        except ValueError:
            pass
        else:
            raise AssertionError("Out-of-frame/time highlight accepted")
    for bad in (float("nan"), float("inf"), True, "1"):
        try:
            number(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid timeline number accepted")
    print("Self-check passed: subtitle timing, wrapping guards, annotations, numeric validation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, nargs="?")
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
    elif args.manifest is None or args.output is None:
        parser.error("manifest and output are required")
    else:
        try:
            render(args.manifest.resolve(), args.output.resolve())
        except (ValueError, KeyError, StopIteration, OSError, subprocess.CalledProcessError) as error:
            parser.exit(1, f"Render failed: {error}\n")


if __name__ == "__main__":
    main()
