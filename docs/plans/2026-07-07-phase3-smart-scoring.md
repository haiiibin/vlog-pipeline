# Phase 3: 智能打分 + Claude 剪辑脚本 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把打分从纯启发式升级为"音频能量感知", 把剪辑脚本从固定模板升级为 Claude(`claude-haiku-4-5`)生成, 成片质量从"凑合"到"能看"。

**Architecture:** 新增 `src/audio.py`(ffmpeg 抽音轨 + librosa RMS 能量)与 `src/cutlist.py`(Claude 结构化输出生成剪辑脚本, 返回后自校验映射为现有 `Timeline`); `src/score.py` 并入能量维度; pipeline 与 server 的渲染路径默认切到 Claude, 保留确定性构建器作为显式逃生口。Claude 失败即停, 绝不启发式兜底。

**Tech Stack:** Python 3.11+, uv, click, pydantic v2, librosa, anthropic SDK(`messages.parse` 结构化输出), FastAPI, ffmpeg/ffprobe, pytest。

**上游文档:** `docs/specs/2026-07-07-phase3-smart-scoring-design.md`(spec)、`docs/DESIGN.md`(总体设计)。起点 HEAD = 8a6a8e4, 32 pytest 全绿。

## Global Constraints

- Python `>=3.11`; ruff line-length 100, target `py311`; 每个 commit 前 `uv run ruff check .` 干净。
- **绝不使用 em dash(U+2014, 单个或成对)**, 任何文件任何位置(代码注释、文档、commit message)。用逗号/冒号/圆括号/句号替代。
- 模型 id 精确为 `claude-haiku-4-5`, 不用其他。
- **Claude 失败即停, 无启发式兜底**(DESIGN §11.1 规则 3): 任何 Anthropic 错误向上传播, 不退回 `build_simple_timeline`。
- 测试永不触真实 Anthropic API、真实 whisper、真实用户素材; 视频一律 ffmpeg lavfi 合成。
- 依赖用 `uv add <pkg>` 安装(同时改 pyproject 并落 .venv); 测试用 `uv run pytest`。
- 打分权重(总分封顶 100, breakdown 只收录取正值的维度):
  `has_speech` 30 / `audio_energy` `round(30 * min(rms_peak/PEAK_REF, 1.0))`(PEAK_REF=0.2, 上限 30)/ `good_length`(时长 ∈ [3,30]s)20 / `has_audio` 10 / `duration_ok`(时长 ≥ 2s)10。
- 字幕上限、hook/outro 时长复用 `src/compose.py` 常量: `MAX_SUBTITLE_LEN`(24)、`HOOK_DURATION`(2.5)、`OUTRO_DURATION`(1.5)、`HOOK_TEXT`、`OUTRO_TEXT`。
- Anthropic 结构化输出调用形态(对照 claude-api skill python 参考核定):
  `client.messages.parse(model=..., max_tokens=..., system=..., messages=[...], output_format=<PydanticModel>)`, 取 `resp.parsed_output` 为已校验实例。

---

### Task 1: `src/audio.py` -- librosa 音频能量分析

**Files:**
- Create: `src/audio.py`
- Test: `tests/test_audio.py`
- Modify: `pyproject.toml`(经 `uv add librosa`)

**Interfaces:**
- Produces: `analyze_audio(video_path: Path) -> dict`, 返回 `{"rms_peak": float, "rms_mean": float}`(值域约 [0,1]), 无音轨时返回 `{}`。

- [ ] **Step 1: 装 librosa**

Run: `cd "C:/Users/yuhai/github_work/vlog-pipeline" && uv add librosa`
Expected: `pyproject.toml` 的 `[project].dependencies` 出现 `librosa>=...`; `.venv` 装好(含 numpy/scipy/soundfile, 首次可能装 1 至 2 分钟)。

- [ ] **Step 2: 写失败测试 `tests/test_audio.py`**

```python
"""audio.py tests: RMS energy from lavfi-synthesized clips. No real media."""
import subprocess
from pathlib import Path

from src.audio import analyze_audio


def _sine_video(path: Path, volume: float = 1.0, duration: float = 3.0) -> Path:
    af = f"sine=frequency=440:duration={duration},volume={volume}"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c=blue:s=640x360:d={duration}:r=30",
        "-f", "lavfi", "-i", af,
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(path),
    ], check=True, capture_output=True)
    return path


def test_audio_has_energy(tmp_path):
    v = _sine_video(tmp_path / "loud.mp4", volume=1.0)
    feats = analyze_audio(v)
    assert feats["rms_peak"] > 0
    assert feats["rms_mean"] > 0


def test_audio_no_stream_returns_empty(tmp_path):
    path = tmp_path / "silent.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=blue:s=640x360:d=2:r=30",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        str(path),
    ], check=True, capture_output=True)
    assert analyze_audio(path) == {}


def test_audio_louder_scores_higher(tmp_path):
    loud = _sine_video(tmp_path / "loud.mp4", volume=1.0)
    quiet = _sine_video(tmp_path / "quiet.mp4", volume=0.2)
    assert analyze_audio(loud)["rms_peak"] > analyze_audio(quiet)["rms_peak"]
```

- [ ] **Step 3: 跑测试确认失败**

Run: `uv run pytest tests/test_audio.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'src.audio'`

- [ ] **Step 4: 实现 `src/audio.py`**

```python
"""Audio energy analysis via ffmpeg + librosa (Phase 3).

Extract the audio track to a temp mono wav, compute RMS energy.
Returns {} for clips without an audio stream (not an error).
"""
import os
import subprocess
import tempfile
from pathlib import Path

import librosa


def _has_audio_stream(video_path: Path) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(video_path)],
        capture_output=True, text=True,
    )
    return bool(out.stdout.strip())


def analyze_audio(video_path: Path) -> dict:
    """Return {"rms_peak": float, "rms_mean": float} (~[0, 1]), or {} if no audio."""
    if not _has_audio_stream(video_path):
        return {}
    fd, wav = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video_path),
             "-vn", "-ac", "1", "-ar", "22050", "-f", "wav", wav],
            check=True, capture_output=True,
        )
        y, _ = librosa.load(wav, sr=22050, mono=True)
        if y.size == 0:
            return {}
        rms = librosa.feature.rms(y=y)[0]
        return {"rms_peak": float(rms.max()), "rms_mean": float(rms.mean())}
    finally:
        if os.path.exists(wav):
            os.remove(wav)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_audio.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: ruff + commit**

```bash
uv run ruff check src/audio.py tests/test_audio.py
git add src/audio.py tests/test_audio.py pyproject.toml uv.lock
git commit -m "feat: audio.py librosa RMS energy analysis"
```

---

### Task 2: `src/score.py` -- 音频能量并入打分 + `ClipMetadata.audio` 字段

**Files:**
- Modify: `src/types.py:12-24`(ClipMetadata 加 `audio` 字段)
- Modify: `src/score.py`(改签名 + 重平衡权重)
- Test: `tests/test_score.py`(重写)

**Interfaces:**
- Consumes: `analyze_audio` 的返回 dict(Task 1): `{"rms_peak", "rms_mean"}` 或 `{}`。
- Produces: `compute_score(raw_meta: dict, transcript: list[dict], audio_features: dict) -> tuple[int, dict]`; `ClipMetadata.audio: dict[str, float]`(默认 `{}`)。

- [ ] **Step 1: types.py 加 `audio` 字段**

`src/types.py` 的 `ClipMetadata` 中, 在 `score_breakdown` 与 `preview_gif` 之间插入一行:

```python
    score: int = 0
    score_breakdown: dict[str, int] = {}
    audio: dict[str, float] = {}   # {"rms_peak": ..., "rms_mean": ...}; {} if no audio
    preview_gif: str | None = None
```

- [ ] **Step 2: 重写 `tests/test_score.py`**

```python
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
```

- [ ] **Step 3: 跑测试确认失败**

Run: `uv run pytest tests/test_score.py -v`
Expected: FAIL(旧 `compute_score` 只接受 2 参数, 新测试传 3 参数报 `TypeError`)

- [ ] **Step 4: 重写 `src/score.py`**

```python
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
```

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_score.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: ruff + commit**

```bash
uv run ruff check src/score.py src/types.py tests/test_score.py
git add src/score.py src/types.py tests/test_score.py
git commit -m "feat: audio-energy scoring, ClipMetadata.audio field"
```

---

### Task 3: `src/cutlist.py` -- Claude 剪辑脚本生成

**Files:**
- Create: `src/cutlist.py`
- Test: `tests/test_cutlist.py`
- Modify: `pyproject.toml`(经 `uv add anthropic`)

**Interfaces:**
- Consumes: `ClipMetadata`(`id`, `duration_sec`, `score`, `transcript`)、`Timeline`/`TimelineClip`/`TextCard`(`src/types.py`); `MAX_SUBTITLE_LEN`/`HOOK_DURATION`/`OUTRO_DURATION`/`HOOK_TEXT`/`OUTRO_TEXT`(`src/compose.py`)。
- Produces: `generate_cutlist(clips: list[ClipMetadata], week: str, *, client=None, model: str="claude-haiku-4-5") -> Timeline`; 异常 `CutlistError`; pydantic 模型 `CutClip`、`CutlistResponse`。

- [ ] **Step 1: 装 anthropic**

Run: `cd "C:/Users/yuhai/github_work/vlog-pipeline" && uv add anthropic`
Expected: `pyproject.toml` 出现 `anthropic>=...`(最新版, 含 `messages.parse` 结构化输出)。

- [ ] **Step 2: 写失败测试 `tests/test_cutlist.py`**

```python
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
```

- [ ] **Step 3: 跑测试确认失败**

Run: `uv run pytest tests/test_cutlist.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'src.cutlist'`

- [ ] **Step 4: 实现 `src/cutlist.py`**

```python
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
```

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_cutlist.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: ruff + commit**

```bash
uv run ruff check src/cutlist.py tests/test_cutlist.py
git add src/cutlist.py tests/test_cutlist.py pyproject.toml uv.lock
git commit -m "feat: cutlist.py Claude cut-list generation (haiku 4.5, structured output)"
```

---

### Task 4: `src/pipeline.py` -- 接线 audio 步 + `run --composer` 开关

**Files:**
- Modify: `src/pipeline.py`(imports、`_analyze_one`、`run`)
- Test: `tests/test_pipeline.py`(更新调用 + 断言 audio 字段)

**Interfaces:**
- Consumes: `analyze_audio`(Task 1)、`compute_score` 新签名(Task 2)、`generate_cutlist`(Task 3)、`build_simple_timeline`(现有)。
- Produces: `run` 新增 `--composer [claude|simple]`(默认 `claude`); `_analyze_one` 落 `cm.audio`。

- [ ] **Step 1: 更新 imports**

`src/pipeline.py` 顶部 import 区(约 11 至 17 行)加两行:

```python
from src.audio import analyze_audio
from src.cutlist import generate_cutlist
```

(保留现有 `from src.compose import build_simple_timeline`。)

- [ ] **Step 2: `_analyze_one` 插入 audio 步**

在 `cm.transcript = [...]` 之后、`compute_score` 之前(现约 40 至 44 行)改为:

```python
    cm.transcript = [TranscriptSegment(**s) for s in transcript_segments]

    audio_features: dict = {}
    try:
        audio_features = analyze_audio(video)
    except Exception as e:
        click.echo(f"  audio failed for {clip_id}: {e}", err=True)
    cm.audio = audio_features

    score, breakdown = compute_score(raw, transcript_segments, audio_features)
    cm.score = score
    cm.score_breakdown = breakdown
```

- [ ] **Step 3: `run` 加 `--composer` 选项并分派**

在 `run` 的 `--language` option 之后加一个 option, 并把函数签名与 compose 调用改掉:

```python
@click.option("--language", default="zh", help="ASR language code")
@click.option("--composer", type=click.Choice(["claude", "simple"]), default="claude",
              show_default=True,
              help="'claude' = Claude cut-list (needs ANTHROPIC_API_KEY); "
                   "'simple' = deterministic no-API builder")
def run(inbox: Path, week: str, select: str, data_root: Path,
        language: str, composer: str):
```

把原 `timeline = build_simple_timeline(selected, week=week)`(现约 104 行)改为:

```python
    click.echo(f"Composing timeline from {len(selected)} clips ({composer})...")
    if composer == "claude":
        timeline = generate_cutlist(selected, week=week)
    else:
        timeline = build_simple_timeline(selected, week=week)
    (work_dir / "timeline.json").write_text(timeline.model_dump_json(indent=2), encoding="utf-8")
```

(删掉原来单独的 `click.echo(f"Composing timeline from ...")` 行, 合并到上面。)

- [ ] **Step 4: 更新 `tests/test_pipeline.py`**

两处 `runner.invoke(cli, [...])` 的 `run` 参数末尾都加 `"--composer", "simple"`:

`test_end_to_end_three_clips` 的 args:
```python
    result = runner.invoke(cli, [
        "run",
        "--inbox", str(inbox),
        "--week", "test-week",
        "--select", "all",
        "--data-root", str(data_root),
        "--language", "en",
        "--composer", "simple",
    ])
```

同测试里的 per-clip 断言块加一行, 验证 audio 落盘:
```python
        assert meta["id"] == cid
        assert meta["score"] >= 40   # has audio + has duration
        assert "rms_peak" in meta["audio"]
```

`test_idempotent_rerun` 的 args 列表末尾加 `"--composer", "simple"`:
```python
    args = ["run", "--inbox", str(inbox), "--week", "w1",
            "--select", "all", "--data-root", str(data_root),
            "--language", "en", "--composer", "simple"]
```

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: PASS (3 passed)。若 `test_end_to_end_three_clips` 因 audio 断言失败, 检查 sine 视频是否有音轨(应有)。

- [ ] **Step 6: ruff + commit**

```bash
uv run ruff check src/pipeline.py tests/test_pipeline.py
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline wires audio step + run --composer claude|simple"
```

---

### Task 5: `src/server.py` -- `compose_fn` 缝, `/api/render` 默认走 Claude

**Files:**
- Modify: `src/server.py`(import、`create_app` 签名、`render`)
- Test: `tests/test_server.py`(render 测试注入 `compose_fn` + 新增失败透传测试)

**Interfaces:**
- Consumes: `generate_cutlist`(Task 3)、`build_simple_timeline`(现有, 测试注入用)。
- Produces: `create_app(data_root: Path, *, compose_fn=generate_cutlist) -> FastAPI`; `/api/render` 用 `compose_fn(clips, week=...)`。

- [ ] **Step 1: 改 import**

`src/server.py` 第 13 行 `from src.compose import build_simple_timeline` 改为:

```python
from src.cutlist import generate_cutlist
```

- [ ] **Step 2: 改 `create_app` 签名**

第 43 行:

```python
def create_app(data_root: Path, *, compose_fn=generate_cutlist) -> FastAPI:
```

- [ ] **Step 3: `render` 用 `compose_fn`**

把 render 里第 110 行 `timeline = build_simple_timeline(clips, week=req.week)` 改为:

```python
            timeline = compose_fn(clips, week=req.week)
```

(其余 try/except 结构不变: `except HTTPException: raise` + `except Exception as e: raise HTTPException(500, str(e))`, 这正是 Claude 失败透传成 JSON 500 的路径。)

- [ ] **Step 4: 更新 `tests/test_server.py`**

顶部 import 区加:
```python
from src.compose import build_simple_timeline
```

三个 render 测试里, `create_app(...)` 调用注入确定性 composer(保持离线):

`test_render_happy_path`:
```python
    client = TestClient(create_app(data, compose_fn=build_simple_timeline))
```
`test_render_failure_surfaces_error`:
```python
    client = TestClient(create_app(data, compose_fn=build_simple_timeline))
```
`test_render_malformed_metadata_returns_json_500`:
```python
    client = TestClient(create_app(data, compose_fn=build_simple_timeline))
```

文件末尾新增一个测试, 证明 compose 失败(如 Claude 挂了)透传成 JSON 500、绝不兜底:
```python
def test_render_compose_failure_returns_500(tmp_path, tmp_video_factory):
    from src.probe import build_clip_metadata
    data = tmp_path / "data"
    analyzed = data / "work" / "w1" / "analyzed"
    analyzed.mkdir(parents=True)
    video = tmp_video_factory("CLIP1.mp4", duration=2.0)
    cm = build_clip_metadata(video, clip_id="CLIP1")
    (analyzed / "CLIP1.json").write_text(cm.model_dump_json(), encoding="utf-8")

    def _boom(clips, week):
        raise RuntimeError("claude boom")

    client = TestClient(create_app(data, compose_fn=_boom))
    client.post("/api/select", json={"week": "w1", "clip_ids": ["CLIP1"]})
    r = client.post("/api/render", json={"week": "w1"})
    assert r.status_code == 500
    assert "claude boom" in r.json()["detail"]
```

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_server.py -v`
Expected: PASS(原 12 个 + 新增 1 个 = 13 passed)

- [ ] **Step 6: ruff + commit**

```bash
uv run ruff check src/server.py tests/test_server.py
git add src/server.py tests/test_server.py
git commit -m "feat: server /api/render defaults to Claude via injectable compose_fn"
```

---

### Task 6: 配置与文档对齐

**Files:**
- Modify: `config.example.yaml`(加 claude 段)
- Modify: `README.md`(Status/Roadmap/ANTHROPIC_API_KEY 说明)
- Modify: `docs/DESIGN.md:315`(旧模型 id 加注记)

**Interfaces:** 无(纯文档/配置)。

- [ ] **Step 1: `config.example.yaml` 加 claude 段**

在 `whisper:` 段之前插入:

```yaml
claude:
  model: "claude-haiku-4-5"          # Phase 3: cut-list generation
  api_key_env: "ANTHROPIC_API_KEY"   # key read from this env var, never stored here
```

- [ ] **Step 2: `README.md` 更新状态、依赖说明、Roadmap**

- 第 7 行状态改为:
  ```markdown
  **Status: WIP (Phase 3 of 5 in progress).** Personal project; interfaces may change without notice.
  ```
- `## Requirements` 末尾加一条:
  ```markdown
  - For Claude-generated cut lists (default composer): an Anthropic API key in `ANTHROPIC_API_KEY`.
    Without it, pass `--composer simple` to use the deterministic builder.
  ```
- Quick start 的第 1 步注释改为标明默认走 Claude:
  ```markdown
  # 1. analyze clips and render a first draft (Claude cut-list; needs ANTHROPIC_API_KEY)
  #    add --composer simple to skip Claude
  uv run python -m src.pipeline run --inbox path/to/clips --week 2026-W28 --select all
  ```
- Roadmap 第 48 行改为(标注人脸推迟 Phase 5):
  ```markdown
  - [~] Phase 3: smarter scoring (audio energy; faces deferred to Phase 5) + LLM-generated cut list
  ```

- [ ] **Step 3: `docs/DESIGN.md` 旧模型 id 加注记**

第 315 行 `claude_model: "claude-sonnet-4-6"` 那行**下面**加一行注释(不改历史正文):

```yaml
claude_model: "claude-sonnet-4-6"
# NOTE(Phase 3, 2026-07-07): 实际使用 claude-haiku-4-5, 见 docs/specs/2026-07-07-phase3-smart-scoring-design.md
```

- [ ] **Step 4: 扫 em dash + 个人信息**

Run: `grep -rnP '\x{2014}' config.example.yaml README.md docs/DESIGN.md | grep -v '^docs/DESIGN.md' || echo OK`
Expected: 本次改动的文件里无新增 em dash(DESIGN.md 历史正文的 em dash 属已知项, 由 going-public-checklist 在转公开时统一清理, 不在本 task 范围)。确认无真实 key、无本机绝对路径写入。

- [ ] **Step 5: commit**

```bash
git add config.example.yaml README.md docs/DESIGN.md
git commit -m "docs: config + README + DESIGN aligned to Phase 3 (claude-haiku-4-5, audio energy)"
```

---

## 收尾(所有 task 完成后)

- [ ] 全量回归: `uv run pytest -v`(应约 37 passed: 原 32 + audio 3 + score 净增 2 + cutlist 5 + server 1, 减去 test_score/test_pipeline 重写抵消; 以实际全绿为准)、`uv run ruff check .` 干净。
- [ ] subagent-driven-development 的整分支终审通过。
- [ ] 推送到私有仓库由用户拍板执行(沿用里程碑推送惯例)。Phase 4(调度 + handoff)另起一轮 spec to plan to build。

---

## Self-Review(计划自审记录)

**1. Spec coverage:** spec §2 audio.py to Task 1; §3 score+types to Task 2; §4 cutlist to Task 3; §5.1 pipeline audio 步 + §5.2 `--composer` to Task 4; §5.2 server compose_fn to Task 5; §5.3 config/README/DESIGN to Task 6; §6 测试策略分散在各 task 的 TDD 步; §7 非目标(不做 MediaPipe/兜底/Phase 4)未引入任何 task, 正确。全部 spec 章节有对应 task。

**2. Placeholder scan:** 无 TBD/TODO/"add error handling" 类占位; 每个改代码的 step 都给了完整代码或精确 diff 位置。

**3. Type consistency:** `analyze_audio -> dict` 在 Task 1 产出、Task 2/4 消费一致; `compute_score` 三参签名 Task 2 定义、Task 4 调用一致; `generate_cutlist(clips, week, *, client, model)` Task 3 定义、Task 4/5 以 `(clips, week=...)` 调用一致; `compose_fn(clips, week=...)` 缝在 Task 5 定义, `build_simple_timeline`/`generate_cutlist`/`_boom` 三者签名均兼容; `ClipMetadata.audio` Task 2 加、Task 4 写、pipeline 测试读一致; 复用常量名(`MAX_SUBTITLE_LEN`/`HOOK_DURATION`/`OUTRO_DURATION`/`HOOK_TEXT`/`OUTRO_TEXT`)与 compose.py 现有定义一致。
