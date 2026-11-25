# Phase 0 validation spike (snapshot)

Throwaway test code for `plans/000-phase0-validation-spike.md`: beat-metric self-tests, the Beat This runner, the frame-accurate FFmpeg render harness, hostile-input tests, and the 8.1 vs 9.0 build comparison. `results/` holds the text results (no audio, clips, renders, model weights or secrets).

Run it from a working copy that has the gitignored `data/` and `downloads/` folders:

```sh
uv python install 3.12 && uv sync
uv run pytest -q
```

Keepers move into `eval/` and the services in Phase 1.
