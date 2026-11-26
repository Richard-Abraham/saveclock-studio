"""The analyze and validate time budgets in one place: the relationships, not the numbers."""

from saveclock.adapters.ffmpeg import CANONICALIZE_TIMEOUT_S, PROBE_TIMEOUT_S
from saveclock.config import (
    ANALYZE_COMPUTE_S,
    ANALYZE_LIMIT_S,
    ANALYZE_WAIT_S,
    DRAFT_LIMIT_S,
    FOOTAGE_WAIT_S,
    HEAVY_TTL_S,
    NORMALIZE_HOLD_S,
    REMUX_FFMPEG_S,
    REMUX_LIMIT_S,
    RENDER_FFMPEG_S,
    RENDER_HEAVY_WAIT_S,
    RENDER_LIMIT_S,
    VET_HOLD_S,
    Settings,
)
from saveclock.workers import analysis as analysis_worker
from saveclock.workers import draft as draft_worker
from saveclock.workers import ingest as ingest_worker
from saveclock.workers import remux as remux_worker
from saveclock.workers import render as render_worker

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


def test_the_draft_limit_sits_between_the_slot_wait_and_the_slot_ttl() -> None:
    """HEAVY_TTL_S > DRAFT_LIMIT_S > FOOTAGE_WAIT_S: a wait for a slot fits inside the actor's
    limit, and a live worker never loses a slot it holds to the TTL."""
    assert HEAVY_TTL_S > DRAFT_LIMIT_S > FOOTAGE_WAIT_S


def test_the_draft_actor_uses_the_limit_and_a_hold_never_outlives_the_slot() -> None:
    assert draft_worker.TIME_LIMIT_MS == DRAFT_LIMIT_S * 1000
    assert max(VET_HOLD_S, NORMALIZE_HOLD_S) < HEAVY_TTL_S


def test_the_render_slot_outlives_the_limit_which_outlives_the_ffmpeg_child() -> None:
    assert HEAVY_TTL_S > RENDER_LIMIT_S > RENDER_FFMPEG_S


def test_the_slot_wait_plus_the_encode_fit_the_render_limit() -> None:
    assert RENDER_LIMIT_S >= RENDER_HEAVY_WAIT_S + RENDER_FFMPEG_S


def test_a_remux_is_shorter_than_a_render_and_its_child_fits_its_limit() -> None:
    assert REMUX_LIMIT_S < RENDER_LIMIT_S
    assert REMUX_LIMIT_S > REMUX_FFMPEG_S


def test_the_render_actors_use_those_numbers() -> None:
    assert render_worker.TIME_LIMIT_MS == RENDER_LIMIT_S * 1000
    assert remux_worker.TIME_LIMIT_MS == REMUX_LIMIT_S * 1000
