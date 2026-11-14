#!/usr/bin/env python3
"""Score a list of models on any OpenAI-compatible server (see medibuddy_bench/sweep.py and docs/SETUP_GPU_MACHINE.md)."""
import argparse, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from medibuddy_bench.sweep import sweep


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/sweep.json")
    ap.add_argument("--data", default="data/lite", help="data/lite for a quick pass, data/dev for the official split")
    ap.add_argument("--runs", default="results/runs")
    ap.add_argument("--out", default=None, help="leaderboard folder to rebuild (default: leaderboard/ for data/dev, "
                                                 "else <runs>/../leaderboard-<split>, so a lite sweep never overwrites "
                                                 "the official board)")
    ap.add_argument("--only", default=None, help="comma-separated model names from the config")
    ap.add_argument("--max-vram", type=float, default=None, help="skip models whose min_vram_gb exceeds this")
    ap.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL"),
                    help="OpenAI-compatible endpoint (default: $OPENAI_BASE_URL, else the config's default, Ollama)")
    ap.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY"))
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None, help="scenarios per task (smoke test; such runs are never ranked)")
    ap.add_argument("--force", action="store_true", help="re-score models that already have a full run on this data")
    ap.add_argument("--list", action="store_true", help="only show which configured models the server has")
    ap.add_argument("--workers", type=int, default=1, help="episodes run at once per model (needs a batching server)")
    ap.add_argument("--baseline", action="store_true", help="record the runs as reference baselines (maintainers)")
    a = ap.parse_args()
    with open(a.config, encoding="utf-8") as f:
        cfg = json.load(f)
    overrides = {k: v for k, v in {"base_url": a.base_url, "api_key": a.api_key}.items() if v}
    split = os.path.basename(os.path.normpath(a.data))
    out = a.out or ("leaderboard" if split == "dev" else os.path.join(os.path.dirname(os.path.abspath(a.runs)),
                                                                    f"leaderboard-{split}"))
    res = sweep(cfg, a.data, a.runs, a.only.split(",") if a.only else None, a.max_vram, a.trials, a.force, a.limit,
                overrides=overrides, listing=a.list, workers=a.workers, baseline=a.baseline, out_dir=out)
    print("\n" + "\n".join(f"{r['status']:>9}  {r['name']:<18} {r['why']}" for r in res))
    sys.exit(1 if any(r["status"] == "failed" for r in res) else 0)


if __name__ == "__main__":
    main()
