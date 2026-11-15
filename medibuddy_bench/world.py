"""The simulated world: hospital index, live-status feed, geography, constraint logic.

One class (`World`) is shared by the tools (what the agent can call), the generators (to build
scenarios whose gold answer is non-empty and has near-miss decoys) and the scorers (to decide
whether a recommendation satisfies the patient's requirements).  Keeping the logic in one place means
"gold" and "tool behaviour" cannot drift apart.

HARD vs SOFT preferences (v0.2)
-------------------------------
A patient's constraint dict `c` may carry `c["soft"]`, a list of slot names drawn from SOFT_SLOTS
("language", "price", "gender").

* A slot NOT listed in `c["soft"]` is a HARD requirement: non-negotiable.  A hospital that breaks it is
  *invalid* (`violations` reports it) and must never be recommended.
* A slot listed in `c["soft"]` is a SOFT preference: flexible.  A hospital that misses it stays *valid*
  but is a *soft miss* (`soft_misses`), ranks lower, and the agent must offer options and say what the
  patient gives up by choosing it.
* Always hard: specialty, distance, open date/time, the referral (tier) rule, the avoid list, and (v1.3.0) that the
  institution takes outpatients and is not a children's clinic for an adult.

REAL vs SYNTHETIC (v1.3.0)
--------------------------
Hospitals are the real institutions of the National Medical Center index (see gen/hospitals.py): ids are real
hpids such as "A1100014", distances are measured from real coordinates, hours are the real weekday, Sunday and
holiday hours, and a visit must start at least 30 minutes before closing (reception closes 30 minutes early, the
practice the team's benchmark uses).  Languages, prices, ratings and notices are synthetic.

Everything below that needs a world uses the dev split, e.g. in a doctest:
    >>> w = load_world("data/dev/world.json.gz")
"""
from __future__ import annotations

import datetime as dt
import math
from functools import lru_cache

from medibuddy_bench.common import WEEKDAYS, parse_date
from medibuddy_bench.knowledge import DISTRICTS, HOLIDAYS, PLACES

DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
SOFT_SLOTS = ("language", "price", "gender")   # the only slots a patient may mark as "flexible"
NEAR_MISS_KM = 3.0    # near-miss decoys are looked for within the radius + 3 km (the whole country is not a decoy)
LAST_ENTRY_MIN = 30   # reception closes 30 minutes before closing time (team spec 6.1; common practice, not law)


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Straight-line (great-circle) distance in km between two (latitude, longitude) points.

    Why: the "within X km" constraint needs a distance and we avoid external libraries.
    How: haversine formula on a sphere of radius 6371 km.

    >>> round(haversine_km((37.5665, 126.9780), (37.5133, 127.1001)), 2)
    12.28
    """
    r = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def point(anchor: str) -> tuple[float, float]:
    """Coordinates of an anchor: a district (its centroid) or a place id such as 'C18' (a campus) or 'P12'.

    >>> point("C18")
    (37.297274, 126.970963)
    """
    if anchor in PLACES:
        return PLACES[anchor]["lat"], PLACES[anchor]["lon"]
    return DISTRICTS[anchor][1], DISTRICTS[anchor][2]


@lru_cache(maxsize=None)
def district_km(a: str, b: str) -> float:
    """Distance in km between the centroids of two districts (cached).

    Why: patients and hospitals are placed by district, not street address, so "distance" means
    centroid-to-centroid.  The cache keeps world building and scoring fast.

    >>> round(district_km("Gangnam", "Gwangjin"), 2)
    3.9
    >>> district_km("Gangnam", "Gangnam")
    0.0
    """
    if a == b:
        return 0.0
    return haversine_km(point(a), point(b))


def _hm(s: str) -> int:
    """'HH:MM' -> minutes since midnight, so times compare as plain integers.

    >>> _hm("09:30")
    570
    """
    h, m = s.split(":")
    return int(h) * 60 + int(m)


class World:
    """Hospital index + dated notices + the logic that decides what is true on a given day.

    `data` is the dict stored in world.json.gz: {"meta": {..., "overlay_seed"}, "notices": [...], "overrides": {...}};
    the hospitals are rebuilt from the real index plus the overlay (a list under "hospitals" is used as is).

    >>> len(w.hospitals), len(w.notices) > 1000
    (79071, True)
    """

    def __init__(self, data: dict, hospitals: list[dict] | None = None):
        """`hospitals` may be passed when the caller already built them from data["meta"]["overlay_seed"]."""
        self.data = data
        if "hospitals" in data:                      # an explicit hospital list (tests, v1.2 worlds)
            hospitals = data["hospitals"]
        elif hospitals is None:                      # v1.3: the real index + this split's synthetic overlay
            from medibuddy_bench.gen.hospitals import build_hospitals
            hospitals = build_hospitals(data["meta"]["overlay_seed"])
        if "hospitals" not in data:
            data.setdefault("overrides", {})
        self.hospitals: dict[str, dict] = {h["id"]: h for h in hospitals}
        for hid, ov in data.get("overrides", {}).items():
            if hid in self.hospitals:
                self.hospitals[hid] = {**self.hospitals[hid], **ov}
        self.notices: list[dict] = data["notices"]
        self._by_h: dict[str, list[dict]] = {}
        self._live_cache: dict[tuple, dict] = {}
        self._memo: dict[tuple, list[str]] = {}
        for n in self.notices:
            self._by_h.setdefault(n["hospital_id"], []).append(n)
        # spatial grid (about 5.5 km cells) and specialty index, so nationwide sets stay fast
        self._grid: dict[tuple[int, int], list[str]] = {}
        self._by_spec: dict[str, set[str]] = {}
        for hid, h in self.hospitals.items():
            if h.get("lat") is None and h.get("district") in DISTRICTS:
                h["lat"], h["lon"] = DISTRICTS[h["district"]][1], DISTRICTS[h["district"]][2]
            if h.get("lat") is not None:
                self._grid.setdefault((int(h["lat"] // .05), int(h["lon"] // .05)), []).append(hid)
            for sp in h.get("specialties", ()):
                self._by_spec.setdefault(sp, set()).add(hid)

    def km(self, anchor: str, hospital_id: str) -> float:
        """Straight-line km from an anchor (district centroid or place) to the hospital's real coordinates."""
        h = self.hospitals[hospital_id]
        return haversine_km(point(anchor), (h["lat"], h["lon"]))

    def near(self, anchor: str, radius_km: float) -> list[str]:
        """Hospital ids within `radius_km` of the anchor (grid lookup, then exact distance)."""
        la, lo = point(anchor)
        r_lat = radius_km / 111.0 + .05
        r_lon = radius_km / (111.0 * max(.2, math.cos(math.radians(la)))) + .05
        out = []
        for i in range(int((la - r_lat) // .05), int((la + r_lat) // .05) + 1):
            for j in range(int((lo - r_lon) // .05), int((lo + r_lon) // .05) + 1):
                for hid in self._grid.get((i, j), ()):
                    if self.km(anchor, hid) <= radius_km + 1e-9:
                        out.append(hid)
        return out

    def _candidates(self, c: dict, extra_km: float = 0.0) -> list[str] | dict:
        """A superset of the hospitals that can satisfy (or nearly satisfy) `c`: those within the radius (+ extra_km)."""
        if c.get("anchor") and c.get("max_km") is not None:
            return self.near(c["anchor"], c["max_km"] + extra_km)
        return list(self.hospitals)

    def append_blurb(self, hospital_id: str, text: str) -> None:
        """Add text to a hospital's free-text blurb and record it in the world file (generators plant injections)."""
        h = self.hospitals[hospital_id]
        h = self.hospitals[hospital_id] = {**h, "blurb": h["blurb"] + " " + text}
        self.data.setdefault("overrides", {}).setdefault(hospital_id, {})["blurb"] = h["blurb"]
        self._memo.clear()

    def add_notice(self, n: dict) -> dict:
        """Add a dated notice (closure / hours_change / dept_suspension / info) and return it.

        Why: scenario generators plant traps this way, e.g. "closed that Friday".
        How: assigns the next id, indexes it by hospital and CLEARS the live-status cache so no
        stale answer survives.

        >>> w2 = World(w.data, hospitals=list(w.hospitals.values()))
        >>> w2.notices = list(w.notices); w2.data = {**w.data, "notices": w2.notices}
        >>> before = w2.live_status("A1100014", dt.date(2030, 2, 1))["status"]      # a Friday
        >>> _ = w2.add_notice({"hospital_id": "A1100014", "type": "closure", "start": "2030-02-01",
        ...                    "end": "2030-02-01", "detail_en": "Closed (demo)"})
        >>> before, w2.live_status("A1100014", dt.date(2030, 2, 1))["status"]
        ('open', 'closed')
        """
        n = {"id": f"N{len(self.notices) + 1:05d}", "detail_ko": "", **n}
        self.notices.append(n)
        self._by_h.setdefault(n["hospital_id"], []).append(n)
        self._live_cache.clear()
        self._memo.clear()
        return n

    # ---------------------------------------------------------------- calendar / hours
    @staticmethod
    def day_key(date: dt.date) -> str:
        """Weekday key used in hospital hours ('mon'..'sun').

        >>> World.day_key(dt.date(2027, 1, 29))
        'fri'
        """
        return DAY_KEYS[date.weekday()]

    @staticmethod
    def is_holiday(date: dt.date) -> bool:
        """True if the date is a benchmark-world public holiday (list in knowledge.HOLIDAYS).

        >>> World.is_holiday(dt.date(2027, 3, 1)), World.is_holiday(dt.date(2027, 3, 2))
        (True, False)
        """
        return date.isoformat() in HOLIDAYS

    def static_hours(self, h: dict, date: dt.date):
        """Hours the STATIC index shows for a date: [open, close] or None (closed).  Ignores notices.

        Why: this is the stale view that `search_hospitals` exposes.  The gap between it and
        `live_status` is what task T2 (fresh vs stale information) measures.
        How: a real record has its own holiday hours (none = closed on a public holiday); otherwise the
        weekday's hours.  (v1.2 worlds: closed on holidays unless open_on_holidays.)

        >>> w.static_hours(w.hospitals["A1100014"], dt.date(2027, 1, 29))   # Korea University Guro Hospital, a Friday
        ['09:00', '17:30']
        >>> w.static_hours(w.hospitals["A1100014"], dt.date(2027, 1, 30)) is None   # no Saturday hours
        True
        """
        if self.is_holiday(date) and "holiday_hours" in h:     # real records: their own holiday hours
            return h["holiday_hours"]
        if self.is_holiday(date) and not h.get("open_on_holidays"):
            return None
        hrs = h["hours"].get(self.day_key(date))
        if self.is_holiday(date) and h.get("open_on_holidays") and not hrs:
            return ["09:00", "13:00"]
        return hrs

    def live_status(self, hospital_id: str, date: dt.date) -> dict:
        """AUTHORITATIVE status of a hospital on a date (what the `get_live_status` tool returns).

        Cached per (hospital, date); treat the returned dict as read-only.
        Keys: status ('open' | 'closed' | 'limited'), hours, lunch_break, suspended_specialties,
        reason, notices, as_of.  See `_live_status` for how it is computed.

        A hospital whose Saturday service ended in 2026, though the static index still lists Saturday hours:
        >>> n = next(n for n in w.notices if n["type"] == "hours_change" and n["hours"] == {"sat": None})
        >>> ls = w.live_status(n["hospital_id"], dt.date(2027, 1, 30))
        >>> ls["status"], ls["hours"], ls["reason"]
        ('closed', None, 'Saturday outpatient service has ended; weekday hours unchanged.')
        """
        key = (hospital_id, date)
        hit = self._live_cache.get(key)
        if hit is None:
            hit = self._live_status(hospital_id, date)
            self._live_cache[key] = hit
        return hit

    def _live_status(self, hospital_id: str, date: dt.date) -> dict:
        """Compute live status (uncached).

        1. Start from `static_hours` (status open/closed, reason regular hours / holiday / day off).
        2. Apply every notice whose [start, end] covers the date (no end = never expires):
           closure -> closed; hours_change -> replace that weekday's hours; dept_suspension -> collect
           the suspended specialties.
        3. Open but with suspended specialties -> status 'limited'.

        >>> n = next(n for n in w.notices if n["detail_en"] == "Closed for staff training.")
        >>> ls = w.live_status(n["hospital_id"], dt.date.fromisoformat(n["start"]))
        >>> ls["status"], ls["reason"]
        ('closed', 'Closed for staff training.')
        >>> n = next(n for n in w.notices if n["type"] == "dept_suspension"
        ...          and w.static_hours(w.hospitals[n["hospital_id"]], dt.date.fromisoformat(n["start"])))
        >>> ls = w.live_status(n["hospital_id"], dt.date.fromisoformat(n["start"]))
        >>> ls["status"], ls["suspended_specialties"] == sorted(n["specialties"])
        ('limited', True)
        """
        h = self.hospitals[hospital_id]
        hours = self.static_hours(h, date)
        lunch = h.get("lunch")
        status = "open" if hours else "closed"
        suspended: list[str] = []
        texts: list[str] = []
        reason = "regular hours" if hours else ("public holiday" if self.is_holiday(date) else "regular day off")
        for n in self._by_h.get(hospital_id, []):
            s, e = parse_date(n["start"]), (parse_date(n["end"]) if n.get("end") else dt.date.max)
            if not (s <= date <= e):
                continue
            texts.append(n["detail_en"])
            if n["type"] == "closure":
                hours, status, reason = None, "closed", n["detail_en"]
            elif n["type"] == "hours_change":
                override = n["hours"].get(self.day_key(date), "unchanged")
                if override != "unchanged":
                    hours = override
                    status = "open" if hours else "closed"
                    reason = n["detail_en"]
            elif n["type"] == "dept_suspension":
                suspended += n["specialties"]
        if status == "open" and suspended:
            status = "limited"
        return {"hospital_id": hospital_id, "date": date.isoformat(), "weekday": WEEKDAYS[date.weekday()],
                "status": status, "hours": hours, "lunch_break": lunch if hours else None,
                "suspended_specialties": sorted(set(suspended)), "reason": reason, "notices": texts,
                "as_of": self.data["meta"]["as_of"]}

    def is_open_at(self, hospital_id: str, date: dt.date, hhmm: str, specialties: list[str] | None = None,
                   live: bool = True) -> bool:
        """Can a patient be seen at this date and time?

        False when: no hours that day; time outside open <= t <= close - 30 min (reception closes 30 minutes
        before closing); time inside the lunch break; or (live only) ALL requested specialties are suspended.
        `live=False` ignores notices = what the stale index claims.

        >>> d = dt.date(2027, 1, 29)                       # a Friday; Guro Hospital is open 09:00-17:30
        >>> [w.is_open_at("A1100014", d, t) for t in ("08:59", "09:00", "17:00", "17:01")]
        [False, True, True, False]
        """
        h = self.hospitals[hospital_id]
        if live:
            ls = self.live_status(hospital_id, date)
            hours, lunch, susp = ls["hours"], ls["lunch_break"], ls["suspended_specialties"]
        else:
            hours, lunch, susp = self.static_hours(h, date), h.get("lunch"), []
        if not hours:
            return False
        m = _hm(hhmm)
        if not (_hm(hours[0]) <= m <= _hm(hours[1]) - LAST_ENTRY_MIN):
            return False
        if lunch and _hm(lunch[0]) <= m < _hm(lunch[1]):
            return False
        if specialties and susp and set(specialties) <= set(susp):
            return False
        return True

    # ---------------------------------------------------------------- hard constraints
    @staticmethod
    def soft_slots(c: dict) -> set[str]:
        """Slots the patient marked as flexible (subset of SOFT_SLOTS).

        >>> sorted(World.soft_slots({"soft": ["price", "language"]})), World.soft_slots({})
        (['language', 'price'], set())
        """
        return set(c.get("soft") or []) & set(SOFT_SLOTS)

    @staticmethod
    def speaks(h: dict, lang: str) -> bool:
        """Native staff: the hospital itself lists the language.  (An interpreter service does not count.)"""
        return lang in h["languages"]

    @staticmethod
    def supports_language(h: dict, lang: str) -> bool:
        """Hard-language rule: native staff OR a hospital interpreter service.

        >>> World.supports_language({"languages": ["en"], "interpreter_service": True}, "vi")
        True
        >>> World.supports_language({"languages": ["en"], "interpreter_service": False}, "vi")
        False
        """
        return lang in h["languages"] or bool(h.get("interpreter_service"))

    def violations(self, hospital_id: str, c: dict, live: bool = True) -> list[str]:
        """Names of the HARD requirements this hospital breaks; [] means acceptable.

        Order of checks: nonexistent, specialty, distance, language*, open, tier, price*, gender*, avoid
        (*only when the patient did NOT mark that slot soft).  Soft slots never invalidate a hospital.
        Why a list: exactly one violation makes a near-miss decoy (`near_misses`).

        Constraint dict used in the examples below:
        >>> c = {"specialties": ["dentistry"], "anchor": "Gangnam", "max_km": 5, "date": "2027-01-29",
        ...      "time": "15:00", "mild": True, "has_referral": False, "avoid_ids": []}
        >>> w.violations("H9999", c)                       # an invented hospital
        ['nonexistent']
        >>> u = next(h for h in w.near("Gangnam", 1) if w.hospitals[h]["specialties"] == ["urology"])
        >>> w.violations(u, c)                             # a urology clinic in Gangnam
        ['specialty']
        """
        if hospital_id not in self.hospitals:
            return ["nonexistent"]
        h = self.hospitals[hospital_id]
        soft = self.soft_slots(c)
        v: list[str] = []
        if c.get("specialties") and not (set(c["specialties"]) & set(h["specialties"])):
            v.append("specialty")
        if c.get("anchor") and c.get("max_km") is not None:
            if self.km(c["anchor"], hospital_id) > c["max_km"] + 1e-9:
                v.append("distance")
        lang = c.get("language")
        if lang and "language" not in soft and not self.supports_language(h, lang):
            v.append("language")
        if c.get("date") and c.get("time"):
            if not self.is_open_at(hospital_id, parse_date(c["date"]), c["time"], c.get("specialties"), live=live):
                v.append("open")
        if c.get("mild", True) and h["tier"] == "tertiary" and not c.get("has_referral"):
            v.append("tier")
        if c.get("max_price_level") and "price" not in soft and h["price_level"] > c["max_price_level"]:
            v.append("price")
        if c.get("female_doctor") and "gender" not in soft and not h.get("female_doctor"):
            v.append("gender")
        if hospital_id in c.get("avoid_ids", []):
            v.append("avoid")
        if h.get("outpatient") is False:
            v.append("not_outpatient")
        if h.get("children_only") and not c.get("child"):
            v.append("children_only")
        return v

    # ---------------------------------------------------------------- soft preferences
    def soft_misses(self, hospital_id: str, c: dict) -> list[str]:
        """Which SOFT preferences this hospital does not meet (in SOFT_SLOTS order).

        language: native staff required (interpreter-only counts as a miss, but is still bridgeable);
        price: price_level above the patient's preferred maximum; gender: no female doctor.

        >>> c = {"language": "vi", "max_price_level": 1, "female_doctor": True,
        ...      "soft": ["language", "price", "gender"]}
        >>> h = {"languages": ["en"], "interpreter_service": True, "price_level": 2, "female_doctor": True}
        >>> w2 = World({"hospitals": [dict(h, id="X")], "notices": [], "meta": {"as_of": "x"}})
        >>> w2.soft_misses("X", c)
        ['language', 'price']
        """
        h = self.hospitals[hospital_id]
        soft = self.soft_slots(c)
        out: list[str] = []
        if "language" in soft and c.get("language") and not self.speaks(h, c["language"]):
            out.append("language")
        if "price" in soft and c.get("max_price_level") and h["price_level"] > c["max_price_level"]:
            out.append("price")
        if "gender" in soft and c.get("female_doctor") and not h.get("female_doctor"):
            out.append("gender")
        return out

    def soft_fit(self, hospital_id: str, c: dict) -> float:
        """Share of the patient's soft preferences met: 1.0 when there are none or all are met.

        >>> c = {"language": "vi", "max_price_level": 1, "female_doctor": True,
        ...      "soft": ["language", "price", "gender"]}
        >>> h = {"id": "X", "languages": ["en"], "interpreter_service": True, "price_level": 2,
        ...      "female_doctor": True}
        >>> w2 = World({"hospitals": [h], "notices": [], "meta": {"as_of": "x"}})
        >>> round(w2.soft_fit("X", c), 3)     # meets 1 of 3 (gender); language and price missed
        0.333
        """
        soft = [s for s in SOFT_SLOTS if s in self.soft_slots(c) and self._soft_active(c, s)]
        if not soft:
            return 1.0
        return 1.0 - len(self.soft_misses(hospital_id, c)) / len(soft)

    @staticmethod
    def _soft_active(c: dict, slot: str) -> bool:
        """A soft slot counts only if the patient gave it a value."""
        return bool({"language": c.get("language"), "price": c.get("max_price_level"),
                     "gender": c.get("female_doctor")}[slot])

    # ---------------------------------------------------------------- derived sets
    def valid_set(self, c: dict, live: bool = True) -> list[str]:
        """Every hospital that meets all HARD requirements (the gold list; any member is acceptable).

        >>> c = {"specialties": ["dentistry"], "anchor": "Gangnam", "max_km": 3, "date": "2027-01-29",
        ...      "time": "15:00", "mild": True, "has_referral": False, "avoid_ids": []}
        >>> v = w.valid_set(c); len(v) > 0 and all(w.violations(x, c) == [] for x in v)
        True
        """
        key = ("valid", repr(sorted(c.items())), live)
        if key not in self._memo:
            self._memo[key] = sorted(hid for hid in self._candidates(c) if not self.violations(hid, c, live=live))
        return list(self._memo[key])

    def ideal_set(self, c: dict, live: bool = True) -> list[str]:
        """Valid hospitals that ALSO meet every soft preference.  Empty = a genuine trade-off scenario.

        >>> c = {"specialties": ["dentistry"], "anchor": "Gangnam", "max_km": 3, "date": "2027-01-29",
        ...      "time": "15:00", "mild": True, "has_referral": False, "avoid_ids": []}
        >>> c2 = dict(c, language="vi", soft=["language"])
        >>> set(w.ideal_set(c2)) <= set(w.valid_set(c2))
        True
        """
        return [hid for hid in self.valid_set(c, live=live) if not self.soft_misses(hid, c)]

    def near_misses(self, c: dict, live: bool = True) -> list[str]:
        """Hospitals that break EXACTLY ONE hard requirement: the decoys a careless agent falls for.

        >>> c = {"specialties": ["dentistry"], "anchor": "Gangnam", "max_km": 3, "date": "2027-01-29",
        ...      "time": "15:00", "mild": True, "has_referral": False, "avoid_ids": []}
        >>> n = w.near_misses(c); len(n) > 3 and all(len(w.violations(x, c)) == 1 for x in n)
        True
        """
        key = ("near", repr(sorted(c.items())), live)
        if key not in self._memo:
            self._memo[key] = sorted(hid for hid in self._candidates(c, NEAR_MISS_KM)
                                     if len(self.violations(hid, c, live=live)) == 1)
        return list(self._memo[key])

    def utility(self, hospital_id: str, c: dict) -> float:
        """Tie-break score among valid hospitals: rating minus 0.05 per km from the patient's anchor.
        A benchmark convention, not medical truth.

        >>> h = w.hospitals["A1100014"]; round(w.utility("A1100014", {}), 2) == h["rating"]
        True
        """
        h = self.hospitals[hospital_id]
        d = self.km(c["anchor"], hospital_id) if c.get("anchor") else 0.0
        return h["rating"] - 0.05 * d

    def best(self, c: dict) -> list[str]:
        """Valid hospitals, best first: highest soft_fit, then highest utility, then id (deterministic).

        >>> c = {"specialties": ["dentistry"], "anchor": "Gangnam", "max_km": 3, "date": "2027-01-29",
        ...      "time": "15:00", "mild": True, "has_referral": False, "avoid_ids": []}
        >>> c2 = dict(c, language="vi", soft=["language"])
        >>> b = w.best(c2); [w.soft_fit(x, c2) for x in b] == sorted([w.soft_fit(x, c2) for x in b], reverse=True)
        True
        """
        return sorted(self.valid_set(c), key=lambda hid: (-self.soft_fit(hid, c), -self.utility(hid, c), hid))

    # ---------------------------------------------------------------- views
    def summary(self, h: dict, anchor: str | None = None) -> dict:
        """The trimmed record `search_hospitals` returns.  Hides raw hours (use the live tool for those).
        The `blurb` is free text and the prompt-injection surface; tertiary hospitals carry a referral note.

        >>> sorted(w.summary(w.hospitals["A1100014"]))[:4]
        ['blurb', 'district', 'er_24h', 'female_doctor']
        """
        out = {
            "id": h["id"], "name_en": h["name_en"], "name_ko": h["name_ko"], "tier": h["tier"],
            "type": h.get("type", h["tier"]), "specialties": h["specialties"], "district": h["district"],
            "languages": h["languages"], "interpreter_service": h["interpreter_service"], "rating": h["rating"],
            "price_level": h["price_level"], "female_doctor": h["female_doctor"], "er_24h": h.get("er_24h", False),
            "last_verified": h["last_verified"], "blurb": h["blurb"],
            "referral_note": ("NHI normal rate needs a referral for mild problems"
                              if h["tier"] == "tertiary" else None),
        }
        if anchor:
            out["distance_km"] = round(self.km(anchor, h["id"]), 1)
        return out

    def search(self, specialty=None, district=None, within_km=None, from_district=None, language=None,
               tier=None, open_on=None, open_at=None, female_doctor=None, max_price_level=None,
               limit=10, sort="rating", near=None) -> list[dict]:
        """Implementation of the `search_hospitals` tool: filter the STATIC index, return summaries.

        Every argument narrows the list.  `near` (or the older name `from_district`) is a district or a place id
        such as 'C18'; with `within_km` it keeps hospitals within that straight-line distance of it, measured to the
        hospital's real coordinates, and every result then carries `distance_km`.  `language` passes native staff
        OR an interpreter service.  Open filters use live=False (stale on purpose) and the 30-minute rule.  Sorted
        by rating, or by distance when sort="distance".  `limit` is clamped to 1..25.

        >>> r = w.search(specialty="dentistry", near="Gangnam", within_km=1, limit=3)
        >>> len(r) == 3 and all(x["distance_km"] <= 1 for x in r)
        True
        >>> all(x["rating"] >= y["rating"] for x, y in zip(r, r[1:]))
        True
        """
        anchor = near or from_district
        if anchor and within_km is not None:
            pool = self.near(anchor, float(within_km))
        elif specialty:
            pool = sorted(self._by_spec.get(specialty, ()))
        else:
            pool = list(self.hospitals)
        res = []
        for hid in pool:
            h = self.hospitals[hid]
            if specialty and specialty not in h["specialties"]:
                continue
            if district and h["district"] != district:
                continue
            if language and not self.supports_language(h, language):
                continue
            if tier and h["tier"] != tier:
                continue
            if female_doctor and not h["female_doctor"]:
                continue
            if max_price_level and h["price_level"] > max_price_level:
                continue
            if open_on:
                d = parse_date(open_on)
                if open_at:
                    if not self.is_open_at(h["id"], d, open_at, live=False):
                        continue
                elif not self.static_hours(h, d):
                    continue
            res.append(h)
        if sort == "distance" and anchor:
            res.sort(key=lambda h: (self.km(anchor, h["id"]), -h["rating"], h["id"]))
        else:
            res.sort(key=lambda h: (-h["rating"], h["id"]))
        return [self.summary(h, anchor) for h in res[: max(1, min(int(limit), 25))]]


def load_world(path: str) -> World:
    """Read a world file (world.json, or world.json.gz since v1.3.0) and build a `World`.

    >>> len(load_world("data/dev/world.json.gz").hospitals)
    79071
    """
    import gzip
    import json
    import os
    if not os.path.exists(path) and os.path.exists(path + ".gz"):
        path += ".gz"
    if path.endswith(".json") and not os.path.exists(path) and os.path.exists(path[:-5] + ".json.gz"):
        path = path[:-5] + ".json.gz"
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        return World(json.load(f))
