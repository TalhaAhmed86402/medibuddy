# MediBuddy-Bench

A benchmark for **MediBuddy-style agents**: assistants that help an international resident of Korea
(1) choose a hospital using current information and personal preferences, (2) interpret a Korean ↔ English
consultation turn by turn, (3) summarise the visit, and (4) remember preferences across visits.

Course project: ESW4028_41 (Agentic AI, SKKU), Phase 2. All data is **synthetic** (fictional hospitals and patients);
the benchmark never produces or evaluates real medical advice. Scoring is deterministic and offline (no LLM judge).

**Pick your path:** [I want to test my agent](#2-test-your-agent) · [I want to compare many models](#4-compare-many-models) ·
[I run the leaderboard](#7-running-the-leaderboard-maintainers) · [Something broke](#9-troubleshooting)

---

## 1. Install (two ways, same result)

Works on Linux, macOS and Windows. The benchmark core needs only **Python ≥ 3.10 and the standard library**.

**A. From a clone (recommended for development)**
```bash
git clone https://github.com/TalhaAhmed86402/medibuddy.git medibuddy-bench && cd medibuddy-bench
python -m medibuddy_bench doctor        # checks Python, data integrity, model server; "FAIL" lines must be fixed
python -m pytest -q tests               # optional: pip install pytest first (~1 min)
```
Optional, only for the A2A service (students' agents over A2A): use a clean virtual environment, because a2a-sdk 1.x is not supported.
```bash
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-a2a.lock                 # exact tested versions (requirements-a2a.txt = loose pins)
```

**B. Docker (identical environment everywhere)**
```bash
docker build -t medibuddy-bench .
docker run --rm medibuddy-bench doctor
docker run --rm medibuddy-bench run --agent oracle --data data/lite     # must print Overall (gated): 100.0
```
All commands below work as `python -m medibuddy_bench <command>` or `docker run --rm medibuddy-bench <command>`.
(`pip install -e .` also gives a `medibuddy` command.) On Windows use these commands instead of `make`.

Sanity check of the whole install, ~1 minute:
```bash
python -m medibuddy_bench run --agent oracle --data data/lite --no-transcripts   # 100.0
python -m medibuddy_bench run --agent rule   --data data/lite --no-transcripts   # 33.7 on lite (35.7 on dev), a template agent with no LLM
```

## 2. Test your agent

An agent receives a task card plus patient/doctor messages as text, may call tools, and replies with text and an optional
`<answer>{json}</answer>`. **Any agent that can answer text with text can be evaluated.** Choose the way that fits yours
(details and wire formats: [`docs/INTEGRATION.md`](docs/INTEGRATION.md)):

| Your agent is… | Command (`--agent …`) |
|---|---|
| a model on any **OpenAI-compatible server** (Ollama, vLLM, llama.cpp, LM Studio, SGLang, hosted APIs) | `openai:<model>` with `OPENAI_BASE_URL`, `OPENAI_API_KEY` set |
| a **Python class** (`Agent` subclass) | `mypkg.myagent:MyAgent` |
| a **web service** (any language) | `http://host:port/chat` |
| a **program** (any language, no server) | `cmd:python my_agent.py` (JSON lines on stdin/stdout) |
| an **A2A agent** | start the service, then `assess` (section 3) |
| a built-in reference | `null`, `naive`, `rule`, `oracle`; wrap any agent with `guarded:<spec>` |

Example, scoring a local model on the small split and recording it for the leaderboard:
```bash
export OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=none        # Windows PowerShell: $env:OPENAI_BASE_URL="..."
python -m medibuddy_bench run --agent openai:qwen2.5:7b --name my-qwen --model qwen2.5:7b \
    --data data/lite --no-transcripts --save-run results/runs --checkpoint results/.checkpoints/my-qwen.jsonl
```
While it runs you see one line per scenario with an ETA. If it is interrupted, run the **same command again**: it resumes.
`--workers 4` scores four episodes at once when the server handles parallel requests (vLLM, Ollama with `OLLAMA_NUM_PARALLEL=4`,
hosted APIs); the scores are the same as a sequential run.
Smoke test first with `--tasks T1 --limit 3`. Closed models (`anthropic:<model>`, hosted OpenAI-compatible APIs) use the same flow;
those adapters are tested only against mocked HTTP, not live services.

**Splits.** `data/lite` (116 scenarios, minutes) for development; `data/dev` (832 scenarios) is the official public split that the
leaderboard ranks; the graded `test` split is hidden. Only a run over the **whole** split is ranked.

**Tasks and weights** (full detail: [`docs/TASKS.md`](docs/TASKS.md)): T1 hospital search 15 · T2 fresh vs stale information 10 ·
T3 clarifying questions 10 · T4 triage 10 · T5 turn-by-turn interpretation 20 · T6 visit summary 10 · T7 memory across visits 15 ·
T8 full journey 10. Each scenario has four difficulty tiers (L1 explicit … L4 colloquial, distracted, pressured).
**Critical failures** (C1 missed red flag, C2 wrong medical fact, C3 privacy breach, C4 obeyed an injected instruction) zero the
episode, so the headline *Overall (gated)* score cannot hide a dangerous answer. The un-gated score is reported next to it.

## 3. The A2A workflow (what students use)

```bash
# terminal 1: the benchmark service
python -m medibuddy_bench serve --port 9009 --data data/lite
# terminal 2: your agent (here the reference agent wrapping a model server; replace with your own A2A agent)
OPENAI_BASE_URL=http://localhost:11434/v1 MEDIBUDDY_MODEL=qwen2.5:7b python -m medibuddy_bench agent --backend openai --port 9019
# terminal 3: start an assessment
python -m medibuddy_bench assess --purple http://localhost:9019 --name my-agent --model qwen2.5:7b
python -m medibuddy_bench leaderboard --data data/lite
```
Or with Docker Compose (copy `.env.example` to `.env` and point it at your model server): `docker compose up --build -d`, then
`docker compose run --rm assess`. The A2A message format follows the public AgentBeats green-agent template: one JSON text message
in (`participants`, `config`), a JSON `result` row plus readable reports out ([`docs/AGENT_INTERFACE.md`](docs/AGENT_INTERFACE.md)).
Deploying on AgentBeats (image, manifest, shards, leaderboard queries): [`docs/AGENTBEATS.md`](docs/AGENTBEATS.md).

## 4. Compare many models

`sweep` scores a list of models one after another on one server, resumes after interruptions, skips models the server does not
have, and rebuilds the leaderboard. It needs only an OpenAI-compatible endpoint, so it is not tied to Ollama, an OS or a GPU.
```bash
python -m medibuddy_bench sweep --list                          # which configured models does the server have?
python -m medibuddy_bench sweep --data data/lite --max-vram 8   # run everything that fits an 8 GB GPU
```
Model list and sizes: `configs/sweep.json`. Setting up a fresh GPU machine from zero: [`docs/SETUP_GPU_MACHINE.md`](docs/SETUP_GPU_MACHINE.md).

## 5. Read the results

> **Rules in one line:** hospital facts come only from the benchmark tools (no web lookups in place of them), any model or reasoning aid is fine,
> and `dev` results are self-reported while official results come from the hidden `test` split. Full text: [`docs/INTEGRATION.md`](docs/INTEGRATION.md#rules-every-agent-is-held-to).

Every assessment writes a **run record** to `results/runs/<run_id>/` (`run.json` with the full report, scope, data hash, machine
and git commit; `episodes.jsonl`; `report.md`). `leaderboard/LEADERBOARD.md` is generated from those records:
ranked agents (full split, official data version), reference baselines, and a "Not ranked" table that states why a run is excluded
(partial scope, stale data). Ranking and tie-break rules: [`docs/LEADERBOARD.md`](docs/LEADERBOARD.md).
<!-- baselines:begin (generated by scripts/baselines_report.py; do not edit by hand) -->
Reference results (data v1.2.0; generated from the run records by `scripts/baselines_report.py`; setup and per-task tables in [`docs/BASELINES.md`](docs/BASELINES.md)).

Dev split (832 scenarios):

| Agent | Overall (gated) | Un-gated |
|---|---|---|
| oracle (scripted) | **100.0** | 100.0 |
| rule (scripted) | **35.7** | 51.4 |
| naive (scripted) | **13.2** | 19.0 |
| null (scripted) | **0.0** | 0.5 |

Open models served locally, lite split (116 scenarios; dev runs not yet made):

| Agent | Overall (gated) | Un-gated |
|---|---|---|
| oracle (scripted) | **100.0** | 100.0 |
| rule (scripted) | **33.7** | 51.5 |
| qwen3-8b | **50.1** | 65.2 |
| llama3.1-8b | **47.0** | 59.9 |
| qwen2.5-7b | **37.5** | 55.3 |
| gemma3-4b | **35.7** | 50.5 |
| llama3.2-3b | **21.5** | 44.5 |
<!-- baselines:end -->

## 6. Reproducibility

Data is generated from a seed and is **byte-identical on every machine** (checked on Linux, Python 3.11/3.12/3.13; CI repeats it on
macOS and Windows): `python -m medibuddy_bench verify --data data/dev --rebuild`. Scoring has no randomness. Dependencies of the
service are pinned (`requirements-a2a.lock`), and the Docker image fails to build if its data differs from its manifest.
Model outputs are not bit-exact across hardware even at temperature 0 with a fixed seed, so each run record stores the model,
server URL, machine and commit; use `--trials 3` (pass^3) to measure consistency. Details: [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md).

## 6b. What is in the data

<!-- stats:begin (generated by scripts/dataset_stats.py --summary; do not edit by hand) -->
1,200 hospitals in 47 districts across 12 regions, 12 specialties, 9 hospital languages, 886 dated notices; 832 scenarios in the dev split.

| Hospital tier | Hospitals | Share |
|---|---|---|
| clinic | 811 | 67.6% |
| hospital | 252 | 21.0% |
| general_hospital | 91 | 7.6% |
| tertiary | 46 | 3.8% |

| Region | Districts | Hospitals | Share |
|---|---|---|---|
| Seoul | 25 | 671 | 55.9% |
| Suwon | 4 | 135 | 11.2% |
| Incheon | 3 | 80 | 6.7% |
| Seongnam | 2 | 69 | 5.8% |
| Busan | 3 | 69 | 5.8% |
| Goyang | 2 | 38 | 3.2% |
| Daejeon | 2 | 35 | 2.9% |
| Daegu | 2 | 30 | 2.5% |
| Bucheon | 1 | 22 | 1.8% |
| Ansan | 1 | 19 | 1.6% |
| Yongin | 1 | 17 | 1.4% |
| Anyang | 1 | 15 | 1.2% |

| Hospital feature | Share of hospitals |
|---|---|
| Female doctor available | 51.6% |
| Walk-ins accepted | 92.0% |
| Open on Saturday / Sunday | 68.2% / 5.8% |
| Open on public holidays | 4.2% |
| Lunch break | 66.2% |
| 24-hour emergency room | 11.4% |
| Interpreter service | 15.1% |
| Names at least one foreign language | 50.8% |
| Price level 1 / 2 / 3 | 41.4% / 47.7% / 10.9% |
| Mean rating (min to max) | 3.80 (2.2 to 5.0) |
| Static record last verified | 2025-01-01 to 2026-10-25 |

| Scenario | n | L1 | L2 | L3 | L4 |
|---|---|---|---|---|---|
| T1 Hospital search | 120 | 28 | 31 | 31 | 30 |
| T2 Fresh vs stale information | 96 | 24 | 24 | 24 | 24 |
| T3 Clarifying questions | 96 | 24 | 24 | 24 | 24 |
| T4 Emergency and urgency triage | 160 | 38 | 44 | 41 | 37 |
| T5 Turn-by-turn interpretation | 120 | 30 | 30 | 30 | 30 |
| T6 Visit summary | 120 | 30 | 30 | 30 | 30 |
| T7 Memory across visits | 72 | 18 | 18 | 18 | 18 |
| T8 Full journey | 48 | 12 | 12 | 12 | 12 |

| Hospital-choice scenarios (T1-T3) | Share |
|---|---|
| Maximum distance (km), 3 / 5 / 8 / 12 | 44.2% / 27.2% / 16.3% / 12.2% |
| Price cap stated (level 1 / 2 / 3) | 16.3% / 23.4% / 16.7%; none: 43.6% |
| Needs a hospital language | 35.9% |
| Needs a female doctor | 37.2% |
| Has a flexible (soft) preference | 31.7% |
| Names a hospital to avoid | 28.8% |
| Has a referral letter | 0.6% |
| Contains a planted injected instruction | 32.4% |
| Visit weekday Mon-Fri / Sat / Sun | 90.4% / 9.6% / 0.0% |
| Valid hospitals per scenario (min / median / max) | 2 / 7 / 15 |
| Complaints used | 22, all mild (emergencies are tested in T4) |

Full breakdown: [`docs/DATASET_STATS.md`](docs/DATASET_STATS.md). Both are generated by `scripts/dataset_stats.py` from the `dev` split and checked by `tests/test_docs.py`.
<!-- stats:end -->

## 7. Running the leaderboard (maintainers)

1. Build the hidden split once with a private seed (never commit it): `python -m medibuddy_bench build --split test --seed <SECRET> --out /private/test`.
   Add `--phrases /private/heldout_phrases.json` to give the hidden split wording that students cannot see in this repo (format and workflow: [`docs/HELDOUT_PHRASES.md`](docs/HELDOUT_PHRASES.md)).
2. Serve it: `python -m medibuddy_bench serve --data /private/test --runs-dir /private/runs`.
3. Publish: `python -m medibuddy_bench leaderboard --runs /private/runs --data /private/test --out leaderboard`.
4. After any scorer or data change follow the versioning policy in [`CHANGELOG.md`](CHANGELOG.md): bump `VERSION`, regenerate
   (`make data SPLIT=dev`, `make data SPLIT=lite`), `make baselines SPLIT=dev`, `python scripts/dataset_stats.py --write`,
   `python scripts/baselines_report.py`; old runs become "stale" automatically.
5. Student questions and disputes: [`docs/SUPPORT.md`](docs/SUPPORT.md) (issue templates in `.github/ISSUE_TEMPLATE/`).

## 8. Repository map

| Path | Purpose |
|---|---|
| `medibuddy_bench/gen/` | seeded generators: the world (1,200 hospitals, 47 districts) and all 8 tasks |
| `medibuddy_bench/scoring/` | deterministic scorers and aggregation (gating, pass^k, tiers) |
| `medibuddy_bench/agents/` | reference agents, model adapters (`llm_*`), plug-in adapters (`adapters.py`), `registry.py` (the `--agent` forms) |
| `medibuddy_bench/a2a/` | A2A benchmark service (green), reference agent (purple), client |
| `medibuddy_bench/{runner,execute,results,leaderboard,sweep,verify,cli}.py` | episode loop, checkpointed runs, run records, leaderboard, model sweep, data checks, CLI |
| `scripts/` | thin command-line wrappers (`run_benchmark`, `sweep`, `leaderboard`, `assess`, `verify_data`, `dataset_stats`, `fairness_twins`, `import_real_data`; optional checks `korean_lint`, `text_realism`) |
| `data/lite`, `data/dev` | public splits; `data/review/` has the CSVs for native-speaker and clinician review |
| `examples/` | minimal `http` and `cmd` agents to copy |
| `configs/sweep.json` | models for the sweep |
| `docs/` | TASKS, INTEGRATION, AGENT_INTERFACE, AGENTBEATS, FAQ, SUPPORT, BASELINES, SETUP_GPU_MACHINE, REPRODUCIBILITY, LEADERBOARD, DATA_CARD, DATASET_STATS, REVIEW_GUIDE, HELDOUT_PHRASES, EXTERNAL_RESOURCES, SUBMISSION, BUILD_LOG |
| `DESIGN.md`, `DECISIONS.md`, `CHANGELOG.md` | what / why / how, the choices made on open questions, and what changed in each data version |
| `results/runs/`, `results/lite-runs/`, `leaderboard/` | reference run records (dev, lite) and the generated dev leaderboard |
| `Dockerfile`, `docker-compose.yml`, `.github/workflows/` | reproducible image, one-machine stack, cross-OS CI and image publishing |
| `amber-manifest.json5`, `agentbeats/` | AgentBeats manifests (green, reference purple), purple image, leaderboard scenario (`docs/AGENTBEATS.md`) |

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| `doctor` says data FAIL | the checkout is damaged or edited; `git checkout data/` or `verify --data data/dev --rebuild` |
| A2A commands: `No module named a2a.server.apps` | a2a-sdk 1.x is installed; use a clean venv with `requirements-a2a.lock` |
| Ollama run scores oddly low | Ollama's default context is 4096 tokens; use `ollama_ctx` in `configs/sweep.json` (the sweep handles it) or a Modelfile with `PARAMETER num_ctx 16384` |
| Ollama: `address already in use` | the Ollama app/service is already running; just use it (it restarts itself if killed) |
| Model ignores `<tool_call>` / `<answer>` | expected for small models; it costs points by design. Read a transcript (omit `--no-transcripts`) |
| Reasoning model is slow or answers are cut off | its thinking counts against the reply budget; `MEDIBUDDY_EXTRA_BODY='{"reasoning_effort": "none"}'` switches it off where supported |
| A run takes hours | `--workers 4` with a server that handles parallel requests |
| A correct answer was scored wrong | open a *scoring dispute* issue with the episode id ([`docs/FAQ.md`](docs/FAQ.md)) |
| Docker cannot reach the model server on the host | use `host.docker.internal` (the compose file maps it on Linux too) |
| Windows: `make` not found | use the `python -m medibuddy_bench …` commands; `make` is only a convenience |

## 10. Status and honest limits

Read `DESIGN.md` §8 and "Scope decisions" before quoting numbers. What is and is not established (data v1.2.0, `CHANGELOG.md`):

- **Checked by tests and CI:** deterministic data (byte-identical rebuilds), no gold in what agents see, every safety gate trips on a
  deliberately unsafe agent, scores identical across adapters and with `--workers`, the A2A service end to end (a2a-sdk 0.3.26).
- **Measured:** the scripted ladder (null 0.0 < naive 13.2 < rule 35.7 < oracle 100.0) and small open models served locally on
  the lite split (`docs/BASELINES.md`); model runs on dev are still to do. Larger and closed models have not been run; the closed-model adapters are tested only against mocked HTTP.
- **Not yet reviewed by people:** the Korean doctor text (native speaker) and the triage labels (clinician); see
  `docs/REVIEW_GUIDE.md` and `docs/EXTERNAL_RESOURCES.md`.
- **Synthetic by design:** fictional hospitals in real districts, simplified rules, patients who write English only, wording from
  author-written paraphrase pools (the hidden split can add private wording). Scores are against this world, not real Korea.
- **Platform:** the A2A service follows the public AgentBeats conventions (`docs/AGENTBEATS.md`) but has not been run on the live
  platform; the Docker image is built and smoke-tested by CI, not against an external purple agent.
