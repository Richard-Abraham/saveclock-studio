"""Image/text ranking model behind a Protocol (SigLIP 2, Apache-2.0) and the fake used by FAKE_ML.

`torch`, `transformers` and `PIL` are imported inside the methods, so importing this module is
free (the API image has none of them). The weights directory is verified against the manifest
first (`verified_group`) and loaded with `local_files_only=True` from safetensors; there is no
unpickling call anywhere (SEC-170).
"""

import hashlib
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

TEXT_MAX_LENGTH = 64  # the SigLIP 2 model card pads text to max_length
FAKE_DIM = 8


class ImageTextRanker(Protocol):
    name: str
    version: str

    def embed_images(self, paths: Sequence[Path]) -> list[list[float]]: ...

    def embed_text(self, prompts: Sequence[str]) -> list[list[float]]: ...


def _features(output: Any) -> Any:  # noqa: ANN401
    """transformers returns a tensor or, in newer versions, a model output with `pooler_output`."""
    return getattr(output, "pooler_output", output)


class SigLipRanker:
    name = "siglip2-base-patch16-224"
    version = "1"

    def __init__(self, model_dir: Path, torch_threads: int) -> None:
        self.model_dir, self.torch_threads = model_dir, torch_threads
        self._model: Any = None
        self._processor: Any = None
        self._lock = threading.Lock()  # one load per process; the heavy lock bounds inference

    def _load(self) -> tuple[Any, Any]:
        with self._lock:
            if self._model is None:
                import torch
                import transformers

                auto_processor: Any = transformers.AutoProcessor
                auto_model: Any = transformers.AutoModel
                torch.set_num_threads(self.torch_threads)
                self._processor = auto_processor.from_pretrained(
                    str(self.model_dir), local_files_only=True
                )
                self._model = auto_model.from_pretrained(
                    str(self.model_dir), local_files_only=True, use_safetensors=True
                ).eval()
            return self._model, self._processor

    def embed_images(self, paths: Sequence[Path]) -> list[list[float]]:
        import torch
        from PIL import Image

        model, processor = self._load()
        images = []
        for path in paths:
            with Image.open(path) as img:
                images.append(img.convert("RGB"))
        with torch.inference_mode():
            inputs = processor(images=images, return_tensors="pt")
            feats = _features(model.get_image_features(**inputs))
        return [[float(x) for x in row] for row in feats.tolist()]

    def embed_text(self, prompts: Sequence[str]) -> list[list[float]]:
        import torch

        model, processor = self._load()
        with torch.inference_mode():
            inputs = processor(
                text=list(prompts),
                padding="max_length",
                max_length=TEXT_MAX_LENGTH,
                truncation=True,
                return_tensors="pt",
            )
            feats = _features(model.get_text_features(**inputs))
        return [[float(x) for x in row] for row in feats.tolist()]


def hash_vector(data: bytes) -> list[float]:
    """The fake embedding: 8 numbers in [-1, 1] from a sha256 (deterministic, no model)."""
    return [(b - 127.5) / 127.5 for b in hashlib.sha256(data).digest()[:FAKE_DIM]]


class FakeRanker:
    """FAKE_ML: vectors from a hash of the text or of the image bytes (same dimension for both)."""

    name = "fake-hash-ranker"
    version = "1"

    def embed_images(self, paths: Sequence[Path]) -> list[list[float]]:
        return [hash_vector(Path(p).read_bytes()) for p in paths]

    def embed_text(self, prompts: Sequence[str]) -> list[list[float]]:
        return [hash_vector(p.encode()) for p in prompts]
