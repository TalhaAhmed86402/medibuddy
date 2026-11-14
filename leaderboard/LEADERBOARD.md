# MediBuddy-Bench leaderboard (dev split)

Benchmark data version `1.2.0`, world hash `950858d17f40e76a`. Scores are 0-100; per-task columns are gated scores x100. Critical failures (C1-C4) zero an episode.

## Ranked agents

| Rank | Agent | Model | Overall | Un-gated | Crit. rate | pass^3 | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | Trials | Finished (UTC) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| | _no ranked runs yet_ | | | | | | | | | | | | | | | |

## Reference baselines (not ranked)

| Rank | Agent | Model | Overall | Un-gated | Crit. rate | pass^3 | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | Trials | Finished (UTC) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| - | oracle |  | **100.0** | 100.0 | 0% | - | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 1 | 2026-11-14 04:16 |
| - | rule |  | **35.7** | 51.4 | 32% | - | 36 | 28 | 63 | 86 | 15 | 39 | 34 | 4 | 1 | 2026-11-14 04:15 |
| - | naive |  | **13.2** | 19.0 | 49% | - | 31 | 25 | 16 | 39 | 0 | 6 | 0 | 0 | 1 | 2026-11-14 04:15 |
| - | null |  | **0.0** | 0.5 | 36% | - | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 2026-11-14 04:15 |

Columns T1-T8: T1 Hospital search, T2 Fresh vs stale information, T3 Clarifying questions, T4 Emergency and urgency triage, T5 Turn-by-turn interpretation, T6 Visit summary, T7 Memory across visits, T8 Full journey.
