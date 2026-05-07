"""Phase 1 simple heuristic scorer. Replaced in Phase 3 by audio + face analysis."""


def compute_score(raw_meta: dict, transcript: list[dict]) -> tuple[int, dict]:
    """Return (score 0-100, breakdown dict). Phase 1 rules:
        +20 if duration >= 2s
        +20 if has audio stream
        +40 if has any non-empty transcribed speech
        +20 if duration in [3, 30]s
    """
    breakdown: dict[str, int] = {}
    duration = float(raw_meta["format"]["duration"])

    if duration >= 2.0:
        breakdown["duration"] = 20
    if any(s.get("codec_type") == "audio" for s in raw_meta.get("streams", [])):
        breakdown["has_audio"] = 20
    if transcript and any(seg.get("text", "").strip() for seg in transcript):
        breakdown["has_speech"] = 40
    if 3.0 <= duration <= 30.0:
        breakdown["good_length"] = 20

    score = min(100, sum(breakdown.values()))
    return score, breakdown
