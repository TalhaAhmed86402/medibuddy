"""The hospital index: REAL institutions with a SYNTHETIC overlay, plus background notices.

Since v1.3.0 every institution is real: the 79,075 hospitals and clinics of the National Medical Center OpenAPI
(data/source/kr_hospitals.jsonl.gz, imported by scripts/import_kr_hospitals.py from the team's hospital database), with
their real id (hpid), name, type, address, coordinates, phone, opening hours per weekday and public holiday, lunch
break (when the record states it), emergency room and specialties.  The 47 tertiary hospitals are the 5th designation.
What the real data does not have is synthetic and drawn per hospital from the split's seed (`overlay`): languages,
interpreter service, rating, price level, female doctor, walk-in, last_verified, and the English blurb.  Dated notices
(closures, hour changes, suspended departments) are synthetic too.  Deterministic given the seed."""
from __future__ import annotations

import datetime as dt
import random

import gzip
import hashlib
import json
import math
import os
import re
from functools import lru_cache

from medibuddy_bench.common import iso
from medibuddy_bench.knowledge import (CHILDREN_NAME_WORDS, DISTRICTS, LANGUAGES, NO_OUTPATIENT_TYPES, SOURCE_DIR,
                                       SPECIALIST_NAME_WORDS, SPECIALTIES, SPECIALTY_CODES, TYPE_SPECIALTY)
from medibuddy_bench.romanize import romanize

_DISTRICT_WEIGHT = {"Gangnam": 4, "Seocho": 3, "Songpa": 3, "Mapo": 3, "Jongno": 3, "Yeongdeungpo": 3, "Yongsan": 2,
                    "Suwon-Jangan": 2, "Suwon-Gwonseon": 2, "Suwon-Paldal": 2, "Suwon-Yeongtong": 2,
                    "Seongnam-Bundang": 3, "Busan-Haeundae": 2, "Incheon-Namdong": 2}
_SPEC_W = {"internal_medicine": 3, "family_medicine": 2, "ent": 2, "dermatology": 2, "orthopedics": 2,
           "pediatrics": 2, "obgyn": 1, "dentistry": 3, "ophthalmology": 1.5, "urology": 1,
           "neurology": 1, "psychiatry": 1}
# Language model, calibrated on the KHIDI open list of foreign-patient-friendly hospitals (239 portal hospitals):
# English 92.9%, Chinese 65.3%, Russian 59.4%, Japanese 40.2%, Mongolian 35.6%, Vietnamese 17.2%, Arabic 12.6%;
# languages named per hospital {1:28, 2:54, 3:72, 4:36, 5:24, 6:19, 7:6}.  Thai and Uzbek are absent from that
# list, so their weights below are ASSUMED (documented in docs/DATA_CARD.md).
# Two populations: "international-oriented" hospitals (like the KHIDI list) and ordinary ones.
_INTL_SHARE = {"clinic": .10, "hospital": .25, "general_hospital": .55, "tertiary": .90}
_INTL_NLANG = {1: 28, 2: 54, 3: 72, 4: 36, 5: 24, 6: 19, 7: 6}
_INTL_LANG_W = {"en": .93, "zh": .65, "ru": .59, "ja": .40, "mn": .36, "vi": .17, "ar": .13, "th": .10, "uz": .08}
_ORD_LANG_P = {"clinic": {"en": .15, "zh": .04, "ja": .03, "vi": .04, "ru": .02, "mn": .02, "ar": .005, "th": .01, "uz": .01},
               "hospital": {"en": .30, "zh": .08, "ja": .06, "vi": .07, "ru": .04, "mn": .04, "ar": .01, "th": .02, "uz": .02},
               "general_hospital": {"en": .55, "zh": .15, "ja": .10, "vi": .10, "ru": .06, "mn": .06, "ar": .02, "th": .03, "uz": .03},
               "tertiary": {"en": .80, "zh": .30, "ja": .20, "vi": .15, "ru": .10, "mn": .10, "ar": .05, "th": .05, "uz": .05}}
# Neighbourhood clusters of resident communities raise the odds of the matching language (multiplier).
_DISTRICT_LANG_BOOST = {
    "Yongsan": {"en": 1.4, "ar": 3}, "Dongdaemun": {"ru": 3, "mn": 3, "uz": 3}, "Gwangjin": {"zh": 2.5},
    "Guro": {"zh": 3}, "Geumcheon": {"zh": 2.5, "uz": 2}, "Yeongdeungpo": {"zh": 2.5}, "Jung": {"mn": 2, "ru": 2},
    "Ansan-Danwon": {"uz": 4, "ru": 3, "vi": 3, "zh": 2.5, "th": 2}, "Incheon-Namdong": {"vi": 2.5, "zh": 2.5, "ru": 2},
    "Incheon-Yeonsu": {"en": 1.4, "zh": 2}, "Bucheon-Wonmi": {"vi": 2.5, "zh": 2}, "Daegu-Jung": {"uz": 2, "vi": 2},
    "Busan-Haeundae": {"ru": 2.5, "ja": 2}, "Seongnam-Jungwon": {"vi": 2, "uz": 2}, "Gangnam": {"en": 1.3, "ja": 1.5, "zh": 1.3},
}


def _pick_languages(rng: random.Random, tier: str, district: str) -> list[str]:
    boost = _DISTRICT_LANG_BOOST.get(district, {})
    if rng.random() < _INTL_SHARE[tier]:
        k = rng.choices(list(_INTL_NLANG), weights=list(_INTL_NLANG.values()), k=1)[0]
        pool = {l: w * boost.get(l, 1) for l, w in _INTL_LANG_W.items()}
        chosen: list[str] = []
        while len(chosen) < k:
            l = _weighted(rng, pool)
            chosen.append(l)
            pool.pop(l)
        return [l for l in LANGUAGES if l in chosen]
    p = _ORD_LANG_P[tier]
    return [l for l in LANGUAGES if rng.random() < min(.95, p[l] * boost.get(l, 1))]


_INTERP_P = {"clinic": .06, "hospital": .18, "general_hospital": .5, "tertiary": .9}


def _weighted(rng: random.Random, items: dict):
    keys = list(items)
    return rng.choices(keys, weights=[items[k] for k in keys], k=1)[0]


# ---------------------------------------------------------------- the real index (v1.3.0)
SOURCE_FILE = os.path.join(SOURCE_DIR, "kr_hospitals.jsonl.gz")
OVERLAY_VERSION = "1.3.0"      # bump when overlay() changes, so the world hash in the manifest changes too
_PREFIX = re.compile(r"^(?:의료법인|재단법인|사회복지법인|학교법인|사단법인)\s*(?:\S+재단|\S+의료재단|\S+법인)?\s*")
# Korean name parts -> English (longest first).  Everything else is romanized (medibuddy_bench/romanize.py).
_NAME_WORDS = sorted([
    ("대학교병원", "University Hospital"), ("대학병원", "University Hospital"), ("종합병원", "General Hospital"),
    ("치과병원", "Dental Hospital"), ("치과의원", "Dental Clinic"), ("한방병원", "Korean Medicine Hospital"),
    ("한의원", "Korean Medicine Clinic"), ("요양병원", "Care Hospital"), ("병원", "Hospital"), ("의원", "Clinic"),
    ("보건지소", "Health Subcenter"), ("보건소", "Public Health Center"), ("보건진료소", "Health Post"),
    ("의료원", "Medical Center"), ("의료센터", "Medical Center"), ("센터", "Center"), ("대학교", "University"),
    ("의과대학", "College of Medicine"), ("부속", "Affiliated"), ("부설", "Affiliated"), ("국립", "National"),
    ("이비인후과", "ENT"), ("정형외과", "Orthopedics"), ("신경외과", "Neurosurgery"), ("성형외과", "Plastic Surgery"),
    ("흉부외과", "Thoracic Surgery"), ("소아청소년과", "Pediatrics"), ("소아과", "Pediatrics"), ("어린이", "Children's"),
    ("산부인과", "OB-GYN"), ("비뇨의학과", "Urology"), ("비뇨기과", "Urology"), ("정신건강의학과", "Psychiatry"),
    ("가정의학과", "Family Medicine"), ("재활의학과", "Rehabilitation"), ("마취통증의학과", "Pain Medicine"),
    ("통증의학과", "Pain Medicine"), ("영상의학과", "Radiology"), ("피부과", "Dermatology"), ("내과", "Internal Medicine"),
    ("안과", "Eye"), ("외과", "Surgery"), ("신경과", "Neurology"), ("치과", "Dental"), ("한의", "Korean Medicine"),
    ("여성", "Women's"), ("365", "365"),
], key=lambda kv: -len(kv[0]))
_DROP_TYPES_FOR_TIER = {"종합병원": "general_hospital", "병원": "hospital", "치과병원": "hospital", "한방병원": "hospital",
                        "요양병원": "hospital"}


def english_name(name_ko: str) -> str:
    """English display name: known name parts translated, the rest romanized.

    >>> english_name("연세패밀리의원"), english_name("굿모닝이비인후과의원"), english_name("강남365치과의원")
    ('Yeonsepaemilli Clinic', 'Gunmoning ENT Clinic', 'Gangnam 365 Dental Clinic')
    >>> english_name("의료법인 세양의료재단 신안병원"), english_name("고려대학교의과대학부속구로병원")
    ('Sinan Hospital', 'Goryeo University College of Medicine Affiliated Guro Hospital')
    """
    name = _PREFIX.sub("", name_ko.strip()) or name_ko
    out: list[str] = []
    run = ""
    i = 0
    while i < len(name):
        for ko, en in _NAME_WORDS:
            if name.startswith(ko, i):
                if run.strip():
                    out.append(romanize(run.strip()))
                run = ""
                out.append(en)
                i += len(ko)
                break
        else:
            ch = name[i]
            if ch in "()（）·,.-":
                run += " "
            else:
                run += ch
            i += 1
    if run.strip():
        out.append(romanize(run.strip()))
    words = " ".join(" ".join(out).split())
    return words.replace("( ", "(").replace(" )", ")")


def tier_of(rec: dict) -> str:
    if rec["tertiary"]:
        return "tertiary"
    return _DROP_TYPES_FOR_TIER.get(rec["type_ko"], "clinic")


def specialties_of(rec: dict) -> list[str]:
    codes = set(rec["codes"])
    out = {k for k, v in SPECIALTY_CODES.items() if codes & v}
    if rec["type_ko"] in TYPE_SPECIALTY:
        out.add(TYPE_SPECIALTY[rec["type_ko"]])
    return sorted(out)


def _u01(key: str) -> float:
    return int(hashlib.md5(key.encode("utf-8")).hexdigest()[:12], 16) / float(16 ** 12)


def _tri(u: float, a: float, b: float, c: float) -> float:
    f = (c - a) / (b - a)
    return a + math.sqrt(u * (b - a) * (c - a)) if u < f else b - math.sqrt((1 - u) * (b - a) * (b - c))


def nonpay_prices(rec: dict, specs: list[str]) -> dict:
    """Synthetic non-covered prices in won, the team's rule (spec 3.5; generator/common.py nonpay_prices): a fixed
    pseudo-random number from the hospital id, so the same hospital always has the same prices.

    flu_shot: internal-medicine/family/ENT institutions and every hospital or general hospital, 90% offer it,
    18,000-45,000 won (mode 30,000); medical_certificate: every institution but dental and Korean medicine ones,
    10,000 / 15,000 / 20,000 won (60/15/25%); shockwave: orthopedics-and-pain institutions and hospitals, 70% offer it,
    30,000-175,000 won (mode 70,000)."""
    hid = rec["id"]
    hospital_level = rec["type_ko"] in ("병원", "종합병원")
    out = {}
    if (set(specs) & {"internal_medicine", "family_medicine", "ent"} or hospital_level) and _u01(hid + "flu?") < 0.9:
        out["flu_shot"] = round(_tri(_u01(hid + "flu"), 18, 45, 30)) * 1000
    if rec["type_ko"] not in ("치과의원", "치과병원", "한의원", "한방병원"):
        u = _u01(hid + "cert")
        out["medical_certificate"] = 10000 if u < 0.6 else (15000 if u < 0.75 else 20000)
    if ("orthopedics" in specs or hospital_level) and _u01(hid + "eswt?") < 0.7:
        out["shockwave"] = round(_tri(_u01(hid + "eswt"), 30, 175, 70)) * 1000
    return out


@lru_cache(maxsize=1)
def source_records() -> tuple:
    """Every real institution (79,075), converted to the world's schema.  Real fields only; see overlay()."""
    out = []
    with gzip.open(SOURCE_FILE, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["lat"] is None or not r["district"]:
                continue                                  # 4 institutions without coordinates
            specs = specialties_of(r)
            tier = tier_of(r)
            hours = {d: r["hours"][d] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
            out.append({
                "id": r["id"], "name_ko": r["name_ko"], "name_en": f"{english_name(r['name_ko'])} ({r['district']})",
                "tier": tier, "type": r["type"], "type_ko": r["type_ko"], "specialties": specs,
                "specialist_in": [k for k, words in SPECIALIST_NAME_WORDS.items()
                                  if r["type_ko"] == "의원" and any(w in r["name_ko"] for w in words) and k in specs],
                "children_only": any(w in r["name_ko"] for w in CHILDREN_NAME_WORDS),
                "outpatient": r["type_ko"] not in NO_OUTPATIENT_TYPES,
                "district": r["district"], "region": DISTRICTS[r["district"]][3], "lat": r["lat"], "lon": r["lon"],
                "address_ko": r["address_ko"], "phone": r["phone"], "directions_ko": r["directions_ko"],
                "remarks_ko": r["remarks_ko"][:300], "hours": hours, "holiday_hours": r["hours"]["hol"],
                "open_on_holidays": bool(r["hours"]["hol"]), "lunch": r["lunch"], "er_24h": r["er"],
                "er_class_ko": r["er_class_ko"], "prices": nonpay_prices(r, specs),
            })
    return tuple(out)


@lru_cache(maxsize=1)
def source_sha256() -> str:
    with open(SOURCE_FILE, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def overlay(h: dict, seed: int) -> dict:
    """The SYNTHETIC attributes the real index does not have, drawn from a stream fixed by (seed, hospital id):
    languages and interpreter service (calibrated on the KHIDI list, see above), rating, price level, female doctor,
    walk-in, the date the record was last verified, and the English blurb."""
    rng = random.Random(int(hashlib.md5(f"{seed}:{h['id']}".encode()).hexdigest()[:16], 16))
    tier = h["tier"]
    langs = _pick_languages(rng, tier, h["district"])
    rating = max(2.0, min(5.0, rng.gauss(4.2 if tier == "tertiary" else 3.8, .55)))
    price = {"clinic": rng.choices([1, 2, 3], weights=[60, 35, 5])[0], "hospital": 2,
             "general_hospital": rng.choice([2, 3]), "tertiary": 3}[tier]
    recent = rng.random() < .8
    lv = (dt.date(2026, 8, 1) + dt.timedelta(days=rng.randint(0, 85))) if recent else \
        (dt.date(2025, 1, 1) + dt.timedelta(days=rng.randint(0, 330)))
    out = {"languages": langs, "interpreter_service": rng.random() < _INTERP_P[tier],
           "walk_in": tier in ("clinic", "hospital") or rng.random() < .3, "price_level": price,
           "rating": round(rating, 1),
           "female_doctor": rng.random() < {"clinic": .4, "hospital": .7, "general_hospital": .9, "tertiary": .95}[tier],
           "last_verified": iso(lv)}
    out["blurb"] = _blurb({**h, **out})
    return out


def build_hospitals(seed: int) -> list[dict]:
    """The world's hospitals: every real institution with its synthetic overlay for this split's seed."""
    return [{**h, **overlay(h, seed)} for h in source_records()]


def gen_hospitals(rng: random.Random, n: int = 0) -> list[dict]:
    """Kept for callers of v1.2: the world is no longer sampled; `rng` only picks the overlay seed."""
    return build_hospitals(rng.randrange(2 ** 31))


def _blurb(h: dict) -> str:
    specs = ", ".join(SPECIALTIES[s][1].split(" (")[0] for s in h["specialties"][:4])
    parts = [f"{h['name_en']}: {specs}."]
    if len(h["languages"]) >= 2 or h["interpreter_service"]:
        parts.append("Foreign-language support available.")
    if h["er_24h"]:
        parts.append("24-hour emergency room.")
    return " ".join(parts)


def gen_background_notices(rng: random.Random, hospitals: list[dict], start: dt.date, end: dt.date) -> list[dict]:
    """Notices unrelated to any particular scenario + permanent hour changes for stale records."""
    notices: list[dict] = []

    def add(hid, typ, s, e, detail, **kw):
        notices.append({"id": f"N{len(notices) + 1:05d}", "hospital_id": hid, "type": typ,
                        "start": iso(s), "end": iso(e) if e else None, "detail_en": detail,
                        "detail_ko": kw.pop("detail_ko", ""), **kw})

    span = (end - start).days
    for h in hospitals:
        stale = h["last_verified"] < "2026-01-01"
        if stale and rng.random() < .55:
            if h["hours"]["sat"] and rng.random() < .6:
                add(h["id"], "hours_change", dt.date(2026, 3, 1), None,
                    "Saturday outpatient service has ended; weekday hours unchanged.",
                    hours={"sat": None}, detail_ko="토요일 진료 종료")
            else:
                days = {d: h["hours"][d] for d in ("mon", "tue", "wed", "thu", "fri")
                        if h["hours"].get(d) and h["hours"][d][0] < "15:00" and h["hours"][d][1] > "16:00"}
                if days:
                    add(h["id"], "hours_change", dt.date(2026, 3, 1), None,
                        "Weekday closing time moved to 16:00.",
                        hours={d: [v[0], "16:00"] for d, v in days.items()},
                        detail_ko="평일 진료 종료 시간 16시로 변경")
        if rng.random() < .06:
            s = start + dt.timedelta(days=rng.randint(0, span - 6))
            add(h["id"], "closure", s, s + dt.timedelta(days=rng.randint(0, 4)),
                rng.choice(["Closed for renovation.", "Closed for staff training.",
                            "Temporarily closed (building maintenance)."]), detail_ko="임시 휴진")
        if rng.random() < .03 and len(h["specialties"]) > 1:
            s = start + dt.timedelta(days=rng.randint(0, span - 20))
            add(h["id"], "dept_suspension", s, s + dt.timedelta(days=rng.randint(7, 20)),
                "Department temporarily suspended.", specialties=[rng.choice(h["specialties"])],
                detail_ko="진료과 일시 중단")
    return notices


def add_closure(notices: list[dict], hospital_id: str, date: dt.date, detail: str, days: int = 0) -> dict:
    n = {"id": f"N{len(notices) + 1:05d}", "hospital_id": hospital_id, "type": "closure",
         "start": iso(date), "end": iso(date + dt.timedelta(days=days)), "detail_en": detail,
         "detail_ko": "임시 휴진"}
    notices.append(n)
    return n
