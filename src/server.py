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
