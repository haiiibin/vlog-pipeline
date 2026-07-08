"""cutlist.py tests. Fake Anthropic client -- never touches the real API."""
import pytest

from src.cutlist import CutClip, CutlistError, CutlistResponse, generate_cutlist
from src.types import ClipMetadata


class _FakeResp:
    def __init__(self, parsed):
        self.parsed_output = parsed


class _FakeMessages:
    def __init__(self, parsed=None, exc=None):
        self._parsed, self._exc = parsed, exc

    def parse(self, **kwargs):
        if self._exc:
            raise self._exc
        return _FakeResp(self._parsed)


class _FakeClient:
    def __init__(self, parsed=None, exc=None):
        self.messages = _FakeMessages(parsed, exc)


def _clip(cid, dur):
    return ClipMetadata(
        id=cid, path=f"{cid}.mp4", captured_at="2026-07-01T08:00:00",
        duration_sec=dur, resolution=[1080, 1920], orientation="portrait",
    )


def test_generate_maps_response_to_timeline():
    clips = [_clip("A", 5.0), _clip("B", 8.0)]
    parsed = CutlistResponse(
        hook="本周三连吃", outro="下周见",
        clips=[CutClip(id="A", trim_start=0.5, trim_end=4.0, subtitle="早餐"),
               CutClip(id="B", trim_start=1.0, trim_end=6.0, subtitle="午餐")],
    )
    tl = generate_cutlist(clips, "w1", client=_FakeClient(parsed=parsed))
    assert tl.week == "w1"
    assert [c.id for c in tl.clips] == ["A", "B"]
    assert tl.hook.text == "本周三连吃"
    # est = (4.0-0.5)+(6.0-1.0) + 2.5 + 1.5 = 12.5 -> int 12
    assert tl.estimated_duration_sec == 12


def test_unknown_id_dropped_and_trim_clamped():
    clips = [_clip("A", 5.0)]
    parsed = CutlistResponse(
        hook="h", outro="o",
        clips=[CutClip(id="GHOST", trim_start=0, trim_end=3, subtitle="x"),
               CutClip(id="A", trim_start=-2.0, trim_end=99.0, subtitle="y")],
    )
    tl = generate_cutlist(clips, "w1", client=_FakeClient(parsed=parsed))
    assert [c.id for c in tl.clips] == ["A"]
    assert tl.clips[0].trim == (0.0, 5.0)


def test_subtitle_truncated():
    clips = [_clip("A", 5.0)]
    parsed = CutlistResponse(
        hook="h", outro="o",
        clips=[CutClip(id="A", trim_start=0, trim_end=4, subtitle="字" * 50)],
    )
    tl = generate_cutlist(clips, "w1", client=_FakeClient(parsed=parsed))
    assert len(tl.clips[0].subtitle) == 24


def test_no_valid_clips_raises():
    clips = [_clip("A", 5.0)]
    parsed = CutlistResponse(
        hook="h", outro="o",
        clips=[CutClip(id="GHOST", trim_start=0, trim_end=3, subtitle="x")],
    )
    with pytest.raises(CutlistError):
        generate_cutlist(clips, "w1", client=_FakeClient(parsed=parsed))


def test_api_failure_propagates_no_fallback():
    clips = [_clip("A", 5.0)]
    with pytest.raises(RuntimeError, match="boom"):
        generate_cutlist(clips, "w1", client=_FakeClient(exc=RuntimeError("boom")))
