"""ffmpeg-based timeline compositor. Outputs 1080x1920 H.264 mp4."""
import platform
import subprocess
import tempfile
from pathlib import Path
from src.types import Timeline, ClipMetadata

TARGET_W = 1080
TARGET_H = 1920
SUBTITLE_FONT_SIZE = 56
HOOK_FONT_SIZE = 90

# On Windows, fontconfig often can't find its config file and crashes ffmpeg drawtext.
# Bypass by specifying an explicit font file (Microsoft YaHei Bold for CJK support).
_WINDOWS_FONT = "C\\:/Windows/Fonts/msyhbd.ttc"


def _fontfile_clause() -> str:
    if platform.system() == "Windows":
        return f":fontfile='{_WINDOWS_FONT}'"
    return ""


def _drawtext_filter_textfile(textfile: Path, fontsize: int, y_expr: str) -> str:
    """Build a drawtext filter that reads text from a file (sidesteps all quoting)."""
    safe_path = str(textfile).replace("\\", "/").replace(":", "\\:")
    return (f"drawtext=textfile='{safe_path}'"
            f"{_fontfile_clause()}"
            f":fontcolor=white:fontsize={fontsize}"
            f":borderw=4:bordercolor=black"
            f":x=(w-text_w)/2:y={y_expr}")


def _run_ffmpeg(cmd: list[str]) -> None:
    """Run ffmpeg, surfacing stderr on failure."""
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="replace") if e.stderr else ""
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd[:3])}...\n{stderr}") from e


def _has_audio_stream(video_path: Path) -> bool:
    """Probe whether a file has an audio stream."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return "audio" in result.stdout
    except subprocess.CalledProcessError:
        return False


def render_clip_segment(
    input_path: Path,
    trim: tuple[float, float],
    subtitle: str,
    output_path: Path,
) -> None:
    """Trim, scale-and-pad to 1080x1920, burn-in subtitle. Handles audio-less inputs."""
    start, end = trim
    duration = max(0.1, end - start)
    has_audio = _has_audio_stream(input_path)

    vf_chain = [
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease",
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:color=black",
        "setsar=1",
    ]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        if subtitle:
            sub_file = tmp_dir / "sub.txt"
            sub_file.write_text(subtitle, encoding="utf-8")
            vf_chain.append(_drawtext_filter_textfile(
                sub_file, SUBTITLE_FONT_SIZE, "h-text_h-200"))

        cmd: list[str] = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", str(start), "-t", str(duration),
            "-i", str(input_path),
        ]
        if not has_audio:
            # synthesize a silent track so concat downstream stays consistent
            cmd += ["-f", "lavfi", "-t", str(duration),
                    "-i", "anullsrc=r=44100:cl=stereo"]
        cmd += [
            "-vf", ",".join(vf_chain),
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "44100", "-ac", "2",
            "-r", "30",
        ]
        if not has_audio:
            cmd += ["-map", "0:v", "-map", "1:a", "-shortest"]
        cmd += [str(output_path)]
        _run_ffmpeg(cmd)


def render_text_card(text: str, duration: float, output_path: Path) -> None:
    """Render a 1080x1920 black card with centered white text + silent audio."""
    with tempfile.TemporaryDirectory() as tmp:
        sub_file = Path(tmp) / "card.txt"
        sub_file.write_text(text, encoding="utf-8")
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"color=c=black:s={TARGET_W}x{TARGET_H}:d={duration}:r=30",
            "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={duration}",
            "-vf", _drawtext_filter_textfile(sub_file, HOOK_FONT_SIZE, "(h-text_h)/2"),
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest",
            str(output_path),
        ]
        _run_ffmpeg(cmd)


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
    _run_ffmpeg(cmd)


def render_timeline(timeline: Timeline, analyzed_dir: Path, output_path: Path) -> None:
    """Render full timeline: hook -> clips -> outro."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        segments: list[Path] = []

        hook_seg = tmp_dir / "hook.mp4"
        render_text_card(timeline.hook.text, timeline.hook.duration, hook_seg)
        segments.append(hook_seg)

        for i, clip in enumerate(timeline.clips):
            meta_path = analyzed_dir / f"{clip.id}.json"
            cm = ClipMetadata.model_validate_json(meta_path.read_text(encoding="utf-8"))
            seg_path = tmp_dir / f"clip_{i:03d}.mp4"
            render_clip_segment(Path(cm.path), clip.trim, clip.subtitle, seg_path)
            segments.append(seg_path)

        outro_seg = tmp_dir / "outro.mp4"
        render_text_card(timeline.outro.text, timeline.outro.duration, outro_seg)
        segments.append(outro_seg)

        _concat_segments(segments, output_path)
