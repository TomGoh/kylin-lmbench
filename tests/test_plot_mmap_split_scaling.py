import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs" / "mmap" / "scripts" / "plot-mmap-split-scaling.py"


def load_plot_module():
    spec = importlib.util.spec_from_file_location("plot_mmap_split_scaling", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PlotMmapSplitScalingTest(unittest.TestCase):
    def test_recomputes_munmap_after_write_touch_scaling(self):
        mod = load_plot_module()
        data = mod.load_measurements(ROOT)

        self.assertEqual(data.sizes, [0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 64.0])
        self.assertAlmostEqual(data.median_us["NVHE"][8.0], 14.7587275, places=6)
        self.assertAlmostEqual(data.median_us["pKVM"][64.0], 295.21862, places=6)
        self.assertAlmostEqual(data.delta_us[64.0], 205.00315, places=5)
        self.assertAlmostEqual(data.fit_slope_us_per_mb, 3.2034976, places=6)
        self.assertGreater(data.fit_r2, 0.9999)

    def test_writes_split_scaling_svgs(self):
        mod = load_plot_module()
        data = mod.load_measurements(ROOT)

        with tempfile.TemporaryDirectory() as tmpdir:
            absolute = Path(tmpdir) / "mmap-split-scaling-absolute.svg"
            delta = Path(tmpdir) / "mmap-split-scaling-delta.svg"
            mod.write_absolute_svg(data, absolute)
            mod.write_delta_svg(data, delta)
            absolute_svg = absolute.read_text()
            delta_svg = delta.read_text()

        self.assertIn("munmap_after_write_touch absolute cost", absolute_svg)
        self.assertIn("full range", absolute_svg)
        self.assertIn("detail: 0-8 MB", absolute_svg)
        self.assertIn("NVHE", absolute_svg)
        self.assertIn("pKVM", absolute_svg)
        self.assertIn("mapping size (MB, linear scale)", absolute_svg)

        self.assertIn("munmap_after_write_touch delta scaling", delta_svg)
        self.assertIn("full range", delta_svg)
        self.assertIn("detail: 0-8 MB", delta_svg)
        self.assertIn("linear fit", delta_svg)
        self.assertIn("3.20 us/MB", delta_svg)
        self.assertIn("R^2=1.000", delta_svg)
        self.assertIn("Source: results/mmap-split-kaitian/{nvhe,pkvm}.csv", delta_svg)


if __name__ == "__main__":
    unittest.main()
