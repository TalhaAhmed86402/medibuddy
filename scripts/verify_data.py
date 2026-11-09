#!/usr/bin/env python3
"""Check that a data split is intact (and, with --rebuild, reproducible from its seed on this machine).

  python scripts/verify_data.py --data data/lite --rebuild     # exit code 0 = OK"""
import argparse, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from medibuddy_bench.verify import check_files, check_rebuild


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/dev")
    ap.add_argument("--rebuild", action="store_true", help="also regenerate from the seed and compare (dev takes ~1-2 min)")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    problems = check_files(a.data) + (check_rebuild(a.data, a.seed) if a.rebuild else [])
    for p in problems:
        print("FAIL:", p)
    print(f"{a.data}: {'OK' if not problems else 'PROBLEMS FOUND'}" + (" (files + rebuild)" if a.rebuild else " (files)"))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
