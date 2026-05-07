"""End-to-end smoke test: 3 synthetic videos -> rendered mp4."""
import json
import subprocess
from pathlib import Path
import pytest
from click.testing import CliRunner
from src.pipeline import cli


def _ffprobe_duration(path: Path) -> float:
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json",
           "-show_format", str(path)]
    return float(json.loads(subprocess.run(
        cmd, capture_output=True, text=True, check=True
    ).stdout)["format"]["duration"])


def test_end_to_end_three_clips(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    for color, name in [("red", "AAA.mp4"), ("green", "BBB.mp4"), ("blue", "CCC.mp4")]:
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"color=c={color}:s=1920x1080:d=4:r=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest",
            str(inbox / name),
        ], check=True, capture_output=True)

    data_root = tmp_path / "data"
    runner = CliRunner()
    result = runner.invoke(cli, [
        "run",
        "--inbox", str(inbox),
        "--week", "test-week",
        "--select", "all",
        "--data-root", str(data_root),
        "--language", "en",
    ])
    if result.exit_code != 0:
        print(result.output)
        if result.exception:
            raise result.exception
    assert result.exit_code == 0

    output_mp4 = data_root / "output" / "test-week_vlog.mp4"
    assert output_mp4.exists()

    # 2.5 hook + 3 clips * 4s = 12 + 1.5 outro = 16s total, with rounding tolerance
    dur = _ffprobe_duration(output_mp4)
    assert 14.0 < dur < 18.0

    # Per-clip JSON should exist
    analyzed = data_root / "work" / "test-week" / "analyzed"
    for cid in ["AAA", "BBB", "CCC"]:
        assert (analyzed / f"{cid}.json").exists()
        meta = json.loads((analyzed / f"{cid}.json").read_text())
        assert meta["id"] == cid
        assert meta["score"] >= 40   # has audio + has duration

    # timeline.json should exist
    assert (data_root / "work" / "test-week" / "timeline.json").exists()


def test_idempotent_rerun(tmp_path):
    """Running twice should not re-analyze (json files reused)."""
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=red:s=1920x1080:d=3:r=30",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        str(inbox / "X.mp4"),
    ], check=True, capture_output=True)

    data_root = tmp_path / "data"
    runner = CliRunner()
    args = ["run", "--inbox", str(inbox), "--week", "w1",
            "--select", "all", "--data-root", str(data_root), "--language", "en"]

    r1 = runner.invoke(cli, args)
    assert r1.exit_code == 0
    json_path = data_root / "work" / "w1" / "analyzed" / "X.json"
    mtime_first = json_path.stat().st_mtime

    r2 = runner.invoke(cli, args)
    assert r2.exit_code == 0
    mtime_second = json_path.stat().st_mtime
    # File was reused, not rewritten
    assert mtime_second == mtime_first
