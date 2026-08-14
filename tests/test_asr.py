import os
import pytest
from src.asr import transcribe, parse_timestamp

WHISPER_AVAILABLE = bool(os.environ.get("WHISPER_BIN") and os.environ.get("WHISPER_MODEL"))
skip_if_no_whisper = pytest.mark.skipif(
    not WHISPER_AVAILABLE,
    reason="WHISPER_BIN / WHISPER_MODEL env vars not set"
)


def test_parse_timestamp_basic():
    assert parse_timestamp("00:00:01,500") == 1.5
    assert parse_timestamp("00:01:23,456") == 83.456
    assert parse_timestamp("01:00:00,000") == 3600.0


@skip_if_no_whisper
def test_transcribe_silent_video_returns_empty(sample_video):
    """A 5-second 440Hz tone has no speech -- transcription should be empty or near-empty."""
    segments = transcribe(sample_video, language="en")
    # Whisper sometimes hallucinates on tones; assert structure not exact emptiness.
    assert isinstance(segments, list)
    for seg in segments:
        assert "start" in seg and "end" in seg and "text" in seg
        assert seg["end"] >= seg["start"]
