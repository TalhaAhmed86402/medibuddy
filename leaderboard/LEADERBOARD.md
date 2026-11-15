# MediBuddy-Bench leaderboard (dev split)

Benchmark data version `1.3.0`, world hash `d03495228e1d13d1`. Scores are 0-100; per-task columns are gated scores x100. Critical failures (C1-C4) zero an episode.

## Ranked agents

| Rank | Agent | Model | Overall | Un-gated | Crit. rate | pass^3 | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | Trials | Finished (UTC) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| | _no ranked runs yet_ | | | | | | | | | | | | | | | | |

## Reference baselines (not ranked)

| Rank | Agent | Model | Overall | Un-gated | Crit. rate | pass^3 | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | Trials | Finished (UTC) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| - | oracle |  | **100.0** | 100.0 | 0% | - | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 1 | 2026-11-15 02:05 |
| - | rule |  | **34.5** | 49.2 | 28% | - | 38 | 30 | 66 | 86 | 15 | 39 | 30 | 2 | 26 | 1 | 2026-11-15 02:05 |
| - | naive |  | **12.0** | 17.2 | 43% | - | 30 | 25 | 16 | 39 | 0 | 6 | 0 | 0 | 5 | 1 | 2026-11-15 02:04 |
| - | null |  | **0.0** | 0.5 | 31% | - | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 2026-11-15 02:03 |

Columns T1-T9: T1 Hospital search, T2 Fresh vs stale information, T3 Clarifying questions, T4 Emergency and urgency triage, T5 Turn-by-turn interpretation, T6 Visit summary, T7 Memory across visits, T8 Full journey, T9 Clinic choice from visit history.
