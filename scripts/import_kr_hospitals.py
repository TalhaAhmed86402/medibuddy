"""Import the team's real data into data/source/ (run once; the outputs are committed, the inputs are not).

Inputs (from the team, 2026-11-14):
  HOSPITAL_DB  hospitals_subjects_filtered.json  79,075 Korean medical institutions from the National Medical Center
               "nationwide hospital and clinic search" OpenAPI (data.go.kr 15000736), specialties filtered to each
               institution's representative group (team's hospital_DB package, README and metadata there)
  BENCH_DIR    MediBuddy_benchmark_2026-11-14/   the team's clinic-choice benchmark (tertiary list, campuses and
               schedule places, symptom table, travel times, items)

Outputs (data/source/):
  kr_hospitals.jsonl.gz   one real institution per line, real fields only (see FIELDS below)
  districts.json          every city/district (시군구) as a district: English key, Korean name, region, centroid
  tertiary.json           the 47 tertiary hospitals of the 5th designation (2024-2026), matched by hpid
  places.json             66 origins: 30 university campuses and 36 schedule places, with their district
  travel.csv.gz           origin_id, hpid, min, source (kakao = measured 2026-11-14, mock = straight-line estimate)
  symptoms.json           the team's 31 mild symptoms with allowed department groups and evidence
  t9_pool.jsonl.gz        the team's 1,165 clinic-choice items (agent view + gold), the pool task T9 is drawn from
  SOURCES.md              provenance and licence

Usage:  python3 scripts/import_kr_hospitals.py <hospitals_subjects_filtered.json> <MediBuddy_benchmark dir> [out_dir]
Deterministic: the same inputs give byte-identical outputs."""
from __future__ import annotations

import csv
import gzip
import io
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from medibuddy_bench.romanize import romanize  # noqa: E402

csv.field_size_limit(10 ** 9)

TYPE_EN = {"종합병원": "general hospital", "병원": "hospital", "의원": "clinic", "요양병원": "long-term care hospital",
           "한방병원": "Korean medicine hospital", "한의원": "Korean medicine clinic", "기타": "other",
           "치과병원": "dental hospital", "치과의원": "dental clinic", "조산원": "midwifery clinic",
           "보건소": "public health center", "기타(구급차)": "ambulance service"}
PROVINCE = {  # Korean first address word -> (English region, short code used in district keys)
    "서울특별시": ("Seoul", ""), "부산광역시": ("Busan", "Busan"), "대구광역시": ("Daegu", "Daegu"),
    "인천광역시": ("Incheon", "Incheon"), "대전광역시": ("Daejeon", "Daejeon"), "울산광역시": ("Ulsan", "Ulsan"),
    "세종특별자치시": ("Sejong", ""), "경기도": ("Gyeonggi", ""), "강원특별자치도": ("Gangwon", ""),
    "충청북도": ("Chungbuk", ""), "충청남도": ("Chungnam", ""), "전북특별자치도": ("Jeonbuk", ""),
    "전남광주통합특별시": ("Jeonnam-Gwangju", ""), "경상북도": ("Gyeongbuk", ""), "경상남도": ("Gyeongnam", ""),
    "제주특별자치도": ("Jeju", ""),
}
# Gwangju's five districts are inside 전남광주통합특별시 in this data; key them like the other metropolitan cities.
GWANGJU_GU = {"동구", "서구", "남구", "북구", "광산구"}
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun", "hol"]
LUNCH = re.compile(r"점심[^0-9]{0,8}(\d{1,2})\s*[:시]\s*(\d{0,2})\s*분?\s*[~\-–]\s*(\d{1,2})\s*[:시]?\s*(\d{0,2})")


def hhmm(v: str):
    """'0900' -> '09:00'; '2400' -> '24:00'; invalid (2600, 2930, '') -> None.  Same rule as the team's generator."""
    v = (v or "").strip()
    if not v.isdigit() or len(v) < 3:
        return None
    h, m = int(v[:-2]), int(v[-2:])
    if h > 24 or m > 59 or (h == 24 and m):
        return None
    return f"{h:02d}:{m:02d}"


def lunch_break(text: str):
    """Real lunch break stated in the free text, e.g. '점심시간 12:30~14:00' or '점심 1시-2시' -> ['12:30', '14:00'].

    >>> lunch_break("점심시간 12시30분~2시까지"), lunch_break("평일 점심휴게 13시-14시"), lunch_break("연중무휴")
    (['12:30', '14:00'], ['13:00', '14:00'], None)
    """
    m = LUNCH.search(text or "")
    if not m:
        return None
    h1, m1, h2, m2 = int(m.group(1)), int(m.group(2) or 0), int(m.group(3)), int(m.group(4) or 0)
    h1 += 12 if h1 < 7 else 0
    h2 += 12 if h2 < 7 else 0
    a, b = h1 * 60 + m1, h2 * 60 + m2
    if not (11 * 60 <= a < b <= 15 * 60 + 30 and 30 <= b - a <= 150 and m1 < 60 and m2 < 60):
        return None
    return [f"{a // 60:02d}:{a % 60:02d}", f"{b // 60:02d}:{b % 60:02d}"]


def district_of(addr: str):
    """(province_ko, district_ko) from a road-name address, or None when the second word is not a district."""
    t = addr.split()
    if len(t) < 2:
        return None
    p = t[0]
    if p == "세종특별자치시":
        return p, "세종특별자치시"
    if len(t) > 2 and re.search(r"(시|군)$", t[1]) and re.search(r"구$", t[2]):
        return p, f"{t[1]} {t[2]}"
    if re.search(r"(시|군|구)$", t[1]):
        return p, t[1]
    return None


def strip_suffix(name: str) -> str:
    return re.sub(r"(특별자치시|특별자치도|광역시|특별시|시|군|구)$", "", name)


def district_key(prov: str, dko: str) -> str:
    region, code = PROVINCE[prov]
    if prov == "세종특별자치시":
        return "Sejong"
    parts = dko.split()
    if prov == "전남광주통합특별시" and dko in GWANGJU_GU:
        return "Gwangju-" + romanize(strip_suffix(dko))
    if code:                                   # metropolitan city: Busan-Haeundae
        return f"{code}-{romanize(strip_suffix(dko))}"
    if region == "Seoul":
        return romanize(strip_suffix(dko))
    if len(parts) == 2:                        # city with districts: Suwon-Jangan
        return f"{romanize(strip_suffix(parts[0]))}-{romanize(strip_suffix(parts[1]))}"
    base = romanize(strip_suffix(dko))
    return base + ("-gun" if dko.endswith("군") else "")


def haversine(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(x))


def main(db_path: str, bench: str, out: str) -> None:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from medibuddy_bench.knowledge import LEGACY_DISTRICTS     # the 47 names used since v1.0 keep their spelling
    metro = {"인천": "인천광역시", "부산": "부산광역시", "대구": "대구광역시", "대전": "대전광역시"}
    legacy_by_ko = {}
    for k, v in LEGACY_DISTRICTS.items():
        ko = v[0].split()
        if v[3] == "Seoul":
            legacy_by_ko[("서울특별시", v[0])] = k
        elif ko[0] in metro:
            legacy_by_ko[(metro[ko[0]], ko[1])] = k
        else:
            legacy_by_ko[("경기도", v[0])] = k
    rows = json.load(open(db_path, encoding="utf-8"))
    src = os.path.join(bench, "source", "data")
    tertiary = list(csv.DictReader(io.open(os.path.join(src, "tertiary_5th.csv"), encoding="utf-8-sig")))
    tert_ids = {r["hpid"] for r in tertiary}

    # ---- districts
    raw_d = {}
    for r in rows:
        d = district_of(r["dutyAddr"])
        if d:
            raw_d[r["hpid"]] = d
    counts = Counter(raw_d.values())
    keyed: dict[tuple, str] = {}
    used: dict[str, tuple] = {}
    for (p, dko), n in sorted(counts.items()):
        if n < 15 and p != "세종특별자치시":       # stray parses (road names); placed by coordinates below
            continue
        legacy = legacy_by_ko.get((p, dko))
        k = legacy or district_key(p, dko)
        if k in used and used[k] != (p, dko):
            k = f"{k} ({PROVINCE[p][0]})"
        used[k] = (p, dko)
        keyed[(p, dko)] = k
    pts = defaultdict(list)
    for r in rows:
        d = raw_d.get(r["hpid"])
        if d in keyed and r["wgs84Lat"]:
            pts[keyed[d]].append((float(r["wgs84Lat"]), float(r["wgs84Lon"])))
    districts = {}
    for k, (p, dko) in sorted(used.items()):
        la = [x for x, _ in pts[k]]
        lo = [y for _, y in pts[k]]
        la.sort()
        lo.sort()
        cen = (la[len(la) // 2], lo[len(lo) // 2]) if la else (0.0, 0.0)   # median: robust to stray coordinates
        if k in LEGACY_DISTRICTS:
            cen = (LEGACY_DISTRICTS[k][1], LEGACY_DISTRICTS[k][2])
        districts[k] = {"ko": dko if p in ("서울특별시", "세종특별자치시") else f"{p} {dko}", "short_ko": dko,
                        "region": PROVINCE[p][0], "lat": round(cen[0], 4), "lon": round(cen[1], 4),
                        "n_institutions": len(pts[k])}

    def nearest_district(lat, lon):
        return min(districts, key=lambda k: haversine((lat, lon), (districts[k]["lat"], districts[k]["lon"])))

    # ---- hospitals
    out_rows = []
    for r in rows:
        lat = float(r["wgs84Lat"]) if r["wgs84Lat"] else None
        lon = float(r["wgs84Lon"]) if r["wgs84Lon"] else None
        d = raw_d.get(r["hpid"])
        dk = keyed.get(d) if d else None
        if dk is None and lat is not None:
            dk = nearest_district(lat, lon)
        hours = {}
        for i, day in enumerate(DAYS, 1):
            s, c = hhmm(r[f"dutyTime{i}s"]), hhmm(r[f"dutyTime{i}c"])
            hours[day] = [s, c] if s and c and c > s else None
        text = "\n".join(x for x in (r["dutyEtc"], r["dutyInf"]) if x)
        out_rows.append({
            "id": r["hpid"], "name_ko": r["dutyName"], "type_ko": r["dutyDivNam"], "type": TYPE_EN[r["dutyDivNam"]],
            "tertiary": r["hpid"] in tert_ids, "er": r["dutyEryn"] == "1",
            "er_class_ko": r["dutyEmclsName"] if r["dutyEmcls"] != "G099" else "",
            "address_ko": r["dutyAddr"], "district": dk, "lat": lat, "lon": lon,
            "phone": r["dutyTel1"], "er_phone": r["dutyTel3"], "directions_ko": r["dutyMapimg"].strip(),
            "about_ko": r["dutyInf"].strip(), "remarks_ko": r["dutyEtc"].strip(),
            "hours": hours, "lunch": lunch_break(text),
            "codes": [c for c in r["filteredSubjectCodes"].split(",") if c],
            "collab_codes": [c for c in r["collabSubjectCodes"].split(",") if c],
        })
    out_rows.sort(key=lambda h: h["id"])
    os.makedirs(out, exist_ok=True)
    with gzip.GzipFile(os.path.join(out, "kr_hospitals.jsonl.gz"), "wb", mtime=0) as gz:
        for h in out_rows:
            gz.write((json.dumps(h, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    json.dump(districts, open(os.path.join(out, "districts.json"), "w", encoding="utf-8"), ensure_ascii=False,
              indent=0, sort_keys=True)
    json.dump([{"id": t["hpid"], "name_ko": t["dutyName"], "region_ko": t["region"]} for t in tertiary],
              open(os.path.join(out, "tertiary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)

    # ---- places (campuses and schedule places)
    places = []
    for p in csv.DictReader(io.open(os.path.join(src, "places.csv"), encoding="utf-8-sig")):
        lat, lon = float(p["lat"]), float(p["lon"])
        near = sorted((haversine((lat, lon), (h["lat"], h["lon"])), h["district"]) for h in out_rows
                      if h["lat"] is not None and abs(h["lat"] - lat) < .05 and abs(h["lon"] - lon) < .05)[:15]
        votes = Counter(d for _, d in near)
        dist = votes.most_common(1)[0][0] if votes else nearest_district(lat, lon)   # majority of the 15 nearest
        osm = [x.strip() for x in p.get("osm_display", "").split(",")]
        for k, v in districts.items():           # the OpenStreetMap address names the district: prefer it
            parts = v["short_ko"].split()
            if parts and all(x in osm for x in parts) and v["region"] == districts[dist]["region"]:
                dist = k
                break
        places.append({"id": p["id"], "kind": p["kind"], "name_ko": p["name"], "name_en": p["name_en"],
                       "lat": lat, "lon": lon, "district": dist})
    json.dump(places, open(os.path.join(out, "places.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)

    # ---- travel times: the package's table, with the measured/estimated flag from the build's hybrid table
    srcflag = {}
    for t in csv.DictReader(io.open(os.path.join(src, "travel.hybrid.csv"), encoding="utf-8-sig")):
        srcflag[(t["origin_id"], t["hpid"])] = t.get("source", "")
    trav = list(csv.DictReader(io.open(os.path.join(bench, "benchmark_full_1165", "resources", "travel.csv"),
                                       encoding="utf-8-sig")))
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["origin_id", "hpid", "min", "source"])
    for t in sorted(trav, key=lambda t: (t["origin_id"], t["hpid"])):
        w.writerow([t["origin_id"], t["hpid"], t["min"], srcflag.get((t["origin_id"], t["hpid"]), "mock")])
    with gzip.GzipFile(os.path.join(out, "travel.csv.gz"), "wb", mtime=0) as gz:
        gz.write(buf.getvalue().encode("utf-8"))

    # ---- T9 pool: the team's clinic-choice items (agent view + gold), all 1,165
    inst = {json.loads(l)["id"]: json.loads(l) for l in io.open(os.path.join(bench, "benchmark_full_1165", "instances.jsonl"),
                                                              encoding="utf-8") if l.strip()}
    pool = []
    for l in io.open(os.path.join(bench, "benchmark_full_1165", "hidden_specs.jsonl"), encoding="utf-8"):
        if not l.strip():
            continue
        g = json.loads(l)
        it = inst[g["id"]]
        public = {k: it[k] for k in ("profile", "history", "query", "ask_menu")}
        viol: dict[str, list[str]] = defaultdict(list)
        for hid, why in sorted(g.get("violations", {}).items()):
            viol[why].append(hid)
        origins = {it["query"]["current_place"]} | {s["place"] for s in it["profile"]["weekly_schedule"]}
        measured = all(o in ("C18", "P12", "P13") for o in origins)
        gold = {k: g.get(k) for k in ("type", "pair_id", "gold", "why", "nearest", "traps", "reason_clinic", "diff",
                                       "candidates", "deciding_reason", "hidden_value", "gold_after_ask", "bounds",
                                       "track", "university")}
        gold.update(valid_ids=sorted(g.get("valid_ids", [])), violations=dict(viol), travel="measured" if measured
                    else "estimated")
        pool.append({"id": g["id"], "public": public, "gold": gold})
    pool.sort(key=lambda x: x["id"])
    with gzip.GzipFile(os.path.join(out, "t9_pool.jsonl.gz"), "wb", mtime=0) as gz:
        for x in pool:
            gz.write((json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))

    # ---- symptoms
    sym = [{"id": s["id"], "en": s["symptom_en"], "ko": s["symptom_ko"], "severity": s["severity"],
            "groups_ko": s["groups"].split("|"), "codes": s["subject_codes"].split(";"), "basis_ko": s["basis"],
            "note_ko": s["note"]}
           for s in csv.DictReader(io.open(os.path.join(src, "symptom_departments.csv"), encoding="utf-8-sig"))]
    json.dump(sym, open(os.path.join(out, "symptoms.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"{len(out_rows)} institutions, {len(districts)} districts, {len(tertiary)} tertiary, {len(places)} places, "
          f"{len(trav)} travel pairs, {len(sym)} symptoms -> {out}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else
         os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "source"))
