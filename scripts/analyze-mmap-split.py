#!/usr/bin/env python3
"""Summarize results from scripts/mmap-split-bench.sh."""

from __future__ import annotations

import csv
import statistics as st
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results" / "mmap-split"


def rows_for(mode: str) -> list[dict[str, str]]:
    path = RESULTS / f"{mode}.csv"
    rows: list[dict[str, str]] = []
    with path.open(newline="") as f:
        filtered = (line for line in f if not line.startswith("#"))
        for row in csv.DictReader(filtered):
            rows.append(row)
    return rows


def median(xs: list[float]) -> float:
    return st.median(xs) if xs else float("nan")


def mad_pct(xs: list[float]) -> float:
    if not xs:
        return float("nan")
    m = median(xs)
    if m == 0:
        return 0.0
    return 100.0 * st.median(abs(x - m) for x in xs) / m


def fmt(v: float, digits: int = 3) -> str:
    if v != v:
        return "-"
    return f"{v:.{digits}f}"


def main() -> int:
    modes = sys.argv[1:] or [p.stem for p in sorted(RESULTS.glob("*.csv"))]
    if not modes:
        print(f"No mmap-split results under {RESULTS}", file=sys.stderr)
        return 1

    data = {mode: rows_for(mode) for mode in modes}
    keys = sorted({
        (row["bench_mode"], row["size_mb"])
        for rows in data.values()
        for row in rows
    }, key=lambda x: (x[0], float(x[1])))

    print("# mmap split summary: median per_iter_us (MAD%)\n")
    print("| bench_mode | size_mb | " + " | ".join(modes) + " | pkvm vs nvhe |")
    print("|---|---:|" + "---|" * (len(modes) + 1))

    medians: dict[tuple[str, str, str], float] = {}
    for bench_mode, size in keys:
        cells: list[str] = []
        for mode in modes:
            xs = [
                float(row["per_iter_us"])
                for row in data[mode]
                if row["bench_mode"] == bench_mode and row["size_mb"] == size
            ]
            m = median(xs)
            medians[(mode, bench_mode, size)] = m
            cells.append(f"{fmt(m)} ({fmt(mad_pct(xs), 2)}%)")

        delta = "-"
        if "pkvm" in modes and "nvhe" in modes:
            p = medians[("pkvm", bench_mode, size)]
            n = medians[("nvhe", bench_mode, size)]
            if n == n and n != 0:
                delta = f"{100.0 * (p - n) / n:+.2f}%"
        print("| " + " | ".join([bench_mode, size] + cells + [delta]) + " |")

    print("\n# Notes")
    print("- per_iter_us means the timed region selected by bench_mode, not always the full mmap/touch/munmap sequence.")
    print("- For *_touch_* modes, per_touch_ns in the raw CSV is often more useful when comparing different touch geometries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
