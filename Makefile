# Convenience wrapper (Linux/macOS).  Everything is also available as `python -m medibuddy_bench <command>` on any OS (see README).
# `make help` lists targets.  Python >= 3.10; A2A targets need `pip install -r requirements-a2a.lock` in a clean venv.
PY ?= python3
SPLIT ?= lite
DATA ?= data/$(SPLIT)

help:
	@echo "make test                run unit tests + docstring examples"
	@echo "make baselines           score null/naive/rule/oracle on DATA (default data/lite) and record them"
	@echo "make ollama MODEL=llama3.2:3b   score a local Ollama model (SPLIT=lite|dev) and record it; re-run the same command to resume after an interruption"
	@echo "make leaderboard         rebuild leaderboard/LEADERBOARD.md from results/runs"
	@echo "make sweep               score every configured model the server has (MAXVRAM=8 SPLIT=lite|dev)"
	@echo "make verify              check data integrity and that it rebuilds identically"
	@echo "make docker              build the Docker image and run the oracle inside it"
	@echo "make serve-green         start the benchmark service (A2A) on :9009"
	@echo "make serve-purple        start the reference student agent (A2A) on :9019 (needs OPENAI_BASE_URL etc.)"
	@echo "make data SPLIT=dev      regenerate a split from its seed"
	@echo "make docs                regenerate the generated parts of the docs (dataset statistics, baseline tables)"
	@echo "make release-check       everything to run before tagging a version (tests, rebuild, docs current)"

test:
	$(PY) -m pytest -q tests

baselines:
	@for a in null naive rule oracle; do $(PY) scripts/run_benchmark.py --agent $$a --data $(DATA) --no-transcripts --baseline --save-run results/runs | tail -1; done
	$(PY) scripts/leaderboard.py --runs results/runs --data $(DATA) --out leaderboard

ollama:
	@test -n "$(MODEL)" || (echo "usage: make ollama MODEL=llama3.2:3b" && exit 1)
	OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=none MEDIBUDDY_MODEL=$(MODEL) \
	  $(PY) scripts/run_benchmark.py --agent medibuddy_bench.agents.llm_openai_compat:OpenAICompatAgent \
	  --name "ollama-$(MODEL)" --model $(MODEL) --data $(DATA) --no-transcripts --save-run results/runs \
	  --checkpoint results/.checkpoints/ollama-$(MODEL)-$(SPLIT).jsonl
	$(PY) scripts/leaderboard.py --runs results/runs --data $(DATA) --out leaderboard

sweep:
	$(PY) scripts/sweep.py --data $(DATA) $(if $(MAXVRAM),--max-vram $(MAXVRAM),)

verify:
	$(PY) scripts/verify_data.py --data $(DATA) --rebuild

docker:
	docker build -t medibuddy-bench .
	docker run --rm medibuddy-bench run --agent oracle --data data/lite --no-transcripts

leaderboard:
	$(PY) scripts/leaderboard.py --runs results/runs --data $(DATA) --out leaderboard

serve-green:
	$(PY) -m medibuddy_bench.a2a.green_server --host 0.0.0.0 --port 9009 --data $(DATA)

serve-purple:
	$(PY) -m medibuddy_bench.a2a.purple_server --backend openai --port 9019

data:
	$(PY) -m medibuddy_bench.gen.build --split $(SPLIT) --seed 1 --out data/$(SPLIT) $(if $(filter dev,$(SPLIT)),--review data/review,)

docs:
	$(PY) scripts/dataset_stats.py --data data/dev --write
	$(PY) scripts/baselines_report.py

release-check:
	$(PY) -m pytest -q tests
	$(PY) -m medibuddy_bench verify --data data/dev --rebuild
	$(PY) -m medibuddy_bench verify --data data/lite --rebuild
	$(PY) scripts/baselines_report.py --check

.PHONY: help test baselines ollama sweep verify docker leaderboard serve-green serve-purple data docs release-check
