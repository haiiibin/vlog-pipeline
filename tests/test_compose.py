from src.compose import build_simple_timeline
from src.types import ClipMetadata, TranscriptSegment


def _make_clip(cid: str, captured_at: str, duration: float = 5.0,
               text: str = "") -> ClipMetadata:
    transcript = [TranscriptSegment(start=0, end=2, text=text)] if text else []
    return ClipMetadata(
        id=cid, path=f"data/inbox/{cid}.MOV", captured_at=captured_at,
        duration_sec=duration, resolution=[1920, 1080], orientation="landscape",
        transcript=transcript,
    )


def test_clips_sorted_by_capture_time():
    clips = [
        _make_clip("C", "2026-05-02T14:00:00"),
        _make_clip("A", "2026-05-02T08:00:00"),
        _make_clip("B", "2026-05-02T10:00:00"),
    ]
    tl = build_simple_timeline(clips, week="2026-W18")
    assert [c.id for c in tl.clips] == ["A", "B", "C"]


def test_long_clips_trimmed_to_max():
    clips = [_make_clip("X", "2026-05-02T08:00:00", duration=20.0, text="hello")]
    tl = build_simple_timeline(clips, week="2026-W18", max_clip_sec=8.0)
    assert tl.clips[0].trim == (0.0, 8.0)


def test_subtitle_is_first_transcript_segment_text():
    clips = [_make_clip("X", "2026-05-02T08:00:00", text="今天早餐做了三明治")]
    tl = build_simple_timeline(clips, week="2026-W18")
    assert tl.clips[0].subtitle == "今天早餐做了三明治"


def test_hook_outro_present():
    clips = [_make_clip("A", "2026-05-02T08:00:00")]
    tl = build_simple_timeline(clips, week="2026-W18")
    assert tl.hook.text == "本周精选"
    assert tl.hook.duration > 0
    assert tl.outro.text.startswith("下周见")
    assert tl.estimated_duration_sec > 0
