"""Scene boundary detection via PySceneDetect."""
from pathlib import Path
from scenedetect import detect, ContentDetector
from src.probe import get_raw_metadata


def detect_scenes(
    video_path: Path,
    threshold: float = 27.0,
) -> list[tuple[float, float]]:
    """Return [(start_sec, end_sec), ...]. If no cuts found, return single full-clip scene."""
    scene_list = detect(str(video_path), ContentDetector(threshold=threshold))
    if scene_list:
        return [(s.seconds, e.seconds) for s, e in scene_list]

    # No cuts: return whole clip as one scene
    duration = float(get_raw_metadata(video_path)["format"]["duration"])
    return [(0.0, duration)]
