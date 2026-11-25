"""The one reader of the environment (STANDARDS §2). Field names are the variable names.

`.env.example` and `infra/ENV.md` are generated from these classes (`make env-docs`).
Every field carries `svc` (A=api, K=worker, M=worker-maint, W=web, ...), `secret`, `doc`
and optionally `example` (value written to the active line of `.env.example`).
"""

from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

LOOPBACK = ("127.0.0.1", "::1", "localhost")


def _f(
    default: Any,  # noqa: ANN401
    svc: str,
    *,
    secret: bool = False,
    doc: str = "ARCH §18",
    example: str | None = None,
) -> Any:  # noqa: ANN401
    extra: dict[str, Any] = {"svc": svc, "secret": secret, "doc": doc}
    if example is not None:
        extra["example"] = example
    return Field(default, json_schema_extra=extra)


def _split(v: object) -> object:
    if isinstance(v, str):
        return [p.strip() for p in v.split(",") if p.strip()]
    return v


CsvList = Annotated[list[str], NoDecode]


class Settings(BaseSettings):
    # extra="ignore": the process environment always holds unrelated variables.
    # hide_input_in_errors: a validation error must never echo a secret value.
    # env_ignore_empty: `PEXELS_API_KEY=` in .env means "unset".
    model_config = SettingsConfigDict(
        extra="ignore", hide_input_in_errors=True, env_ignore_empty=True
    )

    app_env: Literal["local", "ci", "prod"] = _f(..., "all", example="local")
    app_origin: str = _f(..., "A,W", example="http://localhost:3000")
    api_internal_url: str = _f("http://api:8000/api/v1", "W")
    log_level: str = _f("INFO", "all")
    sentry_dsn: SecretStr | None = _f(None, "all", secret=True)
    sentry_env: str | None = _f(None, "all")
    database_url: SecretStr = _f(..., "A,K,M", secret=True)
    redis_url: SecretStr = _f(..., "A,K,M", secret=True)
    allowed_hosts: CsvList = _f(["localhost", "127.0.0.1"], "A")
    bind_addr: str = _f("127.0.0.1", "compose", example="127.0.0.1")
    saveclock_api_url: str = _f("http://127.0.0.1:8000", "CLI")
    pexels_key_configured: bool = _f(False, "A", example="false")
    pixabay_key_configured: bool = _f(False, "A", example="false")
    anthropic_key_configured: bool = _f(False, "A", example="false")
    blob_backend: Literal["fs"] = _f("fs", "A,K,M")
    blob_root: str = _f(..., "A,K,M")
    max_upload_mb: int = _f(100, "A,K")
    min_song_s: int = _f(15, "A,K")
    max_song_s: int = _f(600, "A,K")
    intermediate_ttl_days: int = _f(7, "M")
    sweep_interval_min: int = _f(60, "M")
    disk_low_watermark_gb: float = _f(5, "A,K,M")
    worker_heavy_concurrency: int | None = _f(None, "K")
    ffmpeg_bin: str = _f("/usr/local/bin/ffmpeg", "K")
    ffprobe_bin: str = _f("/usr/local/bin/ffprobe", "K")
    ffmpeg_threads: int | None = _f(None, "K")
    omp_num_threads: int | None = _f(None, "K")
    torch_threads: int | None = _f(None, "K")
    fetch_concurrency: int | None = _f(None, "K")
    device: str = _f("cpu", "K")
    beat_this_checkpoint: str = _f("final0", "K")
    siglip_model: str = _f("google/siglip2-base-patch16-224", "K")
    topk_factor: float = _f(1.3, "K")
    pexels_api_key: SecretStr | None = _f(None, "K", secret=True, example="")
    pixabay_enabled: bool = _f(False, "K", example="false")
    pixabay_api_key: SecretStr | None = _f(None, "K", secret=True, example="")
    pexels_rate_per_hour: int = _f(200, "K")
    pixabay_rate_per_min: int = _f(100, "K")
    stock_host_allowlist: CsvList = _f([], "K")
    llm_enabled: bool | None = _f(None, "K")
    anthropic_api_key: SecretStr | None = _f(None, "K", secret=True, example="")
    llm_model: str = _f("claude-haiku-5-5", "K")
    llm_timeout_s: int = _f(8, "K")
    llm_max_tokens: int = _f(300, "K")
    llm_daily_call_cap: int | None = _f(None, "K")
    llm_cost_cap_usd_per_video: float | None = _f(None, "K")
    # BACKUP_*: read by the host backup script, never by an app container (ARCH §23).
    backup_repo_path: str | None = _f(None, "host", secret=True)
    backup_password_file: str | None = _f(None, "host", secret=True)
    backup_dest_dir: str | None = _f(None, "host", secret=True)
    next_public_app_origin: str | None = _f(None, "W")
    fake_stock: bool = _f(False, "local/CI")
    fake_ml: bool = _f(False, "local/CI")
    fake_llm: bool = _f(False, "local/CI")
    # Not in ARCH §18 (proposed additions, plan 001 Step 2):
    broker_heartbeat_timeout_s: int = _f(60, "A,K,M", doc="plan 001")
    app_version: str = _f("dev", "all", doc="plan 001")

    @field_validator("allowed_hosts", "stock_host_allowlist", mode="before")
    @classmethod
    def _csv(cls, v: object) -> object:
        return _split(v)

    @field_validator("bind_addr")
    @classmethod
    def _loopback_only(cls, v: str) -> str:
        if v not in LOOPBACK:
            msg = f"BIND_ADDR must be one of {LOOPBACK}"  # SEC-165
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _no_fakes_in_prod(self) -> Self:
        if self.app_env == "prod" and (self.fake_stock or self.fake_ml or self.fake_llm):
            msg = "FAKE_* variables are not allowed when APP_ENV=prod"
            raise ValueError(msg)
        return self


class MigrateSettings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore", hide_input_in_errors=True, env_ignore_empty=True
    )

    migrator_database_url: SecretStr = _f(..., "migrate", secret=True)
    owner_display_name: str = _f(..., "migrate", example="")
    owner_email: str = _f("owner@saveclock.local", "migrate", example="owner@saveclock.local")


class ComposeVar(BaseModel):
    name: str
    doc: str


# Compose-only variables (C10, SEC-133): read by compose, never by Settings.
COMPOSE_ONLY = (
    ComposeVar(name="POSTGRES_PASSWORD", doc="superuser password for the postgres container"),
    ComposeVar(name="POSTGRES_APP_PASSWORD", doc="password of role app_rw"),
    ComposeVar(name="POSTGRES_MIGRATOR_PASSWORD", doc="password of role migrator"),
    ComposeVar(name="REDIS_PASSWORD", doc="requirepass for redis"),
)
