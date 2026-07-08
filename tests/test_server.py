"""Candidate-pool server API tests. No whisper, no real videos except where noted."""
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from src.compose import build_simple_timeline
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


def test_invalid_week_rejected(tmp_path):
    client = TestClient(create_app(tmp_path / "data"))
    assert client.get("/api/clips", params={"week": "../evil"}).status_code == 400
    assert client.post("/api/select",
                       json={"week": "..\\evil", "clip_ids": []}).status_code == 400


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

    client = TestClient(create_app(data, compose_fn=build_simple_timeline))
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
    client = TestClient(create_app(data, compose_fn=build_simple_timeline))
    client.post("/api/select", json={"week": "w1", "clip_ids": ["GONE"]})
    r = client.post("/api/render", json={"week": "w1"})
    assert r.status_code == 500
    assert "ffmpeg" in r.json()["detail"].lower()


def test_render_malformed_metadata_returns_json_500(tmp_path):
    """A corrupt analyzed json must yield a JSON {detail} 500, not a text/plain crash."""
    data = tmp_path / "data"
    analyzed = data / "work" / "w1" / "analyzed"
    analyzed.mkdir(parents=True)
    (analyzed / "BAD.json").write_text("{not valid json", encoding="utf-8")
    client = TestClient(create_app(data, compose_fn=build_simple_timeline))
    client.post("/api/select", json={"week": "w1", "clip_ids": ["BAD"]})
    r = client.post("/api/render", json={"week": "w1"})
    assert r.status_code == 500
    assert r.headers["content-type"].startswith("application/json")
    assert "detail" in r.json()


def test_index_serves_ui(tmp_path):
    client = TestClient(create_app(tmp_path / "data"))
    r = client.get("/")
    assert r.status_code == 200
    assert "生成成片" in r.text


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
