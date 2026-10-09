"""Phase 1 simple timeline builder. Phase 3 replaces this with Claude API."""
from src.types import ClipMetadata, TextCard, Timeline, TimelineClip

HOOK_TEXT = "本周精选"
HOOK_DURATION = 2.5
OUTRO_TEXT = "下周见 👋"
OUTRO_DURATION = 1.5
DEFAULT_MAX_CLIP_SEC = 8.0
MAX_SUBTITLE_LEN = 24


def build_simple_timeline(
    clips: list[ClipMetadata],
    week: str,
    max_clip_sec: float = DEFAULT_MAX_CLIP_SEC,
) -> Timeline:
    """Sort clips chronologically, trim each to max_clip_sec, use first transcript line as subtitle."""
    sorted_clips = sorted(clips, key=lambda c: c.captured_at)

    timeline_clips: list[TimelineClip] = []
    total = 0.0
    for c in sorted_clips:
        trim_end = min(c.duration_sec, max_clip_sec)
        subtitle = ""
        if c.transcript:
            subtitle = c.transcript[0].text[:MAX_SUBTITLE_LEN]
        timeline_clips.append(TimelineClip(
            id=c.id,
            trim=(0.0, trim_end),
            subtitle=subtitle,
            transition="cut",
        ))
        total += trim_end

    return Timeline(
        week=week,
        hook=TextCard(text=HOOK_TEXT, duration=HOOK_DURATION),
        clips=timeline_clips,
        outro=TextCard(text=OUTRO_TEXT, duration=OUTRO_DURATION),
        estimated_duration_sec=int(total + HOOK_DURATION + OUTRO_DURATION),
    )
