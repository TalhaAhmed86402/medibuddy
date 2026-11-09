# One-command workflow.  `make help` lists targets.  Python >= 3.10; A2A targets need `pip install -r requirements-a2a.txt`.
PY ?= python3
SPLIT ?= lite
DATA ?= data/$(SPLIT)

help:
	@echo "make test                run unit tests + docstring examples"
	@echo "make baselines           score null/naive/rule/oracle on DATA (default data/lite) and record them"
	@echo "make ollama MODEL=llama3.2:3b   score a local Ollama model (SPLIT=lite|dev) and record it"
	@echo "make leaderboard         rebuild leaderboard/LEADERBOARD.md from results/runs"
	@echo "make serve-green         start the benchmark service (A2A) on :9009"
	@echo "make serve-purple        start the reference student agent (A2A) on :9019 (needs OPENAI_BASE_URL etc.)"
	@echo "make data SPLIT=dev      regenerate a split from its seed"

test:
	$(PY) -m pytest -q tests

baselines:
	@for a in null naive rule oracle; do $(PY) scripts/run_benchmark.py --agent $$a --data $(DATA) --no-transcripts --baseline --save-run results/runs | tail -1; done
	$(PY) scripts/leaderboard.py --runs results/runs --data $(DATA) --out leaderboard

ollama:
	@test -n "$(MODEL)" || (echo "usage: make ollama MODEL=llama3.2:3b" && exit 1)
	OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=none MEDIBUDDY_MODEL=$(MODEL) \
	  $(PY) scripts/run_benchmark.py --agent medibuddy_bench.agents.llm_openai_compat:OpenAICompatAgent \
	  --name "ollama-$(MODEL)" --model $(MODEL) --data $(DATA) --no-transcripts --save-run results/runs
	$(PY) scripts/leaderboard.py --runs results/runs --data $(DATA) --out leaderboard

leaderboard:
	$(PY) scripts/leaderboard.py --runs results/runs --data $(DATA) --out leaderboard

serve-green:
	$(PY) -m medibuddy_bench.a2a.green_server --host 0.0.0.0 --port 9009 --data $(DATA)

serve-purple:
	$(PY) -m medibuddy_bench.a2a.purple_server --backend openai --port 9019

data:
	$(PY) -m medibuddy_bench.gen.build --split $(SPLIT) --seed 1 --out data/$(SPLIT) $(if $(filter dev,$(SPLIT)),--review data/review,)

.PHONY: help test baselines ollama leaderboard serve-green serve-purple data
