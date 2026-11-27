"""`failure_code`: the code of the `failed` event, from the status a project moved to."""

import pytest

from saveclock.errors import RETRYABLE, ErrorCode
from saveclock.services.project_state import FAILED_STAGE, failure_code


def test_a_render_that_failed_verification_has_its_own_retryable_code() -> None:
    code = failure_code("failed_render", "verification_failed")
    assert code is ErrorCode.VERIFICATION_FAILED
    assert code in RETRYABLE


@pytest.mark.parametrize("reason", ["retries_exhausted", "plan_invalid", None])
def test_any_other_render_failure_is_an_internal_error(reason: str | None) -> None:
    assert failure_code("failed_render", reason) is ErrorCode.INTERNAL_ERROR


def test_only_a_render_fails_verification() -> None:
    assert failure_code("failed_analysis", "verification_failed") is ErrorCode.INTERNAL_ERROR
    assert failure_code("failed_plan", "verification_failed") is ErrorCode.INTERNAL_ERROR


def test_the_existing_codes_are_unchanged() -> None:
    assert failure_code("rejected", None) is ErrorCode.FILE_REJECTED
    assert failure_code("failed_plan", "no_usable_clips") is ErrorCode.STOCK_UNAVAILABLE
    assert failure_code("failed_plan", "stock_unavailable") is ErrorCode.STOCK_UNAVAILABLE
    assert failure_code("failed_analysis", "retries_exhausted") is ErrorCode.INTERNAL_ERROR


def test_a_failed_render_is_announced_as_the_render_stage() -> None:
    assert FAILED_STAGE["failed_render"] == "render"
