"""The statistics quoted in README.md and docs/DATASET_STATS.md must match the committed dev data."""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _stats(*extra):
    return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "dataset_stats.py"), "--data",
                           os.path.join(ROOT, "data", "dev"), *extra],
                          capture_output=True, text=True, check=True, cwd=ROOT).stdout


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


class Docs(unittest.TestCase):
    def test_dataset_stats_document_is_current(self):
        self.assertEqual(_stats().strip(), _read("docs/DATASET_STATS.md").strip(),
                         "regenerate: python scripts/dataset_stats.py --data data/dev > docs/DATASET_STATS.md")

    def test_readme_block_is_current(self):
        r = _read("README.md")
        a, b = r.index("<!-- stats:begin"), r.index("<!-- stats:end -->")
        block = r[r.index("\n", a) + 1:b].strip()
        self.assertEqual(block, _stats("--summary").strip(),
                         "regenerate the README block with: python scripts/dataset_stats.py --data data/dev --summary")


if __name__ == "__main__":
    unittest.main()
