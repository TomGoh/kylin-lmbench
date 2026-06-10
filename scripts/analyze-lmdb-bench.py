#!/usr/bin/env python3
"""Summarize results produced by scripts/lmdb-pkvm-bench.sh."""

from __future__ import annotations

import csv
import statistics as st
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results" / "lmdb-bench"
MODES = ["kvmoff", "vhe", "nvhe", "pkvm"]


def read_one(path: Path) -> dict[str, str] | None:
    if not path.exists():
        return None
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    return rows[0] if rows else None


def median_metric(mode: str, prefix: str, metric: str) -> float | None:
    values: list[float] = []
    d = RESULTS / mode
    for path in sorted(d.glob(f"{prefix}-run*.csv")):
        row = read_one(path)
        if row and row.get(metric):
            values.append(float(row[metric]))
    if not values:
        return None
    return st.median(values)


def prepare_metric(mode: str, metric: str) -> float | None:
    row = read_one(RESULTS / mode / "prepare.csv")
    if not row or not row.get(metric):
        return None
    return float(row[metric])


def fmt(v: float | None, unit: str = "") -> str:
    if v is None:
        return "-"
    if abs(v) >= 1000:
        return f"{v:.1f}{unit}"
    return f"{v:.3f}{unit}"


def pct(a: float | None, b: float | None, higher_is_better: bool) -> str:
    if a is None or b is None or b == 0:
        return "-"
    raw = 100.0 * (a - b) / b
    if higher_is_better:
        return f"{raw:+.2f}%"
    return f"{raw:+.2f}%"


def main() -> int:
    modes = [m for m in MODES if (RESULTS / m).exists()]
    if len(sys.argv) > 1:
        modes = sys.argv[1:]
    if not modes:
        print(f"No results under {RESULTS}", file=sys.stderr)
        return 1

    rows = [
        ("prepare ops/s", lambda m: prepare_metric(m, "ops_per_s"), True),
        ("openclose us/op", lambda m: median_metric(m, "openclose", "us_per_openclose"), False),
        ("read ops/s", lambda m: median_metric(m, "read", "ops_per_s"), True),
        ("read ns/op", lambda m: median_metric(m, "read", "ns_per_op"), False),
        ("write ops/s", lambda m: median_metric(m, "write", "ops_per_s"), True),
        ("write ns/op", lambda m: median_metric(m, "write", "ns_per_op"), False),
    ]

    data = {name: {m: getter(m) for m in modes} for name, getter, _ in rows}

    print("# LMDB benchmark summary\n")
    print("| metric | " + " | ".join(modes) + " | pkvm vs kvmoff | pkvm vs vhe |")
    print("|---|" + "---|" * (len(modes) + 2))
    for name, _, higher in rows:
        vals = data[name]
        cells = [fmt(vals.get(m)) for m in modes]
        pk = vals.get("pkvm")
        k = vals.get("kvmoff")
        vhe = vals.get("vhe")
        print("| " + " | ".join([name] + cells + [pct(pk, k, higher), pct(pk, vhe, higher)]) + " |")

    print("\nNotes:")
    print("- ops/s: positive delta means pkvm is faster; ns/op and us/op: positive delta means pkvm is slower.")
    print("- write defaults use MDB_NOSYNC/MDB_NOMETASYNC to reduce storage flush dominance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
