# Reference baselines

Scores of the scripted reference agents (dev and lite) and of small open models (lite), all on data v1.2.0. The tables between the markers are generated
from the run records in `results/runs/` (dev) and `results/lite-runs/` (lite) by `python scripts/baselines_report.py`; do not edit
them by hand. These rows are references for calibrating difficulty; they never take a rank on the leaderboard.

## How the open models were run

<!-- setup:begin -->
- **Server:** Ollama 0.40.13 (OpenAI-compatible endpoint), one NVIDIA RTX 3090 (24 GB, driver 580.126.09) shared with other
  jobs, `OLLAMA_CONTEXT_LENGTH=16384`, `OLLAMA_NUM_PARALLEL=4`, one model loaded at a time.
- **Client:** `python scripts/sweep.py --data data/<split> --baseline --workers 4` (the adapter `openai:` with temperature 0,
  seed 0, at most 1,500 reply tokens, stop after `</tool_call>`); `--workers` does not change scores.
- **Models** (Ollama library tags, all Q4_K_M):

  | Name in the tables | Tag | Ollama id | Parameters |
  |---|---|---|---|
  | qwen2.5-7b | `qwen2.5:7b` | 845dbda0ea48 | 7.6B |
  | llama3.1-8b | `llama3.1:8b` | 46e0c10c039e | 8.0B |
  | qwen3-8b | `qwen3:8b` (thinking off: `reasoning_effort: none`) | 500a1f067a9f | 8.2B |
  | gemma3-4b | `gemma3:4b` | 68ceab7e468a | 3.9B |
  | mistral-7b (not completed: stopped at 114 of 116 lite episodes, very slow on long T7/T8 dialogues) | `mistral:7b` | 6577803aa9a0 | 7.2B |
  | exaone3.5-7.8b (not run yet; Korean-specialised; research licence) | `exaone3.5:7.8b` | c7c4e3d1ca22 | 7.8B |
  | llama3.2-3b | `llama3.2:3b` | a80c4f17acd5 | 3.2B |
- **Prompting:** none beyond the benchmark's own task cards; no system prompt, no examples, no retries. These are what an
  untuned agent gets, not the best a model can do.
- One trial per scenario. Model outputs are not bit-exact across machines (`docs/REPRODUCIBILITY.md`); expect differences of a
  few points between runs of the same model on other hardware.
<!-- setup:end -->

## Dev split (832 scenarios)

Overall and task columns are gated scores x100 (a critical failure zeroes the episode); tier columns are gated means (0-1).

<!-- dev-table:begin -->
| Agent | Overall | Un-gated | Crit. rate | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | L1 | L2 | L3 | L4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| oracle (scripted) | **100.0** | 100.0 | 0% | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 1.00 | 1.00 | 1.00 | 1.00 |
| rule (scripted) | **35.7** | 51.4 | 32% | 36 | 28 | 63 | 86 | 15 | 39 | 34 | 4 | 0.54 | 0.48 | 0.36 | 0.36 |
| naive (scripted) | **13.2** | 19.0 | 49% | 31 | 25 | 16 | 39 | 0 | 6 | 0 | 0 | 0.17 | 0.18 | 0.18 | 0.18 |
| null (scripted) | **0.0** | 0.5 | 36% | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.00 |
<!-- dev-table:end -->

Critical failures (episodes):

<!-- dev-critical:begin -->
| Agent | Episodes | C1 missed red flag | C2 wrong medical fact | C3 privacy | C4 injection obeyed |
|---|---|---|---|---|---|
| oracle (scripted) | 832 | 0 | 0 | 0 | 0 |
| rule (scripted) | 832 | 11 | 254 | 0 | 0 |
| naive (scripted) | 832 | 58 | 351 | 0 | 0 |
| null (scripted) | 832 | 58 | 240 | 0 | 0 |
<!-- dev-critical:end -->

Exact model ids and run records:

<!-- dev-models:begin -->
_No open-model run on this split yet._ To add them: start a model server, then
`python scripts/sweep.py --data data/dev --runs results/runs --baseline --workers 4` and `python scripts/baselines_report.py`.
<!-- dev-models:end -->

## Lite split (116 scenarios)

<!-- lite-table:begin -->
| Agent | Overall | Un-gated | Crit. rate | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | L1 | L2 | L3 | L4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| oracle (scripted) | **100.0** | 100.0 | 0% | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 1.00 | 1.00 | 1.00 | 1.00 |
| rule (scripted) | **33.7** | 51.5 | 36% | 33 | 30 | 63 | 80 | 11 | 25 | 45 | 0 | 0.51 | 0.37 | 0.44 | 0.28 |
| naive (scripted) | **13.6** | 19.6 | 50% | 32 | 24 | 17 | 48 | 0 | 0 | 0 | 0 | 0.19 | 0.16 | 0.21 | 0.17 |
| null (scripted) | **0.0** | 0.5 | 36% | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00 | 0.00 | 0.00 | 0.00 |
| qwen3-8b | **50.1** | 65.2 | 19% | 46 | 48 | 29 | 81 | 66 | 98 | 0 | 43 | 0.74 | 0.52 | 0.57 | 0.41 |
| llama3.1-8b | **47.0** | 59.9 | 23% | 51 | 25 | 47 | 69 | 77 | 76 | 0 | 23 | 0.55 | 0.55 | 0.47 | 0.49 |
| qwen2.5-7b | **37.5** | 55.3 | 28% | 46 | 29 | 23 | 77 | 48 | 67 | 0 | 15 | 0.64 | 0.46 | 0.38 | 0.28 |
| gemma3-4b | **35.7** | 50.5 | 31% | 61 | 31 | 31 | 73 | 24 | 84 | 0 | 0 | 0.52 | 0.48 | 0.43 | 0.35 |
| llama3.2-3b | **21.5** | 44.5 | 38% | 28 | 37 | 12 | 77 | 6 | 36 | 0 | 0 | 0.40 | 0.25 | 0.30 | 0.27 |
<!-- lite-table:end -->

Critical failures (episodes):

<!-- lite-critical:begin -->
| Agent | Episodes | C1 missed red flag | C2 wrong medical fact | C3 privacy | C4 injection obeyed |
|---|---|---|---|---|---|
| oracle (scripted) | 116 | 0 | 0 | 0 | 0 |
| rule (scripted) | 116 | 3 | 39 | 0 | 0 |
| naive (scripted) | 116 | 6 | 52 | 0 | 0 |
| null (scripted) | 116 | 6 | 36 | 0 | 0 |
| qwen3-8b | 116 | 1 | 20 | 1 | 1 |
| llama3.1-8b | 116 | 3 | 23 | 2 | 3 |
| qwen2.5-7b | 116 | 2 | 30 | 0 | 1 |
| gemma3-4b | 116 | 1 | 34 | 1 | 1 |
| llama3.2-3b | 116 | 1 | 43 | 0 | 0 |
<!-- lite-critical:end -->

Exact model ids and run records:

<!-- lite-models:begin -->
| Agent | Model id on the server | Run record | Notes |
|---|---|---|---|
| qwen3-8b | `qwen3:8b` | `20261114-043230-qwen3-8b` | thinking switched off (reasoning_effort none) so runs stay comparable and fast |
| llama3.1-8b | `llama3.1:8b` | `20261114-043825-llama3.1-8b` |  |
| qwen2.5-7b | `qwen2.5:7b` | `20261114-042644-qwen2.5-7b` |  |
| gemma3-4b | `gemma3:4b` | `20261114-045539-gemma3-4b` |  |
| llama3.2-3b | `llama3.2:3b` | `20261114-042203-llama3.2-3b` |  |
<!-- lite-models:end -->

## Reading the numbers

<!-- reading:begin -->
What these runs show (lite split; the dev split has only the scripted rows so far):

- **The benchmark separates agents.** Untuned 3-8B models span 21.5 to 50.1 on lite, around the model-free rule agent (33.7); the
  oracle reaches 100. The safety gates cost every model 13-23 points (gated versus un-gated).
- **T7 (memory) is 0 for every model.** Reading full transcripts (qwen3-8b, qwen2.5-7b, llama3.1-8b) shows why: models store the
  user's facts with `memory_put` (qwen3-8b) or only claim to have stored them (llama3.1-8b), but none reads memory back in the
  final session, so the allergy question is answered from nothing and fails the allergy gate. This is the behaviour T7 tests.
- **T2 (fresh versus stale information) stays low** because the models rarely call `get_live_status` before recommending, so
  closures and shortened hours are missed: the trap works as designed.
- **T5 (interpretation) failures are mostly real translation errors**: native Korean day counts misread (사흘, three days, given
  as four), allergens mistranslated (오징어, squid, for shellfish), romanised or untranslated Korean. qwen3-8b and llama3.1-8b
  reach 66 and 77.
- **T8 (journey)** combines all of the above; its follow-up step is usually booked on the naive date even when the hospital is
  closed that day.
- **Tiers** mostly fall from L1 to L4.

Caveats: lite has 116 scenarios (8-24 per task), so differences of a few points between models are not meaningful; one trial
each; quantised models on one shared GPU; no prompt tuning. Run the dev split (`python scripts/sweep.py --data data/dev
--baseline --workers 4`, then `python scripts/baselines_report.py`) before quoting model numbers. A fairness-twin run on a
model (`scripts/fairness_twins.py --agent openai:<model> --control`) was started but not completed; the scripted agents show a gap
of 0.0000 (`results/fairness_rule.txt`).
<!-- reading:end -->
