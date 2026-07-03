#!/usr/bin/env python3
"""Parse Pixel overview-early raw data and compute protected-vs-nvhe medians."""

from __future__ import annotations

import argparse
import csv
import re
import statistics
from pathlib import Path


SECTION_RE = re.compile(r"^### section=(?P<section>\S+)\s+label=(?P<label>\S+)$")
LAT_RE = re.compile(
    r"^size_mb=(?P<size>[0-9.]+)\s+iters=(?P<iters>\d+)\s+total_ns=(?P<total>[0-9.]+)\s+"
    r"per_iter_ns=(?P<per_iter_ns>[0-9.]+)\s+per_iter_us=(?P<per_iter_us>[0-9.]+)$"
)
LAT_MEM_RE = re.compile(r"^(?P<range>[0-9.]+)\s+(?P<ns>[0-9.]+)$")
BW_RE = re.compile(r"^(?P<mb>[0-9.]+)\s+(?P<mbps>[0-9.]+)$")

MEAS_FIELDS = [
    "mode",
    "family",
    "label",
    "operation",
    "size_mb",
    "run",
    "metric",
    "value",
    "unit",
]
KEY_FIELDS = ["family", "operation", "size_mb", "metric", "unit"]


def append(rows: list[dict[str, str]], **kwargs: object) -> None:
    row = {key: "" for key in MEAS_FIELDS}
    for key, value in kwargs.items():
        row[key] = str(value)
    rows.append(row)


def parse_run_from_label(label: str) -> str:
    match = re.search(r"-run-(\d+)$", label)
    return match.group(1) if match else ""


def parse_lat_mmap(path: Path, mode: str, rows: list[dict[str, str]]) -> None:
    label = ""
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.strip()
        section = SECTION_RE.match(line)
        if section:
            label = section.group("label")
            continue
        match = LAT_RE.match(line)
        if not match:
            continue
        data = match.groupdict()
        append(
            rows,
            mode=mode,
            family="lat_mmap_precise",
            label=label,
            operation="mmap_write_touch_unmap",
            size_mb=data["size"],
            run=parse_run_from_label(label),
            metric="per_iter",
            value=data["per_iter_us"],
            unit="us",
        )


def parse_mmap_split(path: Path, mode: str, rows: list[dict[str, str]]) -> None:
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for data in reader:
            append(
                rows,
                mode=mode,
                family="mmap_split",
                label=f"{data['bench_mode']}-{data['size_mb']}MB-run-{data['run']}",
                operation=data["bench_mode"],
                size_mb=data["size_mb"],
                run=data["run"],
                metric="per_iter",
                value=data["per_iter_us"],
                unit="us",
            )


def parse_lat_mem(path: Path, mode: str, rows: list[dict[str, str]]) -> None:
    label = ""
    values_for_section: list[tuple[str, str]] = []

    def flush() -> None:
        if not label:
            return
        chosen = None
        for range_mb, ns in values_for_section:
            if abs(float(range_mb) - 64.0) < 1e-9:
                chosen = (range_mb, ns)
        if chosen is None and values_for_section:
            chosen = values_for_section[-1]
        if chosen is None:
            return
        append(
            rows,
            mode=mode,
            family="lat_mem_rd",
            label=label,
            operation="load_stride_128",
            size_mb=chosen[0],
            run=parse_run_from_label(label),
            metric="load_latency",
            value=chosen[1],
            unit="ns",
        )

    for raw in path.read_text(errors="replace").splitlines():
        line = raw.strip()
        section = SECTION_RE.match(line)
        if section:
            flush()
            label = section.group("label")
            values_for_section = []
            continue
        match = LAT_MEM_RE.match(line)
        if match:
            values_for_section.append((match.group("range"), match.group("ns")))
    flush()


def parse_bandwidth(path: Path, mode: str, family: str, rows: list[dict[str, str]]) -> None:
    label = ""
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.strip()
        section = SECTION_RE.match(line)
        if section:
            label = section.group("label")
            continue
        match = BW_RE.match(line)
        if not match or not label:
            continue
        operation = label.rsplit("-64m-run-", 1)[0]
        append(
            rows,
            mode=mode,
            family=family,
            label=label,
            operation=operation,
            size_mb=match.group("mb"),
            run=parse_run_from_label(label),
            metric="bandwidth",
            value=match.group("mbps"),
            unit="MB/s",
        )


def parse_mode_dir(mode_dir: Path, mode: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if (mode_dir / "lat_mmap_precise.txt").exists():
        parse_lat_mmap(mode_dir / "lat_mmap_precise.txt", mode, rows)
    if (mode_dir / "mmap_split_full.csv").exists():
        parse_mmap_split(mode_dir / "mmap_split_full.csv", mode, rows)
    if (mode_dir / "lat_mem_rd.txt").exists():
        parse_lat_mem(mode_dir / "lat_mem_rd.txt", mode, rows)
    if (mode_dir / "bw_mem.txt").exists():
        parse_bandwidth(mode_dir / "bw_mem.txt", mode, "bw_mem", rows)
    if (mode_dir / "bw_mmap_rd.txt").exists():
        parse_bandwidth(mode_dir / "bw_mmap_rd.txt", mode, "bw_mmap_rd", rows)
    return rows


def median_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, ...], list[float]] = {}
    for row in rows:
        key = (row["mode"],) + tuple(row[field] for field in KEY_FIELDS)
        grouped.setdefault(key, []).append(float(row["value"]))

    out = []
    for key, values in sorted(grouped.items()):
        mode = key[0]
        data = dict(zip(KEY_FIELDS, key[1:]))
        med = statistics.median(values)
        mad = statistics.median([abs(v - med) for v in values]) if len(values) > 1 else 0.0
        data.update(
            {
                "mode": mode,
                "n": str(len(values)),
                "median": f"{med:.9g}",
                "mad": f"{mad:.9g}",
                "mad_pct": f"{(mad / med * 100.0):.6g}" if med else "",
            }
        )
        out.append(data)
    return out


def diff_rows(summary: list[dict[str, str]]) -> list[dict[str, str]]:
    by_key: dict[tuple[str, ...], dict[str, dict[str, str]]] = {}
    for row in summary:
        key = tuple(row[field] for field in KEY_FIELDS)
        by_key.setdefault(key, {})[row["mode"]] = row

    out = []
    for key, modes in sorted(by_key.items()):
        if "protected" not in modes or "nvhe" not in modes:
            continue
        p = float(modes["protected"]["median"])
        n = float(modes["nvhe"]["median"])
        data = dict(zip(KEY_FIELDS, key))
        data.update(
            {
                "protected_median": f"{p:.9g}",
                "nvhe_median": f"{n:.9g}",
                "gap_protected_minus_nvhe": f"{p - n:.9g}",
                "ratio_protected_over_nvhe": f"{p / n:.9g}" if n else "",
                "protected_n": modes["protected"]["n"],
                "nvhe_n": modes["nvhe"]["n"],
            }
        )
        out.append(data)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", required=True, type=Path)
    args = parser.parse_args()

    rows = []
    rows.extend(parse_mode_dir(args.result_dir / "raw" / "protected", "protected"))
    rows.extend(parse_mode_dir(args.result_dir / "raw" / "nvhe", "nvhe"))

    summary_dir = args.result_dir / "summary"
    summary_dir.mkdir(parents=True, exist_ok=True)

    with (summary_dir / "overview-early-measurements.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MEAS_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    summary = median_rows(rows)
    summary_fields = KEY_FIELDS + ["mode", "n", "median", "mad", "mad_pct"]
    with (summary_dir / "overview-early-summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(summary)

    diffs = diff_rows(summary)
    diff_fields = KEY_FIELDS + [
        "protected_median",
        "nvhe_median",
        "gap_protected_minus_nvhe",
        "ratio_protected_over_nvhe",
        "protected_n",
        "nvhe_n",
    ]
    with (summary_dir / "overview-early-diff.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=diff_fields)
        writer.writeheader()
        writer.writerows(diffs)

    print(f"measurements={len(rows)} summary_rows={len(summary)} diff_rows={len(diffs)}")
    print(summary_dir / "overview-early-measurements.csv")
    print(summary_dir / "overview-early-summary.csv")
    print(summary_dir / "overview-early-diff.csv")


if __name__ == "__main__":
    main()
