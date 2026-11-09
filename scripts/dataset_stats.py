#!/usr/bin/env python3
"""Describe a built split (world + scenarios) as Markdown.

  python scripts/dataset_stats.py --data data/dev > docs/DATASET_STATS.md      # full breakdown
  python scripts/dataset_stats.py --data data/dev --summary                    # the short block quoted in README.md

Every number in both documents comes from the data files, never from memory.  `tests/test_docs.py` regenerates both
and fails if the committed documents have drifted, so they cannot go stale silently."""
import argparse
import collections
import datetime as dt
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from medibuddy_bench.knowledge import LANGUAGE_NAMES  # noqa: E402

KHIDI = {"en": 92.9, "zh": 65.3, "ru": 59.4, "ja": 40.2, "mn": 35.6, "vi": 17.2, "ar": 12.6}   # real KHIDI list, % of hospitals
TIERS = ["clinic", "hospital", "general_hospital", "tertiary"]
TASK_NAMES = {"T1": "Hospital search", "T2": "Fresh vs stale information", "T3": "Clarifying questions",
              "T4": "Emergency and urgency triage", "T5": "Turn-by-turn interpretation", "T6": "Visit summary",
              "T7": "Memory across visits", "T8": "Full journey"}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def pct(n, d, digits=1):
    return f"{100 * n / d:.{digits}f}%" if d else "n/a"


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def gather(data_dir):
    """Read a split and compute every statistic once (the two renderers only format)."""
    with open(os.path.join(data_dir, "world.json"), encoding="utf-8") as f:
        world = json.load(f)
    with open(os.path.join(data_dir, "manifest.json"), encoding="utf-8") as f:
        man = json.load(f)
    hs, notices = world["hospitals"], world["notices"]
    sc = {t: load(os.path.join(data_dir, f"{t}.jsonl")) for t in man["counts"]}
    d = {"split": os.path.basename(data_dir.rstrip("/")), "man": man, "hs": hs, "notices": notices, "sc": sc}
    d["district_hosp"] = collections.Counter(h["district"] for h in hs)
    d["district_region"] = {h["district"]: h["region"] for h in hs}
    choice = [s for t in ("T1", "T2", "T3") for s in sc.get(t, [])]
    d["choice"] = choice
    d["cons"] = [s["gold"]["constraints"] for s in choice]
    return d


# ------------------------------------------------------------------ pieces shared by both renderers
def headline(d):
    hs = d["hs"]
    specs = {s for h in hs for s in h["specialties"]}
    total = sum(len(v) for v in d["sc"].values())
    return (f"{len(hs):,} hospitals in {len(d['district_hosp'])} districts across "
            f"{len({h['region'] for h in hs})} regions, {len(specs)} specialties, "
            f"{len({lang for h in hs for lang in h['languages']})} hospital languages, {len(d['notices'])} dated notices; "
            f"{total} scenarios in the {d['split']} split.")


def tier_rows(d):
    c = collections.Counter(h["tier"] for h in d["hs"])
    return [(t, c[t], pct(c[t], len(d["hs"]))) for t in TIERS]


def region_rows(d):
    by_region = collections.defaultdict(list)
    for h in d["hs"]:
        by_region[h["region"]].append(h)
    rows = []
    for r, items in sorted(by_region.items(), key=lambda kv: -len(kv[1])):
        rows.append((r, len({h["district"] for h in items}), len(items), pct(len(items), len(d["hs"]))))
    return rows


def feature_lines(d):
    hs, n = d["hs"], len(d["hs"])
    count = lambda f: sum(1 for h in hs if f(h))
    return [
        ("Female doctor available", pct(count(lambda h: h["female_doctor"]), n)),
        ("Walk-ins accepted", pct(count(lambda h: h["walk_in"]), n)),
        ("Open on Saturday / Sunday", f"{pct(count(lambda h: h['hours'].get('sat')), n)} / {pct(count(lambda h: h['hours'].get('sun')), n)}"),
        ("Open on public holidays", pct(count(lambda h: h["open_on_holidays"]), n)),
        ("Lunch break", pct(count(lambda h: h["lunch"]), n)),
        ("24-hour emergency room", pct(count(lambda h: h["er_24h"]), n)),
        ("Interpreter service", pct(count(lambda h: h["interpreter_service"]), n)),
        ("Names at least one foreign language", pct(count(lambda h: h["languages"]), n)),
        ("Price level 1 / 2 / 3", " / ".join(pct(count(lambda h: h["price_level"] == k), n) for k in (1, 2, 3))),
        ("Mean rating (min to max)", f"{statistics.mean(h['rating'] for h in hs):.2f} ({min(h['rating'] for h in hs)} to {max(h['rating'] for h in hs)})"),
        ("Static record last verified", f"{min(h['last_verified'] for h in hs)} to {max(h['last_verified'] for h in hs)}"),
    ]


def constraint_lines(d):
    c, n = d["cons"], len(d["cons"])
    if not n:
        return []
    days = collections.Counter(dt.date.fromisoformat(x["date"]).weekday() for x in c)
    valid = [len(s["gold"]["valid"]) for s in d["choice"]]
    share = lambda f: pct(sum(1 for x in c if f(x)), n)
    return [
        (f"Maximum distance (km), 3 / 5 / 8 / 12", " / ".join(share(lambda x, k=k: x["max_km"] == k) for k in (3, 5, 8, 12))),
        ("Price cap stated (level 1 / 2 / 3)", " / ".join(share(lambda x, k=k: x.get("max_price_level") == k) for k in (1, 2, 3)) + f"; none: {share(lambda x: not x.get('max_price_level'))}"),
        ("Needs a hospital language", share(lambda x: x.get("language"))),
        ("Needs a female doctor", share(lambda x: x.get("female_doctor"))),
        ("Has a flexible (soft) preference", share(lambda x: x.get("soft"))),
        ("Names a hospital to avoid", share(lambda x: x.get("avoid_ids"))),
        ("Has a referral letter", share(lambda x: x.get("has_referral"))),
        ("Contains a planted injected instruction", pct(sum(1 for s in d["choice"] if s["gold"].get("injection")), n)),
        ("Visit weekday Mon-Fri / Sat / Sun", f"{pct(sum(days[i] for i in range(5)), n)} / {pct(days[5], n)} / {pct(days[6], n)}"),
        ("Valid hospitals per scenario (min / median / max)", f"{min(valid)} / {statistics.median(valid):g} / {max(valid)}"),
        ("Complaints used", f"{len({s['gold']['complaint'] for s in d['choice']})}, all mild (emergencies are tested in T4)"),
    ]


def scenario_rows(d):
    rows = []
    for t, items in d["sc"].items():
        tc = collections.Counter(s["tier"] for s in items)
        rows.append((f"{t} {TASK_NAMES.get(t, '')}".strip(), len(items), tc["L1"], tc["L2"], tc["L3"], tc["L4"]))
    return rows


# ------------------------------------------------------------------ the short block for README.md
def render_summary(d):
    out = [f"{headline(d)}\n"]
    out.append(table(["Hospital tier", "Hospitals", "Share"], tier_rows(d)))
    out.append("\n" + table(["Region", "Districts", "Hospitals", "Share"], region_rows(d)))
    out.append("\n" + table(["Hospital feature", "Share of hospitals"], feature_lines(d)))
    out.append("\n" + table(["Scenario", "n", "L1", "L2", "L3", "L4"], scenario_rows(d)))
    cl = constraint_lines(d)
    if cl:
        out.append("\n" + table(["Hospital-choice scenarios (T1-T3)", "Share"], cl))
    out.append(f"\nFull breakdown: [`docs/DATASET_STATS.md`](docs/DATASET_STATS.md). "
               f"Both are generated by `scripts/dataset_stats.py` from the `{d['split']}` split and checked by `tests/test_docs.py`.")
    return "\n".join(out)


# ------------------------------------------------------------------ the full document
def render_full(d):
    hs, sc, man = d["hs"], d["sc"], d["man"]
    o = [f"# Dataset statistics ({d['split']} split)\n",
         f"Generated by `scripts/dataset_stats.py`. Synthetic data; world hash `{man['world_hash']}`; data version `{man['version']}`.\n",
         "## World\n", f"- {headline(d)}\n",
         table(["Tier", "Hospitals", "Share"], tier_rows(d))]
    o.append("\n" + table(["Region", "Districts", "Hospitals", "Share"], region_rows(d)))
    rows = [(dist, d["district_region"][dist], n, pct(n, len(hs)))
            for dist, n in sorted(d["district_hosp"].items(), key=lambda kv: (d["district_region"][kv[0]], -kv[1]))]
    hv = list(d["district_hosp"].values())
    o.append(f"\n### Hospitals per district\n\nMinimum {min(hv)}, median {statistics.median(hv):g}, maximum {max(hv)}.\n")
    o.append(table(["District", "Region", "Hospitals", "Share"], rows))

    o.append("\n### Tier by region (hospitals)\n")
    regions = [r[0] for r in region_rows(d)]
    cnt = collections.Counter((h["region"], h["tier"]) for h in hs)
    o.append(table(["Region"] + TIERS, [(r, *[cnt[(r, t)] for t in TIERS]) for r in regions]))

    o.append("\n### Specialties\n")
    sp = collections.Counter(s for h in hs for s in h["specialties"])
    o.append(table(["Specialty", "Hospitals offering it", "Share"], [(s, n, pct(n, len(hs))) for s, n in sp.most_common()]))
    per = collections.Counter(len(h["specialties"]) for h in hs)
    o.append("\nSpecialties per hospital: " + ", ".join(f"{k}: {v}" for k, v in sorted(per.items())) + ".")

    o.append("\n### Price level by tier (hospitals)\n")
    pc = collections.Counter((h["tier"], h["price_level"]) for h in hs)
    o.append(table(["Tier", "Level 1", "Level 2", "Level 3"], [(t, *[pc[(t, k)] for k in (1, 2, 3)]) for t in TIERS]))

    o.append("\n### Services and opening\n")
    o.append(table(["Feature", "Value"], feature_lines(d)))
    o.append("\n### Interpreter service and foreign-language staff by tier\n")
    rows = []
    for t in TIERS:
        sub = [h for h in hs if h["tier"] == t]
        rows.append((t, pct(sum(1 for h in sub if h["interpreter_service"]), len(sub)),
                     pct(sum(1 for h in sub if h["languages"]), len(sub)),
                     f"{statistics.mean(len(h['languages']) for h in sub):.2f}"))
    o.append(table(["Tier", "Interpreter service", "Names a foreign language", "Mean languages per hospital"], rows))

    o.append("\n### Languages supported by hospitals\n")
    lc = collections.Counter(lang for h in hs for lang in h["languages"])
    o.append(table(["Language", "All synthetic hospitals", "KHIDI list share (real, %)"],
                   [(LANGUAGE_NAMES[k], pct(n, len(hs)), KHIDI.get(k, "n/a (assumed)")) for k, n in lc.most_common()]))
    intl = [h for h in hs if len(h["languages"]) >= 2]
    o.append(f"\n- Hospitals naming 2+ languages: {pct(len(intl), len(hs))}; mean languages among them: "
             f"{sum(len(h['languages']) for h in intl) / max(1, len(intl)):.2f}.")

    o.append("\n### Notices (closures, department suspensions, hours changes)\n")
    nt = collections.Counter(n["type"] for n in d["notices"])
    o.append(table(["Type", "Notices", "Share"], [(t, n, pct(n, len(d["notices"]))) for t, n in nt.most_common()]))
    o.append(f"\nHospitals with at least one notice: {len({n['hospital_id'] for n in d['notices']})} of {len(hs)}.")

    o.append("\n## Scenarios\n")
    o.append(table(["Task", "n", "L1", "L2", "L3", "L4"], scenario_rows(d)))
    o.append(f"\nTotal scenarios: {sum(len(v) for v in sc.values())}.\n")

    cl = constraint_lines(d)
    if cl:
        o.append("### Hospital-choice scenarios (T1-T3)\n")
        o.append(table(["Property", "Value"], cl))
        t2 = sc.get("T2", [])
        if t2:
            tc = collections.Counter(len(s["gold"]["traps"]) for s in t2)
            o.append("\nT2 live-status traps per scenario: " + ", ".join(f"{k}: {v}" for k, v in sorted(tc.items())) + ".")
        t3 = sc.get("T3", [])
        if t3:
            hc = collections.Counter(len(s["gold"]["hidden_slots"]) for s in t3)
            hs_slots = collections.Counter(x for s in t3 for x in s["gold"]["hidden_slots"])
            o.append("\nT3 hidden details per scenario: " + ", ".join(f"{k}: {v}" for k, v in sorted(hc.items()))
                     + "; which details are hidden: " + ", ".join(f"{k} {v}" for k, v in hs_slots.most_common()) + ".")
        o.append("")

    pers = [s["gold"]["persona"] for s in d["choice"] if "persona" in s["gold"]]
    if pers:
        nc = collections.Counter(p["nationality"] for p in pers)
        o.append("### Patient nationalities (T1-T3)\n")
        o.append(table(["Nationality", "n", "Share"], [(k, n, pct(n, len(pers))) for k, n in nc.most_common()]))
        o.append(f"\nDistinct names: {len({p['name'] for p in pers})}; distinct visas: {len({p['visa'] for p in pers})}.\n")

    if "T4" in sc:
        t4 = sc["T4"]
        o.append("### Triage (T4)\n")
        lab = collections.Counter(s["gold"]["label"] for s in t4)
        cases = collections.defaultdict(set)
        for s in t4:
            cases[s["gold"]["label"]].add(s["gold"]["case"])
        o.append(table(["Label", "Scenarios", "Distinct cases"], [(k, lab[k], len(cases[k])) for k in ("emergency", "urgent", "routine", "self_care")]))
        o.append(f"\nDistinct cases in total: {len({s['gold']['case'] for s in t4})}.\n")
    enc = [(t, s) for t in ("T5", "T6") for s in sc.get(t, [])]
    if enc:
        o.append("### Doctor visits (T5, T6)\n")
        rows = []
        for tier in ("L1", "L2", "L3", "L4"):
            sub = [s for t, s in enc if t == "T5" and s["tier"] == tier]
            if sub:
                rows.append((tier, f"{statistics.mean(len(s['public']['turns']) for s in sub):.1f}",
                             f"{statistics.mean(len(s['gold']['spec']['drugs']) for s in sub):.1f}"))
        o.append(table(["Tier", "Mean turns per visit", "Mean drugs per visit"], rows))
        specs = [s["gold"]["spec"] for _, s in enc]
        o.append(f"\nDistinct diagnoses: {len({sp['diagnosis'] for sp in specs})}; distinct drugs: "
                 f"{len({dr['drug'] for sp in specs for dr in sp['drugs']})}; visits with a stated allergy: "
                 f"{pct(sum(1 for sp in specs if sp.get('allergy')), len(specs))}.\n")
    if "T7" in sc:
        t7 = sc["T7"]
        o.append("### Memory (T7)\n")
        sess = {tier: sorted({len(s["public"]["sessions"]) for s in t7 if s["tier"] == tier}) for tier in ("L1", "L2", "L3", "L4")}
        pr = collections.Counter(p["type"] for s in t7 for p in s["gold"]["probes"])
        o.append("Sessions per scenario by tier: " + ", ".join(f"{k}: {'/'.join(map(str, v))}" for k, v in sess.items())
                 + ". Probes: " + ", ".join(f"{k} {v}" for k, v in sorted(pr.items())) + ".\n")
    if "T8" in sc:
        t8 = sc["T8"]
        fu = collections.Counter(s["gold"]["follow_up_days"] for s in t8)
        o.append("### Full journey (T8)\n")
        o.append("Follow-up after N days: " + ", ".join(f"{k}: {v}" for k, v in sorted(fu.items()))
                 + f". Mean share of valid hospitals closed on the follow-up date: "
                   f"{statistics.mean(s['gold']['closed_fraction_on_target'] for s in t8):.2f}.\n")

    ops = [s["public"].get("opening", "") for t in ("T1", "T2", "T3", "T4") for s in sc.get(t, [])]
    o.append("### Text variety\n")
    o.append(f"- Distinct openings (T1-T4): {len(set(ops))} of {len(ops)}.")
    if "phrasing" in man:
        o.append(f"- Paraphrased patient wording: {'on' if man['phrasing']['enabled'] else 'off'} "
                 f"(held-out private wording used: {'yes' if man['phrasing']['held_out'] else 'no'}).")
    return "\n".join(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/dev")
    ap.add_argument("--summary", action="store_true", help="print the short block quoted in README.md")
    a = ap.parse_args()
    d = gather(a.data)
    print(render_summary(d) if a.summary else render_full(d))


if __name__ == "__main__":
    main()
