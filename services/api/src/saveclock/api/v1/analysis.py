from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.api.deps import current_user, get_session
from saveclock.api.schemas.analysis import AnalysisOut, ConfidenceOut, SectionOut, SegmentOut
from saveclock.api.schemas.common import CONFLICT_RESPONSE, ERROR_RESPONSES
from saveclock.domain.confidence import band_of
from saveclock.models import Fallback
from saveclock.services.analysis import get_analysis
from saveclock.services.identity import CurrentUser

router = APIRouter(prefix="/projects", tags=["analysis"], responses=ERROR_RESPONSES)


@router.get("/{project_id}/analysis", operation_id="get_analysis", responses={**CONFLICT_RESPONSE})
async def get(
    project_id: UUID,
    user: Annotated[CurrentUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AnalysisOut:
    """409 `conflict` with `details.reason = not_ready` until the analysis exists."""
    view = await get_analysis(session, user.id, project_id)
    a, bm = view.analysis, view.analysis.beat_map
    return AnalysisOut(
        tempo_bpm=float(a.tempo_bpm),
        tempo_octave_adjust=a.tempo_octave_adjust,
        beats_s=view.beats_s,
        downbeats_s=view.downbeats_s,
        sections=[SectionOut(**s) for s in a.sections],
        energy_curve=a.energy_curve,
        waveform_peaks=a.waveform_peaks,
        low_confidence_ranges=a.low_confidence_ranges,
        confidence=ConfidenceOut(
            score=a.beat_confidence,
            band=band_of(a.beat_confidence),
            reasons=bm.get("confidence", {}).get("reasons", []),
        ),
        fallback=Fallback(a.fallback) if a.fallback else None,
        segment=SegmentOut(**bm["segment"]) if "segment" in bm else None,
        flags=view.project.flags,
    )
