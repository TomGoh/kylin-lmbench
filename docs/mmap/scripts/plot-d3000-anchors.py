#!/usr/bin/env python3
"""Render D3000 mechanism-anchor SVGs directly from campaign raw logs.

Each raw anchor point is first reduced to a median inside one boot.  Relative
overheads are then calculated between protected and nVHE within the same pair.
"""

from __future__ import annotations

import argparse
import math
import re
import statistics
from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Dict, List, NamedTuple, Sequence, Tuple, Union


TEXT = "#1F2933"
MUTED = "#64707D"
GRID = "#E8EDF3"
AXIS = "#5C6670"
NVHE = "#4D7C59"
PROTECTED = "#C23B2A"
START = "#D97706"
END = "#526D82"
DOT = "#243B53"

AnchorKey = Tuple[int, str, str, str]

LAT_MMAP_RE = re.compile(r"size_mb=([0-9.]+).*?per_iter_us=([0-9.]+)")
OP_RE = re.compile(r"label=([^ ]+).*?mean=([0-9.]+)\s+us")


class AnchorData(NamedTuple):
    values: Dict[AnchorKey, float]
    sizes: List[float]
    pairs: List[int]
    campaign_name: str


class ControlDef(NamedTuple):
    metric: str
    label: str


CONTROLS = [
    ControlDef("lat_mmap:64", "64 MiB lat_mmap"),
    ControlDef("op:dense-1.9", "dense 1.9 MiB munmap"),
    ControlDef("op:dense-2.0", "dense 2.0 MiB munmap"),
    ControlDef("op:sparse-6.4", "sparse 6.4 MiB munmap"),
]


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


def _format_size(size: float) -> str:
    return str(int(size)) if size.is_integer() else f"{size:g}"


def _parse_lat_mmap(path: Path) -> Dict[float, List[float]]:
    values: Dict[float, List[float]] = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        match = LAT_MMAP_RE.search(line)
        if match:
            values[float(match.group(1))].append(float(match.group(2)))
    if not values:
        raise ValueError(f"{path} has no lat_mmap_precise samples")
    return dict(values)


def _parse_op_sweep(path: Path) -> Dict[str, List[float]]:
    values: Dict[str, List[float]] = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        match = OP_RE.search(line)
        if match:
            values[match.group(1)].append(float(match.group(2)))
    if not values:
        raise ValueError(f"{path} has no op_sweep samples")
    return dict(values)


def _last_numeric_value(path: Path) -> float:
    value = None
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        try:
            float(fields[0])
            value = float(fields[1])
        except ValueError:
            continue
    if value is None:
        raise ValueError(f"{path} has no two-column numeric samples")
    return value


def _parse_lat_mem(root: Path) -> List[float]:
    paths = sorted(root.glob("lat-mem-r*.txt"))
    if not paths:
        raise ValueError(f"{root} has no lat_mem_rd result files")
    return [_last_numeric_value(path) for path in paths]


def load_anchors(campaign: Path) -> AnchorData:
    campaign = campaign.resolve()
    values: Dict[AnchorKey, float] = {}
    all_sizes = None
    present_groups = set()

    for pair_dir in sorted(campaign.glob("pair-[1-5]")):
        try:
            pair = int(pair_dir.name.removeprefix("pair-"))
        except ValueError:
            continue
        for mode in ("nvhe", "protected"):
            for phase in ("start", "end"):
                root = pair_dir / mode / f"anchors-{phase}" / "rep-00"
                if not (root / "VALID").exists():
                    continue
                mmap_values = _parse_lat_mmap(root / "lat-mmap-precise.txt")
                op_values = _parse_op_sweep(root / "op-sweep.txt")
                lat_mem = _parse_lat_mem(root)
                sizes = sorted(mmap_values)
                if all_sizes is None:
                    all_sizes = sizes
                elif sizes != all_sizes:
                    raise ValueError(f"{root} has mmap sizes {sizes}, expected {all_sizes}")

                for size, samples in mmap_values.items():
                    values[(pair, mode, phase, f"lat_mmap:{_format_size(size)}")] = statistics.median(samples)
                for label, samples in op_values.items():
                    values[(pair, mode, phase, f"op:{label}")] = statistics.median(samples)
                values[(pair, mode, phase, "lat_mem:64")] = statistics.median(lat_mem)
                present_groups.add((pair, mode, phase))

    if all_sizes is None:
        raise ValueError(f"{campaign} has no valid anchor groups")
    complete_pairs = [
        pair
        for pair in range(1, 6)
        if all((pair, mode, phase) in present_groups for mode in ("nvhe", "protected") for phase in ("start", "end"))
    ]
    if not complete_pairs:
        raise ValueError(f"{campaign} has no complete nVHE/protected start/end anchor pair")
    return AnchorData(values=values, sizes=all_sizes, pairs=complete_pairs, campaign_name=campaign.name)


def paired_penalties(data: AnchorData, phase: str, metric: str) -> Dict[int, float]:
    penalties = {}
    for pair in data.pairs:
        nvhe = data.values[(pair, "nvhe", phase, metric)]
        protected = data.values[(pair, "protected", phase, metric)]
        penalties[pair] = (protected / nvhe - 1.0) * 100.0
    return penalties


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
    return max(step, math.ceil(max_value / step) * step)


def _polyline(points: Sequence[Tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def _log_x_positions(sizes: Sequence[float], left: float, width: float) -> Dict[float, float]:
    logs = [math.log2(size) for size in sizes]
    low, high = min(logs), max(logs)
    return {
        size: left + ((math.log2(size) - low) / (high - low)) * width if high != low else left + width / 2
        for size in sizes
    }


def _draw_mmap_panel(
    svg: Svg,
    data: AnchorData,
    phase: str,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    y_max: float,
) -> None:
    bottom = top + height
    x_by_size = _log_x_positions(data.sizes, left, width)
    svg.text(left, top - 38, f"Boot {phase}", size=17, weight=700)
    svg.text(left, top - 16, "absolute latency; faint lines are individual boot pairs", size=11, fill=MUTED)

    for index in range(6):
        value = y_max * index / 5
        y = bottom - value / y_max * height
        svg.add(f'<line x1="{left:.1f}" y1="{y:.1f}" x2="{left + width:.1f}" y2="{y:.1f}" stroke="{GRID}"/>')
        svg.text(left - 10, y + 4, f"{value:.0f}", size=11, fill=MUTED, anchor="end")
    for size in data.sizes:
        x = x_by_size[size]
        svg.add(f'<line x1="{x:.1f}" y1="{top:.1f}" x2="{x:.1f}" y2="{bottom:.1f}" stroke="#F3F5F8"/>')
        svg.text(x, bottom + 23, _format_size(size), size=11, fill=TEXT, anchor="middle")
    svg.add(f'<line x1="{left:.1f}" y1="{top:.1f}" x2="{left:.1f}" y2="{bottom:.1f}" stroke="{AXIS}"/>')
    svg.add(f'<line x1="{left:.1f}" y1="{bottom:.1f}" x2="{left + width:.1f}" y2="{bottom:.1f}" stroke="{AXIS}"/>')

    for mode, color in (("nvhe", NVHE), ("protected", PROTECTED)):
        for pair in data.pairs:
            points = []
            for size in data.sizes:
                metric = f"lat_mmap:{_format_size(size)}"
                value = data.values[(pair, mode, phase, metric)]
                points.append((x_by_size[size], bottom - value / y_max * height))
            svg.add(f'<polyline points="{_polyline(points)}" fill="none" stroke="{color}" stroke-width="1.1" opacity="0.22"/>')

        aggregate = []
        for size in data.sizes:
            metric = f"lat_mmap:{_format_size(size)}"
            value = statistics.median(data.values[(pair, mode, phase, metric)] for pair in data.pairs)
            aggregate.append((x_by_size[size], bottom - value / y_max * height))
        svg.add(
            f'<polyline points="{_polyline(aggregate)}" fill="none" stroke="{color}" stroke-width="3" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )
        for x, y in aggregate:
            svg.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#FFFFFF" stroke="{color}" stroke-width="2"/>')

    penalty = statistics.median(paired_penalties(data, phase, "lat_mmap:64").values())
    svg.add(f'<rect x="{left + width - 125:.1f}" y="{top + 14:.1f}" width="115" height="29" rx="4" fill="#FFFFFF" stroke="#D9DEE7"/>')
    svg.text(left + width - 67.5, top + 34, f"64 MiB: {penalty:+.1f}%", size=11, fill=PROTECTED, anchor="middle", weight=700)
    svg.text(left + width / 2, bottom + 49, "mapping size (MiB, log2 scale)", size=12, fill=MUTED, anchor="middle")


def write_lat_mmap_figure(data: AnchorData, out_path: Path, *, source_label: str) -> None:
    width, height = 1240, 610
    all_values = [
        data.values[(pair, mode, phase, f"lat_mmap:{_format_size(size)}")]
        for pair in data.pairs
        for mode in ("nvhe", "protected")
        for phase in ("start", "end")
        for size in data.sizes
    ]
    y_max = _axis_max(max(all_values) * 1.05, 5)
    svg = Svg(
        width,
        height,
        "D3000 lat_mmap anchor across mapping sizes",
        "Boot-start and boot-end D3000 lat_mmap_precise results for nVHE and pKVM, reduced inside each boot and aggregated across complete boot pairs.",
    )
    svg.text(width / 2, 35, "D3000 mechanism anchor: lat_mmap across mapping sizes", size=22, weight=700, anchor="middle")
    svg.text(width / 2, 59, f"THP profile from campaign metadata; n={len(data.pairs)} complete boot pair{'s' if len(data.pairs) != 1 else ''}", size=13, fill=MUTED, anchor="middle")

    _draw_mmap_panel(svg, data, "start", left=86, top=130, width=470, height=330, y_max=y_max)
    _draw_mmap_panel(svg, data, "end", left=684, top=130, width=470, height=330, y_max=y_max)

    legend_y = 92
    for index, (label, color) in enumerate((("nVHE", NVHE), ("pKVM", PROTECTED))):
        x = 482 + index * 118
        svg.add(f'<line x1="{x:.1f}" y1="{legend_y:.1f}" x2="{x + 28:.1f}" y2="{legend_y:.1f}" stroke="{color}" stroke-width="3"/>')
        svg.add(f'<circle cx="{x + 14:.1f}" cy="{legend_y:.1f}" r="4" fill="#FFFFFF" stroke="{color}" stroke-width="2"/>')
        svg.text(x + 37, legend_y + 4, label, size=12)
    svg.text(27, 139, "us", size=12, fill=MUTED)
    svg.text(width / 2, height - 18, f"Source: {source_label}/pair-*/{{nvhe,protected}}/anchors-{{start,end}}", size=11, fill=MUTED, anchor="middle")
    out_path.write_text(svg.render(), encoding="utf-8")


def _control_axis_bounds(values: Sequence[float]) -> Tuple[float, float]:
    low = min(0.0, min(values))
    high = max(0.0, max(values))
    high_axis = _axis_max(high * 1.08, 5)
    if low < 0:
        low_axis = -_axis_max(abs(low) * 1.08, 3)
    else:
        low_axis = 0.0
    if high_axis == low_axis:
        high_axis = low_axis + 1.0
    return low_axis, high_axis


def _x_for(value: float, low: float, high: float, left: float, width: float) -> float:
    return left + (value - low) / (high - low) * width


def _draw_control_penalties(
    svg: Svg,
    data: AnchorData,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
) -> None:
    row_gap = height / len(CONTROLS)
    label_width = 190.0
    plot_left = left + label_width
    plot_width = width - label_width
    penalties = {
        (definition.metric, phase): paired_penalties(data, phase, definition.metric)
        for definition in CONTROLS
        for phase in ("start", "end")
    }
    all_values = [value for series in penalties.values() for value in series.values()]
    low, high = _control_axis_bounds(all_values)
    zero_x = _x_for(0.0, low, high, plot_left, plot_width)

    svg.text(left, top - 40, "Mapping-management penalty", size=17, weight=700)
    svg.text(left, top - 18, "(pKVM / nVHE - 1); bars are paired medians", size=11, fill=MUTED)
    tick_step = _nice_step(high - low, 5)
    tick = math.ceil(low / tick_step) * tick_step
    while tick <= high + tick_step / 10:
        x = _x_for(tick, low, high, plot_left, plot_width)
        svg.add(f'<line x1="{x:.1f}" y1="{top:.1f}" x2="{x:.1f}" y2="{top + height:.1f}" stroke="{AXIS if abs(tick) < 1e-9 else GRID}" stroke-width="{1.5 if abs(tick) < 1e-9 else 1}"/>')
        svg.text(x, top + height + 22, f"{tick:+.0f}%", size=10, fill=MUTED, anchor="middle")
        tick += tick_step

    for row_index, definition in enumerate(CONTROLS):
        row_y = top + row_index * row_gap
        svg.text(left, row_y + row_gap / 2 + 4, definition.label, size=11, fill=TEXT)
        for phase_index, (phase, color) in enumerate((("start", START), ("end", END))):
            series = penalties[(definition.metric, phase)]
            median = statistics.median(series.values())
            center_y = row_y + 18 + phase_index * 18
            value_x = _x_for(median, low, high, plot_left, plot_width)
            bar_x = min(zero_x, value_x)
            bar_width = max(1.2, abs(value_x - zero_x))
            svg.add(f'<rect x="{bar_x:.1f}" y="{center_y - 6:.1f}" width="{bar_width:.1f}" height="12" rx="2" fill="{color}" opacity="0.62"/>')
            for dot_index, (pair, value) in enumerate(sorted(series.items())):
                dot_x = _x_for(value, low, high, plot_left, plot_width)
                jitter = ((dot_index % 3) - 1) * 2.5 if len(series) > 1 else 0
                svg.add(
                    f'<circle cx="{dot_x:.1f}" cy="{center_y + jitter:.1f}" r="2.8" fill="{DOT}" '
                    f'stroke="#FFFFFF" stroke-width="0.7"><title>Pair {pair}: {value:+.2f}%</title></circle>'
                )
            anchor = "start" if median >= 0 else "end"
            label_x = value_x + 6 if median >= 0 else value_x - 6
            svg.text(label_x, center_y + 4, f"{median:+.1f}%", size=10, fill=color, anchor=anchor, weight=700)


def _draw_lat_mem_control(
    svg: Svg,
    data: AnchorData,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
) -> None:
    values = [
        data.values[(pair, mode, phase, "lat_mem:64")]
        for pair in data.pairs
        for mode in ("nvhe", "protected")
        for phase in ("start", "end")
    ]
    span = max(values) - min(values)
    padding = max(0.05, span * 0.18)
    y_min = min(values) - padding
    y_max = max(values) + padding
    bottom = top + height
    x_positions = {"start": left + width * 0.28, "end": left + width * 0.72}

    svg.text(left, top - 40, "Steady-memory negative control", size=17, weight=700)
    svg.text(left, top - 18, "lat_mem_rd 64 MiB endpoint; narrow absolute scale", size=11, fill=MUTED)
    for index in range(5):
        value = y_min + (y_max - y_min) * index / 4
        y = bottom - (value - y_min) / (y_max - y_min) * height
        svg.add(f'<line x1="{left:.1f}" y1="{y:.1f}" x2="{left + width:.1f}" y2="{y:.1f}" stroke="{GRID}"/>')
        svg.text(left - 10, y + 4, f"{value:.2f}", size=10, fill=MUTED, anchor="end")
    svg.add(f'<line x1="{left:.1f}" y1="{top:.1f}" x2="{left:.1f}" y2="{bottom:.1f}" stroke="{AXIS}"/>')
    svg.add(f'<line x1="{left:.1f}" y1="{bottom:.1f}" x2="{left + width:.1f}" y2="{bottom:.1f}" stroke="{AXIS}"/>')

    for mode_index, (mode, color) in enumerate((("nvhe", NVHE), ("protected", PROTECTED))):
        aggregate_points = []
        offset = -12 if mode_index == 0 else 12
        for phase in ("start", "end"):
            x = x_positions[phase] + offset
            phase_values = [data.values[(pair, mode, phase, "lat_mem:64")] for pair in data.pairs]
            for dot_index, value in enumerate(phase_values):
                jitter_x = ((dot_index % 3) - 1) * 2.5 if len(phase_values) > 1 else 0
                y = bottom - (value - y_min) / (y_max - y_min) * height
                svg.add(f'<circle cx="{x + jitter_x:.1f}" cy="{y:.1f}" r="2.8" fill="{color}" opacity="0.32"/>')
            median = statistics.median(phase_values)
            y = bottom - (median - y_min) / (y_max - y_min) * height
            aggregate_points.append((x, y))
            svg.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#FFFFFF" stroke="{color}" stroke-width="2.2"/>')
        svg.add(f'<polyline points="{_polyline(aggregate_points)}" fill="none" stroke="{color}" stroke-width="2.5"/>')

    for phase in ("start", "end"):
        x = x_positions[phase]
        penalty = statistics.median(paired_penalties(data, phase, "lat_mem:64").values())
        svg.text(x, top + 22, f"{penalty:+.2f}%", size=11, fill=TEXT, anchor="middle", weight=700)
        svg.text(x, bottom + 25, f"boot {phase}", size=11, fill=TEXT, anchor="middle")
    svg.text(left - 44, top + 8, "ns", size=11, fill=MUTED)


def write_control_figure(data: AnchorData, out_path: Path, *, source_label: str) -> None:
    width, height = 1240, 610
    svg = Svg(
        width,
        height,
        "D3000 mapping anchors and steady-memory control",
        "Paired pKVM overhead for D3000 mapping-management anchors beside the absolute lat_mem_rd steady-memory negative control.",
    )
    svg.text(width / 2, 35, "D3000 mechanism anchors: mapping cost versus steady memory", size=22, weight=700, anchor="middle")
    svg.text(width / 2, 59, "boot-paired penalties on the left; absolute negative-control latency on the right", size=13, fill=MUTED, anchor="middle")

    _draw_control_penalties(svg, data, left=42, top=135, width=650, height=330)
    _draw_lat_mem_control(svg, data, left=795, top=135, width=350, height=330)

    legend_y = 510
    for index, (label, color) in enumerate((("boot start", START), ("boot end", END), ("nVHE", NVHE), ("pKVM", PROTECTED))):
        x = 310 + index * 155
        svg.add(f'<rect x="{x:.1f}" y="{legend_y - 11:.1f}" width="18" height="12" rx="2" fill="{color}" opacity="0.78"/>')
        svg.text(x + 26, legend_y, label, size=11, fill=MUTED)
    svg.text(width / 2, height - 18, f"Source: {source_label}/pair-*/{{nvhe,protected}}/anchors-{{start,end}}", size=11, fill=MUTED, anchor="middle")
    out_path.write_text(svg.render(), encoding="utf-8")


def _safe_prefix(value: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in "-_" else "-" for character in value)
    return cleaned.strip("-") or "d3000"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render D3000 mechanism-anchor SVGs from a campaign result tree")
    parser.add_argument("campaign", type=Path)
    parser.add_argument("--figure-dir", type=Path, default=Path("docs/mmap/figures"))
    parser.add_argument("--prefix", help="output filename prefix; default is campaign directory name")
    args = parser.parse_args()

    source_label = args.campaign.as_posix().rstrip("/")
    campaign = args.campaign.resolve()
    data = load_anchors(campaign)
    figure_dir = args.figure_dir.resolve()
    figure_dir.mkdir(parents=True, exist_ok=True)
    prefix = _safe_prefix(args.prefix or campaign.name)
    outputs = [
        figure_dir / f"{prefix}-anchor-lat-mmap.svg",
        figure_dir / f"{prefix}-anchor-controls.svg",
    ]
    write_lat_mmap_figure(data, outputs[0], source_label=source_label)
    write_control_figure(data, outputs[1], source_label=source_label)
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
