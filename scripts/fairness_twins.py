#!/usr/bin/env python3
"""Fairness twins for T1-T3: re-run each scenario with the patient's name and nationality swapped
(everything that decides the gold answer stays identical) and report the score gap.

  python scripts/fairness_twins.py --agent rule --data data/dev --limit 60

A fair agent scores the same on both versions; a mean gap far from 0, or a different set of
recommended hospitals, signals that the agent reacts to who the patient is instead of what they need."""
import argparse, copy, os, random, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from medibuddy_bench.agents.baselines import make
from medibuddy_bench.knowledge import FIRST_NAMES, NATIONALITIES
from medibuddy_bench.runner import Runner


def twin(scen: dict, rng: random.Random) -> dict:
    s = copy.deepcopy(scen)
    p = s["gold"]["persona"]
    new_name = rng.choice([n for n in FIRST_NAMES if n != p["name"]])
    new_nat = rng.choice([n for n, _ in NATIONALITIES if n != p["nationality"]])
    # lowest-risk swap: only strings that are demographic labels
    s["public"]["opening"] = s["public"]["opening"].replace(p["name"], new_name).replace(p["nationality"], new_nat)
    s["gold"]["persona"] = {**p, "name": new_name, "nationality": new_nat}
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--data", default="data/dev")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    r = Runner(a.data, make(a.agent), agent_name=a.agent, keep_transcripts=False)
    gaps = []
    for task in ("T1", "T2", "T3"):
        base = r.scen[task][: a.limit]
        diffs = []
        for s in base:
            e0 = r.run_one(s)
            e1 = r.run_one(twin(s, rng))
            diffs.append(e1["score"] - e0["score"])
        gaps += diffs
        print(f"{task}: n={len(diffs)} mean gap (twin - original) = {sum(diffs)/len(diffs):+.4f}, "
              f"max |gap| = {max(abs(d) for d in diffs):.3f}")
    print(f"ALL: mean gap {sum(gaps)/len(gaps):+.4f}")


if __name__ == "__main__":
    main()
