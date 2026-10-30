"""Build a dataset split deterministically from a seed.

    python -m medibuddy_bench.gen.build --split dev --seed 1 --out data/dev
    python -m medibuddy_bench.gen.build --split test --seed <SECRET> --out /private/test   # hidden split

Same seed + same code => byte-identical files (checked by tests/test_benchmark.py::Determinism).
The hidden test split is produced by the benchmark maintainers with a secret seed, so the public
repo contains the generator but not the test data."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import random

from medibuddy_bench import VERSION
from medibuddy_bench.common import WORLD_END, WORLD_START, iso, stable_hash
from medibuddy_bench.gen.choice import finalize_choice, gen_choice
from medibuddy_bench.gen.encounters import gen_encounter
from medibuddy_bench.gen.hospitals import gen_background_notices, gen_hospitals
from medibuddy_bench.gen.journey import gen_journey
from medibuddy_bench.gen.memory import gen_memory
from medibuddy_bench.gen.triage import CASES, gen_triage
from medibuddy_bench.world import World

SIZES = {
    "dev": {"T1": 40, "T2": 32, "T3": 32, "T4": 64, "T5": 40, "T6": 40, "T7": 24, "T8": 16},
    "test": {"T1": 60, "T2": 48, "T3": 48, "T4": 84, "T5": 60, "T6": 60, "T7": 36, "T8": 24},
    "mini": {"T1": 8, "T2": 8, "T3": 8, "T4": 8, "T5": 8, "T6": 8, "T7": 8, "T8": 8},  # for tests / smoke runs
}
TIERS = ["L1", "L2", "L3", "L4"]


def _tier(i: int) -> str:
    return TIERS[i % 4]


def build(split: str, seed: int, sizes: dict | None = None) -> dict:
    sizes = sizes or SIZES[split]
    rng = random.Random(seed)
    hospitals = gen_hospitals(random.Random(rng.random()), 320)
    notices = gen_background_notices(random.Random(rng.random()), hospitals, WORLD_START, WORLD_END)
    world = World({"meta": {"as_of": "2026-10-29", "split": split, "seed_hash": stable_hash(seed),
                            "version": VERSION, "synthetic": True},
                   "hospitals": hospitals, "notices": notices})
    lo, hi = WORLD_START + dt.timedelta(days=50), WORLD_END - dt.timedelta(days=5)
    scen: dict[str, list[dict]] = {}

    def run(task, n, fn, over=1.0):
        """Generate n scenarios, round-robin over tiers; retry until each succeeds."""
        out = []
        i = attempts = 0
        while len(out) < n and attempts < n * 400:
            attempts += 1
            sid = f"{task}-{split}-{len(out):04d}"
            s = fn(sid, len(out), _tier(len(out)))
            if s:
                out.append(s)
        if len(out) < n:
            raise RuntimeError(f"could only generate {len(out)}/{n} {task} scenarios")
        return out

    r = random.Random(rng.random())
    scen["T1"] = run("T1", sizes["T1"], lambda sid, i, t: gen_choice(world, r, "T1", t, sid, i, lo, hi))
    scen["T2"] = run("T2", sizes["T2"], lambda sid, i, t: gen_choice(world, r, "T2", t, sid, i, lo, hi))
    scen["T3"] = run("T3", sizes["T3"], lambda sid, i, t: gen_choice(world, r, "T3", t, sid, i, lo, hi))
    scen["T7"] = run("T7", sizes["T7"], lambda sid, i, t: gen_memory(world, r, t, sid, i, lo, hi))
    scen["T8"] = run("T8", sizes["T8"], lambda sid, i, t: gen_journey(world, r, t, sid, i, lo, hi))
    # T8 contains a choice scenario too; finalise those along with T1-T3
    # world is final now: recompute gold from the final world and drop anything that no longer qualifies
    for task in ("T1", "T2", "T3", "T8"):
        keep = []
        for s in scen[task]:
            if finalize_choice(world, s):
                keep.append(s)
        if len(keep) < len(scen[task]):
            # regenerate replacements (which may again add notices); loop until complete & final
            need = len(scen[task]) - len(keep)
            tries = 0
            while need and tries < 4000:
                tries += 1
                sid = f"{task}-{split}-{len(keep):04d}"
                t = _tier(len(keep))
                if task == "T8":
                    s = gen_journey(world, r, t, sid, len(keep), lo, hi)
                else:
                    s = gen_choice(world, r, task, t, sid, len(keep), lo, hi)
                if s and finalize_choice(world, s):
                    keep.append(s)
                    need -= 1
            if need:
                raise RuntimeError(f"could not repair {task}")
        for i, s in enumerate(keep):          # ids must stay unique after repairs
            s["id"] = f"{task}-{split}-{i:04d}"
        scen[task] = keep
    # one more full pass: later additions must not have invalidated earlier scenarios
    for task in ("T1", "T2", "T3", "T8"):
        for s in scen[task]:
            if not finalize_choice(world, s):
                raise RuntimeError(f"scenario {s['id']} invalidated by later notices; rerun with another seed")
    # T7 gold sets depend on the final world as well -> recompute
    for s in scen["T7"]:
        for p in s["gold"]["probes"]:
            if p["type"] == "recommend":
                c = p["constraints"]
                s["gold"]["valid"] = sorted(world.valid_set(c))
                s["gold"]["best"] = world.best(c)
                s["gold"]["near_misses"] = sorted(world.near_misses(c))
                if len(s["gold"]["valid"]) < 2:
                    raise RuntimeError(f"{s['id']} lost its valid set; rerun with another seed")
    r2 = random.Random(rng.random())
    scen["T4"] = gen_triage(r2, sizes["T4"], f"T4-{split}")
    for task, key in (("T5", 5), ("T6", 6)):
        out = []
        for i in range(sizes[task]):
            tier = _tier(i)
            enc = gen_encounter(random.Random(r2.random()), tier)
            sid = f"{task}-{split}-{i:04d}"
            if task == "T5":
                out.append({"id": sid, "task": "T5", "tier": tier,
                            "public": {"turns": [{"i": t["i"], "speaker": t["speaker"], "lang": t["src_lang"],
                                                  "text": t["text"]} for t in enc["turns"]]},
                            "gold": {"turns": enc["turns"], "spec": enc["spec"]}})
            else:
                out.append({"id": sid, "task": "T6", "tier": tier,
                            "public": {"transcript": [{"speaker": t["speaker"], "lang": t["src_lang"],
                                                       "text": t["text"]} for t in enc["turns"]]},
                            "gold": {"summary": enc["gold_summary"], "spec": enc["spec"],
                                     "turns": enc["turns"]}})
        scen[task] = out
    return {"world": world.data, "scenarios": scen}


def write(ds: dict, out: str) -> dict:
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "world.json"), "w", encoding="utf-8") as f:
        json.dump(ds["world"], f, ensure_ascii=False, sort_keys=True, indent=1)
    manifest = {"version": VERSION, "world_hash": stable_hash(ds["world"]), "counts": {}, "hashes": {}}
    for task, items in ds["scenarios"].items():
        with open(os.path.join(out, f"{task}.jsonl"), "w", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False, sort_keys=True) + "\n")
        manifest["counts"][task] = len(items)
        manifest["hashes"][task] = stable_hash(items)
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
    return manifest


def write_review_sheets(ds: dict, outdir: str):
    """Sheets for the human reviewers on the team (native Korean speaker; clinician)."""
    os.makedirs(outdir, exist_ok=True)
    seen = {}
    for task in ("T5", "T6"):
        for s in ds["scenarios"][task]:
            for t in s["gold"]["turns"]:
                key = (t["speaker"], t["text"])
                seen.setdefault(key, t["reference"])
    with open(os.path.join(outdir, "korean_phrasebook.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["speaker", "source_text", "reference_translation", "OK? (y/n)", "native_speaker_correction",
                    "comment"])
        for (sp, txt), ref in sorted(seen.items()):
            w.writerow([sp, txt, ref, "", "", ""])
    with open(os.path.join(outdir, "triage_labels.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case", "benchmark_label", "example_text_L1", "clinician_agrees? (y/n)", "clinician_label",
                    "comment"])
        for k, (label, texts) in CASES.items():
            w.writerow([k, label, texts["L1"], "", "", ""])
    return len(seen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev", choices=list(SIZES))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=None)
    ap.add_argument("--review", default=None, help="directory for the human-review CSVs")
    a = ap.parse_args()
    ds = build(a.split, a.seed)
    out = a.out or os.path.join("data", a.split)
    m = write(ds, out)
    print(json.dumps(m["counts"]), "world", m["world_hash"])
    if a.review:
        print("phrasebook rows:", write_review_sheets(ds, a.review))


if __name__ == "__main__":
    main()
