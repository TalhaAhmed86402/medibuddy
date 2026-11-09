#!/usr/bin/env python3
"""Build the leaderboard from run records (results/runs/*/run.json).

  python scripts/leaderboard.py --runs results/runs --data data/dev --out leaderboard

Writes leaderboard/LEADERBOARD.md and leaderboard/leaderboard.json.
Ranking (see docs/LEADERBOARD.md): Overall (gated) high -> low; ties: lower critical-failure rate, then higher
un-gated overall, then earlier finish.  Only full-split runs on the official data version and world hash are
ranked; partial and non-comparable runs are listed separately with the reason.  Baselines (kind=baseline) are shown
as reference rows and never take a rank."""
import argparse, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from medibuddy_bench.common import CRITICAL, TASKS
from medibuddy_bench.results import load_runs, read_manifest


def crit_rate(rep):
    n = sum(t["n"] for t in rep["tasks"].values()) or 1
    return sum(t["critical_rate"] * t["n"] for t in rep["tasks"].values()) / n


def classify(run, man):
    if run["coverage"]["full"] is False:
        return "partial", "; ".join(run["coverage"]["reasons"])
    d = run["data"]
    if d.get("world_hash") != man.get("world_hash") or d.get("version") != man.get("version"):
        return "stale", f"scored on data {d.get('version')}/{d.get('world_hash')}, official is {man.get('version')}/{man.get('world_hash')}"
    return "ranked", ""


def row(run):
    r = run["report"]
    cells = [f"{r['tasks'][t]['gated'] * 100:.0f}" if t in r["tasks"] else "-" for t in TASKS]
    pk = r.get("pass_hat_k", {})
    p3 = pk.get("3") if "3" in pk else pk.get(3)
    return cells, p3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="results/runs")
    ap.add_argument("--data", default="data/dev", help="official split; its manifest defines what is comparable")
    ap.add_argument("--out", default="leaderboard")
    a = ap.parse_args()
    man = read_manifest(a.data)
    runs = [r for r in load_runs(a.runs) if r["data"].get("dir") == os.path.basename(os.path.normpath(a.data))]
    ranked, partial, stale, base = [], [], [], []
    for r in runs:
        status, why = classify(r, man)
        r["_why"] = why
        if r["kind"] == "baseline" and status == "ranked":
            base.append(r)
        elif status == "ranked":
            ranked.append(r)
        elif status == "partial":
            partial.append(r)
        else:
            stale.append(r)
    key = lambda r: (-r["report"]["overall"], crit_rate(r["report"]), -r["report"]["overall_ungated"], r["finished_utc"])
    ranked.sort(key=key)
    base.sort(key=key)
    head = ["Rank", "Agent", "Model", "Overall", "Un-gated", "Crit. rate", "pass^3", *[t for t in TASKS], "Trials", "Finished (UTC)"]
    sep = "|" + "---|" * len(head)

    def line(rank, r):
        cells, p3 = row(r)
        rep = r["report"]
        return "| " + " | ".join([str(rank), r["agent"], r.get("model") or "", f"**{rep['overall']:.1f}**",
                                  f"{rep['overall_ungated']:.1f}", f"{crit_rate(rep):.0%}",
                                  f"{p3:.2f}" if p3 is not None else "-", *cells, str(r["scope"]["trials"]),
                                  r["finished_utc"][:16].replace("T", " ")]) + " |"

    md = [f"# MediBuddy-Bench leaderboard ({os.path.basename(os.path.normpath(a.data))} split)", "",
          f"Benchmark data version `{man.get('version')}`, world hash `{man.get('world_hash')}`. Scores are 0-100; per-task columns are "
          f"gated scores x100. Critical failures (C1-C4) zero an episode.", "",
          "## Ranked agents", "", "| " + " | ".join(head) + " |", sep]
    md += [line(i + 1, r) for i, r in enumerate(ranked)] or ["| | _no ranked runs yet_ |" + " |" * (len(head) - 2)]
    md += ["", "## Reference baselines (not ranked)", "", "| " + " | ".join(head) + " |", sep]
    md += [line("-", r) for r in base] or ["| | _none_ |" + " |" * (len(head) - 2)]
    if partial or stale:
        md += ["", "## Not ranked", "", "| Agent | Model | Overall (covered tasks) | Reason | Run |", "|---|---|---|---|---|"]
        for r in partial + stale:
            rep = r["report"]
            ov = rep.get("overall_rescaled_to_covered_tasks", rep["overall"])
            md.append(f"| {r['agent']} | {r.get('model') or ''} | {ov:.1f} | {r['_why']} | `{r['run_id']}` |")
    md += ["", "Columns T1-T8: " + ", ".join(f"{t} {TASKS[t]['name']}" for t in TASKS) + ".", ""]
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "LEADERBOARD.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    with open(os.path.join(a.out, "leaderboard.json"), "w", encoding="utf-8") as f:
        json.dump({"data": man.get("version"), "world_hash": man.get("world_hash"),
                   "ranked": [{"rank": i + 1, "run_id": r["run_id"], "agent": r["agent"], "model": r.get("model"),
                               "overall": r["report"]["overall"], "overall_ungated": r["report"]["overall_ungated"],
                               "critical_rate": crit_rate(r["report"]), "finished_utc": r["finished_utc"]}
                              for i, r in enumerate(ranked)],
                   "baselines": [{"agent": r["agent"], "overall": r["report"]["overall"]} for r in base],
                   "not_ranked": [{"run_id": r["run_id"], "agent": r["agent"], "reason": r["_why"]} for r in partial + stale]},
                  f, indent=1)
    print("\n".join(md))


if __name__ == "__main__":
    main()
