import pytest

from saveclock.main import create_app


@pytest.mark.unit
def test_app_title() -> None:
    assert create_app().title == "SaveClock API"
