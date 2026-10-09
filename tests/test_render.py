import json
import subprocess
from pathlib import Path

import pytest

from src.render import render_clip_segment, render_text_card, render_timeline
from src.types import ClipMetadata, TextCard, Timeline, TimelineClip


def _ffprobe_duration(path: Path) -> float:
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json",
           "-show_format", str(path)]
    return float(json.loads(subprocess.run(cmd, capture_output=True, text=True,
                                            check=True).stdout)["format"]["duration"])


def _ffprobe_resolution(path: Path) -> tuple[int, int]:
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json",
           "-show_streams", str(path)]
    streams = json.loads(subprocess.run(cmd, capture_output=True, text=True,
                                         check=True).stdout)["streams"]
    v = next(s for s in streams if s["codec_type"] == "video")
    return int(v["width"]), int(v["height"])


def test_render_clip_segment_produces_9_16_video(sample_video, tmp_path):
    out = tmp_path / "seg.mp4"
    render_clip_segment(sample_video, (1.0, 4.0), "测试字幕", out)
    assert out.exists()
    w, h = _ffprobe_resolution(out)
    assert (w, h) == (1080, 1920)
    assert _ffprobe_duration(out) == pytest.approx(3.0, abs=0.2)


def test_render_text_card(tmp_path):
    out = tmp_path / "card.mp4"
    render_text_card("本周精选", 2.0, out)
    assert out.exists()
    w, h = _ffprobe_resolution(out)
    assert (w, h) == (1080, 1920)
    assert _ffprobe_duration(out) == pytest.approx(2.0, abs=0.2)


def test_render_timeline_end_to_end(sample_video, tmp_path):
    # Set up an analyzed dir with one ClipMetadata pointing at sample_video
    analyzed = tmp_path / "analyzed"
    analyzed.mkdir()
    cm = ClipMetadata(
        id="C1", path=str(sample_video), captured_at="2026-05-02T08:00:00",
        duration_sec=5.0, resolution=[1920, 1080], orientation="landscape",
    )
    (analyzed / "C1.json").write_text(cm.model_dump_json())

    tl = Timeline(
        week="test",
        hook=TextCard(text="HOOK", duration=1.5),
        clips=[TimelineClip(id="C1", trim=(0.0, 3.0), subtitle="hello")],
        outro=TextCard(text="BYE", duration=1.0),
        estimated_duration_sec=6,
    )
    out = tmp_path / "final.mp4"
    render_timeline(tl, analyzed, out)
    assert out.exists()
    w, h = _ffprobe_resolution(out)
    assert (w, h) == (1080, 1920)
    # 1.5 hook + 3.0 clip + 1.0 outro = 5.5s, allow 0.5s tolerance
    assert _ffprobe_duration(out) == pytest.approx(5.5, abs=0.5)
