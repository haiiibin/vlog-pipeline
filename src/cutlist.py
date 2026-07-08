"""Claude cut-list generation (Phase 3).

Send selected clips to claude-haiku-4-5 with structured output, validate the
response, and map it to a Timeline. On any API failure the exception propagates
(no heuristic fallback, per DESIGN section 11.1 rule 3).
"""
from pydantic import BaseModel

from src.compose import (
    HOOK_DURATION,
    HOOK_TEXT,
    MAX_SUBTITLE_LEN,
    OUTRO_DURATION,
    OUTRO_TEXT,
)
from src.types import ClipMetadata, TextCard, Timeline, TimelineClip

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 2000

_SYSTEM = (
    "你是一个中文生活 vlog 的剪辑助理。给定本周候选片段(每个含 id、时长、打分、口播转录), "
    "产出一条 1 至 3 分钟竖屏 vlog 的剪辑脚本: 一句抖音风格钩子文案(hook)、"
    "按叙事顺序排列的片段(每个给出 id、起止秒 trim_start/trim_end、一句不超过 "
    f"{MAX_SUBTITLE_LEN} 字的字幕 subtitle)、一句结尾文案(outro)。"
    "trim 必须落在该片段时长内, 只使用给定的 id。"
)


class CutClip(BaseModel):
    id: str
    trim_start: float
    trim_end: float
    subtitle: str


class CutlistResponse(BaseModel):
    hook: str
    clips: list[CutClip]
    outro: str


class CutlistError(RuntimeError):
    """Raised when the model returns nothing usable."""


def _clips_prompt(clips: list[ClipMetadata]) -> str:
    lines = []
    for c in clips:
        text = " ".join(seg.text for seg in c.transcript) or "(无口播)"
        lines.append(f"- id={c.id} 时长={c.duration_sec:.1f}s 打分={c.score} 口播={text}")
    return "本周候选片段:\n" + "\n".join(lines)


def generate_cutlist(
    clips: list[ClipMetadata],
    week: str,
    *,
    client=None,
    model: str = MODEL,
) -> Timeline:
    if not clips:
        raise CutlistError("no clips to compose")
    if client is None:
        import anthropic
        client = anthropic.Anthropic()

    resp = client.messages.parse(
        model=model,
        max_tokens=MAX_TOKENS,
        system=_SYSTEM,
        messages=[{"role": "user", "content": _clips_prompt(clips)}],
        output_format=CutlistResponse,
    )
    parsed: CutlistResponse = resp.parsed_output

    by_id = {c.id: c for c in clips}
    timeline_clips: list[TimelineClip] = []
    for cc in parsed.clips:
        src = by_id.get(cc.id)
        if src is None:
            continue
        start = max(0.0, min(cc.trim_start, src.duration_sec))
        end = max(0.0, min(cc.trim_end, src.duration_sec))
        if end <= start:
            continue
        timeline_clips.append(TimelineClip(
            id=cc.id,
            trim=(start, end),
            subtitle=cc.subtitle[:MAX_SUBTITLE_LEN],
            transition="cut",
        ))

    if not timeline_clips:
        raise CutlistError("model returned no valid clips")

    total = sum(tc.trim[1] - tc.trim[0] for tc in timeline_clips)
    return Timeline(
        week=week,
        hook=TextCard(text=parsed.hook.strip() or HOOK_TEXT, duration=HOOK_DURATION),
        clips=timeline_clips,
        outro=TextCard(text=parsed.outro.strip() or OUTRO_TEXT, duration=OUTRO_DURATION),
        estimated_duration_sec=int(total + HOOK_DURATION + OUTRO_DURATION),
    )
