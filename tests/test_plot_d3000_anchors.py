import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs" / "mmap" / "scripts" / "plot-d3000-anchors.py"


def load_plot_module():
    spec = importlib.util.spec_from_file_location("plot_d3000_anchors", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_anchor_group(root, mmap_half, mmap_64, dense_19, dense_20, sparse_64, lat_mem):
    root.mkdir(parents=True)
    (root / "VALID").touch()
    mmap_lines = []
    for value in mmap_half:
        mmap_lines.append(f"size_mb=0.5 iters=10 total_ns=1 per_iter_ns=1 per_iter_us={value}")
    for value in mmap_64:
        mmap_lines.append(f"size_mb=64 iters=10 total_ns=1 per_iter_ns=1 per_iter_us={value}")
    (root / "lat-mmap-precise.txt").write_text("\n".join(mmap_lines) + "\n")
    op_lines = []
    for label, values in (("dense-1.9", dense_19), ("dense-2.0", dense_20), ("sparse-6.4", sparse_64)):
        for index, value in enumerate(values, 1):
            op_lines.append(f"rep={index} label={label} munmap file mb=64 : mean={value} us min=1 us")
    (root / "op-sweep.txt").write_text("\n".join(op_lines) + "\n")
    for index, value in enumerate(lat_mem, 1):
        (root / f"lat-mem-r{index}.txt").write_text(f"0.00098 1.0\n64.00000 {value}\n")


class PlotD3000AnchorsTest(unittest.TestCase):
    def test_loads_raw_anchor_medians_and_paired_penalties(self):
        mod = load_plot_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            campaign = Path(tmpdir) / "campaign-never"
            for mode, scale in (("nvhe", 1.0), ("protected", 1.5)):
                for phase, phase_scale in (("start", 1.0), ("end", 0.96)):
                    root = campaign / "pair-1" / mode / f"anchors-{phase}" / "rep-00"
                    write_anchor_group(
                        root,
                        [10 * scale * phase_scale] * 5,
                        [300 * scale * phase_scale] * 5,
                        [70 * scale * phase_scale] * 5,
                        [65 * scale * phase_scale] * 5,
                        [75 * scale * phase_scale] * 5,
                        [7.0 if mode == "nvhe" else 7.01] * 5,
                    )
            data = mod.load_anchors(campaign)

        self.assertEqual(data.pairs, [1])
        self.assertEqual(data.sizes, [0.5, 64.0])
        self.assertAlmostEqual(data.values[(1, "nvhe", "start", "lat_mmap:64")], 300.0)
        self.assertAlmostEqual(data.values[(1, "protected", "start", "lat_mmap:64")], 450.0)
        self.assertAlmostEqual(mod.paired_penalties(data, "start", "lat_mmap:64")[1], 50.0)
        self.assertAlmostEqual(mod.paired_penalties(data, "start", "lat_mem:64")[1], 0.01 / 7 * 100, places=6)

    def test_renders_anchor_figures(self):
        mod = load_plot_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            campaign = Path(tmpdir) / "campaign-never"
            for mode, scale in (("nvhe", 1.0), ("protected", 1.5)):
                for phase in ("start", "end"):
                    root = campaign / "pair-1" / mode / f"anchors-{phase}" / "rep-00"
                    write_anchor_group(
                        root,
                        [10 * scale] * 5,
                        [300 * scale] * 5,
                        [70 * scale] * 5,
                        [65 * scale] * 5,
                        [75 * scale] * 5,
                        [7.0 if mode == "nvhe" else 7.01] * 5,
                    )
            data = mod.load_anchors(campaign)
            mmap_out = Path(tmpdir) / "mmap.svg"
            controls_out = Path(tmpdir) / "controls.svg"
            mod.write_lat_mmap_figure(data, mmap_out, source_label="fixture/campaign-never")
            mod.write_control_figure(data, controls_out, source_label="fixture/campaign-never")
            mmap_svg = mmap_out.read_text()
            controls_svg = controls_out.read_text()

        self.assertIn("D3000 mechanism anchor: lat_mmap across mapping sizes", mmap_svg)
        self.assertIn("64 MiB: +50.0%", mmap_svg)
        self.assertIn("mapping size (MiB, log2 scale)", mmap_svg)
        self.assertIn("Mapping-management penalty", controls_svg)
        self.assertIn("Steady-memory negative control", controls_svg)
        self.assertIn("sparse 6.4 MiB munmap", controls_svg)


if __name__ == "__main__":
    unittest.main()
