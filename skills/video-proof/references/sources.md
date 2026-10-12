# Research used for version 3

Reviewed upstream skill source on 2026-10-12, rather than adopting search rankings
as evidence of quality. These sources inform the workflow; they are not runtime
dependencies and do not grant authority to run their installers or publish media.

| Source | Practice adopted | Boundary |
| --- | --- | --- |
| [HeyGen PR-to-video](https://github.com/heygen-com/hyperframes/blob/main/skills/pr-to-video/SKILL.md) | Derive the narrative from actual changes; preflight capabilities before story work; select the requested voice explicitly. | Its synthetic code scenes cannot prove application behavior. Use real capture and cover every task change. |
| [HeyGen changelog-video](https://github.com/heygen-com/hyperframes/blob/main/.agents/skills/changelog-video/SKILL.md) | Voice audio is the clock; distinguish spoken pronunciation from display spelling; inspect caption presence in rendered frames. | Its fixed time budget, branded assets, mocks, and publishing steps do not fit a complete feature proof. |
| [Remotion voiceover](https://github.com/remotion-dev/skills/blob/main/skills/remotion-best-practices/remotion-markup/voiceover.md) | Generate per-scene audio and measure duration before composition. | Apply the timing principle with FFmpeg; installing React/Remotion is unnecessary here. |
| [ElevenLabs text-to-speech](https://github.com/elevenlabs/skills/blob/main/text-to-speech/SKILL.md) | Explicit voice selection, stable delivery across scenes, pronunciation checks, and provider error handling. | A paid account is optional; no API key or voice clone is required by this skill. |
| [agent-browser recording](https://github.com/vercel-labs/agent-browser/blob/main/skill-data/core/references/video-recording.md) and [edge-tts](https://github.com/rany2/edge-tts) | Reuse native cursor/click capture, changed-frame contact sheets, and speech-generated subtitle timing. | Confirm capabilities against installed `--help` and a working probe. Edge speech is an online, unofficial service. |

Skills discovery used the skills.sh directory and `skills find` for product demos,
voiceover, and Remotion. Source repositories and actual instructions were checked.
Install counts and stars are changeable popularity signals, not correctness tests;
the local browser/audio/compositor evaluation is the implementation evidence.
