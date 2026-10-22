import pytest
from exceptions_example import Shift
from weekly_hours import overtime_employees, weekly_hours


# Totals are added up correctly for each employee
def test_weekly_hours_multiple_employees() -> None:
    shifts = [
        Shift("E1", 1, 8, 17),
        Shift("E1", 2, 9, 18),
        Shift("E2", 3, 7, 19),
    ]
    assert weekly_hours(shifts) == {"E1": 18, "E2": 12}


# No shifts returns an empty dict, not an error
def test_weekly_hours_empty() -> None:
    assert weekly_hours([]) == {}


# Only hours over 40 count as overtime (39 and 40 are not, 41 is)
@pytest.mark.parametrize(
    ("hours", "expected"),
    [
        (39, []),
        (40, []),
        (41, ["E1"]),
    ],
)
def test_overtime_boundary(hours: int, expected: list[str]) -> None:
    assert overtime_employees({"E1": hours}) == expected


# Overtime IDs come back sorted, and employees under the limit are left out
def test_overtime_sorted() -> None:
    totals = {"E3": 50, "E1": 45, "E2": 12}
    assert overtime_employees(totals) == ["E1", "E3"]


# Works with a generator, so it can take read_shifts output in one pass
def test_weekly_hours_accepts_generator() -> None:
    shifts = [Shift("E1", 1, 8, 17), Shift("E1", 2, 9, 18)]
    gen = (s for s in shifts)
    assert weekly_hours(gen) == {"E1": 18}
