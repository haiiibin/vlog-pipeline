"""Shared data types for the pipeline. All persisted as JSON via pydantic."""
from pydantic import BaseModel, ConfigDict


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(frozen=True)
    start: float
    end: float
    text: str


class ClipMetadata(BaseModel):
    """One analyzed source clip. Written to data/work/<week>/analyzed/<id>.json"""
    id: str
    path: str
    captured_at: str               # ISO 8601
    duration_sec: float
    resolution: list[int]          # [width, height]
    orientation: str               # "landscape" | "portrait"
    scenes: list[tuple[float, float]] = []
    transcript: list[TranscriptSegment] = []
    score: int = 0
    score_breakdown: dict[str, int] = {}
    audio: dict[str, float] = {}   # {"rms_peak": ..., "rms_mean": ...}; {} if no audio
    preview_gif: str | None = None


class TimelineClip(BaseModel):
    id: str
    trim: tuple[float, float]      # (start, end) in source seconds
    subtitle: str = ""
    transition: str = "cut"        # Phase 1: only "cut"


class TextCard(BaseModel):
    text: str
    duration: float


class Timeline(BaseModel):
    """Complete cut list. Written to data/work/<week>/timeline.json"""
    week: str
    hook: TextCard
    clips: list[TimelineClip]
    outro: TextCard
    estimated_duration_sec: int
