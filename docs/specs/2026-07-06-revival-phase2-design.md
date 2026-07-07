# vlog-pipeline 复活 + 搬家 + Phase 2 候选池 UI · 设计文档

**日期**: 2026-07-06
**状态**: 已通过 brainstorming 评审
**上游文档**: `docs/DESIGN.md`(总体设计 v1.0, 2026-05-07)。本文档只覆盖本次里程碑, 与总体设计冲突处以本文档为准。

---

## 0. 背景与已拍板决策

项目于 2026-05 完成 Phase 1(MVP 核心链路: probe / scene / asr / score / compose / render / pipeline CLI, 12 个 commit, 全套 pytest), 之后归档于 `D:\桌面\claude\archive\vlog-pipeline-spec\`。本次重启, 用户已拍板三个决策:

1. **GitHub 定位**: 先私有仓库开发, 保持可公开的卫生标准, 成熟后(Phase 3 效果能看了)一条命令转公开, 进作品集(与 ai-job-hunt-pipeline、claude-multi-agent-investing 同一叙事)。
2. **平台**: 双平台并重(Windows PC + Mac 都要能日常跑)。本次里程碑内所有代码必须跨平台(pathlib、subprocess、webbrowser), 平台专属的调度与素材导入留给 Phase 4。
3. **本次范围**: 搬家 + 环境验证 + Phase 2 候选池 UI。Phase 3(智能打分/Claude API)与 Phase 4(调度/handoff)不做。

---

## 1. 搬家与仓库结构

**动因**: 当前归档位置在 `D:\桌面\claude` 工作区内, 该工作区有铁律绝不配置 git remote(含敏感文件)。要上 GitHub 必须搬出去。用户现有公开仓库均在 `C:\Users\yuhai\github_work\`。

**方式**: 保留历史整仓搬迁(已拍板)。

步骤:

1. 把 `archive/vlog-pipeline-spec/vlog-pipeline-spec/code/` 整个移动到 `C:\Users\yuhai\github_work\vlog-pipeline\`(连 `.git`, 12 个 commit 历史全保留; `.venv/`、`__pycache__/`、`.pytest_cache/`、`.ruff_cache/` 不随迁, 到位后重建)
2. `DESIGN.md` 移入仓库为 `docs/DESIGN.md`, 本文档位于 `docs/specs/`
3. 新增 `config.example.yaml`(配置模板, 占位路径; 真实 `config.yaml` 已在 .gitignore)
4. `gh repo create vlog-pipeline --private --source . --push`
5. 原 archive 位置删除, 留一个 `MOVED.md` 指针(新路径 + GitHub 仓库名 + 搬迁日期), 工作区 git commit。工作区本身保持纯本地不变

现有 `.gitignore` 已覆盖 `data/`、`models/`、`config.yaml`、`.venv/`、缓存目录, 无需大改。

---

## 2. 环境验证门槛(Phase 2 开工前必须全过)

环境搁置两个月, 先证明地基没塌:

1. `uv sync` 重建虚拟环境(含 dev 依赖)
2. 确认外部依赖: `ffmpeg`/`ffprobe` 在 PATH; whisper.cpp 可执行文件与 `models/ggml-*.bin` 模型就位(若缺失, 记录获取方式到 README, 不阻塞纯 pytest)
3. `uv run pytest` 全绿
4. 用测试素材跑一遍 Phase 1 smoke 命令:
   `uv run python -m src.pipeline run --inbox <测试素材目录> --week test --select all`
   产出非零字节 mp4 即为通过

任何一步失败, 先修复再进入 Phase 2 开发。

---

## 3. Phase 2 候选池 UI

遵循总体设计 §5(界面/交互)、§7.2(selected.json 格式)、§11(失败处理)。技术选型: FastAPI + 单页原生 HTML/CSS/JS(内嵌, 无框架, 无 npm), `uvicorn` 跑 `localhost:8765`。

### 3.1 依赖变更

`pyproject.toml` dependencies 增加: `fastapi>=0.110`、`uvicorn>=0.29`。

### 3.2 probe.py: GIF 预览生成

- 每个 clip 生成 3 秒 GIF 预览: 取片段中点前后各 1.5s, ffmpeg 两遍法(palettegen + paletteuse), 缩到宽 240px, 目标单个 <100KB
- 写入 `analyzed/<id>.gif`, 分析 JSON 增加 `preview_gif` 字段(相对路径)
- GIF 生成失败不阻塞分析流程: JSON 中 `preview_gif: null`, UI 显示占位块(总体设计 §11 规则: 单素材失败跳过并记录, 不拖垮整体)

### 3.3 server.py: 新模块

四个端点:

| 端点 | 行为 |
|---|---|
| `GET /` | 返回内嵌的单页 HTML |
| `GET /api/clips?week=<W>` | 读 `data/work/<W>/analyzed/*.json`, 返回 clip 列表 |
| `POST /api/select` | 请求体 = §7.2 的 `selected.json` 结构, 原子写入 `data/work/<W>/selected.json` |
| `POST /api/render` | 同步触发 Compose + Render(读 selected.json), 成功返回成片路径, 失败返回错误详情 |

- GIF 静态文件经 `StaticFiles` 挂载 `data/work/` 只读
- `POST /api/render` 为同步阻塞调用(单用户本地工具, 不做任务队列; 前端按钮置 loading 态), 渲染错误原样透传到页面, 不静默降级
- week 参数缺省 = 当前 ISO 周

### 3.4 UI 行为(单页)

- 按拍摄日分组, 组内按 score 降序
- 每条: 复选框 + GIF(hover 播放, 静态首帧懒加载) + 拍摄时间 + 时长 + 转录文字 + 分数徽章
- 底部粘性状态栏: 已勾选数 / 总数, 勾选片段时长合计, "生成成片"按钮
- 勾选变化即 `POST /api/select`(防抖 500ms), 刷新页面从 selected.json 恢复勾选态
- 不支持字幕编辑(总体设计 §5.2 明确不做)

### 3.5 pipeline.py: serve 子命令

- `uv run python -m src.pipeline serve --week <W>`: 启动 uvicorn 并用标准库 `webbrowser.open` 自动开浏览器(跨平台; 定时自动弹出是 Phase 4 的事)
- 现有 `run` 子命令行为不变

### 3.6 测试(TDD)

- server: FastAPI `TestClient`, 覆盖四个端点的正常路径 + render 失败透传 + selected.json 原子写
- GIF 生成: 复用现有测试 fixtures 视频, 断言文件存在、非零、(若可测)体积上限
- 全部测试不依赖真实素材与 whisper 模型

---

## 4. 开源卫生基线(为转公开铺路)

1. README 重写为英文骨架: 一句话简介 + 架构 ASCII 图 + quick start + 标注 `Status: WIP (Phase 2)`
2. 现在就加 MIT LICENSE
3. `docs/going-public-checklist.md`: 转公开前逐项检查(git log 全量扫个人信息、data/models 确未入库、config.yaml 未泄露、截图/demo 素材脱敏)。规则来源: 用户所有公开内容先扫个人信息
4. git 历史与 commit message 已审阅, 无个人信息, 无需重写历史

---

## 5. 非目标(本次不做)

- 字幕编辑、React/前端框架、任务队列/异步渲染
- Phase 3: librosa/MediaPipe 真打分、Claude API 剪辑脚本
- Phase 4: launchd/Task Scheduler 调度、AirDrop/二维码 handoff、setup 脚本
- 任何抖音自动上传

---

## 6. 验收标准

1. 新仓库 `github_work\vlog-pipeline` 存在, GitHub 私有仓库已推送, git log 包含原 12 个 commit + 本次新 commit
2. 原 archive 位置只剩 `MOVED.md`, 工作区已 commit
3. `uv run pytest` 全绿(含新增 server/GIF 测试)
4. `serve` 起服务后浏览器可见候选池: 分组、GIF、勾选、状态栏正常
5. 勾选若干 clip 点"生成成片", 得到可播放 mp4; 制造一个渲染失败场景, 页面能看到错误信息
6. README(英文)、LICENSE、going-public-checklist 就位
