import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs" / "mmap" / "scripts" / "plot-n90-v10-lat-mmap.py"


def load_plot_module():
    spec = importlib.util.spec_from_file_location("plot_n90_v10_lat_mmap", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PlotN90V10LatMmapTest(unittest.TestCase):
    def test_recomputes_documented_medians_from_logs(self):
        mod = load_plot_module()
        data = mod.load_measurements(ROOT)

        self.assertAlmostEqual(data.median_us["KVM-off"][64.0], 443.084233, places=6)
        self.assertAlmostEqual(data.median_us["NVHE"][64.0], 441.186916, places=6)
        self.assertAlmostEqual(data.median_us["pKVM"][64.0], 816.317767, places=6)
        self.assertAlmostEqual(data.pkvm_vs_nvhe_pct[64.0], 85.03, places=2)
        self.assertIn("results/n90-v10-pkvm-mmap/precise-mmap", data.sources["pKVM"].as_posix())

    def test_writes_separate_svgs(self):
        mod = load_plot_module()
        data = mod.load_measurements(ROOT)

        with tempfile.TemporaryDirectory() as tmpdir:
            absolute = Path(tmpdir) / "lat-mmap-absolute.svg"
            overhead = Path(tmpdir) / "lat-mmap-overhead.svg"
            mod.write_absolute_svg(data, absolute)
            mod.write_overhead_svg(data, overhead)
            absolute_svg = absolute.read_text()
            overhead_svg = overhead.read_text()

        self.assertIn("N90 lat_mmap absolute latency", absolute_svg)
        self.assertIn("full range", absolute_svg)
        self.assertIn("detail: 0-8 MB", absolute_svg)
        self.assertIn("mapping size (MB, linear scale)", absolute_svg)
        self.assertNotIn("baseline detail: delta vs NVHE", absolute_svg)
        self.assertIn("KVM-off", absolute_svg)
        self.assertIn("VHE", absolute_svg)
        self.assertIn("NVHE", absolute_svg)
        self.assertNotIn("pKVM overhead vs NVHE", absolute_svg)
        self.assertIn("pKVM overhead vs NVHE", overhead_svg)
        self.assertIn("mapping size (MB)", overhead_svg)
        self.assertIn("pKVM", overhead_svg)
        self.assertIn("85.0%", overhead_svg)

    def test_absolute_x_positions_use_linear_size_scale(self):
        mod = load_plot_module()
        positions = mod._linear_x_positions([0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 64.0], 100, 700)

        eight_mb_span = positions[16.0] - positions[8.0]
        forty_eight_mb_span = positions[64.0] - positions[16.0]

        self.assertAlmostEqual(forty_eight_mb_span, eight_mb_span * 6, places=6)

    def test_overhead_x_positions_are_categorical(self):
        mod = load_plot_module()
        positions = mod._category_x_positions([0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 64.0], 100, 700)

        self.assertAlmostEqual(
            positions[64.0] - positions[16.0],
            positions[16.0] - positions[8.0],
            places=6,
        )


if __name__ == "__main__":
    unittest.main()
