"""Hard-cut detection inside a stock clip with PySceneDetect (BSD-3) on a downscaled stream.

Deterministic CPU code: FAKE_ML does not replace it, it is tested for real on generated clips.
The OpenCV that PySceneDetect uses is the headless build (no GUI libraries in the worker image).
shortcut: OpenCV's own demuxer reads the clip (a file our ffprobe already accepted as mp4); upgrade
to cut detection on frames decoded by the audited FFmpeg runner if that trust is ever too wide.
"""

from pathlib import Path


def detect_cuts(path: Path, *, downscale_height: int = 360) -> list[float]:
    """Seconds at which a new scene starts (the start of the clip is not a cut)."""
    from scenedetect import ContentDetector, SceneManager, open_video

    video = open_video(str(path))
    manager = SceneManager()
    manager.add_detector(ContentDetector())
    height = int(video.frame_size[1])
    manager.downscale = max(1, height // downscale_height)
    manager.detect_scenes(video, show_progress=False)
    scenes = manager.get_scene_list()
    return [round(start.seconds, 3) for start, _ in scenes[1:]]
