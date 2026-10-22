from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Shift:
    emp_id: str
    day: int
    start_hour: int
    end_hour: int

    @property
    def hours(self) -> int:
        return self.end_hour - self.start_hour


def long_shifts(shifts: list[Shift], min_hours: int) -> Iterator[Shift]:
    for shift in shifts:
        if shift.hours >= min_hours:
            yield shift


shifts = [
    Shift("E1", 1, 8, 17),
    Shift("E1", 2, 9, 18),
    Shift("E2", 3, 7, 19),
]

total = sum(shift.hours for shift in shifts)
print(f"Total hours, all employees: {total}")

employee_ids = {shift.emp_id for shift in shifts}
hours_by_employee = {
    emp_id: sum(shift.hours for shift in shifts if shift.emp_id == emp_id)
    for emp_id in employee_ids
}
print(f"Hours by employee: {hours_by_employee}")

print("Shifts of 9+ hours:")
for shift in long_shifts(shifts, 9):
    print(f"  {shift}")
