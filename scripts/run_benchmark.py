#!/usr/bin/env python3
"""Run the benchmark locally against a built-in baseline or your own agent class.

  python scripts/run_benchmark.py --agent rule --data data/dev --tasks T1,T4 --limit 10
  python scripts/run_benchmark.py --agent mypkg.myagent:MyAgent --data data/dev --trials 3
  python scripts/run_benchmark.py --agent openai:qwen2.5:7b ...     # any OpenAI-compatible server
  python scripts/run_benchmark.py --agent http://localhost:8000/chat ...   # or cmd:"python my_agent.py", guarded:<spec>
Accepted --agent forms are listed in medibuddy_bench/agents/registry.py.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from medibuddy_bench.agents.registry import resolve as factory
from medibuddy_bench.runner import Runner
from medibuddy_bench.scoring.aggregate import aggregate, to_markdown


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
    ap.add_argument("--checkpoint", default=None, metavar="FILE",
                    help="append every scored episode to FILE and, if FILE exists for the same data, resume from it "
                         "(an interrupted run continues instead of restarting)")
    ap.add_argument("--save-run", default=None, metavar="RUNS_DIR",
                    help="store a run record (e.g. results/runs) that scripts/leaderboard.py can rank")
    ap.add_argument("--name", default=None, help="agent name shown on the leaderboard (default: --agent)")
    ap.add_argument("--model", default=None, help="model name shown on the leaderboard (default: $MEDIBUDDY_MODEL)")
    ap.add_argument("--baseline", action="store_true", help="mark the run as a reference baseline (not ranked)")
    a = ap.parse_args()
    r = Runner(a.data, factory(a.agent), agent_name=a.agent, keep_transcripts=not a.no_transcripts)
    from medibuddy_bench.execute import run_with_checkpoint
    eps = run_with_checkpoint(r, a.data, a.name or a.agent, a.tasks.split(",") if a.tasks else None,
                              a.tiers.split(",") if a.tiers else None, a.limit, a.trials, a.checkpoint)
    rep = aggregate(eps)
    print(to_markdown(rep, a.agent))
    if a.save_run:
        from medibuddy_bench.results import save_run
        p = save_run(a.save_run, a.name or a.agent, eps, rep, a.data,
                     {"tasks": a.tasks.split(",") if a.tasks else None, "tiers": a.tiers.split(",") if a.tiers else None,
                      "limit": a.limit, "trials": a.trials}, source="local",
                     model=a.model or os.environ.get("MEDIBUDDY_MODEL"), kind="baseline" if a.baseline else "agent",
                     keep_transcripts=not a.no_transcripts)
        print(f"\nrun record: {p}")
        if a.checkpoint and os.path.exists(a.checkpoint):
            os.remove(a.checkpoint)
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            for e in eps:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        with open(a.out.replace(".jsonl", ".report.json"), "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1)


if __name__ == "__main__":
    main()
