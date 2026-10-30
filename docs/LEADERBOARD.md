# Leaderboard operation (for a top-5 team)

1. **Hidden test split:** `python3 -m medibuddy_bench.gen.build --split test --seed <SECRET> --out data/test --review data/review_test`. Keep the seed and `data/test` private; publish only the manifest hashes.
2. **Submission:** a purple agent endpoint (text protocol) or a Python class. Run `evaluate_remote(...)` (a2a_green.py) or `run_benchmark.py --agent mod:Class --data data/test --trials 3`.
3. **Primary metric:** Overall (gated) ± pass^3. Tie-break: lower critical rate, then un-gated overall.
4. **Report columns:** Overall, un-gated, per-task, per-tier, critical counts C1–C4, tool calls/episode.
5. **Integrity checks before posting:** oracle = 100 and null ≈ 0 on the test split; no tool-call budget overruns; a participant never receives `gold`.
6. **Framework issues log:** keep in `docs/ISSUES.md` (not created yet) with the version/hash for each fix; bump `VERSION` and rerun all entries after any scorer change.
