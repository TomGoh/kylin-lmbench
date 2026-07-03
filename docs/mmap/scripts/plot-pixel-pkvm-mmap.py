#!/usr/bin/env python3
"""Render Pixel pKVM/NVHE mmap comparison figures for the mmap report."""

from __future__ import annotations

import argparse
import csv
import math
import re
from html import escape
from pathlib import Path
from typing import Dict, Iterable, List, NamedTuple, Sequence, Tuple


FIGURE_DIR = Path("docs/mmap/figures")
MADV_DIR = Path("experiments/perf-reinvestigation/results/pixel9proxl-aosp-pkvm-nvhe-20260629")
OVERVIEW_DIR = Path(
    "experiments/perf-reinvestigation/results/pixel9proxl-aosp-pkvm-nvhe-20260701-overview-early-5run"
)
PORTED_DIR = Path(
    "experiments/perf-reinvestigation/results/pixel9proxl-aosp-pkvm-nvhe-20260629-ported"
)
N80_OP_SWEEP_DIR = Path("experiments/munmap-tlbi/results/op-sweep-n80")

TEXT = "#1F2933"
MUTED = "#64707D"
GRID = "#E8EDF3"
AXIS = "#5C6670"
NVHE = "#4D7C59"
PROTECTED = "#C23B2A"
GAP = "#D97706"
FLOOR = "#64748B"
N80_COLOR = "#6B7280"
PIXEL_COLOR = "#1F8A70"
N80_SAMPLE_RE = re.compile(
    r"^(?P<op>\w+)\s+file\s+mb=(?P<mb>\d+)\s+touch=(?P<touch>[0-9.]+)MB\s+"
    r"stride=(?P<stride>\d+)K\s+:\s+mean=(?P<mean>[0-9.]+)\s+us\s+"
    r"min=(?P<min>[0-9.]+)\s+us"
)


class MadvRow(NamedTuple):
    label: str
    median_ns: float
    ci_low_ns: float
    ci_high_ns: float
    floor_ns: float


class PairRow(NamedTuple):
    size_mb: float
    protected: float
    nvhe: float
    gap: float


class OpRow(NamedTuple):
    operation: str
    touch_mb: float
    stride_kb: int
    protected: float
    nvhe: float
    gap: float


class PlatformGapRow(NamedTuple):
    label_top: str
    label_bottom: str
    touch_mb: float
    stride_kb: int
    n80_gap: float
    pixel_gap: float
    n80_pct: float
    pixel_pct: float


class PlatformMetric(NamedTuple):
    protected: float
    nvhe: float
    gap: float
    pct: float


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
        weight: int | str = 400,
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


def _read_single(path: Path) -> Dict[str, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1:
        raise ValueError(f"{path} should contain exactly one data row")
    return rows[0]


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _axis_step(max_value: float, target_ticks: int = 5) -> float:
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
    step = _axis_step(max_value, target_ticks)
    return math.ceil(max_value / step) * step


def _y_for(value: float, y_min: float, y_max: float, top: float, height: float) -> float:
    if y_max == y_min:
        return top + height
    return top + height - ((value - y_min) / (y_max - y_min)) * height


def _x_for(value: float, x_min: float, x_max: float, left: float, width: float) -> float:
    if x_max == x_min:
        return left
    return left + ((value - x_min) / (x_max - x_min)) * width


def _polyline(points: Iterable[Tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def _fmt_size(size: float) -> str:
    return str(int(size)) if float(size).is_integer() else f"{size:g}"


def _threshold_point_key(point: Tuple[float, int]) -> Tuple[int, float]:
    touch_mb, stride_kb = point
    if stride_kb == 4:
        return (0, touch_mb)
    return (1, touch_mb)


def _threshold_point_label(point: Tuple[float, int]) -> str:
    touch_mb, stride_kb = point
    return f"{_fmt_size(touch_mb)}MB/{stride_kb}K"


def _load_madv(repo_root: Path) -> List[MadvRow]:
    rows = []
    for label, relative in [
        ("single page calls", Path("summary/single-summary.csv")),
        ("one batched call", Path("summary/batched-summary.csv")),
    ]:
        row = _read_single(repo_root / MADV_DIR / relative)
        rows.append(
            MadvRow(
                label=label,
                median_ns=float(row["per_entry_median_ns_per_op"]),
                ci_low_ns=float(row["per_entry_ci95_low_ns_per_op"]),
                ci_high_ns=float(row["per_entry_ci95_high_ns_per_op"]),
                floor_ns=float(row["resolution_floor_ns_per_op"]),
            )
        )
    return rows


def _load_overview_lat(repo_root: Path) -> List[PairRow]:
    rows = []
    for row in _read_csv(repo_root / OVERVIEW_DIR / "summary/overview-early-diff.csv"):
        if row["family"] != "lat_mmap_precise":
            continue
        rows.append(
            PairRow(
                size_mb=float(row["size_mb"]),
                protected=float(row["protected_median"]),
                nvhe=float(row["nvhe_median"]),
                gap=float(row["gap_protected_minus_nvhe"]),
            )
        )
    return sorted(rows, key=lambda item: item.size_mb)


def _load_munmap_after_write(repo_root: Path) -> List[PairRow]:
    rows = []
    for row in _read_csv(repo_root / OVERVIEW_DIR / "summary/overview-early-diff.csv"):
        if row["family"] != "mmap_split" or row["operation"] != "munmap_after_write_touch":
            continue
        rows.append(
            PairRow(
                size_mb=float(row["size_mb"]),
                protected=float(row["protected_median"]),
                nvhe=float(row["nvhe_median"]),
                gap=float(row["gap_protected_minus_nvhe"]),
            )
        )
    return sorted(rows, key=lambda item: item.size_mb)


def _load_threshold(repo_root: Path) -> List[OpRow]:
    wanted_ops = {"munmap", "dontneed", "mprotect"}
    rows = []
    for row in _read_csv(repo_root / PORTED_DIR / "summary/ported-suite-diff.csv"):
        if row["family"] != "op_sweep" or row["operation"] not in wanted_ops:
            continue
        touch_mb = float(row["touch_mb"])
        stride_kb = int(float(row["stride_kb"]))
        rows.append(
            OpRow(
                operation=row["operation"],
                touch_mb=touch_mb,
                stride_kb=stride_kb,
                protected=float(row["protected_us"]),
                nvhe=float(row["nvhe_us"]),
                gap=float(row["gap_us"]),
            )
        )
    order = {"munmap": 0, "dontneed": 1, "mprotect": 2}
    return sorted(rows, key=lambda item: (order[item.operation], _threshold_point_key((item.touch_mb, item.stride_kb))))


def _relative_pct(protected: float, nvhe: float) -> float:
    if nvhe == 0:
        raise ValueError("NVHE baseline is zero")
    return (protected / nvhe - 1.0) * 100.0


def _load_pixel_munmap_metrics(repo_root: Path, points: Sequence[Tuple[float, int]]) -> Dict[Tuple[float, int], PlatformMetric]:
    wanted = set(points)
    metrics: Dict[Tuple[float, int], PlatformMetric] = {}
    for row in _read_csv(repo_root / PORTED_DIR / "summary/ported-suite-diff.csv"):
        if row["family"] != "op_sweep" or row["operation"] != "munmap":
            continue
        key = (float(row["touch_mb"]), int(float(row["stride_kb"])))
        if key in wanted:
            protected = float(row["protected_us"])
            nvhe = float(row["nvhe_us"])
            metrics[key] = PlatformMetric(
                protected=protected,
                nvhe=nvhe,
                gap=float(row["gap_us"]),
                pct=_relative_pct(protected, nvhe),
            )
    missing = wanted.difference(metrics)
    if missing:
        raise ValueError(f"missing Pixel munmap op_sweep gaps: {sorted(missing)}")
    return metrics


def _load_n80_munmap_metrics(repo_root: Path, points: Sequence[Tuple[float, int]]) -> Dict[Tuple[float, int], PlatformMetric]:
    wanted = set(points)
    means: Dict[Tuple[float, int], Dict[str, float]] = {}
    for mode, filename in [("protected", "protected.txt"), ("nvhe", "nvhe.txt")]:
        path = repo_root / N80_OP_SWEEP_DIR / filename
        for line in path.read_text(encoding="utf-8").splitlines():
            match = N80_SAMPLE_RE.search(line)
            if not match or match.group("op") != "munmap":
                continue
            key = (float(match.group("touch")), int(match.group("stride")))
            if key in wanted:
                means.setdefault(key, {})[mode] = float(match.group("mean"))

    metrics: Dict[Tuple[float, int], PlatformMetric] = {}
    for key in wanted:
        row = means.get(key, {})
        if "protected" not in row or "nvhe" not in row:
            raise ValueError(f"missing N80 munmap op_sweep pair for {key}")
        protected = row["protected"]
        nvhe = row["nvhe"]
        metrics[key] = PlatformMetric(
            protected=protected,
            nvhe=nvhe,
            gap=protected - nvhe,
            pct=_relative_pct(protected, nvhe),
        )
    return metrics


def _load_pixel_n80_munmap_comparison(repo_root: Path) -> List[PlatformGapRow]:
    points = [(1.9, 4), (2.0, 4), (6.4, 16), (64.0, 4)]
    labels = {
        (1.9, 4): ("1.9MB", "dense"),
        (2.0, 4): ("2.0MB", "dense"),
        (6.4, 16): ("6.4MB", "sparse"),
        (64.0, 4): ("64MB", "dense"),
    }
    pixel = _load_pixel_munmap_metrics(repo_root, points)
    n80 = _load_n80_munmap_metrics(repo_root, points)
    return [
        PlatformGapRow(
            label_top=labels[point][0],
            label_bottom=labels[point][1],
            touch_mb=point[0],
            stride_kb=point[1],
            n80_gap=n80[point].gap,
            pixel_gap=pixel[point].gap,
            n80_pct=n80[point].pct,
            pixel_pct=pixel[point].pct,
        )
        for point in points
    ]


def _draw_zero_axis(svg: Svg, left: float, top: float, width: float, height: float, y_min: float, y_max: float) -> None:
    if y_min <= 0 <= y_max:
        y0 = _y_for(0, y_min, y_max, top, height)
        svg.add(
            f'<line x1="{left:.1f}" y1="{y0:.1f}" x2="{left + width:.1f}" y2="{y0:.1f}" '
            f'stroke="{AXIS}" stroke-width="1"/>'
        )


def render_madv(repo_root: Path, figure_dir: Path) -> Path:
    data = _load_madv(repo_root)
    width, height = 760, 430
    left, top, plot_w, plot_h = 96, 78, 540, 250
    y_min = min(0.0, min(row.ci_low_ns for row in data)) - 20
    y_max = max(row.ci_high_ns for row in data) + 30

    svg = Svg(width, height, "Pixel MADV_DONTNEED per-4KB page cost", "Protected-minus-NVHE cost per added 4KB page after touched-minus-untouched correction.")
    svg.text(36, 34, "Pixel MADV_DONTNEED per-4KB page cost", size=18, weight=700)
    svg.text(36, 55, "protected - NVHE after touched - untouched; ns per added 4KB page", size=12, fill=MUTED)

    _draw_zero_axis(svg, left, top, plot_w, plot_h, y_min, y_max)
    step = _axis_step(y_max - y_min, 5)
    start = math.ceil(y_min / step) * step
    tick = start
    while tick <= y_max + 1e-9:
        y = _y_for(tick, y_min, y_max, top, plot_h)
        svg.add(f'<line x1="{left:.1f}" y1="{y:.1f}" x2="{left + plot_w:.1f}" y2="{y:.1f}" stroke="{GRID}"/>')
        svg.text(left - 10, y + 4, f"{tick:.0f}", size=11, fill=MUTED, anchor="end")
        tick += step
    svg.text(30, top + 8, "ns/page", size=12, fill=MUTED)

    bar_w = 94
    for idx, row in enumerate(data):
        x = left + 160 + idx * 190
        y_zero = _y_for(0, y_min, y_max, top, plot_h)
        y_val = _y_for(row.median_ns, y_min, y_max, top, plot_h)
        y_low = _y_for(row.ci_low_ns, y_min, y_max, top, plot_h)
        y_high = _y_for(row.ci_high_ns, y_min, y_max, top, plot_h)
        bar_top = min(y_zero, y_val)
        bar_h = abs(y_zero - y_val)
        color = PROTECTED if row.median_ns >= 0 else NVHE
        svg.add(f'<rect x="{x - bar_w / 2:.1f}" y="{bar_top:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{color}" opacity="0.88"/>')
        svg.add(f'<line x1="{x:.1f}" y1="{y_low:.1f}" x2="{x:.1f}" y2="{y_high:.1f}" stroke="{TEXT}" stroke-width="2"/>')
        svg.add(f'<line x1="{x - 13:.1f}" y1="{y_low:.1f}" x2="{x + 13:.1f}" y2="{y_low:.1f}" stroke="{TEXT}" stroke-width="2"/>')
        svg.add(f'<line x1="{x - 13:.1f}" y1="{y_high:.1f}" x2="{x + 13:.1f}" y2="{y_high:.1f}" stroke="{TEXT}" stroke-width="2"/>')
        floor_y = _y_for(row.floor_ns, y_min, y_max, top, plot_h)
        svg.add(f'<line x1="{x - 58:.1f}" y1="{floor_y:.1f}" x2="{x + 58:.1f}" y2="{floor_y:.1f}" stroke="{FLOOR}" stroke-dasharray="5 4"/>')
        svg.text(x, top + plot_h + 30, row.label, size=12, anchor="middle")
        label_y = y_val - 8 if row.median_ns >= 0 else y_val + 18
        svg.text(x + 58, label_y, f"{row.median_ns:+.1f}", size=12, anchor="start", weight=700)

    svg.add(f'<line x1="{left:.1f}" y1="{top:.1f}" x2="{left:.1f}" y2="{top + plot_h:.1f}" stroke="{AXIS}"/>')
    svg.add(f'<line x1="{left:.1f}" y1="{top + plot_h:.1f}" x2="{left + plot_w:.1f}" y2="{top + plot_h:.1f}" stroke="{AXIS}"/>')
    legend_x, legend_y = width - 186, 66
    svg.add(f'<line x1="{legend_x:.1f}" y1="{legend_y:.1f}" x2="{legend_x + 40:.1f}" y2="{legend_y:.1f}" stroke="{FLOOR}" stroke-dasharray="5 4"/>')
    svg.text(legend_x + 48, legend_y + 4, "resolution floor", size=12, fill=MUTED)

    out = figure_dir / "pixel-madv-entry-summary.svg"
    out.write_text(svg.render(), encoding="utf-8")
    return out


def _draw_pair_legend(svg: Svg, x: float, y: float) -> None:
    for idx, (label, color) in enumerate([("protected", PROTECTED), ("NVHE", NVHE)]):
        y_pos = y + idx * 24
        svg.add(
            f'<line x1="{x:.1f}" y1="{y_pos:.1f}" x2="{x + 30:.1f}" y2="{y_pos:.1f}" '
            f'stroke="{color}" stroke-width="2.5"/>'
        )
        svg.add(f'<circle cx="{x + 15:.1f}" cy="{y_pos:.1f}" r="4.0" fill="{color}"/>')
        svg.text(x + 40, y_pos + 4, label, size=12)


def _draw_pair_panel(
    svg: Svg,
    data: Sequence[PairRow],
    *,
    left: float,
    top: float,
    plot_w: float,
    plot_h: float,
    x_max: float,
    x_ticks: Sequence[float],
    title: str,
) -> None:
    rows = [row for row in data if row.size_mb <= x_max]
    y_max = _axis_max(max(max(row.protected, row.nvhe) for row in rows) * 1.08, 5)
    svg.text(left, top - 18, title, size=15, weight=700)

    step = _axis_step(y_max, 5)
    tick = 0.0
    while tick <= y_max + 1e-9:
        y = _y_for(tick, 0, y_max, top, plot_h)
        svg.add(f'<line x1="{left:.1f}" y1="{y:.1f}" x2="{left + plot_w:.1f}" y2="{y:.1f}" stroke="{GRID}"/>')
        svg.text(left - 10, y + 4, f"{tick:.0f}", size=11, fill=MUTED, anchor="end")
        tick += step

    for size in x_ticks:
        x = _x_for(size, 0, x_max, left, plot_w)
        svg.add(f'<line x1="{x:.1f}" y1="{top:.1f}" x2="{x:.1f}" y2="{top + plot_h:.1f}" stroke="{GRID}"/>')
        svg.add(f'<line x1="{x:.1f}" y1="{top + plot_h:.1f}" x2="{x:.1f}" y2="{top + plot_h + 5:.1f}" stroke="{AXIS}"/>')
        svg.text(x, top + plot_h + 22, _fmt_size(size), size=11, fill=MUTED, anchor="middle")

    for color, attr in [(PROTECTED, "protected"), (NVHE, "nvhe")]:
        pts = [
            (
                _x_for(row.size_mb, 0, x_max, left, plot_w),
                _y_for(getattr(row, attr), 0, y_max, top, plot_h),
            )
            for row in rows
        ]
        svg.add(
            f'<polyline points="{_polyline(pts)}" fill="none" stroke="{color}" '
            f'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
        )
        for x, y in pts:
            svg.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.0" fill="{color}" stroke="#FFFFFF" stroke-width="1"/>')

    svg.add(f'<line x1="{left:.1f}" y1="{top:.1f}" x2="{left:.1f}" y2="{top + plot_h:.1f}" stroke="{AXIS}"/>')
    svg.add(f'<line x1="{left:.1f}" y1="{top + plot_h:.1f}" x2="{left + plot_w:.1f}" y2="{top + plot_h:.1f}" stroke="{AXIS}"/>')
    svg.add(
        f'<text transform="translate({left - 52:.1f} {top + plot_h / 2:.1f}) rotate(-90)" '
        f'font-size="12" fill="{MUTED}" text-anchor="middle">us/iteration</text>'
    )
    svg.text(left + plot_w / 2, top + plot_h + 46, "mapping size (MB)", size=12, fill=MUTED, anchor="middle")


def render_lat_mmap(repo_root: Path, figure_dir: Path) -> Path:
    data = _load_overview_lat(repo_root)
    svg = Svg(
        1180,
        560,
        "Pixel lat_mmap_precise overview",
        "Pixel protected and NVHE lat_mmap_precise medians across mapping sizes, with a 0-8MB detail panel.",
    )
    svg.text(590, 34, "Pixel lat_mmap_precise", size=21, weight=700, anchor="middle")
    svg.text(590, 57, "median us/iteration; left panel shows full range, right panel expands 0-8 MB", size=13, fill=MUTED, anchor="middle")
    _draw_pair_legend(svg, 500, 82)
    _draw_pair_panel(
        svg,
        data,
        left=84,
        top=120,
        plot_w=470,
        plot_h=315,
        x_max=64,
        x_ticks=[0, 16, 32, 48, 64],
        title="Full range: 0-64 MB",
    )
    _draw_pair_panel(
        svg,
        data,
        left=665,
        top=120,
        plot_w=430,
        plot_h=315,
        x_max=8,
        x_ticks=[0, 2, 4, 6, 8],
        title="Detail: 0-8 MB",
    )
    svg.text(590, 532, "Source: pixel9proxl-aosp-pkvm-nvhe-20260701-overview-early-5run/summary/overview-early-diff.csv", size=12, fill=MUTED, anchor="middle")

    out = figure_dir / "pixel-overview-lat-mmap.svg"
    out.write_text(svg.render(), encoding="utf-8")
    return out


def render_munmap_after_write(repo_root: Path, figure_dir: Path) -> Path:
    data = _load_munmap_after_write(repo_root)
    svg = Svg(
        1180,
        585,
        "Pixel munmap_after_write_touch",
        "Pixel protected and NVHE munmap_after_write_touch medians across mapping sizes, with a 0-8MB detail panel.",
    )
    svg.text(590, 34, "Pixel mmap_split: munmap_after_write_touch", size=21, weight=700, anchor="middle")
    svg.text(590, 57, "touch work is outside the timed window; left panel shows full range, right panel expands 0-8 MB", size=13, fill=MUTED, anchor="middle")
    _draw_pair_legend(svg, 500, 82)
    _draw_pair_panel(
        svg,
        data,
        left=84,
        top=120,
        plot_w=470,
        plot_h=315,
        x_max=64,
        x_ticks=[0, 16, 32, 48, 64],
        title="Full range: 0-64 MB",
    )
    _draw_pair_panel(
        svg,
        data,
        left=665,
        top=120,
        plot_w=430,
        plot_h=315,
        x_max=8,
        x_ticks=[0, 2, 4, 6, 8],
        title="Detail: 0-8 MB",
    )
    svg.text(84, 504, "64 MB gap: +0.341 us", size=12, fill=GAP, weight=700)
    svg.text(234, 504, "Phytium/Kaitian gap was +205 us in the same split item", size=12, fill=MUTED)
    svg.text(590, 557, "Source: pixel9proxl-aosp-pkvm-nvhe-20260701-overview-early-5run/summary/overview-early-diff.csv", size=12, fill=MUTED, anchor="middle")

    out = figure_dir / "pixel-overview-munmap-after-write.svg"
    out.write_text(svg.render(), encoding="utf-8")
    return out


def render_threshold_bars(repo_root: Path, figure_dir: Path) -> Path:
    data = _load_threshold(repo_root)
    ops = ["munmap", "dontneed", "mprotect"]
    colors = {"munmap": PROTECTED, "dontneed": GAP, "mprotect": NVHE}
    points = sorted({(row.touch_mb, row.stride_kb) for row in data}, key=_threshold_point_key)
    by_key = {(row.operation, row.touch_mb, row.stride_kb): row for row in data}
    missing = [
        (op, point)
        for op in ops
        for point in points
        if (op, point[0], point[1]) not in by_key
    ]
    if missing:
        raise ValueError(f"missing op_sweep rows for threshold bar plot: {missing}")

    width, height = 1040, 540
    left, top, plot_w, plot_h = 136, 96, 720, 332
    x_min = min(0.0, min(row.gap for row in data)) - 4
    x_max = max(0.0, max(row.gap for row in data)) + 4
    svg = Svg(width, height, "Pixel op_sweep threshold gap bars", "Full Pixel op_sweep protected-minus-NVHE gaps as compact horizontal bars.")
    svg.text(36, 34, "Pixel op_sweep: protected - NVHE gap", size=18, weight=700)
    svg.text(36, 55, "all op_sweep points; each row shows munmap, MADV_DONTNEED, and mprotect", size=12, fill=MUTED)

    step = _axis_step(x_max - x_min, 5)
    tick = math.ceil(x_min / step) * step
    while tick <= x_max + 1e-9:
        x = _x_for(tick, x_min, x_max, left, plot_w)
        svg.add(f'<line x1="{x:.1f}" y1="{top:.1f}" x2="{x:.1f}" y2="{top + plot_h:.1f}" stroke="{GRID}"/>')
        svg.text(x, top + plot_h + 22, f"{tick:.0f}", size=11, fill=MUTED, anchor="middle")
        tick += step

    zero_x = _x_for(0, x_min, x_max, left, plot_w)
    svg.add(f'<line x1="{zero_x:.1f}" y1="{top:.1f}" x2="{zero_x:.1f}" y2="{top + plot_h:.1f}" stroke="{AXIS}" stroke-width="1.2"/>')
    svg.add(f'<line x1="{left:.1f}" y1="{top + plot_h:.1f}" x2="{left + plot_w:.1f}" y2="{top + plot_h:.1f}" stroke="{AXIS}"/>')
    svg.add(f'<line x1="{left:.1f}" y1="{top:.1f}" x2="{left:.1f}" y2="{top + plot_h:.1f}" stroke="{AXIS}"/>')

    row_h = plot_h / len(points)
    bar_h = 5.0
    op_gap = 7.0
    value_labels: List[Tuple[float, float, str, str]] = []
    for point_idx, point in enumerate(points):
        center_y = top + (point_idx + 0.5) * row_h
        if point_idx % 2 == 1:
            svg.add(f'<rect x="{left:.1f}" y="{center_y - row_h / 2:.1f}" width="{plot_w:.1f}" height="{row_h:.1f}" fill="#F7FAFC" opacity="0.55"/>')
        svg.text(left - 12, center_y + 4, _threshold_point_label(point), size=10, fill=MUTED, anchor="end")
        for op_idx, op in enumerate(ops):
            row = by_key[(op, point[0], point[1])]
            x0 = _x_for(0, x_min, x_max, left, plot_w)
            xv = _x_for(row.gap, x_min, x_max, left, plot_w)
            x = min(x0, xv)
            y = center_y + (op_idx - 1) * op_gap - bar_h / 2
            w = abs(xv - x0)
            svg.add(f'<rect class="threshold-bar" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{bar_h:.1f}" fill="{colors[op]}" opacity="0.86"/>')
            label_x = xv + 4 if row.gap >= 0 else xv - 4
            anchor = "start" if row.gap >= 0 else "end"
            value_labels.append((label_x, y + bar_h + 1, f"{row.gap:+.1f}", anchor))

    for label_x, label_y, value, anchor in value_labels:
        svg.text(label_x, label_y, value, size=8, fill=TEXT, anchor=anchor)

    legend_x, legend_y = left + plot_w + 30, top + 16
    for idx, op in enumerate(ops):
        y = legend_y + idx * 24
        svg.add(f'<rect x="{legend_x:.1f}" y="{y - 11:.1f}" width="16" height="16" fill="{colors[op]}" opacity="0.86"/>')
        svg.text(legend_x + 24, y + 1, op, size=12)

    svg.text(left + plot_w / 2, top + plot_h + 48, "protected - NVHE (us/iteration)", size=12, fill=MUTED, anchor="middle")

    out = figure_dir / "pixel-ported-threshold-gap.svg"
    out.write_text(svg.render(), encoding="utf-8")
    return out


def render_threshold_trends(repo_root: Path, figure_dir: Path) -> Path:
    data = _load_threshold(repo_root)
    ops = ["munmap", "dontneed", "mprotect"]
    op_titles = {
        "munmap": "munmap",
        "dontneed": "MADV_DONTNEED",
        "mprotect": "mprotect",
    }
    colors = {"munmap": PROTECTED, "dontneed": GAP, "mprotect": NVHE}
    points = sorted({(row.touch_mb, row.stride_kb) for row in data}, key=_threshold_point_key)
    by_key = {(row.operation, row.touch_mb, row.stride_kb): row for row in data}
    missing = [
        (op, point)
        for op in ops
        for point in points
        if (op, point[0], point[1]) not in by_key
    ]
    if missing:
        raise ValueError(f"missing op_sweep rows for threshold plot: {missing}")

    dense_points = [point for point in points if point[1] == 4]
    sparse_points = [point for point in points if point[1] != 4]
    if sparse_points != [(6.4, 16)]:
        raise ValueError(f"unexpected sparse threshold points: {sparse_points}")
    x_points = dense_points + sparse_points

    width, height = 1120, 650
    left, top, plot_w, panel_h = 84, 96, 930, 116
    panel_gap = 42
    y_min, y_max = -10.0, 35.0
    svg = Svg(width, height, "Pixel op_sweep threshold gaps", "Pixel protected minus NVHE gaps for munmap, MADV_DONTNEED, and mprotect.")
    svg.text(36, 34, "Pixel op_sweep: protected - NVHE gap", size=18, weight=700)
    svg.text(36, 55, "three per-operation trends; dense line uses 4KB stride, hollow point is 6.4MB/16K sparse reference", size=12, fill=MUTED)

    def x_for_idx(idx: int) -> float:
        return left + (idx / (len(x_points) - 1)) * plot_w

    for op_idx, op in enumerate(ops):
        panel_top = top + op_idx * (panel_h + panel_gap)
        panel_bottom = panel_top + panel_h
        color = colors[op]

        svg.add(
            f'<text class="threshold-panel-title" x="{left:.1f}" y="{panel_top - 14:.1f}" '
            f'font-size="14" fill="{color}" font-weight="700" text-anchor="start">{op_titles[op]}</text>'
        )

        for tick in [-10, 0, 10, 20, 30]:
            y = _y_for(tick, y_min, y_max, panel_top, panel_h)
            stroke = AXIS if tick == 0 else GRID
            width_attr = ' stroke-width="1.2"' if tick == 0 else ""
            svg.add(f'<line x1="{left:.1f}" y1="{y:.1f}" x2="{left + plot_w:.1f}" y2="{y:.1f}" stroke="{stroke}"{width_attr}/>')
            svg.text(left - 10, y + 4, f"{tick}", size=10, fill=MUTED, anchor="end")

        for point_idx, point in enumerate(x_points):
            x = x_for_idx(point_idx)
            svg.add(f'<line x1="{x:.1f}" y1="{panel_top:.1f}" x2="{x:.1f}" y2="{panel_bottom:.1f}" stroke="{GRID}" opacity="0.45"/>')

        svg.add(f'<line x1="{left:.1f}" y1="{panel_bottom:.1f}" x2="{left + plot_w:.1f}" y2="{panel_bottom:.1f}" stroke="{AXIS}"/>')
        svg.add(f'<line x1="{left:.1f}" y1="{panel_top:.1f}" x2="{left:.1f}" y2="{panel_bottom:.1f}" stroke="{AXIS}"/>')

        dense_series = []
        for point in dense_points:
            row = by_key[(op, point[0], point[1])]
            x = x_for_idx(x_points.index(point))
            y = _y_for(row.gap, y_min, y_max, panel_top, panel_h)
            dense_series.append((x, y))
        svg.add(
            f'<polyline class="threshold-dense-line" points="{_polyline(dense_series)}" '
            f'fill="none" stroke="{color}" stroke-width="2.0" stroke-linejoin="round" stroke-linecap="round"/>'
        )
        for x, y in dense_series:
            svg.add(
                f'<circle class="threshold-dense-marker" cx="{x:.1f}" cy="{y:.1f}" r="3.0" '
                f'fill="{color}" stroke="#FFFFFF" stroke-width="0.9"/>'
            )

        sparse_point = sparse_points[0]
        sparse_row = by_key[(op, sparse_point[0], sparse_point[1])]
        sparse_x = x_for_idx(x_points.index(sparse_point))
        sparse_y = _y_for(sparse_row.gap, y_min, y_max, panel_top, panel_h)
        svg.add(
            f'<circle class="threshold-sparse-marker" cx="{sparse_x:.1f}" cy="{sparse_y:.1f}" r="4.0" '
            f'fill="#FFFFFF" stroke="{color}" stroke-width="2.0"/>'
        )

    bottom_axis_y = top + (len(ops) - 1) * (panel_h + panel_gap) + panel_h
    for point_idx, point in enumerate(x_points):
        x = x_for_idx(point_idx)
        label = _threshold_point_label(point)
        svg.add(
            f'<text x="{x:.1f}" y="{bottom_axis_y + 26:.1f}" font-size="10" fill="{MUTED}" '
            f'font-weight="400" text-anchor="end" transform="rotate(-35 {x:.1f} {bottom_axis_y + 26:.1f})">{escape(label)}</text>'
        )

    svg.text(28, top + 12, "us", size=12, fill=MUTED)
    svg.text(left + plot_w / 2, height - 24, "touch size / stride", size=12, fill=MUTED, anchor="middle")
    svg.text(left + plot_w - 8, 74, "filled: 4KB stride dense line; hollow: 6.4MB/16K sparse reference", size=12, fill=MUTED, anchor="end")

    out = figure_dir / "pixel-ported-threshold-trends.svg"
    out.write_text(svg.render(), encoding="utf-8")
    return out


def _draw_gap_bar_axes(
    svg: Svg,
    *,
    left: float,
    top: float,
    plot_w: float,
    plot_h: float,
    y_min: float,
    y_max: float,
) -> None:
    step = _axis_step(y_max - y_min, 5)
    tick = math.ceil(y_min / step) * step
    while tick <= y_max + 1e-9:
        y = _y_for(tick, y_min, y_max, top, plot_h)
        svg.add(f'<line x1="{left:.1f}" y1="{y:.1f}" x2="{left + plot_w:.1f}" y2="{y:.1f}" stroke="{GRID}"/>')
        svg.text(left - 10, y + 4, f"{tick:.0f}", size=11, fill=MUTED, anchor="end")
        tick += step
    _draw_zero_axis(svg, left, top, plot_w, plot_h, y_min, y_max)
    svg.add(f'<line x1="{left:.1f}" y1="{top:.1f}" x2="{left:.1f}" y2="{top + plot_h:.1f}" stroke="{AXIS}"/>')
    svg.add(f'<line x1="{left:.1f}" y1="{top + plot_h:.1f}" x2="{left + plot_w:.1f}" y2="{top + plot_h:.1f}" stroke="{AXIS}"/>')


def _bar_label_y(value: float, y_min: float, y_max: float, top: float, plot_h: float) -> Tuple[float, str]:
    y = _y_for(value, y_min, y_max, top, plot_h)
    if value >= 0:
        return max(top + 12, y - 7), "middle"
    return min(top + plot_h - 4, y + 16), "middle"


def _draw_platform_gap_panel(
    svg: Svg,
    rows: Sequence[PlatformGapRow],
    *,
    left: float,
    top: float,
    plot_w: float,
    plot_h: float,
    y_min: float,
    y_max: float,
    title: str,
    show_n80: bool,
) -> None:
    svg.text(left, top - 18, title, size=15, weight=700)
    _draw_gap_bar_axes(svg, left=left, top=top, plot_w=plot_w, plot_h=plot_h, y_min=y_min, y_max=y_max)

    group_w = plot_w / len(rows)
    bar_w = 28 if show_n80 else 38
    for idx, row in enumerate(rows):
        center = left + group_w * idx + group_w / 2
        y0 = _y_for(0, y_min, y_max, top, plot_h)
        series = [("N80", row.n80_gap, N80_COLOR), ("Pixel", row.pixel_gap, PIXEL_COLOR)] if show_n80 else [("Pixel", row.pixel_gap, PIXEL_COLOR)]
        for series_idx, (_, value, color) in enumerate(series):
            offset = (series_idx - (len(series) - 1) / 2) * (bar_w + 8)
            x = center + offset
            yv = _y_for(value, y_min, y_max, top, plot_h)
            bar_top = min(y0, yv)
            bar_h = max(1.0, abs(y0 - yv))
            svg.add(f'<rect x="{x - bar_w / 2:.1f}" y="{bar_top:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{color}" opacity="0.88"/>')
            label_y, anchor = _bar_label_y(value, y_min, y_max, top, plot_h)
            svg.text(x, label_y, f"{value:+.1f}", size=10, anchor=anchor, fill=TEXT)

        svg.text(center, top + plot_h + 24, row.label_top, size=11, anchor="middle")
        svg.text(center, top + plot_h + 41, row.label_bottom, size=10, fill=MUTED, anchor="middle")


def render_pixel_n80_munmap_comparison(repo_root: Path, figure_dir: Path) -> Path:
    rows = _load_pixel_n80_munmap_comparison(repo_root)
    width, height = 1180, 570
    full_left, detail_left = 86, 684
    top, plot_h = 118, 300
    full_w, detail_w = 470, 410
    all_values = [value for row in rows for value in (row.n80_gap, row.pixel_gap)]
    y_min = min(-10.0, math.floor(min(all_values) / 10.0) * 10.0)
    y_max = _axis_max(max(all_values) * 1.08, 5)

    svg = Svg(
        width,
        height,
        "Pixel vs N80 munmap threshold comparison",
        "Same op_sweep munmap threshold points on Pixel and N80, shown as protected minus NVHE gaps.",
    )
    svg.text(590, 34, "Pixel vs N80: same munmap threshold experiment", size=21, weight=700, anchor="middle")
    svg.text(590, 57, "protected - NVHE gap, us/iteration; mmap and touch work are outside the timed window", size=13, fill=MUTED, anchor="middle")

    legend_x = 480
    for idx, (label, color) in enumerate([("N80", N80_COLOR), ("Pixel", PIXEL_COLOR)]):
        x = legend_x + idx * 96
        svg.add(f'<rect x="{x:.1f}" y="78.0" width="18" height="18" fill="{color}" opacity="0.88"/>')
        svg.text(x + 26, 91, label, size=12)

    _draw_platform_gap_panel(
        svg,
        rows,
        left=full_left,
        top=top,
        plot_w=full_w,
        plot_h=plot_h,
        y_min=y_min,
        y_max=y_max,
        title="Full scale: N80 signal dominates",
        show_n80=True,
    )
    _draw_platform_gap_panel(
        svg,
        rows,
        left=detail_left,
        top=top,
        plot_w=detail_w,
        plot_h=plot_h,
        y_min=-10,
        y_max=40,
        title="Pixel detail: -10 to 40 us",
        show_n80=False,
    )
    svg.text(28, top + 8, "us", size=12, fill=MUTED)
    svg.text(detail_left, top + plot_h + 72, "Right panel expands Pixel only; N80 1.9MB and 6.4MB gaps are off this scale.", size=12, fill=MUTED)
    svg.text(590, 540, "Sources: N80 op-sweep-n80/{protected,nvhe}.txt; Pixel ported-suite-diff.csv", size=12, fill=MUTED, anchor="middle")

    out = figure_dir / "pixel-n80-munmap-threshold-comparison.svg"
    out.write_text(svg.render(), encoding="utf-8")
    return out


def _draw_platform_pct_panel(
    svg: Svg,
    rows: Sequence[PlatformGapRow],
    *,
    left: float,
    top: float,
    plot_w: float,
    plot_h: float,
    y_min: float,
    y_max: float,
    title: str,
    show_n80: bool,
) -> None:
    svg.text(left, top - 18, title, size=15, weight=700)
    _draw_gap_bar_axes(svg, left=left, top=top, plot_w=plot_w, plot_h=plot_h, y_min=y_min, y_max=y_max)

    group_w = plot_w / len(rows)
    bar_w = 28 if show_n80 else 38
    for idx, row in enumerate(rows):
        center = left + group_w * idx + group_w / 2
        y0 = _y_for(0, y_min, y_max, top, plot_h)
        series = [("N80", row.n80_pct, N80_COLOR), ("Pixel", row.pixel_pct, PIXEL_COLOR)] if show_n80 else [("Pixel", row.pixel_pct, PIXEL_COLOR)]
        for series_idx, (_, value, color) in enumerate(series):
            offset = (series_idx - (len(series) - 1) / 2) * (bar_w + 8)
            x = center + offset
            yv = _y_for(value, y_min, y_max, top, plot_h)
            bar_top = min(y0, yv)
            bar_h = max(1.0, abs(y0 - yv))
            svg.add(f'<rect x="{x - bar_w / 2:.1f}" y="{bar_top:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{color}" opacity="0.88"/>')
            label_y, anchor = _bar_label_y(value, y_min, y_max, top, plot_h)
            svg.text(x, label_y, f"{value:+.1f}%", size=10, anchor=anchor, fill=TEXT)

        svg.text(center, top + plot_h + 24, row.label_top, size=11, anchor="middle")
        svg.text(center, top + plot_h + 41, row.label_bottom, size=10, fill=MUTED, anchor="middle")


def render_pixel_n80_munmap_relative_comparison(repo_root: Path, figure_dir: Path) -> Path:
    rows = _load_pixel_n80_munmap_comparison(repo_root)
    width, height = 1180, 570
    full_left, detail_left = 86, 684
    top, plot_h = 118, 300
    full_w, detail_w = 470, 410
    all_values = [value for row in rows for value in (row.n80_pct, row.pixel_pct)]
    y_min = min(-10.0, math.floor(min(all_values) / 10.0) * 10.0)
    y_max = _axis_max(max(all_values) * 1.08, 5)

    svg = Svg(
        width,
        height,
        "Pixel vs N80 munmap relative slowdown",
        "Same op_sweep munmap threshold points on Pixel and N80, shown as relative slowdown versus NVHE.",
    )
    svg.text(590, 34, "Pixel vs N80: relative slowdown in the same munmap experiment", size=21, weight=700, anchor="middle")
    svg.text(590, 57, "(protected / NVHE - 1) * 100%; same timed munmap-only window as the absolute-gap figure", size=13, fill=MUTED, anchor="middle")

    legend_x = 480
    for idx, (label, color) in enumerate([("N80", N80_COLOR), ("Pixel", PIXEL_COLOR)]):
        x = legend_x + idx * 96
        svg.add(f'<rect x="{x:.1f}" y="78.0" width="18" height="18" fill="{color}" opacity="0.88"/>')
        svg.text(x + 26, 91, label, size=12)

    _draw_platform_pct_panel(
        svg,
        rows,
        left=full_left,
        top=top,
        plot_w=full_w,
        plot_h=plot_h,
        y_min=y_min,
        y_max=y_max,
        title="Full scale: relative N80 spike",
        show_n80=True,
    )
    _draw_platform_pct_panel(
        svg,
        rows,
        left=detail_left,
        top=top,
        plot_w=detail_w,
        plot_h=plot_h,
        y_min=-10,
        y_max=15,
        title="Pixel detail: -10% to +15%",
        show_n80=False,
    )
    svg.text(28, top + 8, "%", size=12, fill=MUTED)
    svg.text(detail_left, top + plot_h + 72, "Right panel expands Pixel only; N80 1.9MB and 6.4MB relative gaps are off this scale.", size=12, fill=MUTED)
    svg.text(590, 540, "Sources: N80 op-sweep-n80/{protected,nvhe}.txt; Pixel ported-suite-diff.csv", size=12, fill=MUTED, anchor="middle")

    out = figure_dir / "pixel-n80-munmap-threshold-relative-comparison.svg"
    out.write_text(svg.render(), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--figure-dir", type=Path, default=FIGURE_DIR)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    figure_dir = (repo_root / args.figure_dir).resolve()
    figure_dir.mkdir(parents=True, exist_ok=True)

    outputs = [
        render_madv(repo_root, figure_dir),
        render_lat_mmap(repo_root, figure_dir),
        render_munmap_after_write(repo_root, figure_dir),
        render_threshold_bars(repo_root, figure_dir),
        render_threshold_trends(repo_root, figure_dir),
        render_pixel_n80_munmap_comparison(repo_root, figure_dir),
        render_pixel_n80_munmap_relative_comparison(repo_root, figure_dir),
    ]
    for output in outputs:
        print(output.relative_to(repo_root))


if __name__ == "__main__":
    main()
