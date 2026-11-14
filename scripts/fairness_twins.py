#!/usr/bin/env python3
"""Fairness twins for T1-T3: re-run each scenario with the patient's name and nationality swapped
(everything that decides the gold answer stays identical) and report the score gap.

  python scripts/fairness_twins.py --agent rule --data data/dev --limit 60
  python scripts/fairness_twins.py --agent openai:qwen2.5:7b --data data/dev --limit 30 --json twins.json   # any --agent form

A fair agent scores the same on both versions; a mean gap far from 0, or a different set of
recommended hospitals, signals that the agent reacts to who the patient is instead of what they need."""
import argparse, copy, os, random, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from medibuddy_bench.agents.registry import resolve
from medibuddy_bench.knowledge import NAMES_BY_NATIONALITY, country_phrase
from medibuddy_bench.runner import Runner


def twin(scen: dict, rng: random.Random) -> dict:
    """Same scenario, another (nationality, name) pair of the same sex, so the text stays coherent."""
    s = copy.deepcopy(scen)
    p = s["gold"]["persona"]
    sex = p.get("sex", "f")
    new_nat = rng.choice(sorted(n for n in NAMES_BY_NATIONALITY if n != p["nationality"]))
    new_name = rng.choice([n for n in NAMES_BY_NATIONALITY[new_nat][sex] if n != p["name"]])
    # lowest-risk swap: only whole-word demographic labels
    op = re.sub(rf"\b{re.escape(p['name'])}\b", new_name, s["public"]["opening"])
    op = re.sub(rf"\b{re.escape(country_phrase(p['nationality']))}\b", country_phrase(new_nat), op)
    s["public"]["opening"] = re.sub(rf"\b{re.escape(p['nationality'])}\b", new_nat, op)
    s["gold"]["persona"] = {**p, "name": new_name, "nationality": new_nat}
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--data", default="data/dev")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--json", default=None, help="also write the per-task gaps to this JSON file")
    ap.add_argument("--control", action="store_true",
                    help="also re-run each original once more, to measure run-to-run noise of a model (scripted agents have none)")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    r = Runner(a.data, resolve(a.agent), agent_name=a.agent, keep_transcripts=False)
    gaps, per_task = [], {}
    for task in ("T1", "T2", "T3"):
        base = r.scen[task][: a.limit]
        diffs, noise = [], []
        for s in base:
            e0 = r.run_one(s)
            e1 = r.run_one(twin(s, rng))
            diffs.append(e1["score"] - e0["score"])
            if a.control:                     # the same scenario again: how much a model varies with nothing changed
                noise.append(r.run_one(s)["score"] - e0["score"])
        gaps += diffs
        per_task[task] = {"n": len(diffs), "mean_gap": sum(diffs) / len(diffs), "max_abs_gap": max(abs(d) for d in diffs),
                          "changed": sum(1 for d in diffs if abs(d) > 1e-9)}
        if noise:
            per_task[task].update(control_mean_abs=sum(abs(d) for d in noise) / len(noise),
                                  control_changed=sum(1 for d in noise if abs(d) > 1e-9))
            print(f"    control (same scenario twice): mean |gap| {per_task[task]['control_mean_abs']:.4f}, "
                  f"changed {per_task[task]['control_changed']}")
        print(f"{task}: n={len(diffs)} mean gap (twin - original) = {sum(diffs)/len(diffs):+.4f}, "
              f"max |gap| = {max(abs(d) for d in diffs):.3f}, episodes whose score changed: {per_task[task]['changed']}")
    print(f"ALL: mean gap {sum(gaps)/len(gaps):+.4f}")
    if a.json:
        import json
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"agent": a.agent, "data": a.data, "limit": a.limit, "seed": a.seed, "tasks": per_task,
                       "mean_gap": sum(gaps) / len(gaps)}, f, indent=1)


if __name__ == "__main__":
    main()
