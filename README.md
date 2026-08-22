# vlog-pipeline

[![CI](https://github.com/haiiibin/vlog-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/haiiibin/vlog-pipeline/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://github.com/haiiibin/vlog-pipeline/blob/main/pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Turn a week of raw phone clips into a 1-3 minute vertical (9:16) vlog draft, automatically:
scene detection, Chinese ASR subtitles, heuristic scoring, an ffmpeg compositor, and a local
web UI where you pick which clips make the cut.

**Status: WIP (Phase 3 of 5 in progress).** Personal project; interfaces may change without notice.

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
- For Claude-generated cut lists (default composer): an Anthropic API key in `ANTHROPIC_API_KEY`.
  Without it, pass `--composer simple` to use the deterministic builder.

## Quick start

```bash
uv sync --extra dev
uv run pytest                       # sanity check

# 1. analyze clips and render a first draft (Claude cut-list; needs ANTHROPIC_API_KEY)
#    add --composer simple to skip Claude
uv run python -m src.pipeline run --inbox path/to/clips --week 2026-W28 --select all

# 2. (optional) refine: open the browser, pick the keepers, re-render just those
uv run python -m src.pipeline serve --week 2026-W28
```

## Roadmap

- [x] Phase 1: CLI pipeline (probe / scenes / ASR / score / compose / render)
- [x] Phase 2: candidate-pool web UI (pick clips, one-click render)
- [~] Phase 3: smarter scoring (audio energy; faces deferred to Phase 5) + LLM-generated cut list
- [ ] Phase 4: scheduling + phone handoff (macOS launchd / Windows Task Scheduler)

Design docs: [docs/DESIGN.md](docs/DESIGN.md) (zh) and [docs/specs/](docs/specs/).

## License

MIT
