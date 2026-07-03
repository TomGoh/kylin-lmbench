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
            "wait_for_thermal_gate",
            "combo_order",
            "--cpu",
            "mode_label",
            "freq_before",
            "thermal_before",
            "thermal_gate_ready",
            "WAIT_THERMAL_MAX_MC",
        ]:
            self.assertIn(needle, text)

    def test_remote_probe_does_not_consume_task_list_stdin(self):
        text = RUNNER.read_text()
        self.assertIn("$ADB shell \"$@\" < /dev/null", text)


if __name__ == "__main__":
    unittest.main()
