from src.score import compute_score
from src.types import TranscriptSegment


def test_short_silent_clip_scores_low():
    raw_meta = {
        "format": {"duration": "1.5"},
        "streams": [{"codec_type": "video"}],   # no audio stream
    }
    score, breakdown = compute_score(raw_meta, transcript=[])
    assert score < 30
    assert "duration" not in breakdown   # below threshold
    assert "has_audio" not in breakdown


def test_full_quality_clip_scores_high():
    raw_meta = {
        "format": {"duration": "6.5"},
        "streams": [
            {"codec_type": "video"},
            {"codec_type": "audio"},
        ],
    }
    transcript = [TranscriptSegment(start=0.5, end=4.0, text="今天早上做了三明治").model_dump()]
    score, breakdown = compute_score(raw_meta, transcript=transcript)
    assert score >= 80
    assert breakdown["has_speech"] == 40


def test_score_capped_at_100():
    raw_meta = {
        "format": {"duration": "10"},
        "streams": [{"codec_type": "video"}, {"codec_type": "audio"}],
    }
    transcript = [TranscriptSegment(start=0.0, end=8.0, text="x").model_dump()]
    score, _ = compute_score(raw_meta, transcript=transcript)
    assert 0 <= score <= 100
