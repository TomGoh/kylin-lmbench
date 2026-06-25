#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Render the stage-2 mmap split result for the 64 MB row as SVG."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from html import escape
from pathlib import Path
from typing import Dict, List, NamedTuple, Tuple, Union


SOURCE_DIR = Path("results/mmap-split-kaitian")
SIZE_MB = 64.0

MODE_FILES = {
    "NVHE": SOURCE_DIR / "nvhe.csv",
    "pKVM": SOURCE_DIR / "pkvm.csv",
}

BENCHES: List[Tuple[str, str]] = [
    ("mmap_unmap", "mmap_unmap"),
    ("write_touch_cold", "write_touch_cold"),
    ("munmap_after_no_touch", "munmap_after_no_touch"),
    ("munmap_after_write_touch", "munmap_after_write_touch"),
    ("mmap_write_touch_unmap", "mmap_write_touch_unmap"),
]

MODE_COLORS = {
    "NVHE": "#4D7C59",
    "pKVM": "#C23B2A",
}

DELTA_COLORS = {
    "default": "#7B8794",
    "highlight": "#C23B2A",
    "anchor": "#4B5563",
}


class SplitMeasurements(NamedTuple):
    median_us: Dict[str, Dict[str, float]]
    delta_us: Dict[str, float]
    coverage_pct: float
    sources: Dict[str, Path]


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
        fill: str = "#1F2933",
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


def _read_csv_samples(path: Path) -> Dict[str, List[float]]:
    samples: Dict[str, List[float]] = {bench: [] for bench, _ in BENCHES}
    with path.open(newline="", encoding="utf-8") as f:
        rows = csv.DictReader(line for line in f if not line.startswith("#"))
        for row in rows:
            if float(row["size_mb"]) != SIZE_MB:
                continue
            bench = row["bench_mode"]
            if bench in samples:
                samples[bench].append(float(row["per_iter_us"]))

    missing = [bench for bench, values in samples.items() if not values]
    if missing:
        raise ValueError(f"{path} missing {SIZE_MB:g} MB samples for {missing}")
    return samples


def load_measurements(repo_root: Path) -> SplitMeasurements:
    repo_root = repo_root.resolve()
    median_us: Dict[str, Dict[str, float]] = {}
    sources: Dict[str, Path] = {}

    for mode, relative_path in MODE_FILES.items():
        source = repo_root / relative_path
        if not source.exists():
            raise FileNotFoundError(source)
        samples = _read_csv_samples(source)
        median_us[mode] = {
            bench: statistics.median(values) for bench, values in samples.items()
        }
        sources[mode] = source

    delta_us = {
        bench: median_us["pKVM"][bench] - median_us["NVHE"][bench]
        for bench, _ in BENCHES
    }
    coverage_pct = (
        delta_us["munmap_after_write_touch"]
        / delta_us["mmap_write_touch_unmap"]
        * 100.0
    )
    return SplitMeasurements(
        median_us=median_us,
        delta_us=delta_us,
        coverage_pct=coverage_pct,
        sources=sources,
    )


def _draw_x_axis(
    svg: Svg,
    *,
    x0: float,
    y0: float,
    width: float,
    max_value: float,
    label: str,
    ticks: int = 5,
) -> None:
    axis_max = _axis_max(max_value, ticks)
    step = _nice_step(max_value, ticks)
    value = 0.0
    while value <= axis_max + step / 10:
        x = x0 + (value / axis_max) * width if axis_max else x0
        svg.add(
            f'<line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{y0 + 5:.1f}" '
            f'stroke="#5C6670" stroke-width="1"/>'
        )
        svg.text(x, y0 + 21, f"{value:.0f}", size=11, fill="#5C6670", anchor="middle")
        value += step
    svg.add(
        f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x0 + width:.1f}" y2="{y0:.1f}" '
        f'stroke="#5C6670" stroke-width="1.2"/>'
    )
    svg.text(x0 + width / 2, y0 + 43, label, size=12, fill="#4B5563", anchor="middle")


def _draw_absolute_panel(svg: Svg, data: SplitMeasurements, x0: float, y0: float) -> None:
    label_width = 190
    plot_x = x0 + label_width
    plot_y = y0 + 44
    plot_width = 355
    row_gap = 58
    bar_h = 13
    max_value = max(data.median_us[mode][bench] for mode in MODE_FILES for bench, _ in BENCHES)
    axis_max = _axis_max(max_value, 5)

    svg.text(x0, y0, "NVHE vs pKVM", size=17, weight=700)
    svg.text(x0, y0 + 22, "absolute latency per split test", size=12, fill="#64707D")

    for index, (bench, label) in enumerate(BENCHES):
        y = plot_y + index * row_gap
        svg.text(x0, y + 16, label, size=11, fill="#374151")
        for offset, mode in [(0, "NVHE"), (bar_h + 3, "pKVM")]:
            value = data.median_us[mode][bench]
            width = (value / axis_max) * plot_width if axis_max else 0
            color = MODE_COLORS[mode]
            svg.add(
                f'<rect x="{plot_x:.1f}" y="{y + offset:.1f}" width="{width:.1f}" '
                f'height="{bar_h:.1f}" rx="2" fill="{color}"/>'
            )
            svg.text(plot_x + width + 5, y + offset + 10, f"{value:.1f}", size=10, fill="#374151")

    legend_y = y0 + 12
    legend_x = plot_x + 130
    for mode in ["NVHE", "pKVM"]:
        svg.add(
            f'<rect x="{legend_x:.1f}" y="{legend_y - 10:.1f}" width="14" height="10" '
            f'rx="2" fill="{MODE_COLORS[mode]}"/>'
        )
        svg.text(legend_x + 20, legend_y, mode, size=11, fill="#374151")
        legend_x += 72

    axis_y = plot_y + len(BENCHES) * row_gap + 10
    _draw_x_axis(svg, x0=plot_x, y0=axis_y, width=plot_width, max_value=max_value, label="us / iteration")


def _draw_delta_panel(svg: Svg, data: SplitMeasurements, x0: float, y0: float) -> None:
    label_width = 210
    plot_x = x0 + label_width
    plot_y = y0 + 44
    plot_width = 330
    row_gap = 58
    bar_h = 17
    max_value = max(abs(data.delta_us[bench]) for bench, _ in BENCHES)
    axis_max = _axis_max(max_value, 5)

    svg.text(x0, y0, "pKVM extra time", size=17, weight=700)
    svg.text(x0, y0 + 22, "delta = pKVM - NVHE", size=12, fill="#64707D")

    for index, (bench, label) in enumerate(BENCHES):
        y = plot_y + index * row_gap
        value = data.delta_us[bench]
        svg.text(x0, y + 13, label, size=11, fill="#374151")

        if bench == "munmap_after_write_touch":
            color = DELTA_COLORS["highlight"]
        elif bench == "mmap_write_touch_unmap":
            color = DELTA_COLORS["anchor"]
        else:
            color = DELTA_COLORS["default"]

        width = (max(value, 0.0) / axis_max) * plot_width if axis_max else 0
        svg.add(
            f'<rect x="{plot_x:.1f}" y="{y:.1f}" width="{width:.1f}" '
            f'height="{bar_h:.1f}" rx="3" fill="{color}"/>'
        )
        label = f"{value:+.3f}"
        if width > plot_width * 0.62:
            svg.text(plot_x + width - 6, y + 13, label, size=11, fill="#FFFFFF", anchor="end", weight=700)
        else:
            svg.text(plot_x + max(width, 2) + 6, y + 13, label, size=11, fill="#374151")

        if bench == "munmap_after_write_touch":
            svg.text(
                plot_x + plot_width - 4,
                y + 29,
                f"{data.coverage_pct:.1f}% of full-path extra",
                size=11,
                fill="#9E2F24",
                anchor="end",
                weight=700,
            )

    axis_y = plot_y + len(BENCHES) * row_gap + 10
    _draw_x_axis(svg, x0=plot_x, y0=axis_y, width=plot_width, max_value=max_value, label="extra us / iteration")


def write_svg(data: SplitMeasurements, out_path: Path) -> None:
    width = 1180
    height = 520
    svg = Svg(
        width,
        height,
        "Stage 2 split result, 64 MB",
        "64 MB mmap split result on Kaitian, comparing NVHE and pKVM medians.",
    )
    svg.add(
        '<style>text{font-family:Inter,Arial,"Noto Sans",sans-serif;}</style>'
    )
    svg.text(62, 38, "Stage 2 split result, 64 MB", size=21, weight=700)
    svg.text(
        62,
        61,
        "Kaitian, median of 10 runs; split tests are isolation probes, not additive components",
        size=12,
        fill="#64707D",
    )

    _draw_absolute_panel(svg, data, x0=62, y0=100)
    _draw_delta_panel(svg, data, x0=625, y0=100)

    svg.text(
        width / 2,
        height - 22,
        "Source: results/mmap-split-kaitian/{nvhe,pkvm}.csv",
        size=11,
        fill="#7A8591",
        anchor="middle",
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg.render(), encoding="utf-8")


def _print_summary(data: SplitMeasurements) -> None:
    print("bench,NVHE,pKVM,delta_us,delta_pct")
    for bench, _ in BENCHES:
        nvhe = data.median_us["NVHE"][bench]
        pkvm = data.median_us["pKVM"][bench]
        delta = data.delta_us[bench]
        pct = delta / nvhe * 100.0 if nvhe else 0.0
        print(f"{bench},{nvhe:.6f},{pkvm:.6f},{delta:.6f},{pct:.2f}")
    print(f"coverage_pct,{data.coverage_pct:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/mmap/figures/mmap-split-kaitian-64mb.svg"),
    )
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()

    data = load_measurements(args.repo_root)
    output = args.output
    if not output.is_absolute():
        output = args.repo_root / output
    write_svg(data, output)
    if args.print_summary:
        _print_summary(data)
    print(output)


if __name__ == "__main__":
    main()
