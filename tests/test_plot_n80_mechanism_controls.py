import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docs" / "mmap" / "scripts" / "plot-n80-mechanism-controls.py"


def load_plot_module():
    spec = importlib.util.spec_from_file_location("plot_n80_mechanism_controls", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PlotN80MechanismControlsTest(unittest.TestCase):
    def test_recomputes_sparse_dense_control_points(self):
        mod = load_plot_module()
        rows = mod._load_sparse_dense(ROOT)

        self.assertEqual(rows[0].scenario, "sparse 6.4MB/16K")
        self.assertEqual(rows[0].ptes, 410)
        self.assertAlmostEqual(rows[0].nvhe_us, 113.17966, places=5)
        self.assertAlmostEqual(rows[0].protected_us, 548.10764, places=5)
        self.assertAlmostEqual(rows[0].delta_us, 434.92798, places=5)

        self.assertEqual(rows[1].scenario, "dense 64MB/4K")
        self.assertEqual(rows[1].ptes, 16384)
        self.assertAlmostEqual(rows[1].nvhe_us, 2828.0, places=3)
        self.assertAlmostEqual(rows[1].protected_us, 2785.0, places=3)
        self.assertAlmostEqual(rows[1].delta_us, -43.0, places=3)

    def test_recomputes_core_scaling_means(self):
        mod = load_plot_module()
        data = mod._load_core_scaling(ROOT)

        self.assertAlmostEqual(data["protected"][("0",)], 560.8, places=3)
        self.assertAlmostEqual(data["protected"][("0", "1")], 545.1, places=3)
        self.assertAlmostEqual(data["protected"][("0", "4")], 547.6, places=3)
        self.assertAlmostEqual(
            data["protected"][("0", "1", "2", "3", "4", "5", "6", "7")],
            548.0,
            places=3,
        )
        self.assertAlmostEqual(data["NVHE"][("0",)], 112.8, places=3)
        self.assertAlmostEqual(data["NVHE"][("0", "1")], 107.7, places=3)
        self.assertAlmostEqual(data["NVHE"][("0", "4")], 111.6, places=3)
        self.assertAlmostEqual(
            data["NVHE"][("0", "1", "2", "3", "4", "5", "6", "7")],
            114.4,
            places=3,
        )

    def test_recomputes_tlbi_ab_nslots_2048(self):
        mod = load_plot_module()
        data = mod._load_tlbi_ab(ROOT)

        self.assertAlmostEqual(data["NVHE"].nsh_ns, 10.019, places=3)
        self.assertAlmostEqual(data["NVHE"].is_ns, 23.232, places=3)
        self.assertAlmostEqual(data["protected"].nsh_ns, 288.837, places=3)
        self.assertAlmostEqual(data["protected"].is_ns, 288.896, places=3)

    def test_renders_three_svg_figures(self):
        mod = load_plot_module()

        sparse_dense_svg = mod.render_sparse_dense(mod._load_sparse_dense(ROOT))
        core_scaling_svg = mod.render_core_scaling(mod._load_core_scaling(ROOT))
        tlbi_svg = mod.render_tlbi_ab(mod._load_tlbi_ab(ROOT))

        self.assertIn("Sparse-vs-dense munmap control", sparse_dense_svg)
        self.assertIn("+435 us", sparse_dense_svg)
        self.assertIn("-43 us (~0)", sparse_dense_svg)
        self.assertIn("Core-scaling mean check", core_scaling_svg)
        self.assertIn("560.8", core_scaling_svg)
        self.assertIn("{0..7}", core_scaling_svg)
        self.assertIn("Direct TLBI timing: IS vs NSH", tlbi_svg)
        self.assertIn("288.837", tlbi_svg)
        self.assertIn("IS-NSH = +0.059 ns", tlbi_svg)


if __name__ == "__main__":
    unittest.main()
