# 项目状态快照 (draft)

**日期:** 2026-07-08
**仓库:** haiiibin/vlog-pipeline (私有)。origin/main = `53e10fd`,本地已同步。
**定位:** 个人 Vlog 自动剪辑 pipeline。一周随手拍的手机素材,自动出 1 至 3 分钟竖屏(9:16)vlog 草稿:场景切分、中文 ASR 字幕、打分挑片、Claude 生成剪辑脚本、ffmpeg 渲染,外加本地网页勾选候选池。

## 进度

```
Phase [▓▓▓░░] 3/5
```

- **Phase 1 (MVP 链路)** 完成:probe / scene / asr / score / compose / render / pipeline CLI。10 段素材 5 分钟出一条 mp4,核心可行性验证。
- **Phase 2 (候选池 Web UI)** 完成:FastAPI + 单页原生 HTML,浏览器勾选片段一键出片。
- **Phase 3 (智能打分 + Claude 剪辑脚本)** 完成并推送:
  - 音频能量打分(librosa RMS),人脸/稳定度推迟 Phase 5
  - `claude-haiku-4-5` 结构化输出生成剪辑脚本,返回后自校验
  - Claude 失败即停不兜底(质量优先于可用性)
  - `run --composer claude|simple` + server `/api/render` 默认走 Claude
- **Phase 4 (定时调度 + 跨平台 handoff)** 未开始:下一个独立 spec to plan to build 循环。
- **Phase 5 (可选迭代)** 未开始:人脸/隐私黑名单、BGM、打分调参。

## 代码状态

- 测试:`uv run pytest` = 44 passed / 1 skipped(跳过的是依赖 whisper 的测试);`uv run ruff check .` 干净。
- 栈:Python 3.11+ / uv,click CLI,pydantic v2,FastAPI + uvicorn,ffmpeg/ffprobe,librosa,anthropic SDK,pytest。
- 文档:总体设计 `docs/DESIGN.md`;里程碑 spec 与 plan 在 `docs/specs/`、`docs/plans/`。

## 模块

| 模块 | 职责 |
|---|---|
| `src/probe.py` | ffprobe 元数据 + 3 秒 GIF 预览 |
| `src/scene.py` | PySceneDetect 镜头切分 |
| `src/asr.py` | whisper.cpp 中文转录(可选,未配则跳过) |
| `src/audio.py` | librosa RMS 能量(Phase 3) |
| `src/score.py` | 综合打分(Phase 3 并入音频能量) |
| `src/cutlist.py` | Claude 生成剪辑脚本(Phase 3) |
| `src/compose.py` | 确定性时间线构建器(`--composer simple` 用) |
| `src/render.py` | ffmpeg 9:16 裁剪 + 字幕烧录 + 拼接 |
| `src/server.py` | 候选池 Web UI + API |
| `src/pipeline.py` | CLI 编排(`run` / `serve`) |

## 下一步(按优先级)

1. **真实端到端验证(最实质的缺口):** 至今只用假 Claude client + lavfi 合成视频测过,真 `messages.parse` 调用没真跑过。跑一段真实素材才知道 Haiku 产出的 cut-list(顺序/trim/钩子/字幕)靠不靠谱、prompt 要不要调。这是"设计正确"到"东西好用"的唯一一步。
   - 前置:`ANTHROPIC_API_KEY`(本机未配);whisper.cpp(`WHISPER_BIN`/`WHISPER_MODEL` 未配,不配则真跑没口播字幕)。
2. **Phase 4:** 定时调度(Windows Task Scheduler 先行,Mac launchd 骨架)+ 跨平台 handoff(PC 本地 HTTP + 二维码,Mac AirDrop 骨架)。
3. **Phase 5(可选):** 人脸黑名单/隐私、BGM、打分权重调参。
4. **转公开:** 走 `docs/going-public-checklist.md`(DESIGN.md 正文还有 em dash 待清、全历史扫个人信息),成熟后一条命令转公开进作品集。

## 已知技术债(终审判定可延后,私有单人本地工具)

- audio.py 模块 docstring 未写明"损坏文件抛错"语义。
- `test_score_capped_at_100` 没真正触发 100 封顶(现权重下最大和恰为 100)。
- `_analyze_one` 的 audio 失败守卫路径无测试(与既有 ASR/GIF 守卫同款欠测)。
- cutlist 不去重 Claude 可能返回的重复 id(也可能是有意复用素材)。
- cutlist 的 `trim_start==trim_end` 边界、空 clips 守卫无测试。
- audio.py 与 render.py 各有一个同名 `_has_audio_stream`,语义有意不同(前者抛错、后者返回 False),名字易混。
