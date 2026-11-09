#!/usr/bin/env python3
"""Build the leaderboard from run records.

  python scripts/leaderboard.py --runs results/runs --data data/dev --out leaderboard

Writes leaderboard/LEADERBOARD.md and leaderboard/leaderboard.json.  Rules: docs/LEADERBOARD.md."""
import argparse, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from medibuddy_bench.leaderboard import build


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="results/runs")
    ap.add_argument("--data", default="data/dev", help="official split; its manifest defines what is comparable")
    ap.add_argument("--out", default="leaderboard")
    a = ap.parse_args()
    print(build(a.runs, a.data, a.out))


if __name__ == "__main__":
    main()
