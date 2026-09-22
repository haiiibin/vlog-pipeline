# Contributing

Thanks for your interest in vlog-pipeline. It is a personal project that is
still taking shape (see the roadmap in the README), so small, focused
contributions are the easiest to review.

## Development setup

```bash
git clone https://github.com/haiiibin/vlog-pipeline
cd vlog-pipeline
uv sync --extra dev
```

You also need `ffmpeg` and `ffprobe` on `PATH`. A whisper.cpp binary is
optional: without `WHISPER_BIN` and `WHISPER_MODEL` the ASR tests skip
themselves.

## Running checks

```bash
uv run pytest        # test suite
uv run ruff check .  # lint (config lives in pyproject.toml)
```

Both must pass before a PR can merge. CI runs them on Python 3.11 and 3.12
with ffmpeg installed.

## Things that never go into the repository

- `data/` (clips, work files, rendered output) and `config.yaml`. They are
  gitignored; please keep it that way and do not attach personal footage to
  issues or PRs.
- API keys. The Claude cut-list composer reads `ANTHROPIC_API_KEY` from the
  environment only.

## Pull request guidelines

- Keep changes focused; one concern per PR.
- Add or update tests for any behavior change (a short synthetic clip generated
  with ffmpeg is fine; see `tests/conftest.py`).
- If you change a CLI flag or the web UI, update the README.
