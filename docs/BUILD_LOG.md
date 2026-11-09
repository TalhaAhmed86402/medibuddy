# Build log (how / why / what)

## Order of work
1. Read the Phase-2 requirement and the proposal design; chose 8 tasks mirroring the product journey (search → live info → clarify → triage → interpret → summarise → remember → end to end).
2. Wrote `knowledge.py` (domain lexicons: districts, specialties, complaints, drugs, allergens, diagnoses, tests, Korean/English topic phrases) and `rules.py` (the world's rule document).
3. `world.py`: hospital world, live status, constraint violation logic (`violations`), valid set / near misses / best ordering. One function decides truth for generator, scorer and oracle, so they cannot drift apart.
4. Generators per task (`gen/`), each producing public and gold parts; `build.py` assembles splits and repairs scenarios invalidated by later notices.
5. Fact engine (`scoring/facts.py`) with EN/KO normalisers; then per-task scorers; aggregation with gating and pass^k.
6. Runner, tools, patient simulator, text protocol, baselines and saboteurs.
7. Tests, pilot, docs, A2A adapter.

## Problems found and fixed
| Problem | Fix |
|---|---|
| Korean "이레" matched inside "타이레놀" | lookbehind; dropped ambiguous words |
| "1/2 pill" read as "2 pill" | lookbehind |
| wrong duration classified as missing | day facts do not use `claimed` |
| slow build; T8 could not be repaired | caching; `choice_task` in `finalize_choice` |
| single-turn finality would punish asking agents | a reply naming hospitals is final; 4-turn (8 for T3) caps |
| T7 hygiene checks gave free credit for doing nothing | converted to gates only |
| Triage fallback labelled empty text as self-care | new `none` level scores 0 |
| Rule baseline scored 1.00 on T1–T3, T7 (template-solvable) | tiered phrasing (month-name dates L3, relative dates + informal L4) → T1 0.63, T2 0.62 |
| duplicate scenario id after repair (T1-dev-0039) | renumber ids after repair; `test_ids_unique` |
| a2a-sdk 1.x lacks `a2a.server.apps` | adapter's template imports isolated; documented as unverified |

## Verification
`python3 -W ignore -m unittest discover -s tests` → 12 tests (determinism, leakage, unique ids, solvable gold, oracle/null/naive/ordering, 11 saboteur gates, protocol tool loop) + `tests/test_facts.py` (34).
Saboteur gates observed on dev: flip_freq / drop_negation / add_dose / wrong_allergy_ko → C2 on T5 (and T8); invent_dx / wrong_follow → C2 on T6 (and T8);
canary → C4 on T1/T2/T3/T7/T8; no_escalation → C1 on all 39% emergency T4 cases; keep_deleted / store_id → C3, blood_guess → C2 on T7.

## Not done
LLM baselines; native-speaker and clinician review; paraphrase augmentation; a real A2A server entry point and a live-platform test; `docs/ISSUES.md`.


## v0.2 (2026-10-30) hard vs soft preferences
world.py rewritten with docstrings and runnable examples (52 doctests); soft preferences added to generator, scorer, task card,
rule and oracle agents; dev regenerated (soft: T1 17/40, T2 15/32, T3 6/32). Oracle 1.00 everywhere; rule T1 .65, T2 .63, T3 .81,
pass^1 .61; 46 pytest checks pass. Saboteurs not rerun after this change. Not yet soft: memory (T7), journey (T8).


## v1.0.0 (2026-11-09) final-submission build
- World 320 -> 1,200 hospitals; 47 districts in 12 regions (Seoul, Gyeonggi cities, Incheon, Busan, Daegu, Daejeon).
- Languages 6 -> 9 (ar, th, uz). Hospital languages follow a two-population model calibrated on the KHIDI list (see DATA_CARD).
- Patients: 25 nationalities drawn with resident-mix weights; 60 first names; 10 more complaints (22 total); 8 more triage cases (29 total).
- Splits: dev 832 scenarios, lite 108, test = organiser-built with a secret seed (not in the repo).
- New scripts: `dataset_stats.py` (-> docs/DATASET_STATS.md), `fairness_twins.py` (name/nationality swap; gap 0.0000 for the scripted agents).
- Docstring examples now run in `tests/test_doctests.py` against `data/dev`; hospital ids in them were re-pinned to the new world.
- Baselines on dev: null 1.0, naive 15.0, rule 65.8, oracle 100.0; 46 tests + 25 doctest blocks pass; rebuild is byte-identical.
- Checked: unique ids, no gold in public view, determinism. Saboteur gates covered by the test suite (mini split).
- A2A: `medibuddy_bench/a2a/` (client, green server, reference purple server), `requirements-a2a.txt`, `Dockerfile`, `scenario.toml` commands; tested with `tests/test_a2a.py` (a2a-sdk 0.3.26, clean venv). a2a-sdk 1.x is not supported (server API removed).
- Workflow: run records (`medibuddy_bench/results.py`), `scripts/leaderboard.py` (ranks full-split runs only; partial/stale listed with reasons), `scripts/assess.py`, `Makefile`, `docs/QUICKSTART.md`, fake Ollama server `tests/mock_openai.py` for a GPU-free pipeline test.
- Live progress line per episode and `--checkpoint` resume in `scripts/run_benchmark.py` (also used by `make ollama`); `Runner.run(done=..., progress(ep, i, total))`; `tests/test_resume.py`.

## v1.0.x platform-agnostic and reproducible tooling (2026-11-09)
- Adapters: `http:`, `cmd:`, `guarded:`, `openai:`, `anthropic:`, `package:Class` resolved by `agents/registry.py`; examples in `examples/`.
- `sweep` (any OpenAI-compatible server, resumable, `configs/sweep.json`), `execute.py` (checkpointed runs), `leaderboard.py`, `results.py` (environment metadata), `verify.py`.
- CLI `python -m medibuddy_bench <command>` and `pyproject.toml`; lock file `requirements-a2a.lock`; `Dockerfile`, `docker-compose.yml`, CI matrix (Linux/macOS/Windows x Python 3.10/3.12/3.13 + Docker).
- Verified here: tests on Python 3.11/3.12/3.13, dev rebuild identical after a lint cleanup, image contents simulated from the lock file in a clean venv. Not runnable in the authoring sandbox (Docker Hub unreachable; no Python 3.10; Linux only) but verified by CI on 2026-11-09 (run #3, all green): Docker build with the build-time data check, Linux/macOS/Windows x Python 3.10/3.12/3.13, and the A2A job.
- Small-model robustness (found with llama3.2:3b via Ollama): tolerant tool-call parser, stop sequences after a tool call, `MEDIBUDDY_TRACE=1`, did-you-mean district errors, compact `list_districts`, repeat-call guard. Tool output only; scenarios, scoring and dataset hashes unchanged.
- Lint cleanup: unused imports and dead locals removed (no data change: dev rebuilt, hashes equal).
