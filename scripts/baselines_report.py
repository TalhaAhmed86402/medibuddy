#!/usr/bin/env python3
"""Regenerate the tables of docs/BASELINES.md (and the short block in README.md) from reference run records.

  python scripts/baselines_report.py                       # dev records in results/runs, lite records in results/lite-runs
  python scripts/baselines_report.py --check               # exit 1 if the documents are out of date

Only records marked as baselines (`--baseline`) that cover a whole split on the current data version are used, so every number in
the documents can be traced to a run record in the repository."""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from medibuddy_bench.common import TASKS, TIERS
from medibuddy_bench.leaderboard import crit_rate
from medibuddy_bench.results import load_runs, read_manifest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SCRIPTED = ("oracle", "rule", "naive", "null")


def _records(runs_dir: str, data_dir: str) -> list[dict]:
    if not os.path.isdir(runs_dir):
        return []
    man = read_manifest(data_dir)
    keep = [r for r in load_runs(runs_dir) if r.get("kind") == "baseline" and r["coverage"]["full"]
            and r["data"].get("world_hash") == man.get("world_hash")]
    latest: dict[str, dict] = {}
    for r in sorted(keep, key=lambda r: r["finished_utc"]):
        latest[r["agent"]] = r                       # the newest record per agent
    rows = list(latest.values())
    return sorted(rows, key=lambda r: (r["agent"] not in SCRIPTED, -r["report"]["overall"]))


def _label(r: dict) -> str:
    if r["agent"] in SCRIPTED:
        return f"{r['agent']} (scripted)"
    return f"{r['agent']}"


def table(rows: list[dict]) -> str:
    head = ["Agent", "Overall", "Un-gated", "Crit. rate", *TASKS, *TIERS]
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        rep = r["report"]
        cells = [_label(r), f"**{rep['overall']:.1f}**", f"{rep['overall_ungated']:.1f}", f"{crit_rate(rep):.0%}"]
        cells += [f"{100 * rep['tasks'][t]['gated']:.0f}" if t in rep["tasks"] else "-" for t in TASKS]
        cells += [f"{rep['tiers'][t]['gated']:.2f}" if t in rep.get("tiers", {}) else "-" for t in TIERS]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def critical_table(rows: list[dict]) -> str:
    names = ["C1_missed_red_flag", "C2_wrong_medical_fact", "C3_privacy", "C4_injection_obeyed"]
    out = ["| Agent | Episodes | " + " | ".join(n.split("_", 1)[0] + " " + n.split("_", 1)[1].replace("_", " ") for n in names) + " |",
           "|" + "---|" * (len(names) + 2)]
    for r in rows:
        rep = r["report"]
        out.append(f"| {_label(r)} | {rep['n_episodes']} | " + " | ".join(str(rep["critical"].get(n, 0)) for n in names) + " |")
    return "\n".join(out)


def models_table(rows: list[dict]) -> str:
    if not any(r["agent"] not in SCRIPTED for r in rows):
        return ("_No open-model run on this split yet._ To add them: start a model server, then\n"
                "`python scripts/sweep.py --data data/dev --runs results/runs --baseline --workers 4` and "
                "`python scripts/baselines_report.py`.")
    out = ["| Agent | Model id on the server | Run record | Notes |", "|---|---|---|---|"]
    for r in rows:
        if r["agent"] in SCRIPTED:
            continue
        notes = r.get("notes") or ""
        out.append(f"| {r['agent']} | `{(r.get('extra') or {}).get('served_model') or r.get('model')}` | `{r['run_id']}` | {notes} |")
    return "\n".join(out)


def _replace(text: str, tag: str, body: str) -> str:
    a, b = f"<!-- {tag}:begin", f"<!-- {tag}:end -->"
    if a not in text:
        raise SystemExit(f"marker {a} missing")
    i = text.index("\n", text.index(a)) + 1
    j = text.index(b)
    return text[:i] + body.rstrip("\n") + "\n" + text[j:]


def render(dev_rows, lite_rows) -> dict[str, str]:
    blocks = {"dev-table": table(dev_rows), "dev-critical": critical_table(dev_rows), "dev-models": models_table(dev_rows),
              "lite-table": table(lite_rows) if lite_rows else "_no lite records_",
              "lite-critical": critical_table(lite_rows), "lite-models": models_table(lite_rows)}
    def short(rows):
        out = ["| Agent | Overall (gated) | Un-gated |", "|---|---|---|"]
        return "\n".join(out + [f"| {_label(r)} | **{r['report']['overall']:.1f}** | {r['report']['overall_ungated']:.1f} |"
                                for r in rows])
    version = (dev_rows or lite_rows or [{"data": {"version": "?"}}])[0]["data"]["version"]
    models_dev = [r for r in dev_rows if r["agent"] not in SCRIPTED]
    parts = [f"Reference results (data v{version}; generated from the run records by `scripts/baselines_report.py`; setup and "
             "per-task tables in [`docs/BASELINES.md`](docs/BASELINES.md)).", "", "Dev split (832 scenarios):", "", short(dev_rows)]
    lite_models = [r for r in lite_rows if r["agent"] not in SCRIPTED]
    if lite_models and not models_dev:
        parts += ["", "Open models served locally, lite split (116 scenarios; dev runs not yet made):", "",
                  short([r for r in lite_rows if r["agent"] in ("rule", "oracle")] + lite_models)]
    blocks["baselines"] = "\n".join(parts)
    return blocks


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dev-runs", default=os.path.join(ROOT, "results", "runs"))
    ap.add_argument("--lite-runs", default=os.path.join(ROOT, "results", "lite-runs"))
    ap.add_argument("--check", action="store_true", help="only check that the documents are current")
    a = ap.parse_args()
    dev = _records(a.dev_runs, os.path.join(ROOT, "data", "dev"))
    lite = _records(a.lite_runs, os.path.join(ROOT, "data", "lite"))
    blocks = render(dev, lite)
    stale = []
    for path, tags in ((os.path.join(ROOT, "docs", "BASELINES.md"), ("dev-table", "dev-critical", "dev-models", "lite-table", "lite-critical", "lite-models")),
                       (os.path.join(ROOT, "README.md"), ("baselines",))):
        with open(path, encoding="utf-8") as f:
            old = f.read()
        new = old
        for t in tags:
            new = _replace(new, t, blocks[t])
        if new != old:
            stale.append(os.path.relpath(path, ROOT))
            if not a.check:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new)
    if a.check:
        if stale:
            print("out of date: " + ", ".join(stale) + " (run python scripts/baselines_report.py)")
            sys.exit(1)
        print("baseline documents are current")
    else:
        print("updated: " + (", ".join(stale) if stale else "nothing (already current)"))


if __name__ == "__main__":
    main()
