"""Leaderboard from run records (see results.py for the record format and docs/LEADERBOARD.md for the rules).

Ranking: Overall (gated) high -> low; ties: lower critical-failure rate, then higher un-gated overall, then earlier
finish.  Only runs that cover the whole split on the official data version and world hash are ranked; partial and
non-comparable runs are listed separately with the reason.  Baselines (kind="baseline") are reference rows."""
from __future__ import annotations

import json
import os

from medibuddy_bench.common import TASKS
from medibuddy_bench.results import load_runs, read_manifest

HEAD = ["Rank", "Agent", "Model", "Overall", "Un-gated", "Crit. rate", "pass^3", *TASKS, "Trials", "Finished (UTC)"]


def crit_rate(report: dict) -> float:
    """Share of episodes with a critical failure, weighted by scenarios per task."""
    n = sum(t["n"] for t in report["tasks"].values()) or 1
    return sum(t["critical_rate"] * t["n"] for t in report["tasks"].values()) / n


def classify(run: dict, manifest: dict) -> tuple[str, str]:
    """-> ("ranked" | "partial" | "stale", reason)."""
    if not run["coverage"]["full"]:
        return "partial", "; ".join(run["coverage"]["reasons"])
    d = run["data"]
    if d.get("world_hash") != manifest.get("world_hash") or d.get("version") != manifest.get("version"):
        return "stale", (f"scored on data {d.get('version')}/{d.get('world_hash')}, "
                         f"official is {manifest.get('version')}/{manifest.get('world_hash')}")
    return "ranked", ""


def _sort_key(run: dict):
    rep = run["report"]
    return (-rep["overall"], crit_rate(rep), -rep["overall_ungated"], run["finished_utc"])


def _row(rank, run: dict) -> str:
    rep = run["report"]
    pk = rep.get("pass_hat_k", {})
    p3 = pk.get("3", pk.get(3))
    cells = [f"{rep['tasks'][t]['gated'] * 100:.0f}" if t in rep["tasks"] else "-" for t in TASKS]
    return "| " + " | ".join([str(rank), run["agent"], run.get("model") or "", f"**{rep['overall']:.1f}**",
                              f"{rep['overall_ungated']:.1f}", f"{crit_rate(rep):.0%}",
                              f"{p3:.2f}" if p3 is not None else "-", *cells, str(run["scope"]["trials"]),
                              run["finished_utc"][:16].replace("T", " ")]) + " |"


def build(runs_dir: str, data_dir: str, out_dir: str) -> str:
    """Write LEADERBOARD.md and leaderboard.json into `out_dir`; returns the Markdown."""
    man = read_manifest(data_dir)
    split = os.path.basename(os.path.normpath(data_dir))
    ranked, partial, stale, base = [], [], [], []
    for run in load_runs(runs_dir):
        if run["data"].get("dir") != split:
            continue
        status, why = classify(run, man)
        run["_why"] = why
        if status == "ranked":
            (base if run["kind"] == "baseline" else ranked).append(run)
        else:
            (partial if status == "partial" else stale).append(run)
    ranked.sort(key=_sort_key)
    base.sort(key=_sort_key)
    table = ["| " + " | ".join(HEAD) + " |", "|" + "---|" * len(HEAD)]
    empty = lambda msg: ["| | " + msg + " |" + " |" * (len(HEAD) - 2)]
    md = [f"# MediBuddy-Bench leaderboard ({split} split)", "",
          f"Benchmark data version `{man.get('version')}`, world hash `{man.get('world_hash')}`. Scores are 0-100; per-task "
          f"columns are gated scores x100. Critical failures (C1-C4) zero an episode.", "",
          "## Ranked agents", "", *table,
          *([_row(i + 1, r) for i, r in enumerate(ranked)] or empty("_no ranked runs yet_")),
          "", "## Reference baselines (not ranked)", "", *table,
          *([_row("-", r) for r in base] or empty("_none_"))]
    if partial or stale:
        md += ["", "## Not ranked", "", "| Agent | Model | Overall (covered tasks) | Reason | Run |", "|---|---|---|---|---|"]
        for r in partial + stale:
            rep = r["report"]
            md.append(f"| {r['agent']} | {r.get('model') or ''} | "
                      f"{rep.get('overall_rescaled_to_covered_tasks', rep['overall']):.1f} | {r['_why']} | `{r['run_id']}` |")
    md += ["", "Columns T1-T8: " + ", ".join(f"{t} {TASKS[t]['name']}" for t in TASKS) + ".", ""]
    text = "\n".join(md)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "LEADERBOARD.md"), "w", encoding="utf-8") as f:
        f.write(text)
    with open(os.path.join(out_dir, "leaderboard.json"), "w", encoding="utf-8") as f:
        json.dump({"data": man.get("version"), "world_hash": man.get("world_hash"),
                   "ranked": [{"rank": i + 1, "run_id": r["run_id"], "agent": r["agent"], "model": r.get("model"),
                               "overall": r["report"]["overall"], "overall_ungated": r["report"]["overall_ungated"],
                               "critical_rate": crit_rate(r["report"]), "finished_utc": r["finished_utc"]}
                              for i, r in enumerate(ranked)],
                   "baselines": [{"agent": r["agent"], "overall": r["report"]["overall"]} for r in base],
                   "not_ranked": [{"run_id": r["run_id"], "agent": r["agent"], "reason": r["_why"]}
                                  for r in partial + stale]}, f, indent=1)
    return text
