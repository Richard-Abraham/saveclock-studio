"""GET /projects/{id}/analysis (#10) from stored rows."""

import json
from uuid import UUID, uuid4

import asyncpg
import pytest

from tests.integration.conftest import ApiEnv, Db

pytestmark = pytest.mark.integration

BEAT_MAP = {
    "raw": {"beats_s": [0.0, 0.25, 0.5, 0.75, 1.0], "downbeats_s": [0.0, 1.0]},
    "beats_s": [0.0, 0.5, 1.0],
    "downbeats_s": [0.0, 1.0],
    "downbeats_derived": False,
    "grid": {"kind": "energy_grid", "beats_s": [0.0, 0.6, 1.1]},
    "segment": {"start_s": 0.0, "end_s": 15.0, "total_frames": 450},
    "confidence": {"reasons": ["irregular_beats"], "signals": {}, "version": 1},
}
SECTIONS = [{"id": "s1", "start_s": 0.0, "end_s": 1.0, "label": "quiet", "energy": "e1"}]


async def seed(db: Db, pid: UUID, *, fallback: str | None, confidence: float) -> None:
    conn = await asyncpg.connect(db.raw("postgres"))
    try:
        song = uuid4()
        await conn.execute(
            "INSERT INTO songs (id, project_id, original_filename, size_bytes, content_type,"
            " duration_s, codec) VALUES ($1, $2, 'a.wav', 10, 'audio/wav', 30.5, 'pcm')",
            song,
            pid,
        )
        await conn.execute(
            "INSERT INTO analyses (id, song_id, model, model_version, tempo_bpm,"
            " tempo_octave_adjust, beat_confidence, fallback, beat_map, sections, energy_curve,"
            " waveform_peaks,"
            " low_confidence_ranges) VALUES ($1, $2, 'beat_this', '1.1.0', 120.25, -1, $3, $4,"
            " $5::jsonb, $6::jsonb, '[0.1, 0.9]', '[0.5, 0.25]', '[[0.0, 1.0]]')",
            uuid4(),
            song,
            confidence,
            fallback,
            json.dumps(BEAT_MAP),
            json.dumps(SECTIONS),
        )
        await conn.execute(
            "UPDATE projects SET flags = '{\"low_confidence\": true}' WHERE id = $1", pid
        )
    finally:
        await conn.close()


async def new_project(env: ApiEnv) -> UUID:
    return UUID((await env.client.post("/api/v1/projects", json={})).json()["id"])


async def test_not_ready_is_a_409_with_a_reason(api: ApiEnv) -> None:
    pid = await new_project(api)
    r = await api.client.get(f"/api/v1/projects/{pid}/analysis")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"
    assert r.json()["error"]["details"]["reason"] == "not_ready"


async def test_the_analysis_body(api: ApiEnv) -> None:
    pid = await new_project(api)
    await seed(api.db, pid, fallback=None, confidence=0.9)
    r = await api.client.get(f"/api/v1/projects/{pid}/analysis")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tempo_bpm"] == 120.25
    assert body["tempo_octave_adjust"] == -1
    assert body["beats_s"] == [0.0, 0.5, 1.0]  # the folded grid, not the raw one
    assert body["downbeats_s"] == [0.0, 1.0]
    assert body["sections"] == SECTIONS
    assert body["energy_curve"] == [0.1, 0.9]
    assert body["waveform_peaks"] == [0.5, 0.25]
    assert body["low_confidence_ranges"] == [[0.0, 1.0]]
    assert body["confidence"] == {
        "score": pytest.approx(0.9),
        "band": "high",
        "reasons": ["irregular_beats"],
    }
    assert body["fallback"] is None
    assert body["segment"] == BEAT_MAP["segment"]
    assert body["flags"] == {"low_confidence": True}
    assert set(body) == {
        "tempo_bpm", "tempo_octave_adjust", "beats_s", "downbeats_s", "sections", "energy_curve",
        "waveform_peaks", "low_confidence_ranges", "confidence", "fallback", "segment", "flags",
    }  # fmt: skip


async def test_the_fallback_grid_is_the_effective_one(api: ApiEnv) -> None:
    pid = await new_project(api)
    await seed(api.db, pid, fallback="energy_grid", confidence=0.4)
    body = (await api.client.get(f"/api/v1/projects/{pid}/analysis")).json()
    assert body["fallback"] == "energy_grid"
    assert body["beats_s"] == [0.0, 0.6, 1.1]
    assert body["confidence"]["band"] == "low"


async def test_the_project_detail_carries_the_song_and_the_summary(api: ApiEnv) -> None:
    pid = await new_project(api)
    await seed(api.db, pid, fallback=None, confidence=0.6)
    body = (await api.client.get(f"/api/v1/projects/{pid}")).json()
    assert body["song"] == {
        "original_filename": "a.wav",
        "size_bytes": 10,
        "duration_s": 30.5,
        "codec": "pcm",
        "sample_rate": None,
        "channels": None,
    }
    assert body["analysis"]["tempo_bpm"] == 120.25
    assert body["analysis"]["confidence"] == pytest.approx(0.6)


async def test_reading_the_analysis_counts_as_activity(api: ApiEnv) -> None:
    pid = await new_project(api)
    await seed(api.db, pid, fallback=None, confidence=0.9)
    conn = await asyncpg.connect(api.db.raw("postgres"))
    try:
        await conn.execute("UPDATE projects SET last_activity_at = '2020-01-01' WHERE id = $1", pid)
        await api.client.get(f"/api/v1/projects/{pid}/analysis")
        stamp = await conn.fetchval("SELECT last_activity_at FROM projects WHERE id = $1", pid)
    finally:
        await conn.close()
    assert stamp.year >= 2025
