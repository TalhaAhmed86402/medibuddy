# Pilot results (dev split, 1 trial, non-LLM baselines only)

Date: 2026-10-29. Data: `data/dev` (288 scenarios, world hash 05bdb4da14d0353f). Reproduce:
`python3 scripts/run_benchmark.py --agent <null|naive|rule|oracle> --data data/dev --no-transcripts`.

**Reading guide.** null/naive show the floor; oracle shows the scorers accept perfect behaviour; `rule` is a template-based agent with tools and no
language model: it solves L1-L2 but drops on L3-L4 (colloquial Korean, informal/relative dates), which is the intended gradient.
**No LLM agent has been run**, so absolute difficulty for real agents is unknown. pass^k only has k=1 here (1 trial).

### null

**Overall (gated): 0.9**  |  un-gated: 2.0  |  tasks covered: 100% of weight

| Task | n | gated | un-gated | critical rate | success rate |
|---|---|---|---|---|---|
| T1 Hospital search | 40 | 0.00 | 0.00 | 0% | 0% |
| T2 Fresh vs stale information | 32 | 0.00 | 0.00 | 0% | 0% |
| T3 Clarifying questions | 32 | 0.00 | 0.00 | 0% | 0% |
| T4 Emergency and urgency triage | 64 | 0.09 | 0.15 | 39% | 0% |
| T5 Turn-by-turn interpretation | 40 | 0.00 | 0.02 | 100% | 0% |
| T6 Visit summary | 40 | 0.00 | 0.00 | 0% | 0% |
| T7 Memory across visits | 24 | 0.00 | 0.00 | 100% | 0% |
| T8 Full journey | 16 | 0.00 | 0.01 | 100% | 0% |

| Tier | n | gated | un-gated |
|---|---|---|---|
| L1 | 73 | 0.02 | 0.04 |
| L2 | 73 | 0.02 | 0.04 |
| L3 | 74 | 0.02 | 0.04 |
| L4 | 68 | 0.01 | 0.03 |

Critical failures: C1_missed_red_flag=25, C2_wrong_medical_fact=80, C3_privacy=0, C4_injection_obeyed=0
pass^k: k=1: 0.00
### naive

**Overall (gated): 11.9**  |  un-gated: 17.3  |  tasks covered: 100% of weight

| Task | n | gated | un-gated | critical rate | success rate |
|---|---|---|---|---|---|
| T1 Hospital search | 40 | 0.20 | 0.20 | 0% | 0% |
| T2 Fresh vs stale information | 32 | 0.15 | 0.15 | 0% | 0% |
| T3 Clarifying questions | 32 | 0.27 | 0.27 | 0% | 0% |
| T4 Emergency and urgency triage | 64 | 0.39 | 0.44 | 39% | 20% |
| T5 Turn-by-turn interpretation | 40 | 0.00 | 0.02 | 100% | 0% |
| T6 Visit summary | 40 | 0.07 | 0.26 | 90% | 0% |
| T7 Memory across visits | 24 | 0.00 | 0.09 | 100% | 0% |
| T8 Full journey | 16 | 0.00 | 0.12 | 100% | 0% |

| Tier | n | gated | un-gated |
|---|---|---|---|
| L1 | 73 | 0.19 | 0.24 |
| L2 | 73 | 0.16 | 0.24 |
| L3 | 74 | 0.18 | 0.22 |
| L4 | 68 | 0.15 | 0.21 |

Critical failures: C1_missed_red_flag=25, C2_wrong_medical_fact=116, C3_privacy=0, C4_injection_obeyed=0
pass^k: k=1: 0.05
### rule

**Overall (gated): 67.5**  |  un-gated: 73.2  |  tasks covered: 100% of weight

| Task | n | gated | un-gated | critical rate | success rate |
|---|---|---|---|---|---|
| T1 Hospital search | 40 | 0.63 | 0.63 | 0% | 48% |
| T2 Fresh vs stale information | 32 | 0.62 | 0.62 | 0% | 50% |
| T3 Clarifying questions | 32 | 0.82 | 0.82 | 0% | 53% |
| T4 Emergency and urgency triage | 64 | 0.98 | 0.99 | 2% | 98% |
| T5 Turn-by-turn interpretation | 40 | 0.50 | 0.62 | 50% | 50% |
| T6 Visit summary | 40 | 0.55 | 0.70 | 45% | 55% |
| T7 Memory across visits | 24 | 0.88 | 0.88 | 0% | 50% |
| T8 Full journey | 16 | 0.50 | 0.66 | 50% | 50% |

| Tier | n | gated | un-gated |
|---|---|---|---|
| L1 | 73 | 1.00 | 1.00 |
| L2 | 73 | 0.99 | 0.99 |
| L3 | 74 | 0.46 | 0.55 |
| L4 | 68 | 0.40 | 0.49 |

Critical failures: C1_missed_red_flag=1, C2_wrong_medical_fact=46, C3_privacy=0, C4_injection_obeyed=0
pass^k: k=1: 0.61
### oracle

**Overall (gated): 100.0**  |  un-gated: 100.0  |  tasks covered: 100% of weight

| Task | n | gated | un-gated | critical rate | success rate |
|---|---|---|---|---|---|
| T1 Hospital search | 40 | 1.00 | 1.00 | 0% | 100% |
| T2 Fresh vs stale information | 32 | 1.00 | 1.00 | 0% | 100% |
| T3 Clarifying questions | 32 | 1.00 | 1.00 | 0% | 100% |
| T4 Emergency and urgency triage | 64 | 1.00 | 1.00 | 0% | 100% |
| T5 Turn-by-turn interpretation | 40 | 1.00 | 1.00 | 0% | 100% |
| T6 Visit summary | 40 | 1.00 | 1.00 | 0% | 100% |
| T7 Memory across visits | 24 | 1.00 | 1.00 | 0% | 100% |
| T8 Full journey | 16 | 1.00 | 1.00 | 0% | 100% |

| Tier | n | gated | un-gated |
|---|---|---|---|
| L1 | 73 | 1.00 | 1.00 |
| L2 | 73 | 1.00 | 1.00 |
| L3 | 74 | 1.00 | 1.00 |
| L4 | 68 | 1.00 | 1.00 |

Critical failures: C1_missed_red_flag=0, C2_wrong_medical_fact=0, C3_privacy=0, C4_injection_obeyed=0
pass^k: k=1: 1.00


## Update 2026-10-30 (after hard/soft preferences)
Dev data regenerated. Oracle 1.00 on all tasks. Rule baseline: T1 0.65, T2 0.63, T3 0.81, overall pass^1 0.61. Earlier numbers in this
file refer to the all-hard dev set and are superseded for T1-T3. Saboteur gates were not rerun.
