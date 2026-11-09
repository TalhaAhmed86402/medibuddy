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
python -m medibuddy_bench run --agent rule   --data data/lite --no-transcripts   # ~66, a template agent with no LLM
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
`docker compose run --rm assess`. The A2A message format is defined by this project, not by a course template: one JSON
text message in, a report out ([`docs/AGENT_INTERFACE.md`](docs/AGENT_INTERFACE.md)).

## 4. Compare many models

`sweep` scores a list of models one after another on one server, resumes after interruptions, skips models the server does not
have, and rebuilds the leaderboard. It needs only an OpenAI-compatible endpoint, so it is not tied to Ollama, an OS or a GPU.
```bash
python -m medibuddy_bench sweep --list                          # which configured models does the server have?
python -m medibuddy_bench sweep --data data/lite --max-vram 8   # run everything that fits an 8 GB GPU
```
Model list and sizes: `configs/sweep.json`. Setting up a fresh GPU machine from zero: [`docs/SETUP_GPU_MACHINE.md`](docs/SETUP_GPU_MACHINE.md).

## 5. Read the results

Every assessment writes a **run record** to `results/runs/<run_id>/` (`run.json` with the full report, scope, data hash, machine
and git commit; `episodes.jsonl`; `report.md`). `leaderboard/LEADERBOARD.md` is generated from those records:
ranked agents (full split, official data version), reference baselines, and a "Not ranked" table that states why a run is excluded
(partial scope, stale data). Ranking and tie-break rules: [`docs/LEADERBOARD.md`](docs/LEADERBOARD.md).
Current reference scores on `dev`: null 1.0 · naive 15.0 · rule 65.8 · oracle 100.0. No LLM score is published until it is measured.

## 6. Reproducibility

Data is generated from a seed and is **byte-identical on every machine** (checked on Linux, Python 3.11/3.12/3.13; CI repeats it on
macOS and Windows): `python -m medibuddy_bench verify --data data/dev --rebuild`. Scoring has no randomness. Dependencies of the
service are pinned (`requirements-a2a.lock`), and the Docker image fails to build if its data differs from its manifest.
Model outputs are not bit-exact across hardware even at temperature 0 with a fixed seed, so each run record stores the model,
server URL, machine and commit; use `--trials 3` (pass^3) to measure consistency. Details: [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md).

## 7. Running the leaderboard (maintainers)

1. Build the hidden split once with a private seed (never commit it): `python -m medibuddy_bench build --split test --seed <SECRET> --out /private/test`.
2. Serve it: `python -m medibuddy_bench serve --data /private/test --runs-dir /private/runs`.
3. Publish: `python -m medibuddy_bench leaderboard --runs /private/runs --data /private/test --out leaderboard`.
4. After any scorer or data change: bump `VERSION`, regenerate, re-run `make baselines`; old runs become "stale" automatically.

## 8. Repository map

| Path | Purpose |
|---|---|
| `medibuddy_bench/gen/` | seeded generators: the world (1,200 hospitals, 47 districts) and all 8 tasks |
| `medibuddy_bench/scoring/` | deterministic scorers and aggregation (gating, pass^k, tiers) |
| `medibuddy_bench/agents/` | reference agents, model adapters (`llm_*`), plug-in adapters (`adapters.py`), `registry.py` (the `--agent` forms) |
| `medibuddy_bench/a2a/` | A2A benchmark service (green), reference agent (purple), client |
| `medibuddy_bench/{runner,execute,results,leaderboard,sweep,verify,cli}.py` | episode loop, checkpointed runs, run records, leaderboard, model sweep, data checks, CLI |
| `scripts/` | thin command-line wrappers (`run_benchmark`, `sweep`, `leaderboard`, `assess`, `verify_data`, `dataset_stats`, `fairness_twins`, `import_real_data`) |
| `data/lite`, `data/dev` | public splits; `data/review/` has the CSVs for native-speaker and clinician review |
| `examples/` | minimal `http` and `cmd` agents to copy |
| `configs/sweep.json` | models for the sweep |
| `docs/` | TASKS, INTEGRATION, AGENT_INTERFACE, SETUP_GPU_MACHINE, REPRODUCIBILITY, LEADERBOARD, DATA_CARD, DATASET_STATS, REVIEW_GUIDE, SUBMISSION, BUILD_LOG |
| `DESIGN.md`, `DECISIONS.md` | what / why / how, and the choices made on open questions |
| `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml` | reproducible image, one-machine stack, cross-OS CI |

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| `doctor` says data FAIL | the checkout is damaged or edited; `git checkout data/` or `verify --data data/dev --rebuild` |
| A2A commands: `No module named a2a.server.apps` | a2a-sdk 1.x is installed; use a clean venv with `requirements-a2a.lock` |
| Ollama run scores oddly low | Ollama's default context is 4096 tokens; use `ollama_ctx` in `configs/sweep.json` (the sweep handles it) or a Modelfile with `PARAMETER num_ctx 16384` |
| Ollama: `address already in use` | the Ollama app/service is already running; just use it (it restarts itself if killed) |
| Model ignores `<tool_call>` / `<answer>` | expected for small models; it costs points by design. Read a transcript (omit `--no-transcripts`) |
| Docker cannot reach the model server on the host | use `host.docker.internal` (the compose file maps it on Linux too) |
| Windows: `make` not found | use the `python -m medibuddy_bench …` commands; `make` is only a convenience |

## 10. Status and honest limits

Read `DESIGN.md` §8 and "Scope decisions" before quoting numbers. Korean text and clinical content are template-generated and **not yet
reviewed by a native speaker or clinician** (`docs/REVIEW_GUIDE.md`); the template-based `rule` agent shows that L1–L2 can be solved
without a model (L3–L4 are designed to separate real agents); patients write English only; the A2A service is tested locally with
a2a-sdk 0.3.26 but not on any external platform; closed-model adapters are untested against live APIs; the Docker image and the test suite are built and run by CI on every push (Linux, macOS and Windows; Python 3.10, 3.12 and 3.13; the first green run is
recorded in `docs/BUILD_LOG.md`), but the image has not been exercised against an external purple agent.
