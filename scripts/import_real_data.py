"""Summarise real hospital files from data/real so the synthetic world can be calibrated.  Read-only: never edits the world.

Usage:  python3 scripts/import_real_data.py data/real            (run from the medibuddy-bench folder)
Writes: data/real/derived/<name>.json  (the numbers used for calibration, so they can be audited)

Handled files
  KHIDI "외국인 자주 찾는 병원 언어종류"  (data.go.kr 15152195)  -> khidi_languages()      VERIFIED on the real file (2026-10-30)
  anything else with a type/language-like column                  -> generic_summary()     guesses columns by keyword

KHIDI file facts (from the real file): cp949-encoded, 2,882 rows = 239 hospitals x their languages x 4 translations of the
language NAME (the Medical Korea site shows each page in EN / JP / RU / CN, so "ENGLISH", "英語", "Английский", "日本語" are the
same language).  We map every spelling to one code and count UNIQUE hospitals.  The Russian word "гитара" ("guitar") is a
mistranslation of "ETC" in the source and is mapped to 'other'.
"""
import csv
import glob
import json
import os
import sys
from collections import Counter, defaultdict

CANON = {
    "en": ["ENGLISH", "英語", "АНГЛИЙСКИЙ"], "ja": ["JAPANESE", "日本語", "ЯПОНСКИЙ"],
    "zh": ["CHINESE", "中語", "中文", "КИТАЙСКИЙ"], "ru": ["RUSSIAN", "ロシア語", "俄語", "РУССКИЙ"],
    "mn": ["MONGOLIAN", "モンゴル語", "蒙古語", "МОНГОЛЬСКИЙ"], "vi": ["VIETNAMESE", "ベトナム語", "越南語", "ВЬЕТНАМСКИЙ"],
    "ar": ["ARABIC", "アラビア語", "阿拉伯語", "АРАБСКИЙ"], "other": ["ETC", "その他", "其他", "ГИТАРА"],
}
SPELLING = {s.upper(): code for code, names in CANON.items() for s in names}
TIER_KEYS = ["종별", "type", "category"]
LANG_COLS = ["언어", "외국어", "language", "foreign"]


def read(path):
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except (UnicodeDecodeError, csv.Error):
            continue
    return []


def khidi_languages(rows):
    H, L = "자주찾는병원번호", "언어"
    per_hosp = defaultdict(set)
    unknown = Counter()
    for r in rows:
        code = SPELLING.get((r[L] or "").strip().upper())
        if code:
            per_hosp[r[H]].add(code)
        else:
            unknown[r[L]] += 1
    n = len(per_hosp)
    share = {c: round(sum(1 for s in per_hosp.values() if c in s) / n, 3)
             for c in CANON if c != "other"}
    named = Counter(len(s - {"other"}) for s in per_hosp.values())
    mean = sum(k * v for k, v in named.items()) / n
    out = {"source": "KHIDI 외국인 자주 찾는 병원 언어종류 (data.go.kr 15152195)", "hospitals": n,
           "share_of_hospitals_by_language": share, "named_languages_per_hospital": dict(sorted(named.items())),
           "mean_named_languages": round(mean, 2), "english_only": sum(1 for s in per_hosp.values() if s - {"other"} == {"en"}),
           "no_english": sum(1 for s in per_hosp.values() if "en" not in s), "unmapped_values": dict(unknown),
           "caveat": "Only hospitals listed on the Medical Korea portal (international-patient oriented); NOT all Korean "
                     "hospitals. Thai and Uzbek are not language options in this file."}
    return out


def generic_summary(rows):
    cols = list(rows[0].keys())
    print("columns:", cols)
    tcol = next((c for c in cols if any(k in c.lower() for k in TIER_KEYS)), None)
    if tcol:
        print("by", tcol, Counter(r[tcol] for r in rows).most_common(8))
    for c in [c for c in cols if any(k in c.lower() for k in LANG_COLS)]:
        filled = sum(1 for r in rows if (r[c] or "").strip())
        print(f"{c}: {filled}/{len(rows)} filled; top values:", Counter(r[c] for r in rows).most_common(6))


def main(d):
    files = sorted(glob.glob(os.path.join(d, "*.csv")))
    if not files:
        print("no csv files in", d)
        return
    os.makedirs(os.path.join(d, "derived"), exist_ok=True)
    for p in files:
        rows = read(p)
        print(f"\n== {os.path.basename(p)}: {len(rows)} rows")
        if not rows:
            continue
        if {"자주찾는병원번호", "언어", "사이트언어"} <= set(rows[0]):
            res = khidi_languages(rows)
            print(json.dumps(res, ensure_ascii=False, indent=2))
            with open(os.path.join(d, "derived", "khidi_languages.json"), "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False, indent=2)
        else:
            generic_summary(rows)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/real")
