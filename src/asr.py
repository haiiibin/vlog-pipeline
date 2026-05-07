"""whisper.cpp subprocess wrapper.

Requires env vars:
    WHISPER_BIN   — path to whisper.cpp `main` binary
    WHISPER_MODEL — path to ggml model (e.g. ggml-large-v3.bin)
"""
import json
import os
import subprocess
from pathlib import Path


def parse_timestamp(ts: str) -> float:
    """Parse 'HH:MM:SS,mmm' (whisper.cpp output format) into seconds."""
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def transcribe(audio_path: Path, language: str = "zh") -> list[dict]:
    """Return [{start, end, text}, ...]. Empty list if no speech."""
    bin_path = os.environ.get("WHISPER_BIN")
    model_path = os.environ.get("WHISPER_MODEL")
    if not bin_path or not model_path:
        raise RuntimeError("WHISPER_BIN and WHISPER_MODEL env vars must be set")

    out_prefix = audio_path.with_suffix("")
    cmd = [
        bin_path,
        "-m", model_path,
        "-l", language,
        "-oj",                              # output JSON
        "-of", str(out_prefix),
        str(audio_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    json_path = out_prefix.with_suffix(out_prefix.suffix + ".json")
    if not json_path.exists():
        return []

    data = json.loads(json_path.read_text(encoding="utf-8"))
    segments = []
    for seg in data.get("transcription", []):
        ts = seg.get("timestamps", {})
        text = seg.get("text", "").strip()
        if not text:
            continue
        try:
            segments.append({
                "start": parse_timestamp(ts["from"]),
                "end": parse_timestamp(ts["to"]),
                "text": text,
            })
        except (KeyError, ValueError):
            continue
    return segments
