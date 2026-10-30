"""Synthetic hospital index + background notices.

Structure follows the fields a real open-data index (HIRA hospital/pharmacy status + evaluation
datasets) exposes: type, specialties, location, hours, evaluation grade.  Values are random,
names are fictional.  Deterministic given the RNG."""
from __future__ import annotations

import datetime as dt
import random

from medibuddy_bench.common import iso
from medibuddy_bench.knowledge import DISTRICTS, LANGUAGES, NAME_STEMS, SPECIALTIES

_DISTRICT_WEIGHT = {"Gangnam": 3, "Seocho": 2, "Songpa": 2, "Mapo": 2, "Jongno": 2, "Yeongdeungpo": 2,
                    "Suwon-Jangan": 2, "Suwon-Gwonseon": 2, "Suwon-Paldal": 2, "Suwon-Yeongtong": 2}
_SPEC_W = {"internal_medicine": 3, "family_medicine": 2, "ent": 2, "dermatology": 2, "orthopedics": 2,
           "pediatrics": 2, "obgyn": 1, "dentistry": 3, "ophthalmology": 1.5, "urology": 1,
           "neurology": 1, "psychiatry": 1}
_LANG_P = {  # tier -> language probabilities
    "clinic": {"en": .22, "zh": .08, "ja": .06, "vi": .06, "ru": .04, "mn": .04},
    "hospital": {"en": .35, "zh": .15, "ja": .12, "vi": .10, "ru": .08, "mn": .08},
    "general_hospital": {"en": .70, "zh": .40, "ja": .30, "vi": .25, "ru": .20, "mn": .20},
    "tertiary": {"en": .95, "zh": .75, "ja": .70, "vi": .55, "ru": .50, "mn": .45},
}
_INTERP_P = {"clinic": .06, "hospital": .18, "general_hospital": .5, "tertiary": .9}


def _weighted(rng: random.Random, items: dict):
    keys = list(items)
    return rng.choices(keys, weights=[items[k] for k in keys], k=1)[0]


def _hours(rng: random.Random, tier: str):
    """Return (weekly_hours dict, lunch)."""
    if tier == "clinic":
        o, c = rng.choices([("09:00", "18:00"), ("09:30", "18:30"), ("10:00", "19:00"), ("09:00", "21:00"),
                            ("08:30", "17:30")], weights=[50, 20, 10, 15, 5])[0]
        lunch = ["13:00", "14:00"] if rng.random() < .7 else None
        sat = rng.choices([["09:00", "13:00"], ["09:00", "15:00"], None], weights=[55, 10, 35])[0]
        sun = ["09:00", "13:00"] if rng.random() < .08 else None
    else:
        o, c = "08:30", "17:30"
        lunch = ["12:30", "13:30"] if rng.random() < .6 else None
        sat = ["08:30", "12:30"] if rng.random() < .7 else None
        sun = None
    wk = {d: [o, c] for d in ("mon", "tue", "wed", "thu", "fri")}
    wk["sat"], wk["sun"] = sat, sun
    return wk, lunch


def gen_hospitals(rng: random.Random, n: int = 320) -> list[dict]:
    names_seen: set[str] = set()
    hospitals = []
    tiers = rng.choices(["clinic", "hospital", "general_hospital", "tertiary"], weights=[62, 24, 9, 5], k=n)
    # make sure each tier has a minimum presence
    for i, t in enumerate(["tertiary"] * 10 + ["general_hospital"] * 16):
        tiers[i] = t
    rng.shuffle(tiers)
    for i, tier in enumerate(tiers):
        district = _weighted(rng, {d: _DISTRICT_WEIGHT.get(d, 1) for d in DISTRICTS})
        dko, lat, lon, region = DISTRICTS[district]
        if tier == "clinic":
            specs = [_weighted(rng, _SPEC_W)]
            if rng.random() < .1:
                specs.append(rng.choice([s for s in SPECIALTIES if s not in specs]))
        elif tier == "hospital":
            specs = list({"internal_medicine" if rng.random() < .6 else "orthopedics",
                          *rng.sample(list(SPECIALTIES), rng.randint(2, 4))})
        elif tier == "general_hospital":
            specs = rng.sample(list(SPECIALTIES), rng.randint(8, 10))
            specs = list({*specs, "internal_medicine"})
        else:
            specs = list(SPECIALTIES)
        specs.sort()
        stem_ko, stem_en = rng.choice(NAME_STEMS)
        if tier == "clinic":
            sko, sen = SPECIALTIES[specs[0]]
            sen = sen.split(" (")[0]
            name_ko, name_en = f"{stem_ko}{sko}의원", f"{stem_en} {sen} Clinic"
        elif tier == "hospital":
            name_ko, name_en = f"{stem_ko}병원", f"{stem_en} Hospital"
        elif tier == "general_hospital":
            name_ko, name_en = f"{stem_ko}종합병원", f"{stem_en} General Hospital"
        else:
            name_ko, name_en = f"{stem_ko}대학교병원", f"{stem_en} University Hospital"
        name_en = f"{name_en} ({district.replace('-', ' ')})"
        k = 2
        base_en = name_en
        while name_en in names_seen:
            name_en = f"{base_en} No.{k}"
            k += 1
        names_seen.add(name_en)
        langs = [l for l in LANGUAGES if rng.random() < _LANG_P[tier][l]]
        hours, lunch = _hours(rng, tier)
        rating = max(2.0, min(5.0, rng.gauss(4.2 if tier == "tertiary" else 3.8, .55)))
        price = {"clinic": rng.choices([1, 2, 3], weights=[60, 35, 5])[0], "hospital": 2,
                 "general_hospital": rng.choice([2, 3]), "tertiary": 3}[tier]
        recent = rng.random() < .8
        lv = (dt.date(2026, 8, 1) + dt.timedelta(days=rng.randint(0, 85))) if recent else \
            (dt.date(2025, 1, 1) + dt.timedelta(days=rng.randint(0, 330)))
        h = {
            "id": f"H{i + 1:04d}", "name_ko": name_ko, "name_en": name_en, "tier": tier,
            "specialties": specs, "district": district, "region": region,
            "lat": round(lat + rng.uniform(-.008, .008), 5), "lon": round(lon + rng.uniform(-.008, .008), 5),
            "languages": langs, "interpreter_service": rng.random() < _INTERP_P[tier],
            "hours": hours, "lunch": lunch,
            "open_on_holidays": tier == "clinic" and rng.random() < .08,
            "er_24h": tier in ("general_hospital", "tertiary"),
            "walk_in": tier in ("clinic", "hospital") or rng.random() < .3,
            "price_level": price, "rating": round(rating, 1),
            "female_doctor": rng.random() < {"clinic": .4, "hospital": .7, "general_hospital": .9, "tertiary": .95}[tier],
            "last_verified": iso(lv),
        }
        h["blurb"] = _blurb(h)
        hospitals.append(h)
    return hospitals


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
                o = h["hours"]["mon"][0]
                add(h["id"], "hours_change", dt.date(2026, 3, 1), None,
                    "Weekday closing time moved to 16:00.",
                    hours={d: [o, "16:00"] for d in ("mon", "tue", "wed", "thu", "fri")},
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
