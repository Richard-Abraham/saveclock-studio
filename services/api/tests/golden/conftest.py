"""Golden fixtures: the real chain (Postgres, Redis, FFmpeg, the click picker for Beat This) over a
stock pool of four solid colours, so every planned cut is a measurable colour change."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from saveclock.adapters.ffmpeg import Tools
from tests.factories.render import solid_stock
from tests.integration.conftest import ApiEnv, api, blob_root, fresh_db, migrated_db
from tests.integration.render_harness import Renders

__all__ = ["api", "blob_root", "fresh_db", "migrated_db"]  # fixtures re-exported for this folder


@pytest.fixture(scope="session")
def solid_clips(ffmpeg_tools: Tools, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return solid_stock(ffmpeg_tools, tmp_path_factory.mktemp("solid-stock"))


@pytest.fixture
async def golden(
    api: ApiEnv, ffmpeg_tools: Tools, solid_clips: Path, tmp_path: Path
) -> AsyncIterator[Renders]:
    from tests.integration.draft_harness import build_draft_env

    draft, engine = await build_draft_env(api, ffmpeg_tools, solid_clips, tmp_path)
    yield Renders(draft)
    draft.redis.close()
    await engine.dispose()
