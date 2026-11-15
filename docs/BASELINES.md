# Reference baselines

Scores of the scripted reference agents (dev and lite) and of small open models (lite), all on data v1.3.0. The tables between the markers are generated
from the run records in `results/runs/` (dev) and `results/lite-runs/` (lite) by `python scripts/baselines_report.py`; do not edit
them by hand. These rows are references for calibrating difficulty; they never take a rank on the leaderboard.

## How the open models were run

<!-- setup:begin -->
- **Server:** Ollama 0.40.13 (OpenAI-compatible endpoint), one NVIDIA RTX 3090 (24 GB, driver 580.126.09) shared with another
  job, `OLLAMA_CONTEXT_LENGTH=16384`, `OLLAMA_NUM_PARALLEL=2`, one model loaded at a time (data v1.3.0, 2026-11-15).
- **Client:** `python scripts/sweep.py --data data/<split> --workers 2`, records marked as baselines (the adapter `openai:` with temperature 0,
  seed 0, at most 1,500 reply tokens, stop after `</tool_call>`); `--workers` does not change scores.
- **Models** (Ollama library tags, all Q4_K_M):

  | Name in the tables | Tag | Ollama id | Parameters |
  |---|---|---|---|
  | qwen2.5-7b | `qwen2.5:7b` | 845dbda0ea48 | 7.6B |
  | llama3.1-8b | `llama3.1:8b` | 46e0c10c039e | 8.0B |
  | qwen3-8b | `qwen3:8b` (thinking off: `reasoning_effort: none`) | 500a1f067a9f | 8.2B |
  | gemma3-4b | `gemma3:4b` | 68ceab7e468a | 3.9B |
  | mistral-7b (not run on v1.3.0; on v1.2.0 it stopped at 114 of 116 lite episodes) | `mistral:7b` | 6577803aa9a0 | 7.2B |
  | exaone3.5-7.8b (not run yet; Korean-specialised; research licence) | `exaone3.5:7.8b` | c7c4e3d1ca22 | 7.8B |
  | llama3.2-3b | `llama3.2:3b` | a80c4f17acd5 | 3.2B |
- **Prompting:** none beyond the benchmark's own task cards; no system prompt, no examples, no retries. These are what an
  untuned agent gets, not the best a model can do.
- One trial per scenario. Model outputs are not bit-exact across machines (`docs/REPRODUCIBILITY.md`); expect differences of a
  few points between runs of the same model on other hardware.
<!-- setup:end -->

## Dev split (952 scenarios)

Overall and task columns are gated scores x100 (a critical failure zeroes the episode); tier columns are gated means (0-1).

<!-- dev-table:begin -->
| Agent | Overall | Un-gated | Crit. rate | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | L1 | L2 | L3 | L4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| oracle (scripted) | **100.0** | 100.0 | 0% | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 1.00 | 1.00 | 1.00 | 1.00 |
| rule (scripted) | **34.5** | 49.2 | 28% | 38 | 30 | 66 | 86 | 15 | 39 | 30 | 2 | 26 | 0.53 | 0.45 | 0.35 | 0.33 |
| naive (scripted) | **12.0** | 17.2 | 43% | 30 | 25 | 16 | 39 | 0 | 6 | 0 | 0 | 5 | 0.15 | 0.16 | 0.16 | 0.17 |
| null (scripted) | **0.0** | 0.5 | 31% | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.00 |
<!-- dev-table:end -->

Critical failures (episodes):

<!-- dev-critical:begin -->
| Agent | Episodes | C1 missed red flag | C2 wrong medical fact | C3 privacy | C4 injection obeyed |
|---|---|---|---|---|---|
| oracle (scripted) | 952 | 0 | 0 | 0 | 0 |
| rule (scripted) | 952 | 11 | 258 | 2 | 0 |
| naive (scripted) | 952 | 58 | 351 | 0 | 0 |
| null (scripted) | 952 | 58 | 240 | 0 | 0 |
<!-- dev-critical:end -->

Exact model ids and run records:

<!-- dev-models:begin -->
_No open-model run on this split yet._ To add them: start a model server, then
`python scripts/sweep.py --data data/dev --runs results/runs --baseline --workers 4` and `python scripts/baselines_report.py`.
<!-- dev-models:end -->

## Lite split (132 scenarios)

<!-- lite-table:begin -->
| Agent | Overall | Un-gated | Crit. rate | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | L1 | L2 | L3 | L4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| oracle (scripted) | **100.0** | 100.0 | 0% | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 1.00 | 1.00 | 1.00 | 1.00 |
| rule (scripted) | **33.2** | 49.6 | 31% | 34 | 30 | 61 | 80 | 11 | 25 | 42 | 9 | 28 | 0.49 | 0.38 | 0.42 | 0.26 |
| naive (scripted) | **11.7** | 17.1 | 44% | 30 | 26 | 16 | 48 | 0 | 0 | 0 | 0 | 0 | 0.15 | 0.14 | 0.19 | 0.16 |
| null (scripted) | **0.0** | 0.4 | 32% | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.00 |
| qwen3-8b | **45.0** | 54.6 | 17% | 49 | 37 | 27 | 78 | 73 | 84 | 0 | 37 | 8 | 0.54 | 0.54 | 0.38 | 0.48 |
| llama3.1-8b | **44.3** | 52.1 | 16% | 20 | 24 | 44 | 71 | 90 | 75 | 0 | 45 | 9 | 0.49 | 0.44 | 0.44 | 0.44 |
| gemma3-4b | **27.6** | 40.7 | 26% | 13 | 7 | 25 | 78 | 24 | 90 | 0 | 0 | 20 | 0.40 | 0.33 | 0.30 | 0.37 |
<!-- lite-table:end -->

Critical failures (episodes):

<!-- lite-critical:begin -->
| Agent | Episodes | C1 missed red flag | C2 wrong medical fact | C3 privacy | C4 injection obeyed |
|---|---|---|---|---|---|
| oracle (scripted) | 132 | 0 | 0 | 0 | 0 |
| rule (scripted) | 132 | 3 | 38 | 0 | 0 |
| naive (scripted) | 132 | 6 | 52 | 0 | 0 |
| null (scripted) | 132 | 6 | 36 | 0 | 0 |
| qwen3-8b | 132 | 2 | 20 | 2 | 0 |
| llama3.1-8b | 132 | 3 | 18 | 2 | 0 |
| gemma3-4b | 132 | 0 | 33 | 2 | 0 |
<!-- lite-critical:end -->

Exact model ids and run records:

<!-- lite-models:begin -->
| Agent | Model id on the server | Run record | Notes |
|---|---|---|---|
| qwen3-8b | `qwen3:8b` | `20261115-020832-qwen3-8b` | thinking switched off (reasoning_effort none) so runs stay comparable and fast |
| llama3.1-8b | `llama3.1:8b` | `20261115-021831-llama3.1-8b` |  |
| gemma3-4b | `gemma3:4b` | `20261115-023747-gemma3-4b` |  |
<!-- lite-models:end -->

## Reading the numbers

<!-- reading:begin -->
What these runs show (data v1.3.0, lite split; qwen2.5-7b and llama3.2-3b were still running when this was written; the v1.2.0
numbers are in the git history):

- **The benchmark separates agents.** qwen3-8b 45.0 and llama3.1-8b 44.3 are above the model-free rule agent (33.2); gemma3-4b
  (27.6) is below it; the oracle reaches 100. The safety gates cost the models 8-13 points (gated versus un-gated).
- **Language is easier than action.** Summaries (T6 0.75-0.90) and, for qwen3 and llama3.1, interpretation (T5 0.73-0.90) are
  the strongest tasks; hospital search on the real index (T1 0.13-0.49) and fresh-versus-stale information (T2 0.07-0.37) are weak:
  models rarely check live status and recommend places that are closed at the time, too far, tertiary without a referral, or
  that take no outpatients (a long-term care hospital).
- **T7 (memory) is 0 for every model**, as on v1.2.0: every episode fails the allergy gate (C2), because models do not read
  their memory back in the last session.
- **T9 (clinic choice from visit history, the team's items) is the hardest task**: 0.08-0.20. qwen3-8b and llama3.1-8b ask the
  student a question on items the record already decides (6-7 of 16); gemma3-4b almost never asks, so it misses the ambiguous
  items but hits more control items. All three pick clinics they reach less than 30 minutes before closing.
- **gemma3-4b's T5 (0.24 gated, 0.69 un-gated)**: 75% of its interpretation episodes trip the medical-fact gate.

Caveats: lite has 132 scenarios (8-24 per task), so differences of a few points between models are not meaningful; one trial
each; quantised models on one shared GPU; no prompt tuning. Run the dev split (`python scripts/sweep.py --data data/dev
--baseline --workers 4`, then `python scripts/baselines_report.py`) before quoting model numbers.
<!-- reading:end -->
