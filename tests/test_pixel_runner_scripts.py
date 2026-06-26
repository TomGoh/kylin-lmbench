import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "experiments" / "munmap-tlbi" / "pixel-run-madv-entry-slope.sh"


class PixelRunnerScriptsTest(unittest.TestCase):
    def test_runner_is_syntax_valid_and_contains_fairness_hooks(self):
        subprocess.run(["bash", "-n", str(RUNNER)], cwd=ROOT, check=True)
        text = RUNNER.read_text()
        for needle in [
            "collect_metadata",
            "read_freq",
            "read_thermal",
            "combo_order",
            "--cpu",
            "mode_label",
            "freq_before",
            "thermal_before",
        ]:
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
