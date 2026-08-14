# 个人 Vlog 自动剪辑 Pipeline · 设计文档

**版本**：v1.0
**日期**：2026-05-07
**作者**：Allen
**状态**：设计阶段（已通过 brainstorming 评审）
**目标交付**：私人项目，从 iPhone 素材 → 自动剪辑 → 抖音发布

---

## 0. 文档使用说明

这份文档是**完整、自包含的设计 spec**。带回家后只需要：

1. 在个人 Mac 上建一个 GitHub 私有仓库 `vlog-pipeline`
2. 按 [§13. 启动指南](#13-启动指南) 一步步搭环境
3. 按 [§12. 分阶段构建路径](#12-分阶段构建路径) 逐 Phase 实现

每个 Phase 完成后都能产出可看的成果。即使只做到 Phase 1 也已经能用。

---

## 1. 项目目标与非目标

### 1.1 目标

- 把 iPhone 随手拍的生活素材，**每周自动剪辑**出 1-2 条 1-3 分钟的竖屏 vlog
- 用户每周只需花 **5-6 分钟**：勾选候选片段（30秒）+ 在剪映里配 BGM 导出（2分钟）+ 抖音上传写文案（3分钟）
- 整个 pipeline 在 Apple Silicon Mac 上**完全免费**运行（除 Claude API ≈ ¥5/月）
- **可移植**：以 Mac 为主，PC 作为备份/出差备用机

### 1.2 非目标

- ❌ 不追求"做爆款" -- 自动化生活 vlog 在抖音的常态是 200-2000 播放
- ❌ 不追求"完全无人值守发布" -- 抖音上传/BGM 选择仍然手动（避免被判定为批量号）
- ❌ 不替代用户的"灵魂" -- AI 做苦力（剪、字幕、9:16），用户做关键决策（挑片段、写文案、选封面）
- ❌ 不每天发布 -- 频率定为 1-2条/周（拟人化频率）

---

## 2. 真实效果预期（设定预期，避免落差）

### 2.1 能做好（80分以上）
- 粗剪 + 9:16 竖屏裁剪（人脸跟踪）
- 中文 ASR 字幕（whisper-large-v3 在清晰口播下 95%+ 准确率）
- 去废片（黑屏、抖动、太短的片段）
- **批量节省时间**：10个素材 → 5分钟得到能看的成片

### 2.2 凑合（60-75分）
- "精彩瞬间"挑选（算法用音量/人脸做代理指标，会漏掉 30-40% 的真亮点 -- 这就是为什么有"候选池+人工勾选"机制）
- 节奏感（AI 生成的剪辑顺序合理但不够"踩点"，靠剪映"自动卡点"补救）
- 抖音味钩子文案（Claude 写的偏文艺，缺少"我妈第一次……"这种土味）

### 2.3 做不到
- 替代人的情感和叙事意图
- 绕开抖音对"批量 AI 内容"的识别（所以频率必须是 1-2条/周）

---

## 3. 整体架构（高层视图）

```
[周一 ~ 周五] iPhone 随手拍
            ↓ iCloud Photos 自动同步
[每晚 22:00] Mac 后台分析当天新素材
            ├─ Probe（元数据 + GIF 预览）
            ├─ Scene（PySceneDetect 切场景）
            ├─ ASR（whisper.cpp 中文转录）
            ├─ Audio Energy（librosa 找笑声/重音）
            ├─ Face Detect（MediaPipe）
            └─ Score（综合打分）
            → 写入 analyzed/IMG_xxxx.json
            （只分析，不渲染）

[每周六 09:00] launchd 自动启动 FastAPI 服务
              + 浏览器打开 http://localhost:8765
              用户看候选池界面（GIF 预览 + 自动转录文字）
              勾选 6-12 个想要的片段（约30秒）
              点"生成成片"

[勾选后]      Compose（Claude API 生成时间线 + 钩子）
              Render（ffmpeg 9:16 + 字幕烧录）
              Handoff（Mac: AirDrop 推送到 iPhone /
                       PC: 二维码扫码下载）

[周末某时]    iPhone 剪映 → 导入草稿 → 智能配乐 → 导出
              抖音 APP → 上传 + 加话题 + 写文案 + 定位

每周产出 1-2 条精品 vlog
```

---

## 4. 技术栈与模块边界

每个模块只做一件事，输入输出都是文件（JSON 元数据 + 媒体），互相解耦。

| 模块 | 文件 | 职责 | 工具 | 成本 |
|------|------|------|------|------|
| Ingest | `src/ingest.py` | 监控素材目录，发现新文件 | macOS `launchd` + Python `watchdog` | 0 |
| Probe | `src/probe.py` | 提取元数据 + 生成 3秒 GIF 预览 | `ffprobe` + `ffmpeg` | 0 |
| Scene | `src/scene.py` | 镜头切分 | `PySceneDetect` | 0 |
| ASR | `src/asr.py` | 中文语音→文字+时间戳 | `whisper.cpp` (large-v3, CoreML 加速) | 0 |
| Audio | `src/audio.py` | 找笑声/欢呼/重音瞬间 | `librosa` RMS + onset detection | 0 |
| Face | `src/face.py` | 人脸检测 | `MediaPipe` | 0 |
| Score | `src/score.py` | 综合打分 0-100 | 启发式规则（Phase 1 简化版 → Phase 3 真 AI） | 0 |
| Compose | `src/compose.py` | 生成剪辑脚本（顺序 + 字幕文案 + 钩子） | Claude API | <¥5/月 |
| Render | `src/render.py` | 9:16 裁剪 + 字幕烧录 + 拼接 | `ffmpeg` | 0 |
| Server | `src/server.py` | 候选池 Web UI | `FastAPI` + 静态 HTML | 0 |
| Adapter | `src/platform_adapter.py` | 跨平台抽象层（10% 平台相关代码） | 见 §10 | 0 |
| Pipeline | `src/pipeline.py` | 编排所有阶段 | 自己写 | 0 |

**关键原则**：
- 每个模块的输入输出都是 `data/work/<week>/` 下的 JSON + 媒体文件
- 任何一步失败可单独重跑，不需要从头来
- 用户可以肉眼检查任何中间产物
- **业务逻辑层（90% 代码）跨平台**，**平台胶水层（10% 代码）按 Mac/PC 各一份实现**

---

## 5. 候选池 Web UI

### 5.1 界面（每周六弹给用户的页面）

```
┌─────────────────────────────────────────────────────────┐
│  本周 vlog 候选 · 05/02 - 05/08             [生成成片]  │
├─────────────────────────────────────────────────────────┤
│  分组：周一 (3) · 周二 (5) · 周三 (4) · 周末 (8)         │
├─────────────────────────────────────────────────────────┤
│  ☑ [GIF 3秒预览]  早餐 · 周一 8:23 · 5.2s                │
│    转录："今天早上做了一个三明治"                          │
│    打分: 78/100 (人脸✓ 口播✓ 稳定✓)                     │
│                                                           │
│  ☐ [GIF 3秒预览]  通勤 · 周一 9:10 · 8.1s                │
│    转录：（无口播，环境音）                                │
│    打分: 42/100                                           │
│                                                           │
│  ☑ [GIF 3秒预览]  午餐 · 周三 12:40 · 6.5s               │
│    转录："这家店的牛肉面太顶了"                            │
│    打分: 91/100 (笑声✓ 人脸✓ 口播✓ 高能音✓)              │
│  ...                                                      │
├─────────────────────────────────────────────────────────┤
│  已勾选: 8 / 30  · 预估总时长: 1分42秒  [生成成片 →]      │
└─────────────────────────────────────────────────────────┘
```

### 5.2 交互规则

- 候选池 UI **不支持字幕编辑**（简化 MVP，AI 字幕直接用）
- GIF 预览每个 <100KB，秒加载
- 勾选状态写入 `selected.json`，点"生成成片"才触发 Compose + Render
- 默认按时间分组，按打分降序

### 5.3 技术实现

- `FastAPI` + 静态 HTML/CSS/JS（不用 React，<200 行代码）
- 跑在 `localhost:8765`
- 浏览器 → `GET /` → 列出本周 `analyzed/` 下所有 clip
- 用户勾选 → `POST /select` → 写 `selected.json`
- 点击"生成成片" → `POST /render` → 触发 Compose + Render

---

## 6. 目录结构

```
~/vlog-pipeline/                         ← 项目根
│
├── code/                                ← 代码区（GitHub 同步的就是这部分）
│   ├── pyproject.toml                   ← uv/pip 依赖清单
│   ├── README.md
│   ├── setup_mac.sh                     ← Mac 一键装环境
│   ├── setup_pc.ps1                     ← PC 一键装环境
│   ├── config.example.yaml              ← 配置模板
│   ├── .gitignore                       ← 忽略 data/, models/, config.yaml
│   └── src/
│       ├── ingest.py
│       ├── probe.py
│       ├── scene.py
│       ├── asr.py
│       ├── audio.py
│       ├── face.py
│       ├── score.py
│       ├── compose.py
│       ├── render.py
│       ├── handoff_mac.py
│       ├── handoff_pc.py
│       ├── server.py
│       ├── platform_adapter.py
│       └── pipeline.py
│
├── data/                                ← 数据区（每台机器各自生成，不进 git）
│   ├── inbox/                           ← 平台适配器把素材放这里
│   │   └── 2026-05-02_IMG_1234.MOV
│   ├── work/                            ← 中间产物，按周分目录
│   │   └── 2026-W18/
│   │       ├── analyzed/
│   │       │   ├── IMG_1234.json        ← clip 元数据 + ASR + 评分
│   │       │   └── IMG_1234.gif         ← 3秒 GIF 预览
│   │       ├── selected.json            ← 用户勾选的 subset
│   │       ├── timeline.json            ← Claude 生成的剪辑脚本
│   │       └── draft.mp4                ← 渲染好的半成品（无 BGM）
│   ├── output/
│   │   └── 2026-W18_vlog.mp4
│   └── logs/
│       ├── pipeline.log
│       └── failed.json                  ← 失败 clip 的错误记录
│
└── models/                              ← 大模型（不进 git，setup 脚本下载）
    └── ggml-large-v3.bin                ← whisper.cpp 中文模型，约 3GB
```

---

## 7. 数据格式

### 7.1 `analyzed/IMG_1234.json` -- 单个素材片段的分析结果

```json
{
  "id": "IMG_1234",
  "path": "data/inbox/2026-05-02_IMG_1234.MOV",
  "captured_at": "2026-05-02T08:23:14",
  "duration_sec": 5.2,
  "resolution": [1920, 1080],
  "orientation": "portrait",
  "scenes": [
    {"start": 0.0, "end": 5.2, "type": "single"}
  ],
  "transcript": [
    {"start": 0.5, "end": 2.1, "text": "今天早上"},
    {"start": 2.1, "end": 4.8, "text": "做了一个三明治"}
  ],
  "audio": {
    "rms_peak": 0.42,
    "has_speech": true,
    "has_laughter": false
  },
  "face": {
    "present": true,
    "frames_with_face_pct": 87
  },
  "stability": 0.91,
  "score": 78,
  "score_breakdown": {
    "speech": 25,
    "face": 20,
    "stability": 18,
    "audio_energy": 15
  },
  "preview_gif": "data/work/2026-W18/analyzed/IMG_1234.gif"
}
```

### 7.2 `selected.json` -- 用户从 UI 勾选的结果

```json
{
  "week": "2026-W18",
  "selected_at": "2026-05-09T09:14:23",
  "clip_ids": ["IMG_1234", "IMG_1287", "IMG_1301", "IMG_1342"]
}
```

### 7.3 `timeline.json` -- Claude 生成的剪辑脚本（Render 的输入）

```json
{
  "week": "2026-W18",
  "hook": {"text": "这周吃了三家好店 🍜", "duration": 2.5},
  "clips": [
    {
      "id": "IMG_1234",
      "trim": [0.5, 4.8],
      "subtitle": "早八做的爱心三明治",
      "transition": "cut"
    },
    {
      "id": "IMG_1287",
      "trim": [1.0, 6.5],
      "subtitle": "牛肉面这家店真的太顶",
      "transition": "cut"
    }
  ],
  "outro": {"text": "下周见 👋", "duration": 1.5},
  "estimated_duration_sec": 98
}
```

---

## 8. 配置文件 `config.yaml`

```yaml
# 平台标识 - mac 或 pc
platform: "mac"

# 素材源（不同平台不同路径）
inbox_source:
  mac: "~/Pictures/Photos Library.photoslibrary/originals"   # iCloud 相册
  pc: "C:/Users/me/vlog-inbox"                                # 手动放素材的目录

# 成片输出方式
output_target:
  mac: "airdrop"
  pc: "qr_to_phone"   # PC 上输出二维码扫到手机

# 调度
weekly_trigger: "SAT 09:00"
nightly_trigger: "22:00"

# Claude API
claude_api_key_env: "ANTHROPIC_API_KEY"
claude_model: "claude-sonnet-4-6"
# NOTE(Phase 3, 2026-07-07): 实际使用 claude-haiku-4-5, 见 docs/specs/2026-07-07-phase3-smart-scoring-design.md

# Whisper
whisper_model: "ggml-large-v3"
whisper_language: "zh"

# 成片参数
target_duration_sec: [60, 180]
target_aspect: "9:16"

# 字幕样式
subtitle:
  font: "PingFang SC Bold"   # PC 上回退到 "Microsoft YaHei UI"
  size: 56
  color: "#FFFFFF"
  outline_color: "#000000"
  outline_width: 4
  position: "bottom"   # 距底部 15% 高度
```

---

## 9. 调度

### 9.1 Mac 端（`launchd`）

`~/Library/LaunchAgents/` 下两个 plist：

- `com.vlog.daily-analyze.plist` -- 每晚 22:00 跑分析（不渲染）
- `com.vlog.weekly-review.plist` -- 每周六 09:00 弹候选池 UI

### 9.2 PC 端（Windows Task Scheduler）

`setup_pc.ps1` 注册等价的两个任务：

- `VlogPipeline-DailyAnalyze` -- Daily 22:00
- `VlogPipeline-WeeklyReview` -- Weekly Saturday 09:00

---

## 10. 跨平台适配层

### 10.1 接口定义 `src/platform_adapter.py`

```python
class PlatformAdapter:
    def discover_new_videos(self) -> list[Path]: ...
    def schedule_task(self, name: str, cron: str) -> None: ...
    def handoff_to_phone(self, mp4_path: Path) -> None: ...
    def open_browser(self, url: str) -> None: ...
```

### 10.2 Mac 实现 `src/handoff_mac.py`

| 方法 | 实现 |
|------|------|
| `discover_new_videos` | 扫 `~/Pictures/Photos Library.photoslibrary/originals` |
| `schedule_task` | 写 `~/Library/LaunchAgents/*.plist` |
| `handoff_to_phone` | 调用 `osascript` 触发 AirDrop |
| `open_browser` | `subprocess.run(["open", url])` |

### 10.3 PC 实现 `src/handoff_pc.py`

| 方法 | 实现 |
|------|------|
| `discover_new_videos` | 扫 `C:/Users/me/vlog-inbox`（手动从 iPhone 拷过来） |
| `schedule_task` | PowerShell `Register-ScheduledTask` |
| `handoff_to_phone` | 起临时 HTTP 服务器 + 生成二维码（用 `qrcode` 库），手机扫码下载 mp4 |
| `open_browser` | `subprocess.run(["start", url], shell=True)` |

---

## 11. 失败处理

### 11.1 三条规则

1. **每一步幂等**：`IMG_1234.json` 已存在就跳过，不重新分析
2. **失败不阻塞其他 clip**：单个 clip 损坏不影响整周
3. **质量优先于可用性**（用户决策）：Claude API 调用失败 → 整个 pipeline 停下来报错，**不**用启发式兜底

### 11.2 各阶段错误处理

| 阶段 | 失败行为 |
|------|---------|
| Probe | 单个 clip 失败 → 记 `failed.json`，跳过 |
| ASR | 单个 clip 失败 → 字幕留空，clip 仍可用 |
| Score | 整体失败 → 直接报错 |
| Compose（Claude）| **失败 → pipeline 停止**，不兜底（按用户选择） |
| Render | 失败 → 报错，保留中间产物 |

### 11.3 用户兜底入口

候选池 UI 上有"导出原始素材"按钮：把勾选的 clip 打包成 zip，AirDrop/二维码给手机，用剪映自己剪。

---

## 12. 分阶段构建路径

每个 Phase 都能产出可看的成果。失败可止损，成功就有用。

### Phase 0：环境准备（半天）

- [ ] Mac 装：`uv` + `ffmpeg` (brew) + `whisper.cpp` (CoreML)
- [ ] PC 装：`uv` + `ffmpeg` (scoop/choco) + `whisper.cpp` (CPU 或 CUDA)
- [ ] 建 GitHub 私有仓库 `vlog-pipeline`
- [ ] 配 `ANTHROPIC_API_KEY` 环境变量

**产出**：`python -c "import whisper_cpp"` 不报错

### Phase 1：手动模式跑通（2-3天）⭐ MVP 里程碑

```bash
python -m src.pipeline run \
  --inbox ~/test-clips/ \
  --week 2026-W18 \
  --select all
```

- [ ] `probe.py` `scene.py` `asr.py`
- [ ] `score.py` 简化版（时长>2s + 有声音 + 有人脸 = 加分）
- [ ] `compose.py` 简化版（按时间排，钩子用固定模板，不调 Claude）
- [ ] `render.py` ffmpeg 9:16 + 字幕烧录

**产出**：10个测试 clip → 5分钟出一条 1-2分钟 mp4。**核心可行性已验证**。

### Phase 2：候选池 UI（1-2天）

- [ ] `probe.py` 增加 GIF 预览生成
- [ ] `server.py` FastAPI + HTML
- [ ] 勾选写 `selected.json`，pipeline 读它
- [ ] "生成成片"按钮触发 Compose + Render

**产出**：浏览器勾选片段 → 一键出片

### Phase 3：智能化升级（2天）

- [ ] `score.py` 接入 librosa + MediaPipe 真打分
- [ ] `compose.py` 调用 Claude API 生成钩子+字幕+顺序
- [ ] Claude 失败 → 停止报错（按 §11 规则）

**产出**：成片质量从"凑合"升到"能看"

### Phase 4：自动化与可移植（1-2天）

- [ ] `platform_adapter.py` 接口
- [ ] Mac adapter：launchd + AirDrop
- [ ] PC adapter：Task Scheduler + 二维码
- [ ] `setup_mac.sh` / `setup_pc.ps1` 一键装环境

**产出**：每周六 9 点自动弹候选池，勾完一键出片，扫码到手机

### Phase 5（可选）：迭代优化

跑 4-6 周后根据实际效果调：

- 调打分权重（漏掉某类瞬间 → 加 feature）
- 调字幕样式（颜色/字体/位置）
- 调钩子风格（让 Claude 学用户常用模板）
- **隐私模块**（人脸黑名单：把家人/同事照片放进 `data/face_blacklist/`，pipeline 自动跳过含这些人脸的 clip）

### 推荐节奏

```
本周末    : Phase 0  (装环境)
下周末    : Phase 1  (手动跑通) ← 跑通这步就值了
再下周    : Phase 2  (候选池 UI)
五一节    : Phase 3 + 4 (智能 + 自动化)
```

---

## 13. 启动指南

### 13.1 Mac 第一次设置

```bash
# 1. 安装基础工具
brew install uv ffmpeg
brew install --cask iterm2  # 可选

# 2. 编译 whisper.cpp（CoreML 加速版）
git clone https://github.com/ggerganov/whisper.cpp ~/whisper.cpp
cd ~/whisper.cpp
WHISPER_COREML=1 make -j

# 3. 克隆项目
git clone git@github.com:<你的用户名>/vlog-pipeline.git ~/vlog-pipeline
cd ~/vlog-pipeline

# 4. 一键装环境
./setup_mac.sh
# 这个脚本会：
#   - uv sync 装 Python 依赖
#   - 下载 whisper large-v3 模型到 ~/vlog-pipeline/models/
#   - 复制 config.example.yaml → config.yaml
#   - 注册 launchd 定时任务

# 5. 配 Claude API key
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshrc
source ~/.zshrc

# 6. 测试 Phase 1
python -m src.pipeline run --inbox ~/test-clips/ --week test --select all
```

### 13.2 PC 第一次设置

```powershell
# 1. 安装基础工具（用 scoop）
iex "& {$(irm get.scoop.sh)} -RunAsAdmin"
scoop install python ffmpeg git

# 2. 装 uv
irm https://astral.sh/uv/install.ps1 | iex

# 3. 下载 whisper.cpp Windows release
# 从 https://github.com/ggerganov/whisper.cpp/releases 下载 whisper-bin-x64.zip
# 解压到 C:\whisper.cpp

# 4. 克隆项目
git clone git@github.com:<你的用户名>/vlog-pipeline.git C:\vlog-pipeline
cd C:\vlog-pipeline

# 5. 一键装环境
.\setup_pc.ps1
# 这个脚本会：
#   - uv sync 装 Python 依赖
#   - 下载 whisper large-v3 模型
#   - 复制 config.example.yaml → config.yaml（platform: pc）
#   - 注册 Task Scheduler 任务

# 6. 配 Claude API key
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")

# 7. 测试 Phase 1
uv run python -m src.pipeline run --inbox C:\test-clips --week test --select all
```

### 13.3 PC 端的素材导入

PC 没有 iCloud 自动同步 → 三个选项：

1. **iCloud for Windows**（官方）：装客户端，启用"照片"同步，素材会出现在 `C:\Users\me\Pictures\iCloud Photos\`
2. **数据线 + Win11 "手机连接"**：手动选当天的 mov 文件复制
3. **微信传到自己**：发到"文件传输助手"，PC 端微信下载

`config.yaml` 里 `inbox_source.pc` 指向上面任意一个目录即可。

---

## 14. 同步策略

| 内容 | 同步方式 | 说明 |
|------|---------|------|
| 代码 | GitHub 私有仓库 | `git push` (Mac) → `git pull` (PC) |
| 配置 `config.yaml` | **不同步** | 每台机器独立 (在 `.gitignore`) |
| 素材 `data/inbox/` | **不同步** | iCloud 在 Mac 端已搞定；PC 手动 |
| 中间产物 `data/work/` | **不同步** | 本地缓存，重生成 |
| 模型 `models/*.bin` | **不进 git** (3GB) | `setup_*.sh` 自动下载 |

---

## 15. 抖音发布工作流（人工部分）

成片传到 iPhone 后：

1. 打开**剪映 APP** → 导入草稿（或从相册选 mp4）
2. 点"音频" → "音乐" → 选抖音热门 BGM（用剪映曲库 = 抖音正版授权 = 不会版权下架）
3. 点"自动卡点"（如果素材节奏需要）
4. 点导出 → 1080P + 60fps
5. 打开**抖音 APP** → 上传
6. 写文案（短钩子 + 1-3 个 emoji）
7. 加 2-3 个话题（#vlog #生活记录 #早餐之类）
8. 加定位（让本地流量池能命中）
9. 选封面（关键！选有人脸有表情的帧）
10. 发布

---

## 16. 待决策问题（推迟到 Phase 5）

### 16.1 隐私 / 人脸保护

**默认推荐方案**（写进 Phase 5 的简化版）：

- 用户在 `data/face_blacklist/` 放 1-3 张需要保护的人脸照片
- pipeline 用 MediaPipe 提取黑名单人脸 embedding
- 每个 clip 抽 3 帧检测 → 命中黑名单的 clip 自动 score 降低 50 分（不是删除，因为有时用户想发）
- 候选池 UI 上对这类 clip 标红色 "⚠️ 含黑名单人脸"，用户自己决定要不要勾

**待用户决定**：

- 是改成"自动跳过"还是"打码后保留"？
- 黑名单是单一全局还是每周可配置？

### 16.2 BGM 自动化

剪映的 API 不开放。可以的话：

- 维护本地"已下载抖音热门 BGM"库，通过音频指纹匹配场景情绪
- 但仍然需要手动在剪映里替换为正版授权版本（免版权风险）
- **当前决策**：保持 Phase 4 流程，不自动配乐

---

## 17. 变更日志

- **2026-05-07** -- v1.0 初版（Allen + Claude 协作 brainstorming）

---

## 附录 A：核心依赖（pyproject.toml 关键内容）

```toml
[project]
name = "vlog-pipeline"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "fastapi>=0.110",
    "uvicorn>=0.27",
    "pyyaml>=6.0",
    "pydantic>=2.0",
    "watchdog>=4.0",
    "scenedetect[opencv]>=0.6",
    "librosa>=0.10",
    "mediapipe>=0.10",
    "anthropic>=0.40",
    "qrcode[pil]>=7.4",
    "pillow>=10.0",
    "ffmpeg-python>=0.2",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.5"]
```

注：`whisper.cpp` 通过命令行调用，不作为 Python 依赖。

## 附录 B：参考链接（实施时再查）

- whisper.cpp：https://github.com/ggerganov/whisper.cpp
- PySceneDetect：https://www.scenedetect.com/
- MediaPipe FaceDetection：https://developers.google.com/mediapipe/solutions/vision/face_detector
- launchd 教程：https://www.launchd.info/
- Anthropic Python SDK：https://github.com/anthropics/anthropic-sdk-python

---

**文档结束**
