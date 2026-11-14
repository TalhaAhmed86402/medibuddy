#!/usr/bin/env python3
"""Automatic sanity checks on the Korean text of the benchmark (optional; needs `pip install kiwipiepy`).

  python scripts/korean_lint.py                       # phrasebook + every Korean doctor turn in data/dev

What it checks: every sentence parses into known words, ends in a polite speech level (-yo / -seyo / -hamnida forms) and never in plain
or impolite speech. What it does NOT check: whether a phrase is natural, idiomatic or medically appropriate. Native-speaker review
(docs/REVIEW_GUIDE.md) remains necessary; this only removes the cheap errors before a reviewer's time is spent."""
import argparse
import collections
import csv
import json
import os
import re

POLITE_ENDINGS = {"어요", "아요", "세요", "으세요", "ᆸ니다", "습니다", "ᆯ게요", "ᆯ까요", "ᆫ가요", "나요", "죠", "지요", "네요", "ᆫ데요", "는데요", "고요", "시고요", "으니까요", "니까", "ᆸ니까", "습니까", "여요", "에요", "예요", "이에요", "해요"}


def check(kiwi, text):
    problems = []
    for sent in kiwi.split_into_sents(text):
        toks = kiwi.tokenize(sent.text)
        if any(t.tag in ("UN", "W_HASHTAG") for t in toks):
            problems.append(("unknown word", sent.text))
        ends = [t for t in toks if t.tag == "EF"]
        if ends and ends[-1].form not in POLITE_ENDINGS:
            problems.append((f"unexpected sentence ending {ends[-1].form!r}", sent.text))
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phrasebook", default="data/review/korean_phrasebook.csv")
    ap.add_argument("--data", default="data/dev")
    a = ap.parse_args()
    from kiwipiepy import Kiwi
    kiwi = Kiwi()
    texts = set()
    with open(a.phrasebook, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if re.search(r"[가-힣]", r["source_text"]):
                texts.add(r["source_text"])
            if re.search(r"[가-힣]", r["reference_translation"]):
                texts.add(r["reference_translation"])
    for task in ("T5", "T6"):
        with open(os.path.join(a.data, f"{task}.jsonl"), encoding="utf-8") as f:
            for line in f:
                for tu in json.loads(line)["public"].get("turns", []):
                    if tu["lang"] == "ko":
                        texts.add(tu["text"])
    found = collections.Counter()
    examples = []
    for t in sorted(texts):
        for kind, sent in check(kiwi, t):
            found[kind] += 1
            examples.append((kind, sent))
    print(f"Checked {len(texts)} distinct Korean strings.")
    print("Problems found:", dict(found) if found else "none")
    for kind, sent in examples[:30]:
        print(f"  {kind}: {sent}")


if __name__ == "__main__":
    main()
