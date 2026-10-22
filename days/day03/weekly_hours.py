from collections.abc import Iterable
from pathlib import Path

from context_example import read_shifts
from exceptions_example import Shift


def weekly_hours(shifts: Iterable[Shift]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for shift in shifts:
        emp = shift.emp_id
        current = totals.get(emp, 0)
        totals[emp] = current + shift.hours
    return totals


def overtime_employees(totals: dict[str, int], limit: int = 40) -> list[str]:

    return sorted(emp_id for emp_id, hours in totals.items() if hours > limit)


DATA_FILE = Path(__file__).parent / "shifts.csv"

if __name__ == "__main__":
    total = weekly_hours(read_shifts(DATA_FILE))
    print(total)
    print(f"the overtime employees are {overtime_employees(total)}")
