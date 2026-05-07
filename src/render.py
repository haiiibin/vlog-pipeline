"""ffmpeg-based timeline compositor. Outputs 1080x1920 H.264 mp4."""
import json
import subprocess
import tempfile
from pathlib import Path
from src.types import Timeline, TimelineClip, TextCard, ClipMetadata

TARGET_W = 1080
TARGET_H = 1920
SUBTITLE_FONT_SIZE = 56
HOOK_FONT_SIZE = 90


def _escape_drawtext(text: str) -> str:
    """Escape characters that are special to ffmpeg drawtext filter."""
    # Order matters: backslash first
    return (text
            .replace("\\", "\\\\")
            .replace(":", "\\:")
            .replace("'", "\\'")
            .replace(",", "\\,")
            .replace("[", "\\[")
            .replace("]", "\\]")
            .replace("%", "\\%"))


def _drawtext_filter(text: str, fontsize: int, y_expr: str) -> str:
    escaped = _escape_drawtext(text)
    return (f"drawtext=text='{escaped}'"
            f":fontcolor=white:fontsize={fontsize}"
            f":borderw=4:bordercolor=black"
            f":x=(w-text_w)/2:y={y_expr}")


def render_clip_segment(
    input_path: Path,
    trim: tuple[float, float],
    subtitle: str,
    output_path: Path,
) -> None:
    """Trim, scale-and-pad to 1080x1920, burn-in subtitle."""
    start, end = trim
    duration = max(0.1, end - start)

    # scale to fit inside 1080x1920 keeping aspect ratio, pad black to fill
    vf_chain = [
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease",
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:color=black",
        f"setsar=1",
    ]
    if subtitle:
        vf_chain.append(_drawtext_filter(
            subtitle, SUBTITLE_FONT_SIZE, "h-text_h-200"))

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", str(start), "-t", str(duration),
        "-i", str(input_path),
        "-vf", ",".join(vf_chain),
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", "44100", "-ac", "2",
        "-r", "30",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def render_text_card(text: str, duration: float, output_path: Path) -> None:
    """Render a 1080x1920 black card with centered white text + silent audio."""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c=black:s={TARGET_W}x{TARGET_H}:d={duration}:r=30",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={duration}",
        "-vf", _drawtext_filter(text, HOOK_FONT_SIZE, "(h-text_h)/2"),
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _concat_segments(segment_paths: list[Path], output_path: Path) -> None:
    """Concat using concat filter (re-encodes; robust against codec drift)."""
    inputs: list[str] = []
    for p in segment_paths:
        inputs += ["-i", str(p)]

    n = len(segment_paths)
    streams = "".join(f"[{i}:v][{i}:a]" for i in range(n))
    filter_complex = f"{streams}concat=n={n}:v=1:a=1[v][a]"

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def render_timeline(timeline: Timeline, analyzed_dir: Path, output_path: Path) -> None:
    """Render full timeline: hook → clips → outro."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        segments: list[Path] = []

        hook_seg = tmp_dir / "hook.mp4"
        render_text_card(timeline.hook.text, timeline.hook.duration, hook_seg)
        segments.append(hook_seg)

        for i, clip in enumerate(timeline.clips):
            meta_path = analyzed_dir / f"{clip.id}.json"
            cm = ClipMetadata.model_validate_json(meta_path.read_text())
            seg_path = tmp_dir / f"clip_{i:03d}.mp4"
            render_clip_segment(Path(cm.path), clip.trim, clip.subtitle, seg_path)
            segments.append(seg_path)

        outro_seg = tmp_dir / "outro.mp4"
        render_text_card(timeline.outro.text, timeline.outro.duration, outro_seg)
        segments.append(outro_seg)

        _concat_segments(segments, output_path)
