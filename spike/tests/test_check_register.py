from pathlib import Path

from spike.check_register import cell_count, check, main

GOOD = "| a | b | c | d | e | f |\n|---|---|---|---|---|---|\n| 1 | 2 | 3 | 4 | 5 | 6 |\n| 1 | 2 | 3 | 4 | 5 | x \\| y |\n"


def test_pass() -> None:
    rows, errors = check(GOOD)
    assert rows == 2
    assert errors == []


def test_fail_short_row() -> None:
    rows, errors = check(GOOD + "| 1 | 2 | 3 |\n")
    assert rows == 3
    assert len(errors) == 1 and "3 cells" in errors[0]


def test_cell_count_escaped_pipe() -> None:
    assert cell_count("| a | b \\| c |") == 2


def test_main_exit_codes(tmp_path: Path) -> None:
    ok = tmp_path / "ok.md"
    ok.write_text(GOOD)
    bad = tmp_path / "bad.md"
    bad.write_text(GOOD + "| 1 | 2 |\n")
    assert main(["x", str(ok)]) == 0
    assert main(["x", str(bad)]) == 1
    assert main(["x"]) == 2
