"""The analyze and validate time budgets in one place: the relationships, not the numbers."""

from saveclock.adapters.ffmpeg import CANONICALIZE_TIMEOUT_S, PROBE_TIMEOUT_S
from saveclock.config import (
    ANALYZE_COMPUTE_S,
    ANALYZE_LIMIT_S,
    ANALYZE_WAIT_S,
    HEAVY_TTL_S,
    Settings,
)
from saveclock.workers import analysis as analysis_worker
from saveclock.workers import ingest as ingest_worker

MAX_SONG_S = 600
SLOWEST_BEAT_THIS_PER_AUDIO_S = 22 / 30  # measured: 22 s for a 30 s clip, model load included


def test_slot_ttl_outlives_the_actor_limit_which_outlives_wait_plus_compute() -> None:
    assert HEAVY_TTL_S > ANALYZE_LIMIT_S > ANALYZE_WAIT_S + ANALYZE_COMPUTE_S


def test_the_actor_and_the_setting_use_those_numbers() -> None:
    assert analysis_worker.TIME_LIMIT_MS == ANALYZE_LIMIT_S * 1000
    assert Settings.model_fields["heavy_ttl_s"].default == HEAVY_TTL_S


def test_the_compute_allowance_covers_the_longest_song_at_the_slowest_speed() -> None:
    assert ANALYZE_COMPUTE_S >= MAX_SONG_S * SLOWEST_BEAT_THIS_PER_AUDIO_S


def test_the_validate_limit_covers_every_ffmpeg_timeout_it_can_spend() -> None:
    spent = 2 * PROBE_TIMEOUT_S + CANONICALIZE_TIMEOUT_S  # probe, attached-picture probe, decode
    assert spent * 1000 < ingest_worker.TIME_LIMIT_MS
