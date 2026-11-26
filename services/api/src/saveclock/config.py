"""The one reader of the environment (STANDARDS §2). Field names are the variable names.

`.env.example` and `infra/ENV.md` are generated from these classes (`make env-docs`).
Every field carries `svc` (A=api, K=worker, M=worker-maint, W=web, ...), `secret`, `doc`
and optionally `example` (value written to the active line of `.env.example`).
"""

from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

LOOPBACK = ("127.0.0.1", "::1", "localhost")

# The analyze time budget, in one place (a test asserts the inequalities):
#   HEAVY_TTL_S > ANALYZE_LIMIT_S >= ANALYZE_WAIT_S + ANALYZE_COMPUTE_S
# The lock wait ends (a retryable HeavyLockTimeout) well inside the actor limit; the compute
# allowance is sized for the longest accepted song (MAX_SONG_S = 600 s) at the slowest measured
# Beat This speed (22 s for a 30 s clip including the model load, 0.73 x real time, so 440 s,
# rounded up to 480); the slot TTL outlives the actor limit so a live holder never loses its slot.
ANALYZE_WAIT_S = 120
ANALYZE_COMPUTE_S = 480
ANALYZE_LIMIT_S = ANALYZE_WAIT_S + ANALYZE_COMPUTE_S + 60
HEAVY_TTL_S = 900

# The footage stages run inside plan 006's single draft job and take a heavy slot once per unit of
# work (one candidate's cut detection, sampling and embedding; one mezzanine encode), never for the
# whole batch, so a slot is never held longer than its TTL: HEAVY_TTL_S > *_HOLD_S. A hold covers
# longest child processes it spends (a test asserts it) plus a compute allowance.
FOOTAGE_WAIT_S = 120  # waiting for a slot: HeavyLockTimeout is retryable
VET_HOLD_S = 300  # sample (60 s) + scene detection and embeddings (hypothesis: 240 s, unmeasured)
NORMALIZE_HOLD_S = 300  # one encode (120 s) + the checks that follow (3 x 60 s probes)


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
    allowed_hosts: CsvList = _f(["localhost", "127.0.0.1"], "A,W")
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
    intermediate_ttl_days: int = _f(7, "A,M")
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
    # The password FILE path is not a secret; its content is never read by Settings (plan 003).
    backup_repo: str | None = _f(None, "host")
    backup_password_file: str | None = _f(None, "host")
    backup_staging_dir: str | None = _f(None, "host", doc="plan 003; default .data/backup-staging")
    backup_keep_daily: int = _f(7, "host")
    backup_keep_weekly: int = _f(4, "host")
    backup_keep_monthly: int = _f(6, "host")
    backup_allow_same_disk: Literal["yes", "no"] = _f("no", "host", doc="ARCH §23; plan 003 B5")
    next_public_app_origin: str | None = _f(None, "W")
    # Branch B of OQ-26 (plan 002): the browser calls the API directly at this origin.
    next_public_api_origin: str = _f("http://localhost:8000", "W", example="http://localhost:8000")
    fake_stock: bool = _f(False, "local/CI")
    fake_ml: bool = _f(False, "local/CI")
    fake_llm: bool = _f(False, "local/CI")
    # local/CI only: a directory of generated clips that FAKE_STOCK serves (make fake-stock)
    fake_stock_dir: str | None = _f(None, "K", doc="plan 005")
    # SEC-044 alarm: the estimated monthly LLM spend above which one warning is logged
    llm_monthly_budget_usd: float | None = _f(None, "K", doc="plan 005")
    # Not in ARCH §18 (proposed additions, plan 001 Step 2):
    broker_heartbeat_timeout_s: int = _f(60, "A,K,M", doc="plan 001")
    app_version: str = _f("dev", "all", doc="plan 001")
    # true only on the worker that serves the heavy queues, so one process owns settings:tuning
    tuning_publisher: bool = _f(False, "K", doc="plan 001")
    heavy_ttl_s: int = _f(
        HEAVY_TTL_S, "K", doc="plan 004; heavy-slot TTL, must exceed the analyze limit"
    )
    scratch_root: str = _f("/scratch", "K", doc="plan 004; per-job scratch directories")
    models_dir: str = _f("/opt/models", "K", doc="plan 004; model weights and their manifest")

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
    default: str | None = (
        None  # None = a required secret (CHANGE_ME in .env.example); else an optional setting
    )


# Compose-only variables (C10, SEC-133): read by compose, never by Settings.
COMPOSE_ONLY = (
    ComposeVar(name="POSTGRES_PASSWORD", doc="superuser password for the postgres container"),
    ComposeVar(name="POSTGRES_APP_PASSWORD", doc="password of role app_rw"),
    ComposeVar(name="POSTGRES_MIGRATOR_PASSWORD", doc="password of role migrator"),
    ComposeVar(name="REDIS_PASSWORD", doc="requirepass for redis"),
    ComposeVar(
        name="API_PORT",
        doc="host port of the api (default 8000; the restore scratch stack uses 18000)",
        default="8000",
    ),
    ComposeVar(
        name="WEB_PORT",
        doc="host port of the web shell (default 3000; the scratch stack uses 13000)",
        default="3000",
    ),
    ComposeVar(
        name="IMAGE_TAG",
        doc="tag of the saveclock-* images compose runs (default local; rollback: sha-<commit>)",
        default="local",
    ),
)
