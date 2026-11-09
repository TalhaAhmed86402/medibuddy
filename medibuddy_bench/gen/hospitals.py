"""Synthetic hospital index + background notices.

Structure follows the fields a real open-data index (HIRA hospital/pharmacy status + evaluation
datasets) exposes: type, specialties, location, hours, evaluation grade.  Values are random,
names are fictional.  Deterministic given the RNG."""
from __future__ import annotations

import datetime as dt
import random

from medibuddy_bench.common import iso
from medibuddy_bench.knowledge import DISTRICTS, LANGUAGES, NAME_STEMS, SPECIALTIES

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


def gen_hospitals(rng: random.Random, n: int = 1200) -> list[dict]:
    names_seen: set[str] = set()
    hospitals = []
    tiers = rng.choices(["clinic", "hospital", "general_hospital", "tertiary"], weights=[68, 22, 7, 3], k=n)
    # make sure each tier has a minimum presence
    for i, t in enumerate(["tertiary"] * 12 + ["general_hospital"] * 20):
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
        langs = _pick_languages(rng, tier, district)
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
