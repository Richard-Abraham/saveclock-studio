import pytest
from pydantic import ValidationError

from saveclock.config import COMPOSE_ONLY, MigrateSettings, Settings

BASE = {
    "APP_ENV": "local",
    "APP_ORIGIN": "http://localhost:3000",
    "DATABASE_URL": "postgresql+asyncpg://u:pw-secret-123@h/db",
    "REDIS_URL": "redis://:pw@r:6379/0",
    "BLOB_ROOT": "/data/blobs",
}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in {f.upper() for f in Settings.model_fields} | {
        f.upper() for f in MigrateSettings.model_fields
    }:
        monkeypatch.delenv(name, raising=False)


def make_settings(**env: str) -> Settings:
    """Build Settings from environment-variable names (matched case-insensitively)."""
    merged = {**BASE, **env}
    return Settings(_env_file=None, **{k.lower(): v for k, v in merged.items()})  # type: ignore[arg-type]


@pytest.mark.unit
def test_missing_required_names_variable_without_values() -> None:
    env = {k.lower(): v for k, v in BASE.items() if k != "DATABASE_URL"}
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, **env)  # type: ignore[arg-type]
    text = str(exc.value)
    assert "database_url" in text.lower()
    assert "pw-secret-123" not in text
    assert "http://localhost:3000" not in text


@pytest.mark.unit
def test_prod_refuses_fakes() -> None:
    with pytest.raises(ValidationError):
        make_settings(APP_ENV="prod", FAKE_STOCK="true")


@pytest.mark.unit
def test_bind_addr_must_be_loopback() -> None:
    with pytest.raises(ValidationError):
        make_settings(BIND_ADDR="0.0.0.0")  # noqa: S104
    assert make_settings(BIND_ADDR="::1").bind_addr == "::1"


@pytest.mark.unit
def test_allowed_hosts_csv() -> None:
    assert make_settings(ALLOWED_HOSTS="a,b").allowed_hosts == ["a", "b"]
    assert make_settings().allowed_hosts == ["localhost", "127.0.0.1"]


@pytest.mark.unit
def test_allowed_hosts_from_real_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in BASE.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,api")
    monkeypatch.setenv("PEXELS_API_KEY", "")
    s = Settings(_env_file=None)
    assert s.allowed_hosts == ["localhost", "127.0.0.1", "api"]
    assert s.pexels_api_key is None


@pytest.mark.unit
def test_unrelated_env_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOMETHING_ELSE", "1")
    assert make_settings().app_env == "local"


# Names copied by hand from ARCHITECTURE §18 (BACKUP_* expanded to the three fields we define).
ARCH_18 = {
    "APP_ENV", "APP_ORIGIN", "API_INTERNAL_URL", "LOG_LEVEL", "SENTRY_DSN", "SENTRY_ENV",
    "DATABASE_URL", "MIGRATOR_DATABASE_URL", "REDIS_URL", "ALLOWED_HOSTS", "BIND_ADDR",
    "SAVECLOCK_API_URL", "OWNER_EMAIL", "OWNER_DISPLAY_NAME", "PEXELS_KEY_CONFIGURED",
    "PIXABAY_KEY_CONFIGURED", "ANTHROPIC_KEY_CONFIGURED", "BLOB_BACKEND", "BLOB_ROOT",
    "MAX_UPLOAD_MB", "MIN_SONG_S", "MAX_SONG_S", "INTERMEDIATE_TTL_DAYS", "SWEEP_INTERVAL_MIN",
    "DISK_LOW_WATERMARK_GB", "WORKER_HEAVY_CONCURRENCY", "FFMPEG_BIN", "FFPROBE_BIN",
    "FFMPEG_THREADS", "OMP_NUM_THREADS", "TORCH_THREADS", "FETCH_CONCURRENCY", "DEVICE",
    "BEAT_THIS_CHECKPOINT", "SIGLIP_MODEL", "TOPK_FACTOR", "PEXELS_API_KEY", "PIXABAY_ENABLED",
    "PIXABAY_API_KEY", "PEXELS_RATE_PER_HOUR", "PIXABAY_RATE_PER_MIN", "STOCK_HOST_ALLOWLIST",
    "LLM_ENABLED", "ANTHROPIC_API_KEY", "LLM_MODEL", "LLM_TIMEOUT_S", "LLM_MAX_TOKENS",
    "LLM_DAILY_CALL_CAP", "LLM_COST_CAP_USD_PER_VIDEO", "BACKUP_REPO_PATH",
    "BACKUP_PASSWORD_FILE", "BACKUP_DEST_DIR", "NEXT_PUBLIC_APP_ORIGIN", "FAKE_STOCK",
    "FAKE_ML", "FAKE_LLM",
}  # fmt: skip


@pytest.mark.unit
def test_inventory_parity_with_arch_18() -> None:
    ours = (
        {n.upper() for n in Settings.model_fields}
        | {n.upper() for n in MigrateSettings.model_fields}
        | {c.name for c in COMPOSE_ONLY}
    )
    compose_only = {c.name for c in COMPOSE_ONLY}
    assert ours - ARCH_18 - compose_only == {
        "BROKER_HEARTBEAT_TIMEOUT_S",
        "APP_VERSION",
        "TUNING_PUBLISHER",
    }
    assert ARCH_18 - ours == set()
