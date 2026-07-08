# vlog-pipeline Phase 3 智能打分 + Claude 剪辑脚本 · 设计文档

**日期**: 2026-07-07
**状态**: 已通过 brainstorming 评审
**上游文档**: `docs/DESIGN.md`(总体设计 v1.0, 2026-05-07)、`docs/specs/2026-07-06-revival-phase2-design.md`(Phase 2)。本文档只覆盖 Phase 3, 与总体设计冲突处以本文档为准。

---

## 0. 背景与已拍板决策

Phase 1(MVP 链路)与 Phase 2(候选池 Web UI)已完成并推送到私有仓库 `github_work\vlog-pipeline`(HEAD = ee1580c, 32 个 pytest 全绿)。当前打分是启发式(时长/有声/有口播/时长区间), 时间线是按拍摄时间排序的固定模板(`compose.build_simple_timeline`)。Phase 3 把这两处升级为"能看"的质量。

用户已拍板五个决策:

1. **拆两个循环, Phase 3 先做**: Phase 3(剪辑质量)与 Phase 4(定时调度 + 跨平台 handoff)是两个独立子系统, 各走一遍 spec to plan to build。本文档只做 Phase 3。
2. **打分先只上音频能量(librosa)**: 用 RMS 能量找"高能瞬间"作为亮点代理指标。MediaPipe 人脸检测、画面稳定度推迟到 Phase 5(总体设计 §16 及 §2.2 已把人脸/稳定列为代理指标, 本次不做)。这是相对总体设计 §3、§4、§7.1、附录 A 的**有意收窄**。
3. **Claude 失败即停, 不兜底**: 遵循总体设计 §11.1 规则 3(质量优先于可用性)。Compose 调 Claude 失败 to 整个渲染停止报错, 不退回启发式模板。
4. **模型 = `claude-haiku-4-5`**: 任务是小体量结构化输出, Haiku 4.5 足够且最省(约 $1/$5 每百万 token, 契合总体设计 §1.1 的 "约 ¥5/月" 预算)。总体设计 §8 config 里的 `claude-sonnet-4-6` 是旧值, 本次以 `claude-haiku-4-5` 为准。
5. **本次范围只到 Phase 3**: 不碰调度、handoff、setup 脚本(那些是 Phase 4)。

### 与总体设计的三处偏差(显式记录)

- **只做 librosa, 不做 MediaPipe**: `src/face.py`、`stability`、`score_breakdown.face`、`score_breakdown.stability` 均不在本次实现。deps 只加 `librosa`, 不加 `mediapipe`。
- **不声称检测笑声**: 总体设计 §7.1 的 `audio` 块含 `has_laughter`。RMS 能量无法可靠区分笑声与其他响声, 本次只持久化诚实的能量指标(`rms_peak`、`rms_mean`), 不写 `has_laughter`。
- **模型 id**: 用 `claude-haiku-4-5`, 覆盖总体设计 §8 的旧值。

---

## 1. 模块变更总览

| 模块 | 变更 | 职责 |
|---|---|---|
| `src/audio.py` | 新增 | ffmpeg 抽音轨 + librosa 算 RMS 能量, 返回 `{rms_peak, rms_mean}` |
| `src/score.py` | 改签名 | 把音频能量并入打分, 重新平衡权重 |
| `src/cutlist.py` | 新增 | 调 `claude-haiku-4-5` 结构化输出生成剪辑脚本, 校验后映射为 `Timeline` |
| `src/types.py` | 加字段 | `ClipMetadata.audio` 持久化能量指标 |
| `src/pipeline.py` | 接线 | `_analyze_one` 加 audio 步; `run` 渲染路径默认走 cutlist, 加 `--composer` 开关 |
| `src/server.py` | 接线 | `/api/render` 默认走 cutlist(经可注入的 `compose_fn` 缝) |
| `src/compose.py` | 保留 | `build_simple_timeline` 不删, 作为确定性构建器(测试 + 显式 `--composer simple`), 不做静默兜底 |

### 依赖变更

`pyproject.toml` dependencies 增加: `librosa>=0.10`、`anthropic>=0.40`。(总体设计附录 A 还列了 `mediapipe`、`qrcode`、`ffmpeg-python`, 它们分别属于 Phase 5 / Phase 4, 本次不加。)

---

## 2. `src/audio.py`(新增)

单一职责: 从视频抽音频, 算能量, 返回纯数据。

```python
def analyze_audio(video_path: Path) -> dict:
    """返回 {"rms_peak": float, "rms_mean": float}(值域约 [0, 1])。
    无音轨的片段返回 {}(不是错误, 只是没有能量信号)。"""
```

实现要点:

- 用 ffmpeg 把音轨抽成临时单声道 wav(如 `-ac 1 -ar 22050 -f wav`)到 scratch 临时文件, `librosa.load` 读入, `librosa.feature.rms` 算逐帧 RMS, 取 `max` 为 `rms_peak`、`mean` 为 `rms_mean`。用完删临时文件(try/finally)。
- 纯函数、幂等、无副作用(除临时文件)。
- **失败语义**: 片段本身没有音轨(ffmpeg 报无音频流)to 返回 `{}`, 视为正常(该 clip 就是没声音)。只有 ffmpeg/librosa 真正崩溃(损坏文件)才抛异常; 由上层 `_analyze_one` 的 per-clip try 捕获, 不阻塞其他 clip(总体设计 §11.1 规则 2)。
- 值域: 音频样本是 [-1, 1] 浮点, RMS 天然落在 [0, 1] 附近, 无需额外归一化; 打分侧对 `rms_peak` 做线性映射。

---

## 3. `src/score.py`(改签名 + 重平衡)

新签名(pipeline 相应改调用):

```python
def compute_score(raw_meta: dict, transcript: list[dict], audio_features: dict) -> tuple[int, dict]:
```

Phase 3 权重(总分封顶 100, 让音频能量成为真正的区分维度):

| 维度(breakdown 键) | 分值 | 依据 |
|---|---|---|
| `has_speech` | 30 | 有非空转录 to vlog 口播是核心 |
| `audio_energy` | 0 至 30 | 由 `rms_peak` 线性映射(高能瞬间 to 高分) |
| `good_length` | 20 | 时长 ∈ [3, 30]s |
| `has_audio` | 10 | 有音频流 |
| `duration_ok` | 10 | 时长 ≥ 2s |

- `audio_energy` 映射: `round(30 * min(rms_peak / PEAK_REF, 1.0))`, `PEAK_REF` 为一个经验参考峰值常量(实现时定, 初值取一个使日常口播视频落在中高段的值), 写成模块常量便于 Phase 5 调参。
- 沿用 Phase 1 约定: `score_breakdown` 只收录取正值的维度。因此无音频特征(或 `rms_peak` 映射为 0)时, breakdown 里不出现 `audio_energy` 键。
- 效果对齐总体设计 §5.1 示例: 有口播 + 高能的午餐片段 to 约 90; 无口播的通勤环境音 to 约 40; 静音短片 to 约 10 至 20。
- 打分整体失败即报错(总体设计 §11.2: Score 整体失败 to 直接报错), 但单 clip 的 audio 缺失(`{}`)不算失败, 只是能量项为 0。

`ClipMetadata` 新增字段(`src/types.py`):

```python
audio: dict[str, float] = {}   # {"rms_peak": ..., "rms_mean": ...}
```

`score_breakdown` 仍是 `dict[str, int]`, 键改为上表五项(去掉 Phase 1 的 `good_length` 命名沿用即可)。UI 已按 `score_breakdown` 无关键名地渲染分数徽章, 无需改 UI。

---

## 4. `src/cutlist.py`(新增, Claude 剪辑脚本)

单一职责: 把选中的 clips 交给 Claude, 拿回校验过的 `Timeline`。

```python
def generate_cutlist(
    clips: list[ClipMetadata],
    week: str,
    *,
    client=None,                       # 可注入; 缺省 anthropic.Anthropic()
    model: str = "claude-haiku-4-5",
) -> Timeline:
```

### 4.1 输入 to prompt

把每个选中 clip 压成紧凑列表喂给模型: `id`、`duration_sec`、`score`、转录合并文本。系统提示明确任务: 生成一条 1 至 3 分钟竖屏 vlog 的剪辑脚本, 产出钩子文案(hook)、有序片段(每个含 id + 起止 + 一句字幕)、结尾卡(outro)。风格提示对齐总体设计 §2.2(偏生活流水, 中文口语)。

### 4.2 结构化输出

用 Anthropic SDK 的结构化输出把响应约束到一个专用 schema(不直接复用 `Timeline`, 避免定长 tuple 与嵌套卡片在 JSON schema 下的表达问题):

```python
class CutClip(BaseModel):
    id: str
    trim_start: float
    trim_end: float
    subtitle: str

class CutlistResponse(BaseModel):
    hook: str
    clips: list[CutClip]
    outro: str
```

- 用 `claude-haiku-4-5` + 结构化输出(`messages.parse` 配 `CutlistResponse`, 或 `output_config={"format": {"type": "json_schema", "schema": ...}}`)。**确切 SDK 方法在实现时对照 claude-api skill 的 python 参考核定**(该 skill 已确认 Haiku 4.5 支持结构化输出)。
- Haiku 4.5 不支持 adaptive thinking / effort, 不传 `thinking` 参数。输出体量小, 用非流式, `max_tokens` 约 2000。
- JSON schema 不支持 minLength/maxLength/数值上下界, 因此所有边界(字幕长度、trim 范围)在**返回后的代码里**校验, 不靠 schema。

### 4.3 返回后校验(映射为 Timeline)

- 每个返回 clip 的 `id` 必须属于输入集合; 不在集合的丢弃。
- `trim_start`/`trim_end` 夹到 `[0, duration_sec]`, 且保证 `end > start`(非法则丢弃该 clip)。
- `subtitle` 截断到 `MAX_SUBTITLE_LEN`(复用 compose 常量)。
- 若校验后有效 clip 数为 0 to 抛错(而不是产出空片)。
- `estimated_duration_sec` **由我们自己算**(片段时长合计 + hook + outro 时长), 不信模型的算术。
- hook/outro 时长复用 compose 里的 `HOOK_DURATION` / `OUTRO_DURATION` 常量。

### 4.4 失败语义(核心)

- `client=None` 时构造 `anthropic.Anthropic()`(读 `ANTHROPIC_API_KEY`)。无 key to 构造即抛错 to 渲染停止。这就是"质量优先于可用性"。
- 任何 Anthropic 错误(网络、限流、拒答)向上传播, **不退回 `build_simple_timeline`**(总体设计 §11.1 规则 3, 用户复核保留)。
- `client` 参数可注入, 供测试传入假客户端, 测试永不触网。

---

## 5. 接线(pipeline + server)

### 5.1 `pipeline._analyze_one`

在 ASR 之后、compute_score 之前插入 audio 步:

```python
audio_features = {}
try:
    audio_features = analyze_audio(video)
except Exception as e:
    click.echo(f"  audio failed for {clip_id}: {e}", err=True)
cm.audio = audio_features
score, breakdown = compute_score(raw, transcript_segments, audio_features)
```

per-clip try 保证单 clip 音频失败不拖垮整周(总体设计 §11.1 规则 2)。幂等仍成立(json 已存在则跳过)。

### 5.2 渲染路径切换到 Claude

- **`run` 子命令**: 加 `--composer [claude|simple]`(缺省 `claude`)。`claude` to `generate_cutlist`; `simple` to `build_simple_timeline`(显式选择, 不是静默兜底, 供无 key 时跑通链路)。cutlist 抛错 to 异常上抛 to 进程非零退出并打印错误。
- **`server.create_app`**: 增加缝 `compose_fn`(缺省 `generate_cutlist`), `/api/render` 用它。生产默认 Claude; 失败经现有 try 包成 JSON 500 透传到页面(Phase 2 已实现的 `except Exception -> HTTPException(500)` 正好覆盖)。
  ```python
  def create_app(data_root: Path, *, compose_fn=generate_cutlist) -> FastAPI: ...
  ```
  这个缝同时让 server 测试注入确定性 `compose_fn`(见 §6), 保持 server 测试离线。

### 5.3 配置与文档

- `pyproject.toml`: deps += `librosa>=0.10`、`anthropic>=0.40`。
- `config.example.yaml`: `claude_model: "claude-haiku-4-5"`(如该键尚未在模板中则补上, 标注 Phase 3 生效)。
- `README`: 说明渲染默认需 `ANTHROPIC_API_KEY`(或用 `--composer simple` 跑无 Claude 链路); 状态更新为 `Phase 3`。
- `docs/DESIGN.md`: §8 config 的 `claude-sonnet-4-6` 处加一行注记, 指向本 spec 的 `claude-haiku-4-5`(不重写历史文档正文)。
- `docs/going-public-checklist.md`: 已有条目提示扫描 `docs/` 的 em dash 与个人信息, 本次不改; 但注意新增文件不得引入真实 API key 或本机绝对路径。

---

## 6. 测试(TDD, 全部离线)

- **audio**: 复用 `tmp_video_factory`。有 sine 音轨的视频 to `rms_peak > 0`; `has_audio=False` 的无音轨视频 to `analyze_audio` 返回 `{}`。可用 ffmpeg `volume` 滤镜合成大/小音量两段, 断言 `rms_peak` 有序(响的 > 轻的)。
- **score**: 纯函数, 喂合成 `audio_features` 与 transcript, 断言单调性(`rms_peak` 越大分越高或相等)、`has_speech` 主导、总分封顶 100、无音频特征时 `audio_energy` 缺席。
- **cutlist**: 传入一个假 client(小 stub, 暴露被用到的 SDK 方法), 返回一段 schema 合法的 canned 响应。断言: 得到 `Timeline`; id 保留; 非法 id 被丢弃; trim 被夹取; `estimated_duration_sec` 由我方计算; 空结果抛错; **假 client 抛错 to `generate_cutlist` 抛错(验证无兜底)**。
- **server**: 更新现有 render 测试, 注入 `compose_fn=build_simple_timeline`, 保持全绿; 不新引入触网测试。
- 所有测试不依赖真实素材、whisper 模型、真实 Anthropic API。

---

## 7. 非目标(本次不做)

- MediaPipe 人脸检测、`src/face.py`、画面稳定度、人脸黑名单(Phase 5)。
- Claude 失败的任何自动兜底(总体设计 §11.1 规则 3)。
- 流式输出(响应体量小, 不需要)。
- Phase 4: launchd / Task Scheduler 调度、AirDrop / 二维码 handoff、`platform_adapter.py`、setup 脚本。
- 抖音自动上传、BGM 自动化、字幕编辑。

---

## 8. 验收标准

1. `uv run pytest` 全绿, 含新增 audio / score / cutlist 测试与更新后的 server 测试; ruff clean。
2. `analyze_audio` 对有声视频给出正 `rms_peak`, 对无音轨视频返回 `{}`; `ClipMetadata.audio` 落盘。
3. `compute_score` 新签名生效, 高能有口播片段显著高于静音短片。
4. `generate_cutlist` 用假 client 产出校验过的 `Timeline`(id/trim/字幕/时长均由我方约束); 假 client 抛错时它抛错、绝不退回模板。
5. `run --composer claude` 与 server `/api/render` 默认走 Claude; `run --composer simple` 可无 key 跑通; Claude 失败在 CLI 非零退出、在页面显示错误。
6. `pyproject.toml`、`config.example.yaml`、README、DESIGN 注记就位; 无个人信息 / 无硬编码 key。
