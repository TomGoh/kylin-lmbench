#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Render N80 mechanism-control figures used by the mmap report.

The script reads the archived experiment outputs and emits three SVG figures:

* dense-vs-sparse munmap control for section 7.3
* core-scaling mean check for section 8.3
* direct TLBI IS-vs-NSH timing for section 8.4
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from html import escape
from pathlib import Path
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple, Union


FIGURE_DIR = Path("docs/mmap/figures")

C0_SPARSE_FILES = {
    "NVHE": Path("results/n80-munmap-gate-c0/nvhe/c0-nvhe/bench-perf-nvhe.log"),
    "protected": Path("results/n80-munmap-gate-c0/protected/c0-protected/bench-perf-protected.log"),
}
C1_DENSE_RECORD = Path("docs/mmap/c1-tlbi-threshold.zh-CN.md")

CORE_SCALING_FILES = {
    "NVHE": Path("experiments/munmap-tlbi/results/corescaling-n80/nvhe-main-sweep.csv"),
    "protected": Path("experiments/munmap-tlbi/results/corescaling-n80/protected-main-sweep.csv"),
}
CORE_SCALING_ORDER = [
    ("0",),
    ("0", "1"),
    ("0", "4"),
    ("0", "1", "2", "3", "4", "5", "6", "7"),
]
CORE_SCALING_LABELS = {
    ("0",): ("{0}", "single"),
    ("0", "1"): ("{0,1}", "same cluster"),
    ("0", "4"): ("{0,4}", "cross cluster"),
    ("0", "1", "2", "3", "4", "5", "6", "7"): ("{0..7}", "all cores"),
}

TLBI_AB_FILES = {
    "NVHE": Path("experiments/munmap-tlbi/results/tlbi-ab-n80/tlbi-ab-nvhe.txt"),
    "protected": Path("experiments/munmap-tlbi/results/tlbi-ab-n80/tlbi-ab-protected.txt"),
}

MODE_COLORS = {
    "NVHE": "#4D7C59",
    "protected": "#C23B2A",
}
SPARSE_COLOR = "#C23B2A"
DENSE_COLOR = "#4D7C59"
NSH_COLOR = "#64748B"
IS_COLOR = "#D97706"
TEXT = "#1F2933"
MUTED = "#64707D"
GRID = "#E8EDF3"
AXIS = "#5C6670"


class SparseDenseRow(NamedTuple):
    scenario: str
    ptes: int
    nvhe_us: float
    protected_us: float

    @property
    def delta_us(self) -> float:
        return self.protected_us - self.nvhe_us


class CoreScalingRow(NamedTuple):
    online_set: Tuple[str, ...]
    mean_us: float


class TlbiRow(NamedTuple):
    nsh_ns: float
    is_ns: float

    @property
    def diff_ns(self) -> float:
        return self.is_ns - self.nsh_ns


class Svg:
    def __init__(self, width: int, height: int, title: str, desc: str) -> None:
        self.width = width
        self.height = height
        self.title = title
        self.desc = desc
        self.parts: List[str] = []

    def add(self, markup: str) -> None:
        self.parts.append(markup)

    def text(
        self,
        x: float,
        y: float,
        value: str,
        *,
        size: int = 13,
        fill: str = TEXT,
        anchor: str = "start",
        weight: Union[int, str] = 400,
    ) -> None:
        self.add(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{escape(value)}</text>'
        )

    def render(self) -> str:
        body = "\n  ".join(self.parts)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" '
            f'height="{self.height}" viewBox="0 0 {self.width} {self.height}" '
            f'role="img" aria-labelledby="title desc">\n'
            f'  <title id="title">{escape(self.title)}</title>\n'
            f'  <desc id="desc">{escape(self.desc)}</desc>\n'
            f'  <rect width="100%" height="100%" fill="#FFFFFF"/>\n'
            f'  {body}\n'
            f'</svg>\n'
        )


def _nice_step(max_value: float, target_ticks: int = 5) -> float:
    if max_value <= 0:
        return 1.0
    raw = max_value / target_ticks
    exponent = math.floor(math.log10(raw))
    fraction = raw / (10**exponent)
    if fraction <= 1:
        nice_fraction = 1
    elif fraction <= 2:
        nice_fraction = 2
    elif fraction <= 5:
        nice_fraction = 5
    else:
        nice_fraction = 10
    return nice_fraction * (10**exponent)


def _axis_max(max_value: float, target_ticks: int = 5) -> float:
    step = _nice_step(max_value, target_ticks)
    return math.ceil(max_value / step) * step


def _format_float(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}"


def _read_single_csv_row(path: Path) -> Dict[str, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if len(rows) != 1:
        raise ValueError(f"{path} should contain exactly one data row")
    return rows[0]


def _load_sparse_dense(repo_root: Path) -> List[SparseDenseRow]:
    sparse_values: Dict[str, float] = {}
    sparse_ptes: Optional[int] = None

    for mode, relative in C0_SPARSE_FILES.items():
        row = _read_single_csv_row(repo_root / relative)
        sparse_values[mode] = float(row["per_iter_us"])
        touches = int(row["touches_per_iter"])
        if sparse_ptes is None:
            sparse_ptes = touches
        elif sparse_ptes != touches:
            raise ValueError("sparse C0 logs disagree on touches_per_iter")

    dense_source = repo_root / C1_DENSE_RECORD
    dense_row = None
    for line in dense_source.read_text(encoding="utf-8").splitlines():
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) == 4 and "16384" in parts[0]:
            dense_row = parts
            break
    if dense_row is None:
        raise ValueError(f"could not find dense 64MB control row in {dense_source}")

    dense_ptes_match = re.search(r"([0-9][0-9,]*)\s+PTE", dense_row[0])
    if not dense_ptes_match:
        raise ValueError(f"could not parse dense PTE count from: {dense_row[0]}")
    dense_ptes = int(dense_ptes_match.group(1).replace(",", ""))

    number_re = re.compile(r"([0-9]+(?:\.[0-9]+)?)")
    dense_nvhe_match = number_re.search(dense_row[1])
    dense_protected_match = number_re.search(dense_row[2])
    if dense_nvhe_match is None or dense_protected_match is None:
        raise ValueError(f"could not parse dense latencies from: {dense_row}")

    return [
        SparseDenseRow(
            scenario="sparse 6.4MB/16K",
            ptes=sparse_ptes or 0,
            nvhe_us=sparse_values["NVHE"],
            protected_us=sparse_values["protected"],
        ),
        SparseDenseRow(
            scenario="dense 64MB/4K",
            ptes=dense_ptes,
            nvhe_us=float(dense_nvhe_match.group(1)),
            protected_us=float(dense_protected_match.group(1)),
        ),
    ]


def _parse_core_scaling_line(line: str) -> Optional[CoreScalingRow]:
    if not line or line.startswith("#") or line.startswith("set,"):
        return None
    fields = [field.strip() for field in line.split(",")]
    if len(fields) < 7:
        return None

    try:
        touch_mb = float(fields[-4])
        stride_kb = int(fields[-3])
        mean_us = float(fields[-2])
        n_online = int(fields[-6])
    except ValueError:
        return None

    if abs(touch_mb - 6.4) > 1e-9 or stride_kb != 16:
        return None

    online_set = tuple(fields[: -6])
    if len(online_set) != n_online:
        raise ValueError(f"online set {online_set} does not match n_online={n_online}")
    return CoreScalingRow(online_set=online_set, mean_us=mean_us)


def _load_core_scaling(repo_root: Path) -> Dict[str, Dict[Tuple[str, ...], float]]:
    result: Dict[str, Dict[Tuple[str, ...], float]] = {}
    for mode, relative in CORE_SCALING_FILES.items():
        mode_rows: Dict[Tuple[str, ...], float] = {}
        for line in (repo_root / relative).read_text(encoding="utf-8").splitlines():
            parsed = _parse_core_scaling_line(line)
            if parsed is None:
                continue
            mode_rows[parsed.online_set] = parsed.mean_us
        missing = [online_set for online_set in CORE_SCALING_ORDER if online_set not in mode_rows]
        if missing:
            raise ValueError(f"{relative} missing online sets: {missing}")
        result[mode] = mode_rows
    return result


def _load_tlbi_ab(repo_root: Path, nslots: int = 2048) -> Dict[str, TlbiRow]:
    result: Dict[str, TlbiRow] = {}
    header_re = re.compile(r"^cpu=\d+\s+nslots=(?P<nslots>\d+)\s+reps=(?P<reps>\d+)\s+")
    per_slot_re = re.compile(r"^(?P<kind>IS|NSH)\s+total=\d+\s+ns\s+per_slot=(?P<value>[0-9.]+)\s+ns$")

    for mode, relative in TLBI_AB_FILES.items():
        current_nslots = None
        values: Dict[str, float] = {}
        for line in (repo_root / relative).read_text(encoding="utf-8").splitlines():
            header_match = header_re.match(line)
            if header_match:
                current_nslots = int(header_match.group("nslots"))
                continue
            if current_nslots != nslots:
                continue
            per_slot_match = per_slot_re.match(line)
            if per_slot_match:
                values[per_slot_match.group("kind")] = float(per_slot_match.group("value"))
        if "IS" not in values or "NSH" not in values:
            raise ValueError(f"{relative} missing IS/NSH rows for nslots={nslots}")
        result[mode] = TlbiRow(nsh_ns=values["NSH"], is_ns=values["IS"])
    return result


def _draw_y_axis(
    svg: Svg,
    *,
    x0: float,
    y0: float,
    width: float,
    height: float,
    max_value: float,
    ticks: Sequence[float],
    formatter,
) -> None:
    bottom = y0 + height
    svg.add(
        f'<line x1="{x0:.1f}" y1="{bottom:.1f}" x2="{x0 + width:.1f}" y2="{bottom:.1f}" '
        f'stroke="{AXIS}" stroke-width="1.2"/>'
    )
    svg.add(
        f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x0:.1f}" y2="{bottom:.1f}" '
        f'stroke="{AXIS}" stroke-width="1.2"/>'
    )
    for tick in ticks:
        y = bottom - (tick / max_value) * height
        svg.add(
            f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x0 + width:.1f}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        svg.add(
            f'<line x1="{x0 - 5:.1f}" y1="{y:.1f}" x2="{x0:.1f}" y2="{y:.1f}" '
            f'stroke="{AXIS}" stroke-width="1"/>'
        )
        svg.text(x0 - 10, y + 4, formatter(tick), size=11, fill=MUTED, anchor="end")


def _draw_delta_axis(
    svg: Svg,
    *,
    x0: float,
    y0: float,
    width: float,
    height: float,
    min_value: float,
    max_value: float,
    ticks: Sequence[float],
) -> float:
    bottom = y0 + height

    def y_for(value: float) -> float:
        return y0 + height - ((value - min_value) / (max_value - min_value)) * height

    zero_y = y_for(0)
    svg.add(
        f'<line x1="{x0:.1f}" y1="{bottom:.1f}" x2="{x0 + width:.1f}" y2="{bottom:.1f}" '
        f'stroke="{AXIS}" stroke-width="1.2"/>'
    )
    svg.add(
        f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x0:.1f}" y2="{bottom:.1f}" '
        f'stroke="{AXIS}" stroke-width="1.2"/>'
    )
    svg.add(
        f'<line x1="{x0:.1f}" y1="{zero_y:.1f}" x2="{x0 + width:.1f}" y2="{zero_y:.1f}" '
        f'stroke="#8A94A3" stroke-width="1.2" stroke-dasharray="4 4"/>'
    )
    for tick in ticks:
        y = y_for(tick)
        svg.add(
            f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x0 + width:.1f}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        svg.text(x0 - 10, y + 4, f"{tick:.0f}", size=11, fill=MUTED, anchor="end")
    return zero_y


def render_sparse_dense(rows: List[SparseDenseRow]) -> str:
    svg = Svg(
        1020,
        560,
        "Sparse-vs-dense munmap control",
        "Dense touch greatly increases PTE work but removes the protected minus NVHE gap.",
    )
    svg.text(58, 42, "Sparse-vs-dense munmap control", size=22, weight=700)
    svg.text(58, 66, "More PTE teardown work does not imply larger protected overhead", size=13, fill=MUTED)

    panel_w = 410
    panel_h = 300
    left_x = 90
    right_x = 585
    panel_y = 118
    bar_w = 86
    centers = [left_x + 135, left_x + 282]
    colors = [SPARSE_COLOR, DENSE_COLOR]

    svg.text(left_x, 98, "PTEs cleared by munmap", size=16, weight=700)
    _draw_y_axis(
        svg,
        x0=left_x,
        y0=panel_y,
        width=panel_w,
        height=panel_h,
        max_value=18000,
        ticks=[0, 4000, 8000, 12000, 16000],
        formatter=lambda value: f"{value / 1000:.0f}k" if value else "0",
    )
    for index, row in enumerate(rows):
        x = centers[index] - bar_w / 2
        height = (row.ptes / 18000) * panel_h
        y = panel_y + panel_h - height
        svg.add(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{height:.1f}" '
            f'rx="5" fill="{colors[index]}"/>'
        )
        svg.text(centers[index], y - 9, f"{row.ptes:,}", size=12, weight=700, anchor="middle")
        first, second = row.scenario.split(" ", 1)
        svg.text(centers[index], panel_y + panel_h + 28, first, size=12, fill=TEXT, anchor="middle", weight=700)
        svg.text(centers[index], panel_y + panel_h + 46, second, size=11, fill=MUTED, anchor="middle")
    svg.text(left_x + panel_w / 2, panel_y + panel_h + 78, "dense clears about 40x more PTEs", size=12, fill=MUTED, anchor="middle")

    svg.text(right_x, 98, "protected - NVHE extra time", size=16, weight=700)
    zero_y = _draw_delta_axis(
        svg,
        x0=right_x,
        y0=panel_y,
        width=panel_w,
        height=panel_h,
        min_value=-80,
        max_value=500,
        ticks=[-50, 0, 100, 200, 300, 400, 500],
    )
    for index, row in enumerate(rows):
        center = right_x + 135 + index * 147
        x = center - bar_w / 2
        y_value = panel_y + panel_h - ((row.delta_us + 80) / 580) * panel_h
        if row.delta_us >= 0:
            y = y_value
            height = zero_y - y_value
        else:
            y = zero_y
            height = y_value - zero_y
        svg.add(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{height:.1f}" '
            f'rx="5" fill="{colors[index]}"/>'
        )
        label = f"{row.delta_us:+.0f} us"
        if abs(row.delta_us) < 50:
            label += " (~0)"
        label_y = y - 9 if row.delta_us >= 0 else y + height + 18
        svg.text(center, label_y, label, size=12, weight=700, anchor="middle")
        first, second = row.scenario.split(" ", 1)
        svg.text(center, panel_y + panel_h + 28, first, size=12, fill=TEXT, anchor="middle", weight=700)
        svg.text(center, panel_y + panel_h + 46, second, size=11, fill=MUTED, anchor="middle")
    svg.text(right_x + panel_w / 2, panel_y + panel_h + 78, "the gap disappears once dense touch selects whole-mm flush", size=12, fill=MUTED, anchor="middle")

    svg.text(
        510,
        532,
        "Source: C0 sparse bench logs plus archived dense-control result in docs/mmap/c1-tlbi-threshold.zh-CN.md",
        size=12,
        fill=MUTED,
        anchor="middle",
    )
    return svg.render()


def render_core_scaling(data: Dict[str, Dict[Tuple[str, ...], float]]) -> str:
    svg = Svg(
        1020,
        560,
        "Core-scaling mean check",
        "N80 sparse munmap mean latency does not grow with online core count or cross-cluster topology.",
    )
    svg.text(58, 42, "Core-scaling mean check", size=22, weight=700)
    svg.text(58, 66, "64MB mapping, 6.4MB/16K sparse touch, munmap-only mean", size=13, fill=MUTED)

    x0 = 92
    y0 = 115
    width = 835
    height = 320
    bottom = y0 + height
    y_max = 650.0
    ticks = [0, 100, 200, 300, 400, 500, 600]
    x_positions = [x0 + 70 + index * (width - 140) / (len(CORE_SCALING_ORDER) - 1) for index in range(len(CORE_SCALING_ORDER))]

    _draw_y_axis(
        svg,
        x0=x0,
        y0=y0,
        width=width,
        height=height,
        max_value=y_max,
        ticks=ticks,
        formatter=lambda value: f"{value:.0f}",
    )
    svg.text(x0 - 58, y0 - 12, "us/iter", size=12, fill=MUTED)

    def y_for(value: float) -> float:
        return bottom - (value / y_max) * height

    for mode in ("protected", "NVHE"):
        points = []
        for x, online_set in zip(x_positions, CORE_SCALING_ORDER):
            y = y_for(data[mode][online_set])
            points.append(f"{x:.1f},{y:.1f}")
        svg.add(
            f'<polyline points="{" ".join(points)}" fill="none" stroke="{MODE_COLORS[mode]}" '
            f'stroke-width="2.4" stroke-linejoin="round"/>'
        )
        for x, online_set in zip(x_positions, CORE_SCALING_ORDER):
            value = data[mode][online_set]
            y = y_for(value)
            svg.add(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.5" fill="#FFFFFF" '
                f'stroke="{MODE_COLORS[mode]}" stroke-width="2.2"/>'
            )
            label_y = y - 12 if mode == "protected" else y + 22
            svg.text(x, label_y, _format_float(value), size=11, fill=MODE_COLORS[mode], anchor="middle", weight=700)

    for x, online_set in zip(x_positions, CORE_SCALING_ORDER):
        label, note = CORE_SCALING_LABELS[online_set]
        svg.add(f'<line x1="{x:.1f}" y1="{bottom:.1f}" x2="{x:.1f}" y2="{bottom + 6:.1f}" stroke="{AXIS}" stroke-width="1"/>')
        svg.text(x, bottom + 28, label, size=12, fill=TEXT, anchor="middle", weight=700)
        svg.text(x, bottom + 46, note, size=11, fill=MUTED, anchor="middle")

    legend_x = 705
    legend_y = 105
    for index, mode in enumerate(("protected", "NVHE")):
        y = legend_y + index * 24
        svg.add(f'<line x1="{legend_x:.1f}" y1="{y:.1f}" x2="{legend_x + 28:.1f}" y2="{y:.1f}" stroke="{MODE_COLORS[mode]}" stroke-width="2.5"/>')
        svg.add(f'<circle cx="{legend_x + 14:.1f}" cy="{y:.1f}" r="4.5" fill="#FFFFFF" stroke="{MODE_COLORS[mode]}" stroke-width="2"/>')
        svg.text(legend_x + 38, y + 4, mode, size=12, fill=TEXT)

    svg.text(510, 532, "Source: experiments/munmap-tlbi/results/corescaling-n80/{nvhe,protected}-main-sweep.csv", size=12, fill=MUTED, anchor="middle")
    return svg.render()


def render_tlbi_ab(data: Dict[str, TlbiRow]) -> str:
    svg = Svg(
        1020,
        560,
        "Direct TLBI IS vs NSH timing",
        "Direct TLBI timing shows protected mode makes local TLBI expensive while IS and NSH are nearly identical.",
    )
    svg.text(58, 42, "Direct TLBI timing: IS vs NSH", size=22, weight=700)
    svg.text(58, 66, "nslots=2048, reps=2, IRQ-off kernel module timing", size=13, fill=MUTED)

    x0 = 105
    y0 = 115
    width = 820
    height = 320
    bottom = y0 + height
    y_max = 320.0
    _draw_y_axis(
        svg,
        x0=x0,
        y0=y0,
        width=width,
        height=height,
        max_value=y_max,
        ticks=[0, 50, 100, 150, 200, 250, 300],
        formatter=lambda value: f"{value:.0f}",
    )
    svg.text(x0 - 70, y0 - 12, "ns/slot", size=12, fill=MUTED)

    def y_for(value: float) -> float:
        return bottom - (value / y_max) * height

    group_centers = [x0 + width * 0.33, x0 + width * 0.70]
    modes = ["NVHE", "protected"]
    bar_w = 62
    offset = 38
    for center, mode in zip(group_centers, modes):
        row = data[mode]
        for label, value, color, dx in (("NSH", row.nsh_ns, NSH_COLOR, -offset), ("IS", row.is_ns, IS_COLOR, offset)):
            x = center + dx - bar_w / 2
            y = y_for(value)
            height_px = bottom - y
            svg.add(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{height_px:.1f}" '
                f'rx="5" fill="{color}"/>'
            )
            svg.text(center + dx, y - 9, f"{value:.3f}", size=11, fill=color, anchor="middle", weight=700)
            svg.text(center + dx, bottom + 25, label, size=12, fill=TEXT, anchor="middle", weight=700)

        bracket_y = min(y_for(row.nsh_ns), y_for(row.is_ns)) - 34
        svg.add(
            f'<path d="M {center - offset:.1f} {bracket_y:.1f} '
            f'L {center - offset:.1f} {bracket_y - 8:.1f} '
            f'L {center + offset:.1f} {bracket_y - 8:.1f} '
            f'L {center + offset:.1f} {bracket_y:.1f}" '
            f'fill="none" stroke="{AXIS}" stroke-width="1.2"/>'
        )
        svg.text(center, bracket_y - 14, f"IS-NSH = {row.diff_ns:+.3f} ns", size=12, fill=MUTED, anchor="middle")
        svg.text(center, bottom + 54, mode, size=14, fill=TEXT, anchor="middle", weight=700)

    legend_x = 760
    legend_y = 84
    svg.add(
        f'<rect x="{legend_x - 14:.1f}" y="{legend_y - 26:.1f}" width="158" height="63" '
        f'rx="6" fill="#FFFFFF" stroke="#D8DEE8" stroke-width="1"/>'
    )
    for index, (label, color) in enumerate((("NSH vae1", NSH_COLOR), ("IS vae1is", IS_COLOR))):
        y = legend_y + index * 26
        svg.add(f'<rect x="{legend_x:.1f}" y="{y - 11:.1f}" width="18" height="18" rx="3" fill="{color}"/>')
        svg.text(legend_x + 28, y + 3, label, size=12, fill=TEXT)

    svg.text(510, 532, "Source: experiments/munmap-tlbi/results/tlbi-ab-n80/tlbi-ab-{nvhe,protected}.txt", size=12, fill=MUTED, anchor="middle")
    return svg.render()


def write_figure(output_dir: Path, filename: str, content: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / filename).write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="repository root; defaults to the script location",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="output directory; defaults to docs/mmap/figures under repo root",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir or (repo_root / FIGURE_DIR)

    sparse_dense = _load_sparse_dense(repo_root)
    core_scaling = _load_core_scaling(repo_root)
    tlbi_ab = _load_tlbi_ab(repo_root)

    write_figure(output_dir, "n80-dense-sparse-control.svg", render_sparse_dense(sparse_dense))
    write_figure(output_dir, "n80-broadcast-core-scaling.svg", render_core_scaling(core_scaling))
    write_figure(output_dir, "n80-broadcast-tlbi-is-nsh.svg", render_tlbi_ab(tlbi_ab))


if __name__ == "__main__":
    main()
