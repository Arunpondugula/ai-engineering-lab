import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from exceptions_example import InvalidShiftError, Shift, parse_shift


@contextmanager
def timer(label: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"{label}: {elapsed_ms:.2f} ms")


def read_shifts(path: Path) -> Iterator[Shift]:
    with open(path, encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            try:
                yield parse_shift(line.strip())
            except InvalidShiftError as e:
                print(f"ERROR line {line_number}: {e}")


DATA_FILE = Path(__file__).parent / "shifts.csv"

if __name__ == "__main__":
    with timer("parse shifts"):
        for shift in read_shifts(DATA_FILE):
            print(f"OK: {shift} -> {shift.hours} hours")
