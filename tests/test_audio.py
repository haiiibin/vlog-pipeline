"""audio.py tests: RMS energy from lavfi-synthesized clips. No real media."""
import subprocess
from pathlib import Path

from src.audio import analyze_audio


def _sine_video(path: Path, volume: float = 1.0, duration: float = 3.0) -> Path:
    af = f"sine=frequency=440:duration={duration},volume={volume}"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c=blue:s=640x360:d={duration}:r=30",
        "-f", "lavfi", "-i", af,
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(path),
    ], check=True, capture_output=True)
    return path


def test_audio_has_energy(tmp_path):
    v = _sine_video(tmp_path / "loud.mp4", volume=1.0)
    feats = analyze_audio(v)
    assert feats["rms_peak"] > 0
    assert feats["rms_mean"] > 0


def test_audio_no_stream_returns_empty(tmp_path):
    path = tmp_path / "silent.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=blue:s=640x360:d=2:r=30",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        str(path),
    ], check=True, capture_output=True)
    assert analyze_audio(path) == {}


def test_audio_louder_scores_higher(tmp_path):
    loud = _sine_video(tmp_path / "loud.mp4", volume=1.0)
    quiet = _sine_video(tmp_path / "quiet.mp4", volume=0.2)
    assert analyze_audio(loud)["rms_peak"] > analyze_audio(quiet)["rms_peak"]
