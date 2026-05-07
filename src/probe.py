"""ffprobe wrapper + GIF preview generator."""
import json
import subprocess
from datetime import datetime
from pathlib import Path
from src.types import ClipMetadata


def get_raw_metadata(video_path: Path) -> dict:
    """Run ffprobe and return parsed JSON."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed on {video_path}: {e.stderr}") from e
    return json.loads(result.stdout)


def _video_stream(meta: dict) -> dict:
    for s in meta["streams"]:
        if s.get("codec_type") == "video":
            return s
    raise ValueError("no video stream")


def _captured_at(meta: dict, fallback: Path) -> str:
    """Prefer creation_time tag, else file mtime."""
    tags = meta.get("format", {}).get("tags", {}) or {}
    if "creation_time" in tags:
        return tags["creation_time"].replace("Z", "")
    return datetime.fromtimestamp(fallback.stat().st_mtime).isoformat()


def build_clip_metadata(video_path: Path, clip_id: str) -> ClipMetadata:
    """Wrap raw ffprobe output into a ClipMetadata."""
    raw = get_raw_metadata(video_path)
    vstream = _video_stream(raw)
    width = int(vstream["width"])
    height = int(vstream["height"])
    duration = float(raw["format"]["duration"])
    orientation = "portrait" if height > width else "landscape"

    return ClipMetadata(
        id=clip_id,
        path=str(video_path),
        captured_at=_captured_at(raw, video_path),
        duration_sec=duration,
        resolution=[width, height],
        orientation=orientation,
    )


def generate_gif_preview(
    video_path: Path,
    output_path: Path,
    duration: float = 3.0,
    width: int = 240,
) -> None:
    """Generate a GIF preview from the middle of the clip."""
    raw = get_raw_metadata(video_path)
    total = float(raw["format"]["duration"])
    start = max(0.0, (total - duration) / 2)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", str(start),
        "-i", str(video_path),
        "-t", str(min(duration, total)),
        "-vf", f"fps=10,scale={width}:-1:flags=lanczos",
        "-loop", "0",
        str(output_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="replace") if e.stderr else ""
        raise RuntimeError(f"ffmpeg gif failed on {video_path}: {stderr}") from e
