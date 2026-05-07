"""Pytest fixtures: generate synthetic videos via ffmpeg so we don't bundle binary fixtures."""
import subprocess
from pathlib import Path
import pytest


def _make_video(path: Path, duration: float, has_audio: bool = True,
                size: str = "1920x1080", color: str = "blue") -> Path:
    """Generate a deterministic test video using ffmpeg lavfi sources."""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c={color}:s={size}:d={duration}:r=30",
    ]
    if has_audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
    if has_audio:
        cmd += ["-c:a", "aac", "-shortest"]
    cmd += [str(path)]
    subprocess.run(cmd, check=True, capture_output=True)
    return path


@pytest.fixture
def tmp_video_factory(tmp_path):
    """Yields a callable: tmp_video_factory(name, duration=5, has_audio=True) -> Path."""
    def _factory(name: str = "clip.mp4", duration: float = 5.0,
                 has_audio: bool = True, size: str = "1920x1080",
                 color: str = "blue") -> Path:
        return _make_video(tmp_path / name, duration, has_audio, size, color)
    return _factory


@pytest.fixture
def sample_video(tmp_video_factory):
    """A 5-second 1080p test video with audio."""
    return tmp_video_factory("sample.mp4", duration=5.0)
