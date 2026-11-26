import pytest

from tests.conftest import make_app


@pytest.mark.unit
def test_app_title() -> None:
    assert make_app(checks={}).title == "SaveClock API"
