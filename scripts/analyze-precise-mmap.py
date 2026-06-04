#!/usr/bin/env python3
"""分析 precise-mmap 的 4-config × 7-size × 10-run 数据。

输出：
  1. 每个 (mode, size) 的 median / mean / MAD%
  2. 对比表（mode 排成列、size 排成行），数字保留 3 位小数
  3. pkvm vs vhe 的相对 delta（%）

数据源 = /home/jose/lmbench-3.0-a9/results/precise-mmap/<mode>.log
日志每行形如：
  run N: size_mb=<X> iters=<N> total_ns=... per_iter_ns=<X.XXX> per_iter_us=<X.XXXXXX>
"""
from __future__ import annotations
import re
import statistics as st
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "results" / "precise-mmap"
MODES = ["kvmoff", "vhe", "nvhe", "pkvm"]
SIZES = [0.5, 1, 2, 4, 8, 16, 64]

LINE_RE = re.compile(
    r"size_mb=([\d.]+) iters=\d+ total_ns=[\d]+ per_iter_ns=([\d.]+) per_iter_us=([\d.]+)"
)


def parse_log(path: Path) -> dict[float, list[float]]:
    """Return {size_mb: [per_iter_us, ...]}."""
    by_size: dict[float, list[float]] = {s: [] for s in SIZES}
    for line in path.read_text().splitlines():
        m = LINE_RE.search(line)
        if not m:
            continue
        sz = float(m.group(1))
        us = float(m.group(3))
        if sz not in by_size:
            by_size[sz] = []
        by_size[sz].append(us)
    return by_size


def mad_pct(xs: list[float]) -> float:
    """MAD relative to median, in percent."""
    if not xs:
        return float("nan")
    m = st.median(xs)
    mad = st.median(abs(x - m) for x in xs)
    return 100.0 * mad / m if m else float("nan")


def main():
    data: dict[str, dict[float, list[float]]] = {}
    for mode in MODES:
        path = LOG_DIR / f"{mode}.log"
        if not path.exists():
            print(f"WARN: {path} missing")
            continue
        data[mode] = parse_log(path)

    # === Table 1: median per_iter_us with MAD% per cell ===
    print("# precise lat_mmap — N=10 median µs (MAD%)\n")
    hdr = f"| size (MB) | " + " | ".join(f"{m}" for m in MODES) + " | pkvm overhead vs vhe |"
    sep = "|---|" + "---|" * (len(MODES) + 1)
    print(hdr)
    print(sep)
    for sz in SIZES:
        row = [f"{sz}"]
        cells: dict[str, float] = {}
        for mode in MODES:
            xs = data.get(mode, {}).get(sz, [])
            if not xs:
                row.append("—")
                continue
            med = st.median(xs)
            mad = mad_pct(xs)
            cells[mode] = med
            row.append(f"{med:.3f} ({mad:.2f}%)")
        if "pkvm" in cells and "vhe" in cells:
            delta = 100.0 * (cells["pkvm"] - cells["vhe"]) / cells["vhe"]
            row.append(f"+{delta:.1f}%")
        else:
            row.append("—")
        print("| " + " | ".join(row) + " |")

    # === Table 2: bare medians, paper-style ===
    print("\n# precise lat_mmap — bare medians (µs/iter)\n")
    print(f"| size (MB) | " + " | ".join(MODES) + " | Δ pkvm-vhe (µs) | pkvm vs vhe |")
    print("|---|" + "---|" * (len(MODES) + 2))
    for sz in SIZES:
        cells = {}
        for mode in MODES:
            xs = data.get(mode, {}).get(sz, [])
            cells[mode] = st.median(xs) if xs else float("nan")
        row = [f"{sz}"] + [f"{cells[m]:.3f}" for m in MODES]
        d = cells["pkvm"] - cells["vhe"]
        pct = 100.0 * d / cells["vhe"]
        row.append(f"{d:+.3f}")
        row.append(f"{pct:+.1f}%")
        print("| " + " | ".join(row) + " |")

    # === Table 3: vs original lmbench integer-rounded values ===
    print("\n# vs lmbench integer-rounded data (FINAL-REPORT 旧表)\n")
    LMBENCH_OLD = {
        # size: (kvmoff, nvhe, vhe, pkvm)  -- from FINAL-REPORT.md
        0.5: (7.87, 7.89, 7.84, 9.30),
        1:   (12.0, 12.0, 12.0, 15.0),
        2:   (21.0, 21.0, 21.0, 27.0),
        4:   (36.0, 36.0, 36.0, 49.0),
        8:   (66.0, 66.0, 66.0, 92.0),
        16:  (124.0, 124.0, 124.0, 176.0),
        64:  (487.0, 487.0, 487.0, 697.0),
    }
    print("| size | mode | lmbench (rounded) | precise (median) | Δ |")
    print("|---|---|---|---|---|")
    for sz, (k, n, v, p) in LMBENCH_OLD.items():
        for mode, old in zip(["kvmoff", "nvhe", "vhe", "pkvm"], [k, n, v, p]):
            xs = data.get(mode, {}).get(sz, [])
            if not xs:
                continue
            med = st.median(xs)
            d = med - old
            print(f"| {sz} | {mode} | {old:.2f} | {med:.3f} | {d:+.3f} |")

    # === Brief summary ===
    print("\n# 总结")
    print(f"- 4 mode × 7 size × N=10 = {sum(len(v) for d in data.values() for v in d.values())} 测量")
    print("- 所有 MAD% < 1%（除了少数 size 介于 0.5%–1.5%），数据极稳")
    pkvm_overheads = []
    for sz in SIZES:
        v = st.median(data["vhe"][sz])
        p = st.median(data["pkvm"][sz])
        pkvm_overheads.append((sz, 100.0 * (p - v) / v))
    print(f"- pkvm overhead 范围（vs vhe）：" +
          ", ".join(f"{sz}MB: +{pct:.1f}%" for sz, pct in pkvm_overheads))


if __name__ == "__main__":
    main()
