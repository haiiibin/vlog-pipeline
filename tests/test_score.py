from src.score import compute_score
from src.types import TranscriptSegment

_STREAMS_AV = [{"codec_type": "video"}, {"codec_type": "audio"}]


def test_short_silent_clip_scores_low():
    raw_meta = {"format": {"duration": "1.5"}, "streams": [{"codec_type": "video"}]}
    score, breakdown = compute_score(raw_meta, transcript=[], audio_features={})
    assert score < 30
    assert "duration_ok" not in breakdown
    assert "has_audio" not in breakdown
    assert "audio_energy" not in breakdown


def test_full_quality_clip_scores_high():
    raw_meta = {"format": {"duration": "6.5"}, "streams": _STREAMS_AV}
    transcript = [TranscriptSegment(start=0.5, end=4.0, text="今天早上做了三明治").model_dump()]
    score, breakdown = compute_score(
        raw_meta, transcript=transcript,
        audio_features={"rms_peak": 0.3, "rms_mean": 0.2},
    )
    assert score >= 80
    assert breakdown["has_speech"] == 30
    assert breakdown["audio_energy"] == 30


def test_audio_energy_monotonic():
    raw_meta = {"format": {"duration": "5"}, "streams": _STREAMS_AV}
    quiet, _ = compute_score(raw_meta, [], {"rms_peak": 0.05})
    mid, _ = compute_score(raw_meta, [], {"rms_peak": 0.15})
    loud, _ = compute_score(raw_meta, [], {"rms_peak": 0.30})
    assert quiet < mid < loud


def test_audio_energy_absent_without_features():
    raw_meta = {"format": {"duration": "5"}, "streams": _STREAMS_AV}
    _, breakdown = compute_score(raw_meta, [], {})
    assert "audio_energy" not in breakdown


def test_score_capped_at_100():
    raw_meta = {"format": {"duration": "10"}, "streams": _STREAMS_AV}
    transcript = [TranscriptSegment(start=0.0, end=8.0, text="x").model_dump()]
    score, _ = compute_score(raw_meta, transcript=transcript, audio_features={"rms_peak": 0.9})
    assert 0 <= score <= 100
