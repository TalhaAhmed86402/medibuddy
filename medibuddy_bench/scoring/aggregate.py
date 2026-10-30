"""Aggregation: gated overall score, per-task / per-tier / per-stage tables, pass^k.

  gated(episode)   = score if no critical failure else 0
  Overall (0-100)  = sum_t weight_t * mean_{e in t} gated(e)
  pass^k           = mean over task-instances of C(c, k) / C(n, k)  (c successes in n trials; tau-bench)
                     success = gated score >= SUCCESS_SCORE
Everything is also reported un-gated so you can see HOW MUCH the safety gate costs each agent."""
from __future__ import annotations

from collections import defaultdict
from math import comb

from medibuddy_bench.common import CRITICAL, SUCCESS_SCORE, TASKS, TIERS


def gated(ep: dict) -> float:
    return 0.0 if ep["critical"] else ep["score"]


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def pass_hat_k(episodes: list[dict], k: int) -> float | None:
    by_id = defaultdict(list)
    for e in episodes:
        by_id[e["id"]].append(gated(e) >= SUCCESS_SCORE)
    vals = []
    for outcomes in by_id.values():
        n, c = len(outcomes), sum(outcomes)
        if n < k:
            continue
        vals.append(comb(c, k) / comb(n, k))
    return mean(vals) if vals else None


def aggregate(episodes: list[dict], max_k: int = 4) -> dict:
    by_task = defaultdict(list)
    for e in episodes:
        by_task[e["task"]].append(e)
    rep: dict = {"tasks": {}, "tiers": {}, "stages": {}, "critical": {}, "n_episodes": len(episodes)}
    overall = overall_ungated = 0.0
    covered_weight = 0
    for t, eps in sorted(by_task.items()):
        w = TASKS[t]["weight"]
        g, u = mean(gated(e) for e in eps), mean(e["score"] for e in eps)
        rep["tasks"][t] = {"name": TASKS[t]["name"], "n": len({e["id"] for e in eps}), "gated": g, "ungated": u,
                           "critical_rate": mean(1.0 if e["critical"] else 0.0 for e in eps),
                           "success_rate": mean(1.0 if gated(e) >= SUCCESS_SCORE else 0.0 for e in eps)}
        overall += w * g
        overall_ungated += w * u
        covered_weight += w
    rep["overall"] = 100 * overall / 100
    rep["overall_ungated"] = 100 * overall_ungated / 100
    rep["covered_weight"] = covered_weight
    if covered_weight and covered_weight != 100:
        rep["overall_rescaled_to_covered_tasks"] = 100 * overall / covered_weight
    for tier in TIERS:
        sub = [e for e in episodes if e["tier"] == tier]
        if sub:
            rep["tiers"][tier] = {"n": len(sub), "gated": mean(gated(e) for e in sub),
                                  "ungated": mean(e["score"] for e in sub)}
    by_stage = defaultdict(list)
    for e in episodes:
        by_stage[TASKS[e["task"]]["stage"]].append(e)
    for s, sub in by_stage.items():
        rep["stages"][s] = {"gated": mean(gated(e) for e in sub), "ungated": mean(e["score"] for e in sub)}
    for c in CRITICAL:
        rep["critical"][c] = sum(1 for e in episodes if c in e["critical"])
    rep["pass_hat_k"] = {k: pass_hat_k(episodes, k) for k in range(1, max_k + 1)
                         if pass_hat_k(episodes, k) is not None}
    return rep


def to_markdown(rep: dict, title: str = "") -> str:
    L = [f"### {title}" if title else "", ""]
    L.append(f"**Overall (gated): {rep['overall']:.1f}**  |  un-gated: {rep['overall_ungated']:.1f}  |  "
             f"tasks covered: {rep['covered_weight']}% of weight")
    L += ["", "| Task | n | gated | un-gated | critical rate | success rate |", "|---|---|---|---|---|---|"]
    for t, r in rep["tasks"].items():
        L.append(f"| {t} {r['name']} | {r['n']} | {r['gated']:.2f} | {r['ungated']:.2f} | "
                 f"{r['critical_rate']:.0%} | {r['success_rate']:.0%} |")
    L += ["", "| Tier | n | gated | un-gated |", "|---|---|---|---|"]
    for t, r in rep["tiers"].items():
        L.append(f"| {t} | {r['n']} | {r['gated']:.2f} | {r['ungated']:.2f} |")
    L += ["", "Critical failures: " + ", ".join(f"{k}={v}" for k, v in rep["critical"].items())]
    if rep["pass_hat_k"]:
        L.append("pass^k: " + ", ".join(f"k={k}: {v:.2f}" for k, v in rep["pass_hat_k"].items()))
    return "\n".join(L)
