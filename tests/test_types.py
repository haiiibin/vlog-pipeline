import json
from src.types import ClipMetadata, Timeline, TimelineClip, TextCard, TranscriptSegment


def test_clip_metadata_round_trip():
    meta = ClipMetadata(
        id="IMG_0001",
        path="data/inbox/IMG_0001.MOV",
        captured_at="2026-05-02T08:23:14",
        duration_sec=5.2,
        resolution=[1920, 1080],
        orientation="landscape",
        scenes=[(0.0, 5.2)],
        transcript=[TranscriptSegment(start=0.5, end=2.0, text="hello")],
        score=78,
        score_breakdown={"duration": 20, "has_speech": 40},
        preview_gif="data/work/test/analyzed/IMG_0001.gif",
    )
    blob = meta.model_dump_json()
    restored = ClipMetadata.model_validate_json(blob)
    assert restored == meta


def test_timeline_round_trip():
    tl = Timeline(
        week="2026-W18",
        hook=TextCard(text="本周精选", duration=2.0),
        clips=[TimelineClip(id="IMG_0001", trim=(0.0, 4.5), subtitle="早餐")],
        outro=TextCard(text="下周见", duration=1.5),
        estimated_duration_sec=8,
    )
    blob = tl.model_dump_json()
    restored = Timeline.model_validate_json(blob)
    assert restored == tl
    # JSON should be human-readable Chinese
    assert "本周精选" in blob
