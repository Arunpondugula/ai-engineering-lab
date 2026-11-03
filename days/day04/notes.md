# Day 04 — Data foundations: NumPy, Pandas, real datasets

**Status: partial.** Topics 1–2 done. Topics 3–6 moved to the day each one is first needed:

| Topic | Moved to |
|---|---|
| 3. Memory profiling + dtype optimization | Day 8 (IEEE-CIS fraud data) |
| 4. Reshaping wide → long, joins | Day 11 (clustering M5 stores) |
| 5. Reading and cleaning nested JSONL | Day 19 (embedding Amazon reviews) |
| 6. Parquet vs CSV | Day 10 (saving features and the model) |

Files: `numpy_basics.py` (Topic 1 exercises), `profiling.ipynb` (Topic 2 on real M5 data).
Data: `data/raw/m5/`, `data/raw/amazon/` (not in Git).

## Topic 1 — NumPy arrays

### My numbers (Windows laptop, 16 GB RAM)

| Exercise | Result |
|---|---|
| Ex 1 memory, 10M ints | list 343 MB vs array 76 MB → list is **4.5x bigger** |
| Ex 1 speed, sum of 10M ints | Python loop 685 ms · `sum(list)` 85 ms · `arr.sum()` 7.7 ms → NumPy **89x faster** than the loop |
| Ex 2 dtype, M5-shaped 30,490 × 1,941 | int64 452 MB → int8 56 MB → **88% saved**, no data lost (max value 18) |
| Ex 3 overflow | int8 `[120, 10] + 10` → `[-126, 20]` · int16 `[30000] * 2` → `[-5536]` |
| Ex 5 revenue = units × price, 1,000 × 1,941 | loop 827 ms vs vectorized 4.4 ms → **188x faster** |
| Ex 6 zeros | 5.0% of item-days had zero sales (matches Poisson(3) ≈ 5%) |

Timings are single runs, so they are rough. The ratios are what matter.

### What I learned

**Why NumPy uses less memory than a list**
A Python list stores a pointer for each element, and each pointer leads to a full Python int object (~28 bytes) somewhere on the heap. A NumPy array stores only the raw values, side by side in one block, all with the same dtype. That's why it's smaller, and why it can only hold one data type.

**Choosing a dtype**
1. Find the max and min values the column can hold.
2. Think about what operations I'll run on it (sums, multiplication) and whether the results still fit.
3. Pick the smallest type that fits with headroom.

int8 = −128 to 127 · int16 = ±32,767 · int32 = ±2.1 billion · int64 = huge.
NumPy defaults to int64, so real data wastes memory until I set dtypes myself.

**Overflow**
Reductions like `sum()` and `mean()` upcast small ints to int64 automatically, so they're safe. Element-wise math (`+`, `*`) keeps the dtype, and if the result doesn't fit it wraps around silently with no error. Fix: convert to a bigger dtype before the risky math (`a.astype(np.int16) + 10`).

**Views vs copies**
A view points to the same memory as the original. A copy gets new memory.
- Slices (`x[2:6]`) give views.
- Boolean masks (`x[x > 5]`) and fancy indexing (`x[[0, 3]]`) give copies.

Changing a view changes the original. If I need to modify data without touching the original, use `.copy()`. Another trap: a small view of a huge array keeps the whole array in memory.

**axis (cross-out method)**
The axis I pass is the one that disappears. Write the shape, cross out that axis, and what's left is the result shape.
M5 `sales` is (30,490 items, 1,941 days):
- `sum(axis=1)` → removes days → (30,490,) → one total per item
- `sum(axis=0)` → removes items → (1,941,) → one total per day

Sanity check: ask "how many answers do I expect?" and make sure the shape matches.

**Vectorization and broadcasting**
Vectorized code is fast because the loop runs inside NumPy's C code instead of Python. Broadcasting lets NumPy combine different shapes without copying. `prices[:, None]` turns shape (1000,) into (1000, 1), so each item's price stretches across all 1,941 days. Without it, (1000,) lines up with the days axis and fails.

**rng.poisson**
`np.random.default_rng(42)` creates a seeded generator, so I get the same numbers every run. `rng.poisson(lam=3, size=(rows, cols))` fills an array of that shape with random whole-number counts ≥ 0 that average `lam`. It's a good stand-in for daily sales, but real M5 has far more zeros (intermittent demand), which I'll measure in the Pandas part.

### What took longest
The new terms around vectors and embeddings. Those are covered properly on Days 13, 16, 19 and 25, so I parked Ex 7 for Day 25.

### Where this shows up in my projects
- **ShelfSense:** embeddings are float32 arrays. On Day 36 I'll compare float32 vs float16 vs binary to cut index memory.
- **ShiftWise:** M5 sales become hourly staffing needs, so I need the right dtypes to keep it in RAM.
- **LedgerGuard:** fraud feature matrices and vectorized feature math.
- **Anywhere:** big datasets on a 16 GB laptop. Choosing dtypes is what keeps them in memory.


## Topic 2 — Pandas DataFrames

### My findings (real M5 data, Pandas 3.1.0)

| Check | Result |
|---|---|
| Text dtype | `str` (Pandas 3 string dtype, not Python `object`) |
| `sales` memory | ~455 MB, almost all from the 1,941 int64 day columns; the 6 text columns are only a few MB |
| Calendar | 1,969 days; 162 have an event, only 5 have two. A missing `event_name_1` means no event on that day |
| Catalog | FOODS 14,370 · HOUSEHOLD 10,470 · HOBBIES 5,650 rows. Every store carries the same 3,049 items (3,049 × 10 = 30,490) |
| Day-1 sales | CA sold the most: 14,195 units |
| Price by store | Store averages differ by only $0.09, so pricing looks mostly national |
| Label alignment | Adding d_1 (all stores) + d_2 (CA only) gave NaN for the 6 TX and WI stores, and the result became float64 |
| Safe update | Changing a `.copy()` set FOODS_3 d_1 to 0; the original `sales` stayed at 7,080 |

### What I learned

**Series and DataFrame**
A Series is one column: a NumPy array plus an Index of labels. A DataFrame is a set of Series that share one Index, and each column keeps its own dtype. That's how a table holds text, ints and floats together.

**Why column operations are fast and row loops are slow**
Each column is one contiguous array with one dtype, so `sales["d_1"].sum()` runs a C loop over it. A row cuts across all 1,947 columns with different dtypes, so `iterrows()` has to build a new Series object for every row. Use column operations, not row loops.

**Index and label alignment**
Pandas combines data by label, not by position. Labels without a partner become NaN, and an int column turns into float64 because classic ints can't hold NaN. After every combine or merge, check `isna().sum()` and compare labels with `a.index.difference(b.index)`. Only use `fill_value=0` when missing really means zero.

**Missing values: unknown vs absent**
Missing can mean the value exists but wasn't recorded (unknown), or there is nothing to record (absent, like a day with no event). Absent values usually become a real value like `"none"` or a 0/1 flag. Unknown values get imputed or flagged.

**loc vs iloc**
`loc` selects by label, `iloc` by position. Filtering keeps the original labels (my CA + FOODS filter started at label 1612), so `loc[0]` can fail after a filter. Use `iloc` for positions or `reset_index(drop=True)` for fresh labels.

**Filtering**
Combine conditions with `&`, `|`, `~`, each wrapped in parentheses. `and` / `or` raise an error on Series.

**Safe updates**
- Change the original in one step: `sales.loc[mask, "d_1"] = 0`.
- Change an independent subset: `sub = sales[mask].copy()`, then `sub.loc[...] = value`.
- Chained assignment `sales[mask]["d_1"] = 0` writes to a temporary copy and never changes `sales`. Pandas 3 raises `ChainedAssignmentError`.

**When a CSV won't fit in RAM**
Pandas often needs 5–10× the file size in memory, and default dtypes (int64, float64, full strings) waste space. Load a small sample with `nrows=` first to see the ranges, then load with `usecols=` and `dtype=` so the big version never exists. For files that still don't fit, read in `chunksize=` pieces, convert to Parquet, or query with DuckDB.

**Pandas vs other tools**
- Pandas: data fits in memory, exploration, ML ecosystem.
- Polars: fits on one machine but Pandas is too slow; multi-threaded, lazy query planning.
- DuckDB: SQL directly on Parquet or CSV, including files bigger than RAM; reads only the columns a query needs.
- Spark: too big for one machine, runs on a cluster.

**Paths in real projects**
Notebooks run from their own folder, so relative paths break. In the lab I find the repo root and use `data/raw/` for untouched downloads and `data/processed/` for cleaned output. In production, the data location comes from config (an environment variable), not hardcoded paths.
