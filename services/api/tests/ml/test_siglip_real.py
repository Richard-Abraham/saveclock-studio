"""The real SigLIP 2 weights on two generated frames (`make test-ml`).

Needs the ml extra and the weights: MODELS_DIR points at the directory `make models-cache` fills.
A missing snapshot FAILS (never skips): this is the check that the model loads offline from
safetensors with `local_files_only`.
"""

import os
import time
from pathlib import Path

import pytest
from PIL import Image

from saveclock.adapters.models import verified_group
from saveclock.adapters.siglip import SigLipRanker
from saveclock.domain.sampling import cosine

pytestmark = pytest.mark.ml

GROUP = "siglip2-base-patch16-224"


def model_dir() -> Path:
    models_dir = os.environ.get("MODELS_DIR")
    if not models_dir:
        pytest.fail("MODELS_DIR is not set: run `make test-ml`")
    return verified_group(models_dir, GROUP)


def square(path: Path, rgb: tuple[int, int, int]) -> Path:
    Image.new("RGB", (224, 224), rgb).save(path)
    return path


def test_red_frame_ranks_above_blue_for_red_and_the_reverse_for_blue(tmp_path: Path) -> None:
    ranker = SigLipRanker(model_dir(), torch_threads=4)
    red = square(tmp_path / "red.png", (220, 20, 20))
    blue = square(tmp_path / "blue.png", (20, 20, 220))
    started = time.monotonic()
    images = ranker.embed_images([red, blue])
    texts = ranker.embed_text(["red", "blue"])
    wall_ms = int((time.monotonic() - started) * 1000)
    assert len(images) == 2
    assert len(texts) == 2
    assert len(images[0]) == len(texts[0]) > 100
    assert cosine(images[0], texts[0]) > cosine(images[1], texts[0])  # "red": red frame wins
    assert cosine(images[1], texts[1]) > cosine(images[0], texts[1])  # "blue": blue frame wins
    print(f"siglip2 load+embed 2 images and 2 texts: {wall_ms} ms")
