from pathlib import Path

import pytest
from context_example import read_shifts
from exceptions_example import InvalidShiftError, Shift, parse_shift


# 1. A valid line parses into the right Shift, with the right hours
def test_parse_valid_line() -> None:
    shift = parse_shift("E1,1,8,17")
    assert shift == Shift("E1", 1, 8, 17)  # compare the whole Shift (see example 2)
    assert shift.hours == 9  # check .hours


# 2. Each bad line raises InvalidShiftError
@pytest.mark.parametrize(
    "line",
    [
        "E1,1,17,25",
        "E1,1,17,8",
        "E1,1,eight,17",
        "E1,1,8",
    ],  # the 4 bad lines: end before start, "eight", only 3 parts, hour 25
)
def test_parse_rejects_bad_lines(line: str) -> None:
    with pytest.raises(InvalidShiftError):
        parse_shift(line)


# 3. Creating a Shift directly with end <= start raises, matching a key phrase
def test_shift_end_before_start() -> None:
    with pytest.raises(InvalidShiftError, match="greater than start hour"):
        Shift("E1", 1, 17, 8)


# 4. read_shifts skips bad lines and returns only the good one
def test_read_shifts_skips_bad_lines(tmp_path: Path) -> None:
    csv_file = tmp_path / "shifts.csv"
    csv_file.write_text(
        "E1,1,8,17\nE1,1,17,8\nE1,1,eight,17\n", encoding="utf-8"
    )  # 1 good line + 2 bad lines, separated by \n
    shifts = list(read_shifts(csv_file))
    assert len(shifts) == 1  # exactly 1 shift
