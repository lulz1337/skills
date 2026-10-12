# Version 3 evaluation

## Version 3 evaluation — 2026-10-12

Independent agent forward test, plus deterministic renderer integration checks.
This is one exercised workflow, not a paired benchmark or a statistical quality
score. No paid Claude eval-harness run was used for this revision.

| Check | Result |
| --- | --- |
| Scenario | Real profile edit/save followed by blank-name validation; four contiguous scenes from one take |
| Tools | agent-browser 0.39.0; FFmpeg 8.1.3; edge-tts 7.2.8, `en-US-AriaNeural` |
| Final media | 35.772 seconds; 1280×720; 30 fps; VP8 video / 48 kHz Opus audio; full-file decode passed |
| Coverage | Confirmation visible by 10.10s; validation visible by 25.50s; both results and retained fields highlighted |
| Click evidence | Five real logged clicks at 5.19, 7.20, 9.99, 21.15, 25.35s; native pointer plus vector fallback rings |
| Caption evidence | Measured provider SRT; small bottom captions; sampled white-text contrast about 10.4:1 |
| Application checks | Save confirmation; entries retained; page time origin unchanged; blank and whitespace-only rejection; no browser errors; JS syntax passed |
| Renderer checks | Multi-scene composition, fractional trim, full decode, subtitle timing/wrapping, numeric/annotation bounds, refused overwrite, refused long final-frame freeze |
| Package checks | Frontmatter validation and reference links passed; both skill copies identical; skills CLI discovers exported package |
| Activation | Existing shared skill links resolve to version 3; Claude/Codex policy enabled; speech CLI installed |
| Cleanup | Evaluation browser and server stopped; generated media remained outside tracked repositories |

The forward test found and resolved oversized subtitles, 50 ms provider cue
overlaps, scientific-notation frame-hold durations, weak caption contrast, and
faint native click ripples. Caption geometry now uses explicit ASS resolution;
small adjacent overlaps are trimmed to the next measured cue start, longer ones
fail; hold duration uses fixed decimal notation; background opacity is 75%;
logged real-click coordinates can supply font-independent vector rings.

Evaluated renderer SHA-256:
`116c4be80d1f815630880df6411b8f2fc13c0a2178308653c416100c8207a91c`.

**Open gates:** listening and full real-time playback were unavailable. Natural
voice quality, pronunciation, and end-to-end pacing therefore remain unverified.
Sampled frames and media-stream checks do not replace those gates. The fixture
proves retained page entries, not database persistence. No historical diff was
available; its README supplied the prior reload behavior. MP4/macOS were not
exercised on this Fedora machine; the WebM path was exercised.

Broader repository checks also exposed unrelated failures: `check-linux.sh`
reported live Claude settings semantic drift; `test-repo.sh` reported 116 passes
and one failure, a stale orchestrator mutation target (`unbound postreview repair
accepted`). Those files were not changed by this work.

Reproduce deterministic checks:

```bash
python3 skills/video-proof/scripts/render.py --self-check
python3 /path/to/skill-creator/scripts/quick_validate.py agents/skills/video-proof
```

For the visual workflow, start the
[profile-app fixture](https://github.com/lulz1337/.dotfiles/tree/main/agents/evals/suites/video-proof/fixtures/profile-app)
in a disposable Git repo, record editing both fields and saving, then clear Display name and save
again. Generate per-scene speech and SRT as documented in `references/production.md`,
compose the four contiguous clips, inspect change/click/caption/seam frames, and
watch/listen before declaring presentation verification complete.
