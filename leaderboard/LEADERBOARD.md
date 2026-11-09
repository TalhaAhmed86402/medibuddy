# MediBuddy-Bench leaderboard (dev split)

Benchmark data version `1.0.0`, world hash `250037d54de12f55`. Scores are 0-100; per-task columns are gated scores x100. Critical failures (C1-C4) zero an episode.

## Ranked agents

| Rank | Agent | Model | Overall | Un-gated | Crit. rate | pass^3 | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | Trials | Finished (UTC) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| | _no ranked runs yet_ | | | | | | | | | | | | | | | |

## Reference baselines (not ranked)

| Rank | Agent | Model | Overall | Un-gated | Crit. rate | pass^3 | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | Trials | Finished (UTC) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| - | oracle |  | **100.0** | 100.0 | 0% | - | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 1 | 2026-11-09 02:18 |
| - | rule |  | **65.8** | 70.8 | 18% | - | 64 | 63 | 80 | 86 | 50 | 53 | 86 | 50 | 1 | 2026-11-09 02:18 |
| - | naive |  | **15.0** | 20.5 | 49% | - | 32 | 25 | 32 | 39 | 0 | 6 | 0 | 0 | 1 | 2026-11-09 02:18 |
| - | null |  | **1.0** | 2.0 | 36% | - | 0 | 0 | 0 | 10 | 0 | 0 | 0 | 0 | 1 | 2026-11-09 02:18 |

Columns T1-T8: T1 Hospital search, T2 Fresh vs stale information, T3 Clarifying questions, T4 Emergency and urgency triage, T5 Turn-by-turn interpretation, T6 Visit summary, T7 Memory across visits, T8 Full journey.
