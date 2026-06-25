import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs" / "mmap" / "scripts" / "plot-mmap-split-stage2.py"


def load_plot_module():
    spec = importlib.util.spec_from_file_location("plot_mmap_split_stage2", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PlotMmapSplitStage2Test(unittest.TestCase):
    def test_recomputes_64mb_medians_from_csv(self):
        mod = load_plot_module()
        data = mod.load_measurements(ROOT)

        self.assertAlmostEqual(data.median_us["NVHE"]["mmap_unmap"], 3.20962, places=6)
        self.assertAlmostEqual(data.median_us["pKVM"]["write_touch_cold"], 346.1593565, places=6)
        self.assertAlmostEqual(data.median_us["NVHE"]["munmap_after_write_touch"], 90.21547, places=6)
        self.assertAlmostEqual(data.median_us["pKVM"]["munmap_after_write_touch"], 295.21862, places=6)
        self.assertAlmostEqual(data.delta_us["munmap_after_write_touch"], 205.00315, places=5)
        self.assertAlmostEqual(data.coverage_pct, 95.65, places=2)

    def test_writes_dual_panel_svg(self):
        mod = load_plot_module()
        data = mod.load_measurements(ROOT)

        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "mmap-split-stage2.svg"
            mod.write_svg(data, out)
            svg = out.read_text()

        self.assertIn("Stage 2 split result, 64 MB", svg)
        self.assertIn("NVHE vs pKVM", svg)
        self.assertIn("pKVM extra time", svg)
        self.assertIn("munmap_after_write_touch", svg)
        self.assertIn("95.7% of full-path extra", svg)
        self.assertIn("not additive components", svg)


if __name__ == "__main__":
    unittest.main()
