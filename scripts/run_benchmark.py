#!/usr/bin/env python3
"""Run the benchmark locally against a built-in baseline or your own agent class.

  python scripts/run_benchmark.py --agent rule --data data/dev --tasks T1,T4 --limit 10
  python scripts/run_benchmark.py --agent mypkg.myagent:MyAgent --data data/dev --trials 3
"""
import argparse, importlib, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from medibuddy_bench.agents.baselines import make
from medibuddy_bench.runner import Runner
from medibuddy_bench.scoring.aggregate import aggregate, to_markdown


def factory(spec: str):
    if ":" in spec and not spec.startswith("saboteur:"):
        mod, cls = spec.split(":")
        C = getattr(importlib.import_module(mod), cls)
        return lambda scen: C()
    return make(spec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--data", default="data/dev")
    ap.add_argument("--tasks", default=None)
    ap.add_argument("--tiers", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--out", default=None, help="write episodes as JSONL")
    ap.add_argument("--no-transcripts", action="store_true")
    a = ap.parse_args()
    r = Runner(a.data, factory(a.agent), agent_name=a.agent, keep_transcripts=not a.no_transcripts)
    eps = r.run(tasks=a.tasks.split(",") if a.tasks else None, tiers=a.tiers.split(",") if a.tiers else None,
                limit=a.limit, trials=a.trials)
    rep = aggregate(eps)
    print(to_markdown(rep, a.agent))
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            for e in eps:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        with open(a.out.replace(".jsonl", ".report.json"), "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1)


if __name__ == "__main__":
    main()
