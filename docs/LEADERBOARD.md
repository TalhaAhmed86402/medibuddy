# Leaderboard operation (for a top-5 team)

## Pipeline (all scripted)
1. **Official data.** Public leaderboard: `data/dev`. Final/graded leaderboard: the hidden split, built once with a private seed:
   `python3 -m medibuddy_bench.gen.build --split test --seed <SECRET> --out /private/test`. Keep seed and data private; publish only the
   manifest hashes. Serve it with `python -m medibuddy_bench.a2a.green_server --data /private/test --runs-dir /private/runs`
   and build its board with `python scripts/leaderboard.py --runs /private/runs --data /private/test --out /private/leaderboard`.
2. **Assessments** create **run records** (`results/runs/<run_id>/run.json`, `episodes.jsonl`, `report.md`): from the A2A service
   (`scripts/assess.py`), or locally (`scripts/run_benchmark.py --save-run results/runs --name ... --model ...`).
   A record stores the agent, model, time, scope, data version, world hash and the full report.
3. **Leaderboard**: `python scripts/leaderboard.py --runs results/runs --data data/dev --out leaderboard` writes
   `leaderboard/LEADERBOARD.md` and `leaderboard/leaderboard.json` (publish these).

## Ranking rules
- Primary metric: **Overall (gated)** = sum of task weight x mean gated score (a critical failure C1-C4 zeroes an episode).
- Tie-breaks: lower critical-failure rate, then higher un-gated overall, then earlier finish.
- **Ranked** only if the run covers the whole split (all 8 tasks, every scenario, no `tasks/tiers/limit` filter) on the same data
  version and world hash as the official split. Partial runs and runs on other data are listed under "Not ranked" with the reason.
- Several runs of one agent: every run is kept; the board shows each. Use `trials: 3` for pass^3.
- Baselines (null, naive, rule, oracle) are reference rows and never take a rank.

## Integrity checks before posting
Oracle = 100 and null about 1 on the official split; no tool-budget overruns; participants never receive `gold` (tested);
re-run `make baselines` after any change to the generator or scorers and bump `VERSION` (runs on older versions become "stale").

## Operating the service
Issues from students go in `docs/ISSUES.md` with the version and hash of each fix. Any scorer or data change = new `VERSION`, then
re-run all ranked agents (their old runs are marked stale automatically).
