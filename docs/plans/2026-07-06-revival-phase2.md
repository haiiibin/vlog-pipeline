# vlog-pipeline 复活 + 搬家 + Phase 2 候选池 UI · 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把项目从归档区迁到 `C:\Users\yuhai\github_work\vlog-pipeline`(保留 git 历史 + GitHub 私有仓库), 验证 Phase 1 环境仍可用, 然后实现 Phase 2 候选池 Web UI(FastAPI 四端点 + 单页原生 HTML + `serve` 子命令)。

**Architecture:** 现有 Phase 1 是 click CLI 串起 probe/scene/asr/score/compose/render 六个纯函数模块, 数据经 `data/work/<week>/analyzed/*.json` 流转。Phase 2 在其上加一层 `src/server.py`(FastAPI app 工厂, 注入 `data_root`), 复用 compose/render 函数做同步渲染; UI 是一个静态单页 `src/static/index.html`。

**Tech Stack:** Python 3.11+, uv, click, pydantic v2, FastAPI + uvicorn, ffmpeg/ffprobe(子进程), pytest + httpx TestClient, ruff。

**Spec:** `docs/specs/2026-07-06-revival-phase2-design.md`

## Global Constraints

- 仓库最终位置 `C:\Users\yuhai\github_work\vlog-pipeline`, GitHub 私有仓库 `haiiibin/vlog-pipeline`; Task 1 之后所有命令的 cwd 都是该目录
- 跨平台: 只用 `pathlib` / `subprocess` / `webbrowser` / `threading`, 不写平台分支(render.py 里已有的 Windows 字体分支除外, 不动它)
- `data/`、`models/`、`config.yaml`、`.venv/` 永不入 git(现有 .gitignore 已覆盖, 不得删改这些行)
- 依赖只加: `fastapi>=0.110`、`uvicorn>=0.29`(运行时), `httpx>=0.27`(dev, TestClient 需要); 不引入其他新依赖, 不用前端框架/npm
- 测试不得依赖 whisper 模型; 需要视频时用 conftest 的 `tmp_video_factory`(ffmpeg lavfi 合成)
- commit message 沿用仓库惯例(`feat:` / `fix:` / `docs:` / `test:` / `chore:` 前缀), 结尾加 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- ruff: line-length 100, target py311(pyproject 已配)
- 所有新文档禁用 em dash(—)

## 对 spec 的三处已确认偏差

1. **GIF 预览已在 Phase 1 实现**(`probe.generate_gif_preview`, 单遍 fps=10/scale=240, 已接入 `pipeline._analyze_one`, 失败时 `preview_gif=null` 不阻塞)。spec §3.2 的"两遍法 palettegen"不做, 现有单遍产物够小(120px/2s 测试断言 <200KB), YAGNI。
2. spec §3.4 "hover 播放, 静态首帧懒加载"简化为 `<img loading="lazy">` 的自动播放 GIF(每个 <100KB 量级, 无性能问题)。
3. `GET /api/clips` 响应带 `selected_ids` 字段(读 selected.json), 用于刷新后恢复勾选态; 端点总数仍为四个。

---

### Task 1: 整仓搬迁 + GitHub 私有仓库 + 原位指针

**Files:**
- Move: `D:\桌面\claude\archive\vlog-pipeline-spec\vlog-pipeline-spec\code\` → `C:\Users\yuhai\github_work\vlog-pipeline\`
- Move: `D:\桌面\claude\archive\vlog-pipeline-spec\vlog-pipeline-spec\DESIGN.md` → `C:\Users\yuhai\github_work\vlog-pipeline\docs\DESIGN.md`
- Create: `D:\桌面\claude\archive\vlog-pipeline-spec\MOVED.md`
- Modify: `D:\桌面\claude\.gitignore`(删除第 7 行 `archive/vlog-pipeline-spec/`)

**Interfaces:**
- Produces: 后续所有任务的仓库根 `C:\Users\yuhai\github_work\vlog-pipeline`; GitHub remote `origin` = `haiiibin/vlog-pipeline`(私有)

- [ ] **Step 1: 移动仓库并清理不随迁产物**(PowerShell)

```powershell
Move-Item "D:\桌面\claude\archive\vlog-pipeline-spec\vlog-pipeline-spec\code" "C:\Users\yuhai\github_work\vlog-pipeline"
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue `
  "C:\Users\yuhai\github_work\vlog-pipeline\.venv", `
  "C:\Users\yuhai\github_work\vlog-pipeline\.pytest_cache", `
  "C:\Users\yuhai\github_work\vlog-pipeline\.ruff_cache", `
  "C:\Users\yuhai\github_work\vlog-pipeline\src\__pycache__", `
  "C:\Users\yuhai\github_work\vlog-pipeline\tests\__pycache__"
```

- [ ] **Step 2: 验证 git 历史完好**

Run: `git -C "C:\Users\yuhai\github_work\vlog-pipeline" log --oneline | Measure-Object -Line`
Expected: 14 行(Phase 1 的 12 个 commit + spec commit + 本计划 commit), `git status` 完全干净

- [ ] **Step 3: DESIGN.md 入仓**

```powershell
Move-Item "D:\桌面\claude\archive\vlog-pipeline-spec\vlog-pipeline-spec\DESIGN.md" "C:\Users\yuhai\github_work\vlog-pipeline\docs\DESIGN.md"
```

- [ ] **Step 4: commit 设计文档**

```bash
cd "C:/Users/yuhai/github_work/vlog-pipeline"
git add docs/DESIGN.md
git commit -m "docs: import overall design doc v1.0

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 5: 建 GitHub 私有仓库并推送**

```bash
cd "C:/Users/yuhai/github_work/vlog-pipeline"
gh repo create vlog-pipeline --private --source . --push
gh repo view haiiibin/vlog-pipeline --json visibility,defaultBranchRef
```

Expected: `"visibility": "PRIVATE"`, 默认分支 `main`

- [ ] **Step 6: 原位置删除 + 指针文件**

```powershell
Remove-Item -Recurse -Force "D:\桌面\claude\archive\vlog-pipeline-spec"
New-Item -ItemType Directory "D:\桌面\claude\archive\vlog-pipeline-spec"
```

创建 `D:\桌面\claude\archive\vlog-pipeline-spec\MOVED.md`:

```markdown
# 项目已搬迁

vlog-pipeline(个人 vlog 自动剪辑 pipeline)已于 2026-07-06 搬迁:

- 本地: C:\Users\yuhai\github_work\vlog-pipeline
- GitHub: https://github.com/haiiibin/vlog-pipeline (私有, 成熟后转公开)

原因: 本工作区是纯本地仓库(绝不配置远程), 该项目需要 GitHub 备份并计划进作品集。
git 历史(Phase 1 全部 commit)完整保留在新仓库中。
```

- [ ] **Step 7: 外层工作区 .gitignore 清理并 commit**

编辑 `D:\桌面\claude\.gitignore`, 删除整行 `archive/vlog-pipeline-spec/`。然后:

```bash
cd "/d/桌面/claude"
git add .gitignore archive/vlog-pipeline-spec/MOVED.md
git commit -m "archive: vlog-pipeline 搬迁至 github_work(GitHub 私有仓库), 原位留 MOVED.md 指针

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

注意: 只 add 这两个路径, 不要 `git add -A`(工作区有无关的 finance 改动和 cofco 截图, 不属于本次)。

---

### Task 2: 环境验证门槛(全过才能进 Task 3)

**Files:** 无新增/修改(纯验证; 若有修复, 修什么 commit 什么)

**Interfaces:**
- Produces: 可工作的 `.venv`, 全绿的 pytest 基线, 确认 ffmpeg 可用

- [ ] **Step 1: 重建虚拟环境**

Run: `cd "C:\Users\yuhai\github_work\vlog-pipeline" && uv sync --extra dev`
Expected: 解析并安装成功, 退出码 0

- [ ] **Step 2: 确认外部工具**

Run: `ffmpeg -version && ffprobe -version`
Expected: 两者都打印版本号。若缺失: `scoop install ffmpeg` 或 `choco install ffmpeg`, 装好重跑。

- [ ] **Step 3: 全量 pytest**

Run: `uv run pytest -q`
Expected: 全部通过(Phase 1 基线约 25 个测试), 无 fail/error。若有失败: 先按 superpowers:systematic-debugging 修复并单独 commit(`fix: ...`), 修完重跑, 全绿才继续。

- [ ] **Step 4: Phase 1 smoke(真实 CLI 出片)**

```powershell
cd "C:\Users\yuhai\github_work\vlog-pipeline"
New-Item -ItemType Directory -Force data\smoke-inbox
ffmpeg -y -loglevel error -f lavfi -i "color=c=red:s=1920x1080:d=4:r=30" -f lavfi -i "sine=frequency=440:duration=4" -c:v libx264 -preset ultrafast -pix_fmt yuv420p -c:a aac -shortest data\smoke-inbox\AAA.mp4
ffmpeg -y -loglevel error -f lavfi -i "color=c=green:s=1080x1920:d=3:r=30" -f lavfi -i "sine=frequency=880:duration=3" -c:v libx264 -preset ultrafast -pix_fmt yuv420p -c:a aac -shortest data\smoke-inbox\BBB.mp4
uv run python -m src.pipeline run --inbox data\smoke-inbox --week smoke --select all --language en
```

Expected: 输出 `Done: data\output\smoke_vlog.mp4`, 文件存在且 >100KB; `data\work\smoke\analyzed\` 下有 `AAA.json`/`AAA.gif`/`BBB.json`/`BBB.gif`(GIF 已由 Phase 1 代码生成, 顺带验证偏差 1)

- [ ] **Step 5: 记录 whisper 状态(不阻塞)**

Run: `echo $env:WHISPER_BIN; echo $env:WHISPER_MODEL`
若为空: ASR 会被跳过(pipeline 已优雅处理), 在 Task 7 的 README 里写清配置方法即可, 不在此安装。

---

### Task 3: server.py 只读与选择端点(/api/clips + /api/select)

**Files:**
- Modify: `pyproject.toml`(dependencies + dev)
- Create: `src/server.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `src.types.ClipMetadata`(现有, 字段见 src/types.py:12-24)
- Produces:
  - `create_app(data_root: Path) -> FastAPI`(app 工厂, 后续任务往里加端点)
  - `default_week() -> str`(格式 `YYYY-Wnn`, Task 6 复用)
  - `GET /api/clips?week=` → `{"week": str, "clips": [ClipMetadata dict + "gif_url": str|null], "selected_ids": [str]}`
  - `POST /api/select` body `{"week": str, "clip_ids": [str]}` → `{"ok": true, "count": int}`; 原子写 `data/work/<week>/selected.json`(结构含服务端时间戳 `selected_at`)
  - 静态挂载 `/media` → `data/work/`

- [ ] **Step 1: pyproject.toml 加依赖**

```toml
dependencies = [
    "click>=8.1",
    "pyyaml>=6.0",
    "pydantic>=2.5",
    "scenedetect[opencv]>=0.6.4",
    "fastapi>=0.110",
    "uvicorn>=0.29",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.5",
    "httpx>=0.27",
]
```

Run: `uv sync --extra dev`
Expected: fastapi/uvicorn/httpx 安装成功

- [ ] **Step 2: 写失败测试**

`tests/test_server.py`:

```python
"""Candidate-pool server API tests. No whisper, no real videos except where noted."""
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from src.server import create_app, default_week
from src.types import ClipMetadata


def _write_meta(analyzed: Path, clip_id: str, score: int = 50,
                path: str = "x.mp4", captured_at: str = "2026-07-01T08:00:00"):
    analyzed.mkdir(parents=True, exist_ok=True)
    cm = ClipMetadata(
        id=clip_id, path=path, captured_at=captured_at,
        duration_sec=4.0, resolution=[1920, 1080], orientation="landscape",
        score=score,
    )
    (analyzed / f"{clip_id}.json").write_text(cm.model_dump_json(indent=2), encoding="utf-8")


def test_default_week_format():
    assert re.fullmatch(r"\d{4}-W\d{2}", default_week())


def test_clips_empty_week(tmp_path):
    client = TestClient(create_app(tmp_path / "data"))
    r = client.get("/api/clips", params={"week": "2026-W99"})
    assert r.status_code == 200
    body = r.json()
    assert body["week"] == "2026-W99"
    assert body["clips"] == []
    assert body["selected_ids"] == []


def test_clips_lists_metadata_and_gif_url(tmp_path):
    data = tmp_path / "data"
    analyzed = data / "work" / "w1" / "analyzed"
    _write_meta(analyzed, "AAA", score=80)
    _write_meta(analyzed, "BBB", score=30)
    (analyzed / "AAA.gif").write_bytes(b"GIF89a")

    client = TestClient(create_app(data))
    body = client.get("/api/clips", params={"week": "w1"}).json()
    ids = {c["id"]: c for c in body["clips"]}
    assert set(ids) == {"AAA", "BBB"}
    assert ids["AAA"]["gif_url"] == "/media/w1/analyzed/AAA.gif"
    assert ids["BBB"]["gif_url"] is None
    # mounted static file is actually servable
    assert client.get("/media/w1/analyzed/AAA.gif").status_code == 200


def test_select_roundtrip_and_overwrite(tmp_path):
    data = tmp_path / "data"
    client = TestClient(create_app(data))

    r = client.post("/api/select", json={"week": "w1", "clip_ids": ["AAA", "BBB"]})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "count": 2}

    saved = json.loads((data / "work" / "w1" / "selected.json").read_text(encoding="utf-8"))
    assert saved["week"] == "w1"
    assert saved["clip_ids"] == ["AAA", "BBB"]
    assert "selected_at" in saved

    client.post("/api/select", json={"week": "w1", "clip_ids": ["AAA"]})
    saved2 = json.loads((data / "work" / "w1" / "selected.json").read_text(encoding="utf-8"))
    assert saved2["clip_ids"] == ["AAA"]

    body = client.get("/api/clips", params={"week": "w1"}).json()
    assert body["selected_ids"] == ["AAA"]
```

- [ ] **Step 3: 跑测试确认失败**

Run: `uv run pytest tests/test_server.py -v`
Expected: 收集时即 `ModuleNotFoundError: No module named 'src.server'`

- [ ] **Step 4: 最小实现**

`src/server.py`:

```python
"""FastAPI candidate-pool server (Phase 2). App factory closes over data_root."""
import json
import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.types import ClipMetadata

INDEX_HTML_PATH = Path(__file__).parent / "static" / "index.html"


class Selection(BaseModel):
    week: str
    clip_ids: list[str]


def default_week() -> str:
    iso = datetime.now().isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def create_app(data_root: Path) -> FastAPI:
    app = FastAPI(title="vlog-pipeline candidate pool")
    work_root = data_root / "work"
    work_root.mkdir(parents=True, exist_ok=True)

    def _analyzed_dir(week: str) -> Path:
        return work_root / week / "analyzed"

    def _selected_path(week: str) -> Path:
        return work_root / week / "selected.json"

    @app.get("/api/clips")
    def list_clips(week: str | None = None):
        wk = week or default_week()
        adir = _analyzed_dir(wk)
        clips: list[dict] = []
        if adir.is_dir():
            for jf in sorted(adir.glob("*.json")):
                cm = ClipMetadata.model_validate_json(jf.read_text(encoding="utf-8"))
                d = cm.model_dump()
                gif = adir / f"{cm.id}.gif"
                d["gif_url"] = f"/media/{wk}/analyzed/{cm.id}.gif" if gif.exists() else None
                clips.append(d)
        selected_ids: list[str] = []
        sp = _selected_path(wk)
        if sp.exists():
            selected_ids = json.loads(sp.read_text(encoding="utf-8")).get("clip_ids", [])
        return {"week": wk, "clips": clips, "selected_ids": selected_ids}

    @app.post("/api/select")
    def save_selection(sel: Selection):
        (work_root / sel.week).mkdir(parents=True, exist_ok=True)
        payload = {
            "week": sel.week,
            "selected_at": datetime.now().isoformat(timespec="seconds"),
            "clip_ids": sel.clip_ids,
        }
        target = _selected_path(sel.week)
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, target)
        return {"ok": True, "count": len(sel.clip_ids)}

    app.mount("/media", StaticFiles(directory=work_root), name="media")
    return app
```

注意: `selected.json` 里的 `analyzed/*.json` 之外的文件不能被 `list_clips` 误读; `glob("*.json")` 只扫 `analyzed/` 子目录, selected.json 在上一级, 天然隔离。

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_server.py -v`
Expected: 4 个测试全 PASS

- [ ] **Step 6: 全量回归 + commit**

```bash
uv run pytest -q && uv run ruff check src tests
git add pyproject.toml uv.lock src/server.py tests/test_server.py
git commit -m "feat: candidate-pool API: clips listing + selection persistence

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: /api/render 同步渲染端点

**Files:**
- Modify: `src/server.py`
- Test: `tests/test_server.py`(追加)

**Interfaces:**
- Consumes: `src.compose.build_simple_timeline(clips: list[ClipMetadata], week: str) -> Timeline`; `src.render.render_timeline(timeline, analyzed_dir: Path, output_path: Path) -> None`(失败抛 `RuntimeError`, 消息含 ffmpeg stderr); Task 3 的 `_selected_path`/`_analyzed_dir`
- Produces: `POST /api/render` body `{"week": str}` → 成功 `{"ok": true, "output": str, "estimated_duration_sec": int}`; 无选择/未知 id → 400; 渲染失败 → 500, `detail` 为原始错误文本; 副作用: 写 `data/work/<week>/timeline.json` 与 `data/output/<week>_vlog.mp4`

- [ ] **Step 1: 追加失败测试**

`tests/test_server.py` 末尾追加:

```python
def test_render_no_selection_400(tmp_path):
    client = TestClient(create_app(tmp_path / "data"))
    r = client.post("/api/render", json={"week": "w1"})
    assert r.status_code == 400


def test_render_happy_path(tmp_path, tmp_video_factory):
    from src.probe import build_clip_metadata
    data = tmp_path / "data"
    analyzed = data / "work" / "w1" / "analyzed"
    analyzed.mkdir(parents=True)
    video = tmp_video_factory("CLIP1.mp4", duration=2.0)
    cm = build_clip_metadata(video, clip_id="CLIP1")
    (analyzed / "CLIP1.json").write_text(cm.model_dump_json(), encoding="utf-8")

    client = TestClient(create_app(data))
    client.post("/api/select", json={"week": "w1", "clip_ids": ["CLIP1"]})
    r = client.post("/api/render", json={"week": "w1"})
    assert r.status_code == 200, r.text
    out = Path(r.json()["output"])
    assert out.exists() and out.stat().st_size > 0
    assert (data / "work" / "w1" / "timeline.json").exists()


def test_render_failure_surfaces_error(tmp_path):
    data = tmp_path / "data"
    analyzed = data / "work" / "w1" / "analyzed"
    _write_meta(analyzed, "GONE", path=str(data / "does-not-exist.mp4"))
    client = TestClient(create_app(data))
    client.post("/api/select", json={"week": "w1", "clip_ids": ["GONE"]})
    r = client.post("/api/render", json={"week": "w1"})
    assert r.status_code == 500
    assert "ffmpeg" in r.json()["detail"].lower()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_server.py -v -k render`
Expected: 3 个 render 测试 FAIL(404, 端点不存在)

- [ ] **Step 3: 实现端点**

`src/server.py` 修改: imports 区加

```python
from fastapi import FastAPI, HTTPException

from src.compose import build_simple_timeline
from src.render import render_timeline
```

`Selection` 类后加:

```python
class RenderRequest(BaseModel):
    week: str
```

`create_app` 内, `app.mount(...)` 之前加:

```python
    @app.post("/api/render")
    def render(req: RenderRequest):
        sp = _selected_path(req.week)
        if not sp.exists():
            raise HTTPException(status_code=400, detail=f"no selection for week {req.week}")
        clip_ids = json.loads(sp.read_text(encoding="utf-8")).get("clip_ids", [])
        if not clip_ids:
            raise HTTPException(status_code=400, detail="selection is empty")

        adir = _analyzed_dir(req.week)
        clips: list[ClipMetadata] = []
        for cid in clip_ids:
            mp = adir / f"{cid}.json"
            if not mp.exists():
                raise HTTPException(status_code=400, detail=f"unknown clip id: {cid}")
            clips.append(ClipMetadata.model_validate_json(mp.read_text(encoding="utf-8")))

        timeline = build_simple_timeline(clips, week=req.week)
        (work_root / req.week / "timeline.json").write_text(
            timeline.model_dump_json(indent=2), encoding="utf-8")

        out_dir = data_root / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{req.week}_vlog.mp4"
        try:
            render_timeline(timeline, adir, out_path)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        return {"ok": True, "output": str(out_path),
                "estimated_duration_sec": timeline.estimated_duration_sec}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_server.py -v`
Expected: 7 个测试全 PASS(render happy path 会真跑 ffmpeg, 约 10-20 秒)

- [ ] **Step 5: 全量回归 + commit**

```bash
uv run pytest -q && uv run ruff check src tests
git add src/server.py tests/test_server.py
git commit -m "feat: candidate-pool API: synchronous render endpoint

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: 单页 Web UI(GET / + index.html)

**Files:**
- Create: `src/static/index.html`
- Modify: `src/server.py`(加 `GET /`)
- Test: `tests/test_server.py`(追加)

**Interfaces:**
- Consumes: Task 3/4 的三个 API 契约(含 `gif_url`、`selected_ids`、render 的 `detail` 错误)
- Produces: `GET /` 返回候选池页面; JS 从 `location.search` 读 `?week=`(缺省则由服务端 default_week 兜底)

- [ ] **Step 1: 追加失败测试**

```python
def test_index_serves_ui(tmp_path):
    client = TestClient(create_app(tmp_path / "data"))
    r = client.get("/")
    assert r.status_code == 200
    assert "生成成片" in r.text
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_server.py::test_index_serves_ui -v`
Expected: FAIL(404)

- [ ] **Step 3: server.py 加路由**

imports 加 `from fastapi.responses import HTMLResponse`; `create_app` 内第一个路由位置加:

```python
    @app.get("/", response_class=HTMLResponse)
    def index():
        return INDEX_HTML_PATH.read_text(encoding="utf-8")
```

- [ ] **Step 4: 写 `src/static/index.html`**(完整文件)

```html
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>vlog 候选池</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
         background: #14161a; color: #e8e8e8; padding-bottom: 84px; }
  header { padding: 16px 24px; border-bottom: 1px solid #2a2d33;
           display: flex; justify-content: space-between; align-items: baseline; }
  h1 { font-size: 18px; margin: 0; }
  .day { padding: 0 24px; }
  .day h2 { font-size: 14px; color: #9aa0a8; margin: 16px 0 8px; }
  .card { display: flex; gap: 14px; padding: 10px; border: 1px solid #2a2d33;
          border-radius: 10px; margin-bottom: 8px; align-items: center;
          background: #1b1e24; cursor: pointer; }
  .card.checked { border-color: #4c8dff; background: #1d2533; }
  .card input[type=checkbox] { width: 18px; height: 18px; flex: none; }
  .thumb { width: 120px; height: 68px; object-fit: cover; border-radius: 6px;
           background: #000; flex: none; }
  div.thumb { display: flex; align-items: center; justify-content: center;
              color: #555; font-size: 12px; }
  .info { flex: 1; min-width: 0; }
  .meta { font-size: 13px; color: #9aa0a8; }
  .transcript { font-size: 14px; margin-top: 4px; white-space: nowrap;
                overflow: hidden; text-overflow: ellipsis; }
  .score { flex: none; font-weight: 600; padding: 4px 10px; border-radius: 999px;
           font-size: 13px; background: #2a2d33; }
  .score.hi { background: #1f4d2e; color: #7ee2a0; }
  .score.mid { background: #4d3d1f; color: #e2c67e; }
  footer { position: fixed; bottom: 0; left: 0; right: 0; background: #1b1e24;
           border-top: 1px solid #2a2d33; padding: 14px 24px; display: flex;
           justify-content: space-between; align-items: center; gap: 16px; }
  button { background: #4c8dff; border: 0; color: white; font-size: 15px;
           padding: 10px 22px; border-radius: 8px; cursor: pointer; }
  button:disabled { background: #333; color: #777; cursor: wait; }
  #result { padding: 12px 24px 24px; white-space: pre-wrap;
            font-family: Consolas, monospace; font-size: 13px; }
  #result.err { color: #ff7b72; }
  #result.ok { color: #7ee2a0; }
</style>
</head>
<body>
<header>
  <h1>本周 vlog 候选 · <span id="week"></span></h1>
  <div class="meta" id="clipcount"></div>
</header>
<main id="groups"></main>
<div id="result"></div>
<footer>
  <div id="status">已勾选 0 / 0</div>
  <button id="go">生成成片</button>
</footer>
<script>
const weekParam = new URLSearchParams(location.search).get("week");
// 与 src/compose.py 的常量保持一致: DEFAULT_MAX_CLIP_SEC=8, hook 2.5s + outro 1.5s
const MAX_CLIP_SEC = 8, CARDS_SEC = 4;
let clips = [], selected = new Set(), currentWeek = "";

function fmtDuration(s) {
  return s >= 60 ? `${Math.floor(s / 60)}分${Math.round(s % 60)}秒` : `${Math.round(s)}秒`;
}

async function load() {
  const q = weekParam ? `?week=${encodeURIComponent(weekParam)}` : "";
  const body = await (await fetch(`/api/clips${q}`)).json();
  currentWeek = body.week;
  clips = body.clips;
  selected = new Set(body.selected_ids);
  document.getElementById("week").textContent = currentWeek;
  document.getElementById("clipcount").textContent = `${clips.length} 个候选片段`;
  renderGroups();
}

function renderGroups() {
  const groups = {};
  for (const c of clips) (groups[c.captured_at.slice(0, 10)] ??= []).push(c);
  const root = document.getElementById("groups");
  root.innerHTML = "";
  for (const day of Object.keys(groups).sort()) {
    const div = document.createElement("div");
    div.className = "day";
    div.innerHTML = `<h2>${day}（${groups[day].length}）</h2>`;
    for (const c of groups[day].sort((a, b) => b.score - a.score)) div.appendChild(card(c));
    root.appendChild(div);
  }
  updateStatus();
}

function card(c) {
  const el = document.createElement("label");
  el.className = "card" + (selected.has(c.id) ? " checked" : "");
  const thumb = c.gif_url
    ? `<img class="thumb" loading="lazy" src="${c.gif_url}" alt="">`
    : `<div class="thumb">无预览</div>`;
  const text = (c.transcript || []).map(t => t.text).join(" ") || "（无口播）";
  const scoreCls = c.score >= 70 ? "hi" : c.score >= 50 ? "mid" : "";
  el.innerHTML = `
    <input type="checkbox" ${selected.has(c.id) ? "checked" : ""}>
    ${thumb}
    <div class="info">
      <div class="meta">${c.id} · ${c.captured_at.replace("T", " ").slice(0, 16)} · ${c.duration_sec.toFixed(1)}s</div>
      <div class="transcript">${text}</div>
    </div>
    <div class="score ${scoreCls}">${c.score}</div>`;
  el.querySelector("input").addEventListener("change", (e) => {
    e.target.checked ? selected.add(c.id) : selected.delete(c.id);
    el.classList.toggle("checked", e.target.checked);
    updateStatus();
    queueSave();
  });
  return el;
}

function updateStatus() {
  const total = clips.filter(c => selected.has(c.id))
                     .reduce((s, c) => s + Math.min(c.duration_sec, MAX_CLIP_SEC), 0);
  const est = selected.size ? ` · 预估 ${fmtDuration(total + CARDS_SEC)}` : "";
  document.getElementById("status").textContent =
    `已勾选 ${selected.size} / ${clips.length}${est}`;
}

let saveTimer;
function saveSelection() {
  return fetch("/api/select", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ week: currentWeek, clip_ids: [...selected] }),
  });
}
function queueSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveSelection, 500);
}

document.getElementById("go").addEventListener("click", async () => {
  const btn = document.getElementById("go"), out = document.getElementById("result");
  if (!selected.size) { out.className = "err"; out.textContent = "先勾选至少一个片段"; return; }
  btn.disabled = true; btn.textContent = "渲染中…";
  out.className = ""; out.textContent = "";
  clearTimeout(saveTimer);
  try {
    await saveSelection();
    const r = await fetch("/api/render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ week: currentWeek }),
    });
    const body = await r.json();
    if (!r.ok) throw new Error(body.detail || JSON.stringify(body));
    out.className = "ok";
    out.textContent = `成片完成: ${body.output}（约 ${body.estimated_duration_sec} 秒）`;
  } catch (e) {
    out.className = "err";
    out.textContent = `渲染失败:\n${e.message}`;
  } finally {
    btn.disabled = false; btn.textContent = "生成成片";
  }
});

load();
</script>
</body>
</html>
```

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_server.py -v`
Expected: 8 个测试全 PASS

- [ ] **Step 6: 全量回归 + commit**

```bash
uv run pytest -q && uv run ruff check src tests
git add src/static/index.html src/server.py tests/test_server.py
git commit -m "feat: candidate-pool web UI (single page, no framework)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: pipeline serve 子命令

**Files:**
- Modify: `src/pipeline.py`(在 `run` 命令之后追加 `serve`)
- Test: `tests/test_pipeline.py`(追加)

**Interfaces:**
- Consumes: `src.server.create_app`、`src.server.default_week`(Task 3)
- Produces: CLI `python -m src.pipeline serve [--week W] [--data-root data] [--port 8765] [--no-browser]`; 启动 uvicorn(127.0.0.1)并延迟 1 秒自动开浏览器到 `http://127.0.0.1:<port>/?week=<W>`

- [ ] **Step 1: 追加失败测试**

`tests/test_pipeline.py` 末尾追加:

```python
def test_serve_command_registered():
    """serve exists and exposes the expected options (does not start the server)."""
    runner = CliRunner()
    result = runner.invoke(cli, ["serve", "--help"])
    assert result.exit_code == 0
    for opt in ["--week", "--data-root", "--port", "--no-browser"]:
        assert opt in result.output
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_pipeline.py::test_serve_command_registered -v`
Expected: FAIL(`No such command 'serve'`, exit_code 2)

- [ ] **Step 3: 实现 serve**

`src/pipeline.py` 的 `run` 函数体之后追加:

```python
@cli.command()
@click.option("--week", default=None, help="Week tag; default = current ISO week")
@click.option("--data-root", type=click.Path(path_type=Path), default=Path("data"))
@click.option("--port", default=8765, type=int, show_default=True)
@click.option("--no-browser", is_flag=True, help="Do not auto-open the browser")
def serve(week: str | None, data_root: Path, port: int, no_browser: bool):
    """Start the candidate-pool web UI (Phase 2)."""
    import threading
    import webbrowser

    import uvicorn

    from src.server import create_app, default_week

    wk = week or default_week()
    url = f"http://127.0.0.1:{port}/?week={wk}"
    click.echo(f"Candidate pool for {wk}: {url}")
    if not no_browser:
        threading.Timer(1.0, webbrowser.open, args=[url]).start()
    uvicorn.run(create_app(data_root), host="127.0.0.1", port=port)
```

(库导入放函数内: serve 之外的 CLI 路径不应付出 fastapi/uvicorn 的导入成本, 也让 `run` 在未装 web 依赖的精简环境下仍可用。)

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: 3 个测试全 PASS

- [ ] **Step 5: 手动验证(用 Task 2 的 smoke 数据)**

```powershell
cd "C:\Users\yuhai\github_work\vlog-pipeline"
uv run python -m src.pipeline serve --week smoke --no-browser
```

另开终端: `curl http://127.0.0.1:8765/api/clips?week=smoke` 应返回含 AAA/BBB 的 JSON; 浏览器开 `http://127.0.0.1:8765/?week=smoke` 应看到两张卡片(带 GIF), 勾选 AAA+BBB 点"生成成片", 页面显示成片路径。完成后 Ctrl+C 停服务。

- [ ] **Step 6: 全量回归 + commit**

```bash
uv run pytest -q && uv run ruff check src tests
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline serve subcommand with browser auto-open

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: 开源卫生基线(README / LICENSE / checklist / config 模板)

**Files:**
- Modify: `README.md`(整体重写)
- Create: `LICENSE`、`docs/going-public-checklist.md`、`config.example.yaml`

**Interfaces:**
- Consumes: 无代码依赖
- Produces: 转公开所需的文档基线

- [ ] **Step 1: 重写 `README.md`**(完整内容)

````markdown
# vlog-pipeline

Turn a week of raw phone clips into a 1-3 minute vertical (9:16) vlog draft, automatically:
scene detection, Chinese ASR subtitles, heuristic scoring, an ffmpeg compositor, and a local
web UI where you pick which clips make the cut.

**Status: WIP (Phase 2 of 5 done).** Personal project; interfaces may change without notice.

## How it works

```
phone clips -> inbox/
  probe (ffprobe metadata + GIF preview)
  scene detection (PySceneDetect)
  ASR (whisper.cpp, optional)
  heuristic scoring
        -> data/work/<week>/analyzed/*.json
web UI (FastAPI, localhost:8765)
  pick clips -> selected.json
  one click  -> compose timeline -> ffmpeg render
        -> data/output/<week>_vlog.mp4  (9:16, burned-in subtitles)
```

## Requirements

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- `ffmpeg` / `ffprobe` on PATH
- Optional, for subtitles: a [whisper.cpp](https://github.com/ggml-org/whisper.cpp) binary and
  a ggml model. Set `WHISPER_BIN` and `WHISPER_MODEL` env vars; without them ASR is skipped.

## Quick start

```bash
uv sync --extra dev
uv run pytest                       # sanity check

# analyze a folder of clips and render everything in one go
uv run python -m src.pipeline run --inbox path/to/clips --week 2026-W28 --select all

# or: analyze first, then pick clips in the browser
uv run python -m src.pipeline run --inbox path/to/clips --week 2026-W28 --select all
uv run python -m src.pipeline serve --week 2026-W28
```

## Roadmap

- [x] Phase 1: CLI pipeline (probe / scenes / ASR / score / compose / render)
- [x] Phase 2: candidate-pool web UI (pick clips, one-click render)
- [ ] Phase 3: smarter scoring (audio energy, faces) + LLM-generated cut list
- [ ] Phase 4: scheduling + phone handoff (macOS launchd / Windows Task Scheduler)

Design docs: [docs/DESIGN.md](docs/DESIGN.md) (zh) and [docs/specs/](docs/specs/).

## License

MIT
````

- [ ] **Step 2: 创建 `LICENSE`**(MIT 全文)

```text
MIT License

Copyright (c) 2026 Haibin Yu

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3: 创建 `docs/going-public-checklist.md`**

```markdown
# 转公开前 checklist

规则: 任何内容公开前必扫个人信息。全部勾完才允许 `gh repo edit --visibility public`。

- [ ] 全历史个人信息扫描: `git log -p --all` 里无手机号/邮箱/证件号/住址;
      本地绝对路径(C:/Users/yuhai、D:/桌面)只允许出现在 docs/ 的历史记录性文档里,
      逐处确认可接受或改写
- [ ] 确认 data/、models/、config.yaml 从未进过历史:
      `git log --all --name-only --pretty=format: | sort -u` 无这三类路径
- [ ] README/docs 里的截图与 demo 素材不含真实生活片段(用 lavfi 合成视频演示)
- [ ] LICENSE 年份与署名正确
- [ ] GitHub repo description 与 topics 已写好(作品集口径, 对齐 ai-job-hunt-pipeline 风格)
- [ ] 执行: `gh repo edit haiiibin/vlog-pipeline --visibility public`
```

- [ ] **Step 4: 创建 `config.example.yaml`**

```yaml
# Copy to config.yaml and edit. config.yaml is gitignored.
# NOTE: Phase 1/2 read CLI flags and env vars only; this file becomes
# authoritative in Phase 4 (scheduling / platform adapters). Fields mirror
# docs/DESIGN.md section 8.

platform: "pc"                 # "mac" | "pc"

inbox_source:
  mac: "~/vlog-inbox"
  pc: "C:/Users/<you>/vlog-inbox"

whisper:
  bin: "C:/tools/whisper.cpp/whisper-cli.exe"   # or /opt/homebrew/bin/whisper-cli
  model: "models/ggml-large-v3.bin"
  language: "zh"

render:
  target_duration_sec: [60, 180]
  target_aspect: "9:16"
```

- [ ] **Step 5: commit**

```bash
git add README.md LICENSE docs/going-public-checklist.md config.example.yaml
git commit -m "docs: open-source hygiene baseline (README, MIT license, going-public checklist, config template)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: 终验 + 推送(对照 spec §6 验收标准)

**Files:** 无新增(纯验证与 push)

- [ ] **Step 1: 全量测试与 lint**

Run: `uv run pytest -q && uv run ruff check src tests`
Expected: 全绿, ruff 无告警

- [ ] **Step 2: 对照验收标准逐条核**

1. `git -C "C:\Users\yuhai\github_work\vlog-pipeline" log --oneline` 含原 12 个 Phase 1 commit + spec/plan/design 导入 + Task 3-7 的 5 个新 commit
2. `D:\桌面\claude\archive\vlog-pipeline-spec\` 下只有 `MOVED.md`; 外层工作区 `git log -1` 可见搬迁 commit
3. pytest 全绿(Step 1)
4. `uv run python -m src.pipeline serve --week smoke --no-browser` + 浏览器验证: 分组/GIF/勾选/状态栏正常(Task 6 Step 5 已做过, 若 smoke 数据被清理则按 Task 2 Step 4 重新生成)
5. 勾选出片得到可播放 mp4; 渲染失败场景页面显示错误(由 `test_render_failure_surfaces_error` 自动覆盖, 手动不再重复)
6. `README.md`(英文)、`LICENSE`、`docs/going-public-checklist.md`、`config.example.yaml` 存在

- [ ] **Step 3: 推送**

```bash
cd "C:/Users/yuhai/github_work/vlog-pipeline"
git push
gh repo view haiiibin/vlog-pipeline --json visibility,pushedAt
```

Expected: push 成功, `"visibility": "PRIVATE"`

- [ ] **Step 4: 清理 smoke 数据(可选)**

```powershell
Remove-Item -Recurse -Force "C:\Users\yuhai\github_work\vlog-pipeline\data\smoke-inbox", `
  "C:\Users\yuhai\github_work\vlog-pipeline\data\work\smoke" -ErrorAction SilentlyContinue
```

(`data/` 本就 gitignored, 留着也无害; 清理只为目录整洁。)
