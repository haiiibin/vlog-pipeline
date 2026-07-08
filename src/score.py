"""Phase 3 scorer: Phase 1 heuristics + librosa audio-energy bonus."""

# rms_peak that maps to full audio-energy credit. Tunable in Phase 5.
PEAK_REF = 0.2
AUDIO_ENERGY_MAX = 30


def compute_score(
    raw_meta: dict,
    transcript: list[dict],
    audio_features: dict,
) -> tuple[int, dict]:
    """Return (score 0-100, breakdown). Only positive contributions appear in breakdown.

    Weights: has_speech 30, audio_energy 0-30, good_length 20, has_audio 10, duration_ok 10.
    """
    breakdown: dict[str, int] = {}
    duration = float(raw_meta["format"]["duration"])

    if transcript and any(seg.get("text", "").strip() for seg in transcript):
        breakdown["has_speech"] = 30

    rms_peak = float(audio_features.get("rms_peak", 0.0)) if audio_features else 0.0
    if rms_peak > 0:
        energy = round(AUDIO_ENERGY_MAX * min(rms_peak / PEAK_REF, 1.0))
        if energy > 0:
            breakdown["audio_energy"] = energy

    if 3.0 <= duration <= 30.0:
        breakdown["good_length"] = 20
    if any(s.get("codec_type") == "audio" for s in raw_meta.get("streams", [])):
        breakdown["has_audio"] = 10
    if duration >= 2.0:
        breakdown["duration_ok"] = 10

    score = min(100, sum(breakdown.values()))
    return score, breakdown
