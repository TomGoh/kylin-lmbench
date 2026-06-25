#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Render munmap_after_write_touch scaling across mapping sizes."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from html import escape
from pathlib import Path
from typing import Dict, List, NamedTuple, Tuple, Union


SOURCE_DIR = Path("results/mmap-split-kaitian")
BENCH = "munmap_after_write_touch"

MODE_FILES = {
    "NVHE": SOURCE_DIR / "nvhe.csv",
    "pKVM": SOURCE_DIR / "pkvm.csv",
}

MODE_COLORS = {
    "NVHE": "#4D7C59",
    "pKVM": "#C23B2A",
}


class ScalingMeasurements(NamedTuple):
    sizes: List[float]
    median_us: Dict[str, Dict[float, float]]
    delta_us: Dict[float, float]
    fit_slope_us_per_mb: float
    fit_intercept_us: float
    fit_r2: float
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


def _format_size(size: float) -> str:
    if size.is_integer():
        return str(int(size))
    return str(size)


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


def _linear_fit(xs: List[float], ys: List[float]) -> Tuple[float, float, float]:
    n = len(xs)
    sx = sum(xs)
    sy = sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    slope = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    intercept = (sy - slope * sx) / n
    mean_y = sy / n
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 - ss_res / ss_tot if ss_tot else 1.0
    return slope, intercept, r2


def _read_csv_samples(path: Path) -> Dict[float, List[float]]:
    samples: Dict[float, List[float]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        rows = csv.DictReader(line for line in f if not line.startswith("#"))
        for row in rows:
            if row["bench_mode"] != BENCH:
                continue
            size = float(row["size_mb"])
            samples.setdefault(size, []).append(float(row["per_iter_us"]))
    if not samples:
        raise ValueError(f"{path} has no {BENCH} samples")
    return samples


def load_measurements(repo_root: Path) -> ScalingMeasurements:
    repo_root = repo_root.resolve()
    median_us: Dict[str, Dict[float, float]] = {}
    sources: Dict[str, Path] = {}
    expected_sizes = None

    for mode, relative_path in MODE_FILES.items():
        source = repo_root / relative_path
        if not source.exists():
            raise FileNotFoundError(source)
        samples = _read_csv_samples(source)
        sizes = sorted(samples)
        if expected_sizes is None:
            expected_sizes = sizes
        elif sizes != expected_sizes:
            raise ValueError(f"{source} has sizes {sizes}, expected {expected_sizes}")
        median_us[mode] = {
            size: statistics.median(values) for size, values in samples.items()
        }
        sources[mode] = source

    if expected_sizes is None:
        raise ValueError("no mode files configured")

    delta_us = {
        size: median_us["pKVM"][size] - median_us["NVHE"][size]
        for size in expected_sizes
    }
    deltas = [delta_us[size] for size in expected_sizes]
    slope, intercept, r2 = _linear_fit(expected_sizes, deltas)

    return ScalingMeasurements(
        sizes=expected_sizes,
        median_us=median_us,
        delta_us=delta_us,
        fit_slope_us_per_mb=slope,
        fit_intercept_us=intercept,
        fit_r2=r2,
        sources=sources,
    )


def _x_for(size: float, max_size: float, x0: float, width: float) -> float:
    return x0 + (size / max_size) * width if max_size else x0


def _y_for(value: float, y_max: float, y0: float, height: float) -> float:
    return y0 + height - (value / y_max) * height if y_max else y0 + height


def _polyline(points: List[Tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def _draw_axes(
    svg: Svg,
    *,
    x0: float,
    y0: float,
    width: float,
    height: float,
    x_max: float,
    y_max: float,
    y_label: str,
) -> None:
    bottom = y0 + height
    svg.add(
        f'<line x1="{x0:.1f}" y1="{bottom:.1f}" x2="{x0 + width:.1f}" y2="{bottom:.1f}" '
        f'stroke="#5C6670" stroke-width="1.2"/>'
    )
    svg.add(
        f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x0:.1f}" y2="{bottom:.1f}" '
        f'stroke="#5C6670" stroke-width="1.2"/>'
    )

    for fraction in range(5):
        x_value = x_max * fraction / 4
        x = _x_for(x_value, x_max, x0, width)
        svg.add(
            f'<line x1="{x:.1f}" y1="{y0:.1f}" x2="{x:.1f}" y2="{bottom:.1f}" '
            f'stroke="#F0F3F7" stroke-width="1"/>'
        )
        svg.add(
            f'<line x1="{x:.1f}" y1="{bottom:.1f}" x2="{x:.1f}" y2="{bottom + 5:.1f}" '
            f'stroke="#5C6670" stroke-width="1"/>'
        )
        svg.text(x, bottom + 22, _format_size(x_value), size=11, fill="#5C6670", anchor="middle")

    y_step = _nice_step(y_max, 5)
    value = 0.0
    while value <= y_max + y_step / 10:
        y = _y_for(value, y_max, y0, height)
        svg.add(
            f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x0 + width:.1f}" y2="{y:.1f}" '
            f'stroke="#E6EAF0" stroke-width="1"/>'
        )
        svg.text(x0 - 10, y + 4, f"{value:.0f}", size=11, fill="#5C6670", anchor="end")
        value += y_step

    svg.text(x0 + width / 2, bottom + 46, "mapping size (MB, linear scale)", size=12, fill="#4B5563", anchor="middle")
    svg.add(
        f'<text transform="translate({x0 - 48:.1f} {y0 + height / 2:.1f}) rotate(-90)" '
        f'font-size="12" fill="#4B5563" text-anchor="middle">{escape(y_label)}</text>'
    )


def _draw_absolute_panel(
    svg: Svg,
    data: ScalingMeasurements,
    x0: float,
    y0: float,
    width: float,
    height: float,
    *,
    sizes: List[float],
    panel_title: str,
    subtitle: str,
    show_legend: bool = False,
) -> None:
    x_max = max(sizes)
    y_max = _axis_max(max(data.median_us[mode][size] for mode in MODE_FILES for size in sizes), 5)
    svg.text(x0, y0 - 34, panel_title, size=17, weight=700)
    svg.text(x0, y0 - 13, subtitle, size=12, fill="#64707D")
    _draw_axes(svg, x0=x0, y0=y0, width=width, height=height, x_max=x_max, y_max=y_max, y_label="us / iteration")

    for mode in ["NVHE", "pKVM"]:
        color = MODE_COLORS[mode]
        points = [
            (_x_for(size, x_max, x0, width), _y_for(data.median_us[mode][size], y_max, y0, height))
            for size in sizes
        ]
        svg.add(
            f'<polyline points="{_polyline(points)}" fill="none" stroke="{color}" '
            f'stroke-width="{3 if mode == "pKVM" else 2.3}" stroke-linejoin="round" stroke-linecap="round"/>'
        )
        for x, y in points:
            svg.add(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{4.0 if mode == "pKVM" else 3.5}" '
                f'fill="#FFFFFF" stroke="{color}" stroke-width="1.7"/>'
            )

    if show_legend:
        legend_x = x0 + 18
        legend_y = y0 + 22
        for mode in ["NVHE", "pKVM"]:
            svg.add(
                f'<line x1="{legend_x:.1f}" y1="{legend_y:.1f}" x2="{legend_x + 24:.1f}" y2="{legend_y:.1f}" '
                f'stroke="{MODE_COLORS[mode]}" stroke-width="{3 if mode == "pKVM" else 2.3}"/>'
            )
            svg.text(legend_x + 31, legend_y + 4, mode, size=12, fill="#374151")
            legend_x += 92


def _draw_delta_panel(
    svg: Svg,
    data: ScalingMeasurements,
    x0: float,
    y0: float,
    width: float,
    height: float,
    *,
    sizes: List[float],
    panel_title: str,
    subtitle: str,
    show_fit_label: bool = False,
) -> None:
    x_max = max(sizes)
    y_max = _axis_max(max(data.delta_us[size] for size in sizes), 5)
    svg.text(x0, y0 - 34, panel_title, size=17, weight=700)
    svg.text(x0, y0 - 13, subtitle, size=12, fill="#64707D")
    _draw_axes(svg, x0=x0, y0=y0, width=width, height=height, x_max=x_max, y_max=y_max, y_label="extra us / iteration")

    delta_points = [
        (_x_for(size, x_max, x0, width), _y_for(data.delta_us[size], y_max, y0, height))
        for size in sizes
    ]
    svg.add(
        f'<polyline points="{_polyline(delta_points)}" fill="none" stroke="#C23B2A" '
        f'stroke-width="2.8" stroke-linejoin="round" stroke-linecap="round"/>'
    )
    for x, y in delta_points:
        svg.add(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#FFFFFF" stroke="#C23B2A" stroke-width="1.8"/>'
        )

    fit_points = []
    for size in [0.0, x_max]:
        y_value = data.fit_intercept_us + data.fit_slope_us_per_mb * size
        fit_points.append((_x_for(size, x_max, x0, width), _y_for(y_value, y_max, y0, height)))
    svg.add(
        f'<polyline points="{_polyline(fit_points)}" fill="none" stroke="#334E68" '
        f'stroke-width="2" stroke-dasharray="6 5" stroke-linecap="round"/>'
    )

    if show_fit_label:
        annotation = f"linear fit: {data.fit_slope_us_per_mb:.2f} us/MB, R^2={data.fit_r2:.3f}"
        svg.add(
            f'<rect x="{x0 + 18:.1f}" y="{y0 + 18:.1f}" width="286" height="31" rx="4" '
            f'fill="#FFFFFF" stroke="#D9DEE7" stroke-width="1"/>'
        )
        svg.text(x0 + 30, y0 + 39, annotation, size=12, fill="#334E68", weight=700)


def _add_source_note(svg: Svg, y: float) -> None:
    svg.text(
        svg.width / 2,
        y,
        "Source: results/mmap-split-kaitian/{nvhe,pkvm}.csv",
        size=11,
        fill="#7A8591",
        anchor="middle",
    )


def write_absolute_svg(data: ScalingMeasurements, out_path: Path) -> None:
    width = 1180
    height = 520
    svg = Svg(
        width,
        height,
        "munmap_after_write_touch absolute cost",
        "Kaitian mmap split absolute munmap_after_write_touch cost across mapping sizes.",
    )
    svg.add('<style>text{font-family:Inter,Arial,"Noto Sans",sans-serif;}</style>')
    svg.text(62, 38, "munmap_after_write_touch absolute cost", size=21, weight=700)
    svg.text(
        62,
        61,
        "Kaitian, median of 10 runs; values recomputed from mmap-split CSV files",
        size=12,
        fill="#64707D",
    )

    small_sizes = [size for size in data.sizes if size <= 8]
    _draw_absolute_panel(
        svg,
        data,
        x0=84,
        y0=112,
        width=430,
        height=280,
        sizes=data.sizes,
        panel_title="full range",
        subtitle="0-64 MB",
        show_legend=True,
    )
    _draw_absolute_panel(
        svg,
        data,
        x0=680,
        y0=112,
        width=410,
        height=280,
        sizes=small_sizes,
        panel_title="detail: 0-8 MB",
        subtitle="same data, small-size range only",
    )

    _add_source_note(svg, height - 22)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg.render(), encoding="utf-8")


def write_delta_svg(data: ScalingMeasurements, out_path: Path) -> None:
    width = 1180
    height = 520
    svg = Svg(
        width,
        height,
        "munmap_after_write_touch delta scaling",
        "Kaitian mmap split pKVM minus NVHE delta for munmap_after_write_touch across mapping sizes.",
    )
    svg.add('<style>text{font-family:Inter,Arial,"Noto Sans",sans-serif;}</style>')
    svg.text(62, 38, "munmap_after_write_touch delta scaling", size=21, weight=700)
    svg.text(
        62,
        61,
        "Kaitian, median of 10 runs; delta = pKVM - NVHE",
        size=12,
        fill="#64707D",
    )

    small_sizes = [size for size in data.sizes if size <= 8]
    _draw_delta_panel(
        svg,
        data,
        x0=84,
        y0=112,
        width=430,
        height=280,
        sizes=data.sizes,
        panel_title="full range",
        subtitle="0-64 MB",
        show_fit_label=True,
    )
    _draw_delta_panel(
        svg,
        data,
        x0=680,
        y0=112,
        width=410,
        height=280,
        sizes=small_sizes,
        panel_title="detail: 0-8 MB",
        subtitle="same fit, small-size range only",
    )

    _add_source_note(svg, height - 22)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg.render(), encoding="utf-8")


def _print_summary(data: ScalingMeasurements) -> None:
    print("size_mb,NVHE,pKVM,delta_us")
    for size in data.sizes:
        print(
            f"{_format_size(size)},"
            f"{data.median_us['NVHE'][size]:.6f},"
            f"{data.median_us['pKVM'][size]:.6f},"
            f"{data.delta_us[size]:.6f}"
        )
    print(
        f"fit_slope_us_per_mb,{data.fit_slope_us_per_mb:.6f},"
        f"fit_intercept_us,{data.fit_intercept_us:.6f},fit_r2,{data.fit_r2:.6f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--absolute-output",
        type=Path,
        default=Path("docs/mmap/figures/mmap-split-munmap-scaling-absolute.svg"),
    )
    parser.add_argument(
        "--delta-output",
        type=Path,
        default=Path("docs/mmap/figures/mmap-split-munmap-scaling-delta.svg"),
    )
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()

    data = load_measurements(args.repo_root)
    absolute_output = args.absolute_output
    delta_output = args.delta_output
    if not absolute_output.is_absolute():
        absolute_output = args.repo_root / absolute_output
    if not delta_output.is_absolute():
        delta_output = args.repo_root / delta_output
    write_absolute_svg(data, absolute_output)
    write_delta_svg(data, delta_output)
    if args.print_summary:
        _print_summary(data)
    print(absolute_output)
    print(delta_output)


if __name__ == "__main__":
    main()
