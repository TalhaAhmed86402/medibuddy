"""Run an agent over a split with live progress and resume (shared by scripts/run_benchmark.py and scripts/sweep.py).

A *checkpoint* is a JSONL file: a header describing the run, then one scored episode per line.  Re-running with the
same checkpoint skips what is already scored; a checkpoint written for a different agent, data or scope is refused,
so partial results from different setups can never be mixed."""
from __future__ import annotations

import json
import os
import sys
import time

from medibuddy_bench.results import read_manifest
from medibuddy_bench.runner import Runner


def run_with_checkpoint(runner: Runner, data_dir: str, agent_name: str, tasks=None, tiers=None, limit=None,
                        trials: int = 1, checkpoint: str | None = None, log=sys.stderr, workers: int = 1,
                        ids=None) -> list[dict]:
    """Score every scenario in scope; returns all episodes (resumed + new).  Raises SystemExit on a foreign checkpoint."""
    man = read_manifest(data_dir)
    header = {"agent": agent_name, "world_hash": man.get("world_hash"), "version": man.get("version"),
              "tasks": tasks, "tiers": tiers, "limit": limit, "trials": trials, **({"ids": ids} if ids else {})}
    prev: list[dict] = []
    if checkpoint and os.path.exists(checkpoint):
        with open(checkpoint, encoding="utf-8") as f:
            lines = [json.loads(l) for l in f if l.strip()]
        if lines and lines[0].get("_header") == header:
            prev = lines[1:]
            print(f"resuming: {len(prev)} episodes already scored in {checkpoint}", file=log)
        else:
            raise SystemExit(f"{checkpoint} belongs to a different run (agent, data, scope or trials differ); "
                             "delete it or choose another --checkpoint")
    elif checkpoint:
        os.makedirs(os.path.dirname(checkpoint) or ".", exist_ok=True)
        with open(checkpoint, "w", encoding="utf-8") as f:
            f.write(json.dumps({"_header": header}) + "\n")
    done = {(e["id"], e.get("trial", 0)) for e in prev}
    t0, started = time.time(), len(prev)

    def progress(ep, i, total):
        if checkpoint:
            with open(checkpoint, "a", encoding="utf-8") as f:
                f.write(json.dumps(ep, ensure_ascii=False) + "\n")
        eta = (time.time() - t0) / max(1, i - started) * (total - i)
        flag = " CRITICAL " + ",".join(ep["critical"]) if ep["critical"] else ""
        print(f"[{i}/{total}] {ep['task']} {ep['tier']} score={ep['score']:.2f}{flag}  "
              f"elapsed {time.time() - t0:.0f}s, ~{eta / 60:.0f} min left", file=log, flush=True)

    new = runner.run(tasks=tasks, tiers=tiers, limit=limit, trials=trials, progress=progress, done=done, workers=workers,
                     ids=set(ids) if ids else None)
    return prev + new
