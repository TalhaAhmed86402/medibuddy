# Submission checklist

## What this repository contains
A runnable benchmark (generator, 8 tasks, deterministic scorers, tools, simulators, baselines, tests) plus a public dev split.
Entry point: `python -m medibuddy_bench <command>` (wraps `scripts/*`). A2A: `python -m medibuddy_bench.a2a.green_server` (A2A green-agent service, tested end to end against the reference purple agent with a2a-sdk 0.3.26; **not yet tried on the live AgentBeats platform, and incompatible with a2a-sdk 1.x**), `python -m medibuddy_bench.a2a.purple_server` (reference student agent for open and closed models).

## Verify before submitting
```bash
python3 -m pytest -q tests                                   # 46 tests + docstring examples (+2 A2A end-to-end tests in a venv with requirements-a2a.txt)
python3 scripts/run_benchmark.py --agent oracle --data data/dev --no-transcripts   # 100.0
python3 scripts/run_benchmark.py --agent rule   --data data/dev --no-transcripts   # ~65.8
python3 scripts/fairness_twins.py --agent rule --data data/dev --limit 60          # gap 0.0000
```

## Hidden test split (organiser only)
```bash
python3 -m medibuddy_bench.gen.build --split test --seed <PRIVATE_SEED> --out /private/test
```
Never commit the seed or the output. Same seed + same code = identical files.

## Running the workflow
See README.md (install, test an agent, sweep, leaderboard), docs/INTEGRATION.md, docs/SETUP_GPU_MACHINE.md, docs/REPRODUCIBILITY.md.

## Rules for agents
See `docs/INTEGRATION.md` ("Rules every agent is held to"): benchmark tools are the only source of hospital facts; reasoning aids are allowed; `dev` is self-reported, official scores come from the hidden `test` split run by the maintainers.

## Reporting an agent
1. Run dev with `--trials 3` (pass^k) and without `--no-transcripts` for error analysis.
2. Report overall (gated), per task, per tier L1-L4, critical-failure counts, and the un-gated score.
3. Quote the limits in DESIGN.md "Threats to validity" and "Scope decisions".

## Still needed from the team / course
- The course's AgentBeats template/version, to confirm the A2A request format and a2a-sdk version match (scenario.toml `cmd` entries now point at our servers).
- At least one real LLM baseline (needs an API key, or a local run, e.g. llama3.1 8B via Ollama); none has been scored yet.
- Native-Korean review of `data/review/korean_phrasebook.csv`; clinician review of `data/review/triage_labels.csv`.
- A private seed for the test split.
- Decisions pending in DECISIONS.md (#14-#17).
