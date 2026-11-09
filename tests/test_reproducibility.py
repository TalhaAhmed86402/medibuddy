"""Data must be intact and regenerate byte-for-byte (same hashes) on every machine and Python version."""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

from medibuddy_bench.verify import check_files, check_rebuild


class Reproducible(unittest.TestCase):
    def test_committed_splits_are_intact(self):
        for split in ("lite", "dev"):
            self.assertEqual(check_files(os.path.join(ROOT, "data", split)), [], split)

    def test_lite_rebuilds_identically(self):
        self.assertEqual(check_rebuild(os.path.join(ROOT, "data", "lite"), seed=1), [])


if __name__ == "__main__":
    unittest.main()
