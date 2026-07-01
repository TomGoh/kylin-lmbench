#!/usr/bin/env python3
"""Parse Pixel ported mmap-suite raw output and diff protected vs nvhe."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


OP_SWEEP_RE = re.compile(
    r"^(?P<op>munmap|dontneed|mprotect)\s+"
    r"(?P<mapping>file|anon)\s+mb=(?P<mb>\d+)\s+"
    r"touch=(?P<touch>[0-9.]+)MB\s+stride=(?P<stride>\d+)K\s+:\s+"
    r"mean=(?P<mean>[0-9.]+)\s+us\s+min=(?P<min>[0-9.]+)\s+us$"
)
MUNMAP_ONLY_RE = re.compile(
    r"^(?P<mapping>file|anon_base|anon_huge)\s+mb=(?P<mb>\d+)\s+"
    r"touch=(?P<touch>[0-9.]+)MB\s+stride=(?P<stride>\d+)K\s+:\s+"
    r"munmap mean=(?P<mean>[0-9.]+)\s+us\s+min=(?P<min>[0-9.]+)\s+us$"
)
MUNMAP_BENCH_RE = re.compile(
    r"^(?P<mapping>file|anon_base|anon_huge)\s+(?P<mb>\d+)MB\s+x(?P<iters>\d+)\s+:\s+"
    r"(?P<total>[0-9.]+)\s+s\s+total,\s+(?P<per_iter>[0-9.]+)\s+us/iter$"
)
LAT_RE = re.compile(
    r"^size_mb=(?P<mb>[0-9.]+)\s+iters=(?P<iters>\d+)\s+total_ns=(?P<total>[0-9.]+)\s+"
    r"per_iter_ns=(?P<per_iter_ns>[0-9.]+)\s+per_iter_us=(?P<per_iter_us>[0-9.]+)$"
)
SECTION_RE = re.compile(r"^### section=(?P<section>\S+)\s+label=(?P<label>\S+)$")
HUGE_HEADER_RE = re.compile(
    r"^huge_check\s+(?P<mapping>anon|shmem)\s+mb=(?P<mb>\d+)\s+"
    r"touch=(?P<touch>[0-9.]+)MB\s+stride=(?P<stride>\d+)K\s+:$"
)
HUGE_VALUE_RE = re.compile(r"^(?P<name>AnonHugePages|ShmemPmdMapped|FilePmdMapped):\s+(?P<kb>\d+)\s+kB$")


def fnum(value: str) -> float:
    return float(value)


def append_measurement(rows: list[dict[str, str]], **kwargs: object) -> None:
    row = {key: "" for key in FIELDNAMES}
    for key, value in kwargs.items():
        row[key] = str(value)
    rows.append(row)


FIELDNAMES = [
    "mode",
    "family",
    "source",
    "section",
    "label",
    "operation",
    "mapping",
    "size_mb",
    "touch_mb",
    "stride_kb",
    "timed",
    "iters",
    "mean_us",
    "min_us",
    "per_iter_us",
    "per_touch_ns",
    "huge_anon_kb",
    "huge_shmem_kb",
    "huge_file_kb",
]

KEY_FIELDS = [
    "family",
    "section",
    "label",
    "operation",
    "mapping",
    "size_mb",
    "touch_mb",
    "stride_kb",
    "timed",
]


def parse_text_file(path: Path, mode: str, family: str, rows: list[dict[str, str]]) -> None:
    section = ""
    label = ""
    current_huge: dict[str, str] | None = None

    for raw_line in path.read_text(errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        section_match = SECTION_RE.match(line)
        if section_match:
            section = section_match.group("section")
            label = section_match.group("label")
            continue

        op_match = OP_SWEEP_RE.match(line)
        if op_match:
            data = op_match.groupdict()
            append_measurement(
                rows,
                mode=mode,
                family=family,
                source=path.name,
                section=section,
                label=label,
                operation=data["op"],
                mapping=data["mapping"],
                size_mb=data["mb"],
                touch_mb=data["touch"],
                stride_kb=data["stride"],
                mean_us=data["mean"],
                min_us=data["min"],
            )
            continue

        munmap_match = MUNMAP_ONLY_RE.match(line)
        if munmap_match:
            data = munmap_match.groupdict()
            append_measurement(
                rows,
                mode=mode,
                family=family,
                source=path.name,
                section=section,
                label=label,
                operation="munmap",
                mapping=data["mapping"],
                size_mb=data["mb"],
                touch_mb=data["touch"],
                stride_kb=data["stride"],
                mean_us=data["mean"],
                min_us=data["min"],
            )
            continue

        bench_match = MUNMAP_BENCH_RE.match(line)
        if bench_match:
            data = bench_match.groupdict()
            append_measurement(
                rows,
                mode=mode,
                family=family,
                source=path.name,
                section=section,
                label=label,
                operation="mmap_touch_munmap",
                mapping=data["mapping"],
                size_mb=data["mb"],
                iters=data["iters"],
                per_iter_us=data["per_iter"],
            )
            continue

        lat_match = LAT_RE.match(line)
        if lat_match:
            data = lat_match.groupdict()
            append_measurement(
                rows,
                mode=mode,
                family=family,
                source=path.name,
                section=section,
                label=label,
                operation="lat_mmap_precise",
                mapping="file",
                size_mb=data["mb"],
                touch_mb=str(fnum(data["mb"]) / 10.0),
                stride_kb="16",
                iters=data["iters"],
                per_iter_us=data["per_iter_us"],
            )
            continue

        huge_header = HUGE_HEADER_RE.match(line)
        if huge_header:
            if current_huge is not None:
                append_measurement(rows, **current_huge)
            data = huge_header.groupdict()
            current_huge = {
                "mode": mode,
                "family": family,
                "source": path.name,
                "section": section,
                "label": label,
                "operation": "huge_check",
                "mapping": data["mapping"],
                "size_mb": data["mb"],
                "touch_mb": data["touch"],
                "stride_kb": data["stride"],
                "huge_anon_kb": "0",
                "huge_shmem_kb": "0",
                "huge_file_kb": "0",
            }
            continue

        huge_value = HUGE_VALUE_RE.match(line)
        if huge_value and current_huge is not None:
            name = huge_value.group("name")
            key = {
                "AnonHugePages": "huge_anon_kb",
                "ShmemPmdMapped": "huge_shmem_kb",
                "FilePmdMapped": "huge_file_kb",
            }[name]
            current_huge[key] = huge_value.group("kb")

    if current_huge is not None:
        append_measurement(rows, **current_huge)


def parse_mmap_split(path: Path, mode: str, rows: list[dict[str, str]]) -> None:
    section = ""
    label = ""
    for raw_line in path.read_text(errors="replace").splitlines():
        line = raw_line.strip()
        section_match = SECTION_RE.match(line)
        if section_match:
            section = section_match.group("section")
            label = section_match.group("label")
            continue
        if not line or line.startswith("###") or line.startswith("mode,"):
            continue
        if line.count(",") < 13:
            continue
        data = next(csv.DictReader(["mode,size_mb,iters,warmups,timed,touch_divisor,stride_kb,touch_bytes,touches_per_iter,total_ns,per_iter_ns,per_iter_us,per_touch_ns,sink", line]))
        append_measurement(
            rows,
            mode=mode,
            family="mmap_split",
            source=path.name,
            section=section,
            label=label,
            operation=data["timed"],
            mapping="file",
            size_mb=data["size_mb"],
            touch_mb=str(float(data["size_mb"]) / float(data["touch_divisor"])),
            stride_kb=data["stride_kb"],
            timed=data["timed"],
            iters=data["iters"],
            per_iter_us=data["per_iter_us"],
            per_touch_ns=data["per_touch_ns"],
        )


def parse_mode_dir(mode_dir: Path, mode: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    files = {
        "lat_mmap": "lat_mmap_precise.txt",
        "munmap_threshold": "munmap_threshold.txt",
        "op_sweep": "op_sweep.txt",
        "backing": "backing_munmap_only.txt",
        "munmap_bench": "munmap_bench.txt",
        "huge_check": "huge_check.txt",
        "tmpfs_op_sweep": "tmpfs_op_sweep.txt",
    }
    for family, name in files.items():
        path = mode_dir / name
        if path.exists():
            parse_text_file(path, mode, family, rows)
    split = mode_dir / "mmap_split.csv"
    if split.exists():
        parse_mmap_split(split, mode, rows)
    return rows


def numeric_metric(row: dict[str, str]) -> float | None:
    for key in ("mean_us", "per_iter_us"):
        value = row.get(key, "")
        if value:
            return float(value)
    return None


def build_diff(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_key: dict[tuple[str, ...], dict[str, dict[str, str]]] = {}
    for row in rows:
        metric = numeric_metric(row)
        if metric is None:
            continue
        key = tuple(row[field] for field in KEY_FIELDS)
        by_key.setdefault(key, {})[row["mode"]] = row

    out = []
    for key, modes in sorted(by_key.items()):
        if "protected" not in modes or "nvhe" not in modes:
            continue
        protected = numeric_metric(modes["protected"])
        nvhe = numeric_metric(modes["nvhe"])
        if protected is None or nvhe is None:
            continue
        row = {field: value for field, value in zip(KEY_FIELDS, key)}
        row.update(
            {
                "protected_us": f"{protected:.6f}",
                "nvhe_us": f"{nvhe:.6f}",
                "gap_us": f"{protected - nvhe:.6f}",
                "ratio": f"{protected / nvhe:.6f}" if nvhe else "",
            }
        )
        out.append(row)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", required=True, type=Path)
    parser.add_argument("--protected-dir", type=Path)
    parser.add_argument("--nvhe-dir", type=Path)
    args = parser.parse_args()

    protected_dir = args.protected_dir or args.result_dir / "raw" / "protected"
    nvhe_dir = args.nvhe_dir or args.result_dir / "raw" / "nvhe"
    rows = []
    if protected_dir.exists():
        rows.extend(parse_mode_dir(protected_dir, "protected"))
    if nvhe_dir.exists():
        rows.extend(parse_mode_dir(nvhe_dir, "nvhe"))

    summary = args.result_dir / "summary"
    summary.mkdir(parents=True, exist_ok=True)
    with (summary / "ported-suite-measurements.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    diff_rows = build_diff(rows)
    diff_fields = KEY_FIELDS + ["protected_us", "nvhe_us", "gap_us", "ratio"]
    with (summary / "ported-suite-diff.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=diff_fields)
        writer.writeheader()
        writer.writerows(diff_rows)

    print(f"measurements={len(rows)} diff_rows={len(diff_rows)}")
    print(summary / "ported-suite-measurements.csv")
    print(summary / "ported-suite-diff.csv")


if __name__ == "__main__":
    main()
