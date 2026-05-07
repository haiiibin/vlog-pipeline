"""Phase 1 CLI orchestrator.

Usage:
    python -m src.pipeline run --inbox PATH --week WEEK [--select all|id1,id2,...] [--data-root data]
"""
import json
import os
import sys
from pathlib import Path
import click

from src.probe import build_clip_metadata, generate_gif_preview, get_raw_metadata
from src.scene import detect_scenes
from src.asr import transcribe
from src.score import compute_score
from src.compose import build_simple_timeline
from src.render import render_timeline
from src.types import ClipMetadata, TranscriptSegment

VIDEO_EXTS = {".mov", ".mp4", ".m4v"}


def _analyze_one(video: Path, analyzed_dir: Path, language: str = "zh") -> ClipMetadata:
    """Probe + scenes + ASR + score for one clip. Idempotent: skip if json exists."""
    clip_id = video.stem
    out_json = analyzed_dir / f"{clip_id}.json"
    if out_json.exists():
        return ClipMetadata.model_validate_json(out_json.read_text())

    cm = build_clip_metadata(video, clip_id=clip_id)
    cm.scenes = detect_scenes(video)

    raw = get_raw_metadata(video)

    transcript_segments: list[dict] = []
    if os.environ.get("WHISPER_BIN") and os.environ.get("WHISPER_MODEL"):
        try:
            transcript_segments = transcribe(video, language=language)
        except Exception as e:
            click.echo(f"  ASR failed for {clip_id}: {e}", err=True)
    cm.transcript = [TranscriptSegment(**s) for s in transcript_segments]

    score, breakdown = compute_score(raw, transcript_segments)
    cm.score = score
    cm.score_breakdown = breakdown

    gif_path = analyzed_dir / f"{clip_id}.gif"
    try:
        generate_gif_preview(video, gif_path)
        cm.preview_gif = str(gif_path)
    except Exception as e:
        click.echo(f"  GIF failed for {clip_id}: {e}", err=True)

    out_json.write_text(cm.model_dump_json(indent=2))
    return cm


@click.group()
def cli():
    """Vlog pipeline."""


@cli.command()
@click.option("--inbox", required=True,
              type=click.Path(exists=True, file_okay=False, path_type=Path),
              help="Folder of source videos")
@click.option("--week", required=True, help="Week tag, e.g. 2026-W18")
@click.option("--select", default="all",
              help="'all' or comma-separated clip IDs")
@click.option("--data-root", type=click.Path(path_type=Path), default=Path("data"))
@click.option("--language", default="zh", help="ASR language code")
def run(inbox: Path, week: str, select: str, data_root: Path, language: str):
    """End-to-end: ingest -> analyze -> compose -> render."""
    work_dir = data_root / "work" / week
    analyzed_dir = work_dir / "analyzed"
    analyzed_dir.mkdir(parents=True, exist_ok=True)
    output_dir = data_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    videos = sorted(p for p in inbox.iterdir() if p.suffix.lower() in VIDEO_EXTS)
    if not videos:
        click.echo(f"No videos found in {inbox}", err=True)
        sys.exit(1)

    click.echo(f"Analyzing {len(videos)} clips...")
    analyzed: list[ClipMetadata] = []
    for v in videos:
        click.echo(f"  {v.name}")
        try:
            analyzed.append(_analyze_one(v, analyzed_dir, language=language))
        except Exception as e:
            click.echo(f"  FAILED {v.name}: {e}", err=True)

    if select == "all":
        selected = analyzed
    else:
        wanted = {s.strip() for s in select.split(",")}
        selected = [c for c in analyzed if c.id in wanted]

    if not selected:
        click.echo("No clips selected, aborting", err=True)
        sys.exit(1)

    click.echo(f"Composing timeline from {len(selected)} clips...")
    timeline = build_simple_timeline(selected, week=week)
    (work_dir / "timeline.json").write_text(timeline.model_dump_json(indent=2))

    output_path = output_dir / f"{week}_vlog.mp4"
    click.echo(f"Rendering -> {output_path}")
    render_timeline(timeline, analyzed_dir, output_path)
    click.echo(f"Done: {output_path}")


if __name__ == "__main__":
    cli()
