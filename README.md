# vlog-pipeline

Turn a week of raw phone clips into a 1-3 minute vertical (9:16) vlog draft, automatically:
scene detection, Chinese ASR subtitles, heuristic scoring, an ffmpeg compositor, and a local
web UI where you pick which clips make the cut.

**Status: WIP (Phase 2 of 5 done).** Personal project; interfaces may change without notice.

## How it works

```
phone clips -> inbox/
  probe (ffprobe metadata + GIF preview)
  scene detection (PySceneDetect)
  ASR (whisper.cpp, optional)
  heuristic scoring
        -> data/work/<week>/analyzed/*.json
web UI (FastAPI, localhost:8765)
  pick clips -> selected.json
  one click  -> compose timeline -> ffmpeg render
        -> data/output/<week>_vlog.mp4  (9:16, burned-in subtitles)
```

## Requirements

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- `ffmpeg` / `ffprobe` on PATH
- Optional, for subtitles: a [whisper.cpp](https://github.com/ggml-org/whisper.cpp) binary and
  a ggml model. Set `WHISPER_BIN` and `WHISPER_MODEL` env vars; without them ASR is skipped.

## Quick start

```bash
uv sync --extra dev
uv run pytest                       # sanity check

# analyze a folder of clips and render everything in one go
uv run python -m src.pipeline run --inbox path/to/clips --week 2026-W28 --select all

# or: analyze first, then pick clips in the browser
uv run python -m src.pipeline run --inbox path/to/clips --week 2026-W28 --select all
uv run python -m src.pipeline serve --week 2026-W28
```

## Roadmap

- [x] Phase 1: CLI pipeline (probe / scenes / ASR / score / compose / render)
- [x] Phase 2: candidate-pool web UI (pick clips, one-click render)
- [ ] Phase 3: smarter scoring (audio energy, faces) + LLM-generated cut list
- [ ] Phase 4: scheduling + phone handoff (macOS launchd / Windows Task Scheduler)

Design docs: [docs/DESIGN.md](docs/DESIGN.md) (zh) and [docs/specs/](docs/specs/).

## License

MIT
