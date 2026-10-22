# Day 3 · Python essentials, written by a Java dev

Done when: three scripts with passing pytest tests ✅ (14 passed)

Files: `shifts_demo.py`, `exceptions_example.py`, `context_example.py`, `weekly_hours.py`, `shifts.csv`, `test_shifts.py`, `test_weekly_hours.py`

---

## 1. Type hints

Written at the definition, like Java. Python does NOT enforce them at runtime.

```python
def double_it(x: int) -> int:
    return x * 2

double_it("ab")   # returns "abab", no error
```

Who checks them:

| Where | Tool | When |
|---|---|---|
| Editor + CI | mypy, pyright (Pylance) | before the code runs |
| Runtime | Pydantic, FastAPI | on data going through their models |

Rules:
- Always annotate function params, returns, class fields. Skip obvious locals.
- Hint the TYPE, not the variable: `list[Shift]`, not `list[shifts]`.
- Accept loose, return specific: `Iterable[Shift]` in, `Iterator[Shift]` out.

```
Iterable   → anything you can loop over (list, set, dict, file, generator)
 └ Iterator  → has next(), gets used up (file objects, generators)
    └ Generator → made with yield or ( ... for ... )
```

Java: like generics, but nothing checks them unless you run a checker.

---

## 2. Dataclasses

`@dataclass` generates `__init__`, `__repr__`, `__eq__` from the fields.

```python
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class Shift:
    emp_id: str
    day: int
    start_hour: int
    end_hour: int
    roles: list[str] = field(default_factory=list)   # never = []

    @property
    def hours(self) -> int:                # computed, used like a field: shift.hours
        return self.end_hour - self.start_hour

    def __post_init__(self) -> None:       # runs right after __init__: validation
        if self.end_hour <= self.start_hour:
            raise InvalidShiftError("end hour must be greater than start hour")
```

| Option | Effect | Java |
|---|---|---|
| `@dataclass` | boilerplate generated | Lombok `@Data` |
| `frozen=True` | immutable, hashable | `record` |
| `slots=True` | less memory per object | — |
| `__post_init__` | validate on creation | record compact constructor |

- `==` compares values (like `.equals()`), `is` checks same object (like Java `==`).
- No validation, no type conversion → **Pydantic at the edges, dataclasses inside.**

Mutable default trap (plain functions, no error from Python):

```python
def add_role(role, roles=[]):      # [] created ONCE, shared by every call
    roles.append(role)
    return roles

add_role("cashier")
add_role("stocker")                # ['cashier', 'stocker']  ← bug

# fix
def add_role(role: str, roles: list[str] | None = None) -> list[str]:
    if roles is None:
        roles = []
    roles.append(role)
    return roles
```

---

## 3. Comprehensions and generators

```python
[s.hours for s in shifts if s.hours > 8]     # list   (built now)
{s.emp_id: s for s in shifts}                 # dict
{s.emp_id for s in shifts}                    # set
(s.hours for s in shifts)                     # generator (lazy, built later)
sum(s.hours for s in shifts)                  # sum needs a COLLECTION, not one value
```

Generator function:

```python
def long_shifts(shifts: Iterable[Shift], min_hours: int) -> Iterator[Shift]:
    for shift in shifts:
        if shift.hours >= min_hours:
            yield shift                # hand back one, pause here
```

Calling a generator function runs NONE of its code. It starts at the first `next()`:

```python
def nums():
    print("start")
    yield 1
    print("middle")
    yield 2

g = nums()        # nothing printed
next(g)           # start → 1
next(g)           # middle → 2
```

- Single use: second `sum(gen)` returns 0, no error.
- `print(gen)` shows `<generator object ...>`. Loop over it or `list(gen)` to see items.
- List when: need data again, `len()`, indexing. Generator when: one pass over big data.

| Size of 1M squares | |
|---|---|
| list `[...]` | ~8 MB |
| generator `(...)` | ~200 bytes |

Single-pass tally (instead of looping once per employee):

```python
totals: dict[str, int] = {}
for shift in shifts:
    totals[shift.emp_id] = totals.get(shift.emp_id, 0) + shift.hours
```

`.get(key, 0)` only READS: value if present, else 0. Nothing is written. Java: `getOrDefault`.

Dict loops: `for k in d` (keys), `d.values()`, `d.items()` (key, value) — Java `entrySet()`.

Java: comprehensions ≈ Streams. Generator ≈ lazy Stream / Iterator without the boilerplate.

---

## 4. Exceptions

```python
try:
    n = int(text)
except ValueError:
    print("bad")              # only if that error happened
else:
    print("good", n)          # only if NO error
finally:
    print("done")             # always
```

Custom exception + chaining:

```python
class InvalidShiftError(Exception):
    """Raised when shift data breaks a scheduling rule."""

def parse_shift(line: str) -> Shift:
    try:
        emp_id, day, start, end = line.split(",")
        return Shift(emp_id, int(day), int(start), int(end))
    except ValueError as e:
        raise InvalidShiftError(f"could not parse line {line!r}: {e}") from e
```

One `try` is enough: `{e}` already says which value failed.

```
could not parse line 'E1,1,eight,17': invalid literal for int() with base 10: 'eight'
could not parse line 'E1,1,8': not enough values to unpack (expected 4, got 3)
```

Hierarchy (catch the most specific one):

```
BaseException
 ├── KeyboardInterrupt, SystemExit     ← never catch by accident
 └── Exception
      ├── ValueError, TypeError, KeyError, OSError
      └── InvalidShiftError (mine)
```

Rules:
- Never `except:` or `except Exception: pass`. It hides real bugs (mine hid an `r.hour` typo).
- Keep `try` small. Log once, where you handle it.
- Retry 429 (rate limited, temporary). Never retry 400 (request is wrong).

| Python | Java |
|---|---|
| `raise X(...)` | `throw new X(...)` |
| `raise X(...) from e` | `new X(msg, cause)` |
| `else:` | no equivalent |
| no checked exceptions | `throws` |

---

## 5. Context managers

Setup at the start of `with`, cleanup at the end — **even if the block raises**.

```python
with open(path, encoding="utf-8") as f:   # always utf-8 on Windows (default is cp1252)
    for line in f:
        ...
# file closed here
```

Write your own with `@contextmanager` — one `yield`, wrapped in `try/finally`:

```python
@contextmanager
def timer(label: str) -> Iterator[None]:
    start = time.perf_counter()        # SETUP   (__enter__)
    try:
        yield                          # the with-block runs here
    finally:
        print(f"{label}: {(time.perf_counter() - start) * 1000:.2f} ms")   # CLEANUP (__exit__)
```

Order when the block raises:

```
start parse  →  working  →  end parse (cleanup)  →  caught: bad line (outer except)
```

`return` leaves the `with`, `yield` pauses inside it:

```python
# BROKEN: file closes BEFORE the first line is read
def read_lines(path):
    with open(path, encoding="utf-8") as f:
        return (line.strip() for line in f)

# OK: lazy, file stays open until the last line
def read_lines(path) -> Iterator[str]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            yield line.strip()

# OK: eager, [ ] reads everything while the file is open
def read_lines(path) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f]
```

Catch inside the generator so one bad line doesn't kill it:

```python
def read_shifts(path: Path) -> Iterator[Shift]:
    with open(path, encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            try:
                yield parse_shift(line.strip())
            except InvalidShiftError as e:
                print(f"ERROR line {line_number}: {e}")
```

Three different things:
- `with` → setup/cleanup
- file object → readable line by line (an iterator)
- generator → `yield` / `( ... )`

Java: try-with-resources + `AutoCloseable`.

---

## 6. Modules and packages

- Module = `.py` file. Package = folder (+ `__init__.py`).
- Import order (`sys.path`): script's folder → PYTHONPATH → stdlib → installed packages. NOT parent folders.
- Never name a file after a library (`dataclasses.py` hid the real module).
- Importing runs all top-level code once. Use the main guard:

```python
if __name__ == "__main__":     # runs when executed, skipped when imported
    ...
```

- No side effects at import (DB connect, model load, API call) → put them in a function.
- Paths relative to the script, not the terminal:

```python
DATA_FILE = Path(__file__).parent / "shifts.csv"
```

| Python | Java |
|---|---|
| `sys.path` | classpath |
| `if __name__ == "__main__":` | `public static void main` |
| top-level code on import | `static {}` block |
| `_helper` | private (convention only) |

---

## 7. pytest

```
uv add --dev pytest
uv run pytest days/day03 -v
```

Discovery: files `test_*.py`, functions `test_*`.

```python
def test_parse_valid_line() -> None:
    assert parse_shift("E1,1,8,17") == Shift("E1", 1, 8, 17)   # dataclass __eq__

def test_end_before_start() -> None:
    with pytest.raises(InvalidShiftError, match="greater than start hour"):   # match, not matches
        Shift("E1", 1, 17, 8)

@pytest.mark.parametrize(
    ("hours", "expected"),
    [(39, []), (40, []), (41, ["E1"])],      # pytest calls the test once per tuple
)
def test_overtime_boundary(hours: int, expected: list[str]) -> None:
    assert overtime_employees({"E1": hours}) == expected

def test_read_shifts(tmp_path: Path) -> None:          # built-in fixture: temp folder
    csv_file = tmp_path / "shifts.csv"
    csv_file.write_text("E1,1,8,17\nE1,1,17,8\n", encoding="utf-8")
    assert len(list(read_shifts(csv_file))) == 1
```

- `pytest.raises` FAILS if nothing is raised. try/except in a test would pass silently.
- Don't call real LLM APIs in tests: cost, slow, flaky, non-deterministic → mock.
- Green only means the tests you wrote passed. Check the count.

| pytest | JUnit 5 |
|---|---|
| `assert a == b` | `assertEquals` |
| `pytest.raises` | `assertThrows` |
| `parametrize` | `@ParameterizedTest` |
| fixture | `@BeforeEach` / DI |
| `tmp_path` | `@TempDir` |

---

## Bugs I hit today

| Bug | Lesson |
|---|---|
| `sum(shift.hours)` → `'int' object is not iterable` | `sum` needs a collection |
| `print(generator)` showed the object | generators are lazy |
| file named `dataclasses.py` → circular import error | don't shadow library names |
| methods at column 0, outside the class | indentation is the braces |
| `if start or end > 24` always true | each value needs its own comparison |
| bare `except:` hid `r.hour` typo | catch specific exceptions |
| `list[shifts]` | hint the type, not the variable |
| `matches=` in `pytest.raises` | it's `match=` |
| good line in the bad-lines test | `pytest.raises` caught my test bug |
| 6 passed instead of 7 | check the test count |

## Moved to later days
- Retry with backoff → Day 6
- TTL cache → Day 36 (ShelfSense semantic cache), Day 86 (LedgerGuard Redis TTLs)