# Submission checklist

## What this repository contains
A runnable benchmark (generator, 8 tasks, deterministic scorers, tools, simulators, baselines, tests) plus a public dev split.
Entry points: `scripts/run_benchmark.py` (local), `medibuddy_bench/a2a_green.py` (A2A green-agent adapter, **not yet verified against the live AgentBeats platform**).

## Verify before submitting
```bash
python3 -m pytest -q tests                                   # 46 tests + docstring examples
python3 scripts/run_benchmark.py --agent oracle --data data/dev --no-transcripts   # 100.0
python3 scripts/run_benchmark.py --agent rule   --data data/dev --no-transcripts   # ~65.8
python3 scripts/fairness_twins.py --agent rule --data data/dev --limit 60          # gap 0.0000
```

## Hidden test split (organiser only)
```bash
python3 -m medibuddy_bench.gen.build --split test --seed <PRIVATE_SEED> --out /private/test
```
Never commit the seed or the output. Same seed + same code = identical files.

## Reporting an agent
1. Run dev with `--trials 3` (pass^k) and without `--no-transcripts` for error analysis.
2. Report overall (gated), per task, per tier L1-L4, critical-failure counts, and the un-gated score.
3. Quote the limits in DESIGN.md "Threats to validity" and "Scope decisions".

## Still needed from the team / course
- Exact submission format, deadline and deliverables (AgentBeats template version, scenario.toml keys; `cmd` is empty today).
- At least one real LLM baseline (needs an API key, or a local run, e.g. llama3.1 8B via Ollama); none has been scored yet.
- Native-Korean review of `data/review/korean_phrasebook.csv`; clinician review of `data/review/triage_labels.csv`.
- A private seed for the test split.
- Decisions pending in DECISIONS.md (#14-#17).
