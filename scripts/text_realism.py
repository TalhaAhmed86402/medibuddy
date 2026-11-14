#!/usr/bin/env python3
"""Compare the benchmark's patient wording with real doctor-patient conversations (optional check, not part of the build).

  git clone --depth 1 https://github.com/wyim/aci-bench      /path/aci-bench       # CC BY 4.0
  git clone --depth 1 https://github.com/abachaa/MTS-Dialog  /path/MTS-Dialog      # CC BY 4.0
  python scripts/text_realism.py --aci /path/aci-bench --mts /path/MTS-Dialog --data data/dev

The real corpora are spoken English consultations, so differences in length and question rate are partly genre. The measures that matter
are variety: how many different sentence shapes and word triples the data contains. The corpora are read, never copied into this repository."""
import argparse
import csv
import json
import os
import random
import re

FILL = re.compile(r"\b(um+|uh+|well|like|kind of|sort of|i think|maybe|probably|you know|actually|i guess|a little|a bit|pretty|really|so)\b", re.I)
CONTR = re.compile(r"\w+'(s|m|ve|re|d|ll|t)\b", re.I)


def sentences(texts):
    return [s for t in texts for s in re.split(r"(?<=[.!?])\s+", t.strip()) if len(s.split()) >= 3]


def shape(s):
    s = re.sub(r"\d+([:\-]\d+)*", "#", s.lower())
    return re.sub(r"\b(anya|[a-z]+-gu|[a-z]+-si)\b", "N", s)


def measures(name, texts):
    ss = sentences(texts)
    words = [w for s in ss for w in re.findall(r"[a-z']+", s.lower())]
    tri = list(zip(words, words[1:], words[2:]))
    n = len(ss)
    return (f"| {name} | {n} | {len(words) / n:.1f} | {len({shape(s) for s in ss}) / n:.2f} | {len(set(tri)) / len(tri):.2f} | "
            f"{sum(bool(CONTR.search(s)) for s in ss) / n:.2f} | {sum(bool(FILL.search(s)) for s in ss) / n:.2f} |")


def real_patient_turns(aci, mts):
    csv.field_size_limit(10 ** 8)
    out = []
    path = os.path.join(mts, "Main-Dataset", "MTS-Dialog-TrainingSet.csv")
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            for line in re.split(r"\r?\n", r["dialogue"]):
                m = re.match(r"\s*(Patient|Guest_family|Guest)\s*:\s*(.*)", line, re.I)
                if m and len(m.group(2).split()) >= 4:
                    out.append(m.group(2))
    path = os.path.join(aci, "data", "challenge_data", "train.csv")
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            for line in re.split(r"\r?\n", r["dialogue"]):
                m = re.match(r"\s*\[patient\]\s*(.*)", line, re.I)
                if m and len(m.group(1).split()) >= 4:
                    out.append(m.group(1))
    return out


def load(data, task):
    with open(os.path.join(data, f"{task}.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aci", required=True)
    ap.add_argument("--mts", required=True)
    ap.add_argument("--data", default="data/dev")
    a = ap.parse_args()
    real = real_patient_turns(a.aci, a.mts)
    random.seed(0)
    openings = [s["public"]["opening"] for t in ("T1", "T2", "T3") for s in load(a.data, t)]
    turns = [tu["text"] for s in load(a.data, "T5") for tu in s["public"]["turns"] if tu["speaker"] == "patient"]
    print("| Text | Sentences | Words per sentence | Distinct shapes per sentence | Distinct word triples (share of all) | Contraction rate | Hedge or filler rate |")
    print("|---|---|---|---|---|---|---|")
    print(measures("Real patient turns (all)", real))
    print(measures("Real patient turns (800 sampled)", random.sample(real, 800)))
    print(measures("Benchmark: T1-T3 openings", openings))
    print(measures("Benchmark: T5 patient turns", turns))
    print(f"\nDistinct patient turns in T5: {len({re.sub(chr(92) + 'd+', '#', t) for t in turns})} shapes over {len(turns)} turns.")


if __name__ == "__main__":
    main()
