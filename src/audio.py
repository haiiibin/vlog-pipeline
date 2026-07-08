"""Audio energy analysis via ffmpeg + librosa (Phase 3).

Extract the audio track to a temp mono wav, compute RMS energy.
Returns {} for clips without an audio stream (not an error).
"""
import os
import subprocess
import tempfile
from pathlib import Path

import librosa


def _has_audio_stream(video_path: Path) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(video_path)],
        capture_output=True, text=True,
    )
    return bool(out.stdout.strip())


def analyze_audio(video_path: Path) -> dict:
    """Return {"rms_peak": float, "rms_mean": float} (~[0, 1]), or {} if no audio."""
    if not _has_audio_stream(video_path):
        return {}
    fd, wav = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video_path),
             "-vn", "-ac", "1", "-ar", "22050", "-f", "wav", wav],
            check=True, capture_output=True,
        )
        y, _ = librosa.load(wav, sr=22050, mono=True)
        if y.size == 0:
            return {}
        rms = librosa.feature.rms(y=y)[0]
        return {"rms_peak": float(rms.max()), "rms_mean": float(rms.mean())}
    finally:
        if os.path.exists(wav):
            os.remove(wav)
