from typing import Annotated

from fastapi import APIRouter, Depends

from saveclock.api.deps import get_deps
from saveclock.api.schemas.common import ERROR_RESPONSES
from saveclock.api.schemas.health import HealthLive, HealthReady
from saveclock.container import Deps
from saveclock.errors import UpstreamUnavailable
from saveclock.services.health import readiness

router = APIRouter(prefix="/health", tags=["health"], responses=ERROR_RESPONSES)


@router.get("/live", operation_id="health_live")
async def live() -> HealthLive:
    return HealthLive(status="ok")


@router.get("/ready", operation_id="health_ready", responses={503: ERROR_RESPONSES[500]})
async def ready(deps: Annotated[Deps, Depends(get_deps)]) -> HealthReady:
    checks = await readiness(deps.checks)
    if any(v != "ok" for v in checks.values()):
        raise UpstreamUnavailable("not ready", {"checks": checks})
    return HealthReady(status="ok", checks=checks)
