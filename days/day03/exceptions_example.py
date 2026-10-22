"""Shift validation and parsing

File: days/day03/shift_errors.py. Don’t name it after a library.

Build these four things:

A custom exception. Define InvalidShiftError that inherits from Exception, with a one-line docstring.
The Shift dataclass (frozen=True, slots=True) with fields emp_id, day, start_hour, end_hour, plus:
the hours property
a __post_init__ that raises InvalidShiftError with a clear message when:
start_hour or end_hour is outside 0–24
end_hour <= start_hour
parse_shift(line: str) -> Shift
Input looks like "E1,1,8,17". Split it on commas into 4 parts.
Convert day, start_hour and end_hour to int.
If a conversion fails (that’s a ValueError), raise InvalidShiftError(...) from e with a message showing the bad line.
Return the Shift.
A test loop over these three lines:
python
   lines = ["E1,1,8,17", "E1,1,17,8", "E1,1,eight,17"]

For each line: try parse_shift. On success print the shift and its hours. On InvalidShiftError, print the error message. The loop must keep going after an error, so all three lines get processed.

Expected output, roughly (your messages can be worded differently):

OK: Shift(emp_id='E1', day=1, start_hour=8, end_hour=17) -> 9 hours
ERROR: end_hour (8) must be after start_hour (17)
ERROR: could not parse numbers in line 'E1,1,eight,17'"""

from dataclasses import dataclass


class InvalidShiftError(Exception):
    """custom exception class to catch the errors in Shifts"""


@dataclass(frozen=True, slots=True)
class Shift:
    emp_id: str
    day: int
    start_hour: int
    end_hour: int

    @property
    def hours(self) -> int:
        return self.end_hour - self.start_hour

    def __post_init__(self) -> None:
        if not (0 <= self.start_hour <= 24):
            raise InvalidShiftError(
                f"start hour {self.start_hour} must be between 0 and 24"
            )
        if not (0 <= self.end_hour <= 24):
            raise InvalidShiftError(
                f"end hour ({self.end_hour}) must be between 0 and 24"
            )
        if self.end_hour <= self.start_hour:
            raise InvalidShiftError(
                f"end hour ({self.end_hour}) must be greater than start hour"
            )


def parse_shift(line: str) -> Shift:
    try:
        emp_id, day, start, end = line.split(",")
        shift = Shift(emp_id, int(day), int(start), int(end))
    except ValueError as e:
        raise InvalidShiftError(f"could not parse line {line!r}: {e}") from e

    return shift


lines = ["E1,1,8,17", "E1,1,17,8", "E1,1,eight,17", "E1,1,8"]

if __name__ == "__main__":
    for line in lines:
        try:
            r = parse_shift(line)
            print(f"OK: {r} -> {r.hours}")
        except InvalidShiftError as e:
            print(f"ERROR: {e}")
