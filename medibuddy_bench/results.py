"""Run records: one folder per assessment, so every number on the leaderboard can be traced and re-checked.

    results/runs/<run_id>/run.json        metadata + the full report (everything the leaderboard needs)
    results/runs/<run_id>/episodes.jsonl  one scored episode per line
    results/runs/<run_id>/report.md       human-readable report

A run is **ranked** only when it covers the whole split (all 8 tasks, every scenario, no tier filter) AND was
scored against the same data version and world hash as the official split.  Anything else is listed as
*partial* or *not comparable*, never silently mixed in."""
from __future__ import annotations

import datetime as dt
import json
import os
import re

from medibuddy_bench import VERSION
from medibuddy_bench.common import TASKS
from medibuddy_bench.scoring.aggregate import to_markdown


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-")[:60] or "agent"


def read_manifest(data_dir: str) -> dict:
    with open(os.path.join(data_dir, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def coverage(report: dict, manifest: dict, scope: dict) -> dict:
    """-> {"full": bool, "reasons": [why not]}"""
    why = []
    missing = [t for t in TASKS if t not in report["tasks"]]
    if missing:
        why.append("tasks not run: " + ",".join(missing))
    if scope.get("tiers"):
        why.append("tier filter " + ",".join(scope["tiers"]))
    if scope.get("limit"):
        why.append(f"limit {scope['limit']} per task")
    short = [t for t, r in report["tasks"].items() if r["n"] < manifest["counts"].get(t, 0)]
    if short and not scope.get("limit"):
        why.append("fewer scenarios than the split: " + ",".join(short))
    return {"full": not why, "reasons": why}


def save_run(runs_dir: str, agent: str, episodes: list[dict], report: dict, data_dir: str, scope: dict,
             source: str = "local", model: str | None = None, kind: str = "agent", notes: str = "",
             keep_transcripts: bool = False) -> str:
    man = read_manifest(data_dir)
    now = dt.datetime.now(dt.timezone.utc)
    run_id = f"{now:%Y%m%d-%H%M%S}-{slug(agent)}"
    path = os.path.join(runs_dir, run_id)
    os.makedirs(path, exist_ok=True)
    cov = coverage(report, man, scope)
    meta = {"run_id": run_id, "agent": agent, "model": model, "kind": kind, "source": source, "notes": notes,
            "finished_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "benchmark_version": VERSION,
            "data": {"dir": os.path.basename(os.path.normpath(data_dir)), "version": man.get("version"),
                     "world_hash": man.get("world_hash"), "hashes": man.get("hashes")},
            "scope": {"tasks": scope.get("tasks"), "tiers": scope.get("tiers"), "limit": scope.get("limit"),
                      "trials": scope.get("trials", 1)},
            "coverage": cov, "report": report}
    with open(os.path.join(path, "run.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
    with open(os.path.join(path, "episodes.jsonl"), "w", encoding="utf-8") as f:
        for e in episodes:
            if not keep_transcripts:
                e = {k: v for k, v in e.items() if k != "transcript"}
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    with open(os.path.join(path, "report.md"), "w", encoding="utf-8") as f:
        f.write(to_markdown(report, f"{agent} ({run_id})") + "\n")
    return path


def load_runs(runs_dir: str) -> list[dict]:
    out = []
    if not os.path.isdir(runs_dir):
        return out
    for name in sorted(os.listdir(runs_dir)):
        p = os.path.join(runs_dir, name, "run.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                out.append(json.load(f))
    return out
