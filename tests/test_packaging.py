"""Packaging consistency and the single CLI entry point."""
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

from medibuddy_bench import VERSION


class Packaging(unittest.TestCase):
    def test_pyproject_version_matches(self):
        text = open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8").read()
        self.assertEqual(re.search(r'^version = "([^"]+)"', text, re.M).group(1), VERSION)

    def test_cli_runs_a_baseline(self):
        r = subprocess.run([sys.executable, "-m", "medibuddy_bench", "run", "--agent", "oracle", "--data", "data/lite",
                            "--tasks", "T4", "--no-transcripts"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Overall (gated)", r.stdout)

    def test_cli_help_and_unknown(self):
        ok = subprocess.run([sys.executable, "-m", "medibuddy_bench", "--help"], cwd=ROOT, capture_output=True, text=True)
        self.assertIn("leaderboard", ok.stdout)
        bad = subprocess.run([sys.executable, "-m", "medibuddy_bench", "nope"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)

    def test_doctor_passes_on_a_clean_clone(self):
        r = subprocess.run([sys.executable, "-m", "medibuddy_bench", "doctor"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
