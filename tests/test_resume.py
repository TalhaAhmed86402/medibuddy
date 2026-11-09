"""Resume support: skipping already-scored episodes must reproduce the uninterrupted result."""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

from medibuddy_bench.agents.baselines import make
from medibuddy_bench.runner import Runner
from medibuddy_bench.scoring.aggregate import aggregate


class Resume(unittest.TestCase):
    def test_resume_equals_full_run(self):
        r = Runner(os.path.join(ROOT, "data", "lite"), make("rule"), "rule", keep_transcripts=False)
        full = r.run(tasks=["T1", "T4"], limit=6)
        part = full[:5]
        done = {(e["id"], e.get("trial", 0)) for e in part}
        seen = []
        rest = r.run(tasks=["T1", "T4"], limit=6, done=done, progress=lambda e, i, n: seen.append((i, n)))
        self.assertEqual(len(part) + len(rest), len(full))
        self.assertEqual(seen[0][0], 6)                      # progress counts the skipped ones
        self.assertEqual(seen[-1], (12, 12))
        self.assertAlmostEqual(aggregate(part + rest)["overall"], aggregate(full)["overall"])


if __name__ == "__main__":
    unittest.main()
