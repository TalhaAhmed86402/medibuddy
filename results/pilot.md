# Pilot results (dev split, v1.0.0, 832 scenarios, 1 trial, non-LLM baselines only)

Date: 2026-11-09. Reproduce: `python3 scripts/run_benchmark.py --agent <null|naive|rule|oracle> --data data/dev --no-transcripts`.

**Reading guide.** null/naive show the floor; oracle shows the scorers accept perfect behaviour; `rule` is template-based with tools and no language model: it solves L1-L2 but drops on L3-L4, the intended gradient. **No LLM agent has been run**, so absolute difficulty for real agents is unknown. pass^k only has k=1.

### null

**Overall (gated): 1.0**  |  un-gated: 2.0  |  tasks covered: 100% of weight

| Task | n | gated | un-gated | critical rate | success rate |
|---|---|---|---|---|---|
| T1 Hospital search | 120 | 0.00 | 0.00 | 0% | 0% |
| T2 Fresh vs stale information | 96 | 0.00 | 0.00 | 0% | 0% |
| T3 Clarifying questions | 96 | 0.00 | 0.00 | 0% | 0% |
| T4 Emergency and urgency triage | 160 | 0.10 | 0.15 | 36% | 0% |
| T5 Turn-by-turn interpretation | 120 | 0.00 | 0.02 | 100% | 0% |
| T6 Visit summary | 120 | 0.00 | 0.00 | 0% | 0% |
| T7 Memory across visits | 72 | 0.00 | 0.00 | 100% | 0% |
| T8 Full journey | 48 | 0.00 | 0.01 | 100% | 0% |

| Tier | n | gated | un-gated |
|---|---|---|---|
| L1 | 203 | 0.02 | 0.03 |
| L2 | 212 | 0.02 | 0.03 |
| L3 | 209 | 0.02 | 0.03 |
| L4 | 208 | 0.02 | 0.03 |

Critical failures: C1_missed_red_flag=58, C2_wrong_medical_fact=240, C3_privacy=0, C4_injection_obeyed=0
pass^k: k=1: 0.00

### naive

**Overall (gated): 15.0**  |  un-gated: 20.5  |  tasks covered: 100% of weight

| Task | n | gated | un-gated | critical rate | success rate |
|---|---|---|---|---|---|
| T1 Hospital search | 120 | 0.32 | 0.32 | 0% | 2% |
| T2 Fresh vs stale information | 96 | 0.25 | 0.25 | 0% | 0% |
| T3 Clarifying questions | 96 | 0.32 | 0.32 | 0% | 0% |
| T4 Emergency and urgency triage | 160 | 0.39 | 0.45 | 36% | 18% |
| T5 Turn-by-turn interpretation | 120 | 0.00 | 0.02 | 100% | 0% |
| T6 Visit summary | 120 | 0.06 | 0.17 | 92% | 0% |
| T7 Memory across visits | 72 | 0.00 | 0.14 | 100% | 0% |
| T8 Full journey | 48 | 0.00 | 0.12 | 100% | 0% |

| Tier | n | gated | un-gated |
|---|---|---|---|
| L1 | 203 | 0.19 | 0.25 |
| L2 | 212 | 0.21 | 0.26 |
| L3 | 209 | 0.19 | 0.24 |
| L4 | 208 | 0.19 | 0.23 |

Critical failures: C1_missed_red_flag=58, C2_wrong_medical_fact=351, C3_privacy=0, C4_injection_obeyed=0
pass^k: k=1: 0.04

### rule

**Overall (gated): 65.8**  |  un-gated: 70.8  |  tasks covered: 100% of weight

| Task | n | gated | un-gated | critical rate | success rate |
|---|---|---|---|---|---|
| T1 Hospital search | 120 | 0.64 | 0.64 | 0% | 48% |
| T2 Fresh vs stale information | 96 | 0.63 | 0.63 | 0% | 50% |
| T3 Clarifying questions | 96 | 0.80 | 0.80 | 0% | 49% |
| T4 Emergency and urgency triage | 160 | 0.86 | 0.87 | 7% | 81% |
| T5 Turn-by-turn interpretation | 120 | 0.50 | 0.60 | 50% | 50% |
| T6 Visit summary | 120 | 0.53 | 0.65 | 47% | 53% |
| T7 Memory across visits | 72 | 0.86 | 0.86 | 0% | 44% |
| T8 Full journey | 48 | 0.50 | 0.66 | 50% | 50% |

| Tier | n | gated | un-gated |
|---|---|---|---|
| L1 | 203 | 0.98 | 0.98 |
| L2 | 212 | 0.95 | 0.96 |
| L3 | 209 | 0.39 | 0.48 |
| L4 | 208 | 0.38 | 0.46 |

Critical failures: C1_missed_red_flag=11, C2_wrong_medical_fact=140, C3_privacy=0, C4_injection_obeyed=0
pass^k: k=1: 0.56

### oracle

**Overall (gated): 100.0**  |  un-gated: 100.0  |  tasks covered: 100% of weight

| Task | n | gated | un-gated | critical rate | success rate |
|---|---|---|---|---|---|
| T1 Hospital search | 120 | 1.00 | 1.00 | 0% | 100% |
| T2 Fresh vs stale information | 96 | 1.00 | 1.00 | 0% | 100% |
| T3 Clarifying questions | 96 | 1.00 | 1.00 | 0% | 100% |
| T4 Emergency and urgency triage | 160 | 1.00 | 1.00 | 0% | 100% |
| T5 Turn-by-turn interpretation | 120 | 1.00 | 1.00 | 0% | 100% |
| T6 Visit summary | 120 | 1.00 | 1.00 | 0% | 100% |
| T7 Memory across visits | 72 | 1.00 | 1.00 | 0% | 100% |
| T8 Full journey | 48 | 1.00 | 1.00 | 0% | 100% |

| Tier | n | gated | un-gated |
|---|---|---|---|
| L1 | 203 | 1.00 | 1.00 |
| L2 | 212 | 1.00 | 1.00 |
| L3 | 209 | 1.00 | 1.00 |
| L4 | 208 | 1.00 | 1.00 |

Critical failures: C1_missed_red_flag=0, C2_wrong_medical_fact=0, C3_privacy=0, C4_injection_obeyed=0
pass^k: k=1: 1.00

## Fairness twins (rule agent, 180 pairs)
T1: n=60 mean gap (twin - original) = +0.0000, max |gap| = 0.000
T2: n=60 mean gap (twin - original) = +0.0000, max |gap| = 0.000
T3: n=60 mean gap (twin - original) = +0.0000, max |gap| = 0.000
ALL: mean gap +0.0000
