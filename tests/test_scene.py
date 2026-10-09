import pytest

from src.scene import detect_scenes


def test_single_color_video_returns_single_scene(sample_video):
    """Constant blue video has no scene cuts."""
    scenes = detect_scenes(sample_video)
    assert len(scenes) == 1
    assert scenes[0][0] == 0.0
    assert scenes[0][1] == pytest.approx(5.0, abs=0.2)


def test_multi_color_video_returns_multiple_scenes(tmp_path):
    """Concatenate three different-color videos to force scene boundaries."""
    import subprocess
    parts = []
    for i, color in enumerate(["red", "green", "blue"]):
        p = tmp_path / f"part_{i}.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"color=c={color}:s=640x360:d=2:r=30",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(p),
        ], check=True, capture_output=True)
        parts.append(p)

    list_file = tmp_path / "parts.txt"
    list_file.write_text("".join(f"file '{p}'\n" for p in parts))
    merged = tmp_path / "merged.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", str(merged),
    ], check=True, capture_output=True)

    scenes = detect_scenes(merged)
    assert len(scenes) >= 2     # at least one cut detected
