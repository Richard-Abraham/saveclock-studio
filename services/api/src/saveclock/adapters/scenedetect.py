"""Hard-cut detection inside a stock clip with PySceneDetect (BSD-3) on a downscaled stream.

Deterministic CPU code: FAKE_ML does not replace it, it is tested for real on generated clips.
The OpenCV that PySceneDetect uses is the headless build (no GUI libraries in the worker image).
The call is bounded: it reads at most `max_s` seconds of the clip, and a watcher thread calls the
thread-safe `SceneManager.stop()` when `timeout_s` passes or `cancel()` says so.
shortcut: OpenCV's own demuxer reads the clip (a file our ffprobe already accepted as mp4); upgrade
to cut detection on frames decoded by the audited FFmpeg runner if that trust is ever too wide.
"""

import threading
import time
from collections.abc import Callable
from pathlib import Path

MAX_CLIP_S = 60.0  # stock_rules.MAX_DURATION_S: nothing longer is ever vetted
TIMEOUT_S = 120.0
POLL_S = 1.0


class DetectionStopped(RuntimeError):
    """Detection ended early (time limit or cancel): the cut list would be incomplete."""


def detect_cuts(
    path: Path,
    *,
    downscale_height: int = 360,
    max_s: float = MAX_CLIP_S,
    timeout_s: float = TIMEOUT_S,
    cancel: Callable[[], bool] | None = None,
    poll_s: float = POLL_S,
) -> list[float]:
    """Seconds at which a new scene starts (the start of the clip is not a cut)."""
    from scenedetect import ContentDetector, SceneManager, open_video

    video = open_video(str(path))
    manager = SceneManager()
    manager.add_detector(ContentDetector())
    height = int(video.frame_size[1])
    manager.auto_downscale = False  # the factor below is what is used (360 px high)
    manager.downscale = max(1, height // downscale_height)
    finished = threading.Event()
    reason: list[str] = []

    def watch() -> None:
        started = time.monotonic()
        while not finished.wait(poll_s):
            if time.monotonic() - started > timeout_s:
                reason.append("timeout")
            elif cancel is not None and cancel():
                reason.append("canceled")
            if reason:
                manager.stop()
                return

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    try:
        manager.detect_scenes(video, end_time=max_s, show_progress=False)
    finally:
        finished.set()
        watcher.join()
    if reason:
        raise DetectionStopped(reason[0])
    scenes = manager.get_scene_list()
    return [round(start.seconds, 3) for start, _ in scenes[1:]]
