"""Sharpness of sampled frames (OpenCV, imported on use)."""

from collections.abc import Sequence
from pathlib import Path


def laplacian_variance(frames: Sequence[Path]) -> float:
    """Mean over the frames of the Laplacian variance of the grayscale image (low = blurry)."""
    import cv2

    values: list[float] = []
    for path in frames:
        gray = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            msg = "frame is not a readable image"
            raise ValueError(msg)
        values.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
    return sum(values) / len(values)
