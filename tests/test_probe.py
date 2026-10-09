import pytest

from src.probe import build_clip_metadata, generate_gif_preview, get_raw_metadata


def test_get_raw_metadata_returns_streams_and_format(sample_video):
    meta = get_raw_metadata(sample_video)
    assert "format" in meta
    assert "streams" in meta
    assert float(meta["format"]["duration"]) == pytest.approx(5.0, abs=0.1)


def test_build_clip_metadata_landscape(sample_video):
    cm = build_clip_metadata(sample_video, clip_id="TEST_01")
    assert cm.id == "TEST_01"
    assert cm.duration_sec == pytest.approx(5.0, abs=0.1)
    assert cm.resolution == [1920, 1080]
    assert cm.orientation == "landscape"
    assert cm.path == str(sample_video)


def test_build_clip_metadata_portrait(tmp_video_factory):
    video = tmp_video_factory("portrait.mp4", duration=3.0, size="1080x1920")
    cm = build_clip_metadata(video, clip_id="P1")
    assert cm.orientation == "portrait"
    assert cm.resolution == [1080, 1920]


def test_generate_gif_preview_creates_file(sample_video, tmp_path):
    out = tmp_path / "preview.gif"
    generate_gif_preview(sample_video, out, duration=2.0, width=120)
    assert out.exists()
    assert out.stat().st_size > 0
    assert out.stat().st_size < 200_000   # under 200KB
