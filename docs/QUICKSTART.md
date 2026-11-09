# Quickstart: from zero to a leaderboard row

Everything below is one of three workflows. All use the same data, the same scorer and the same run records,
so the numbers are comparable.

## 0. Check the install
```bash
python3 -m pytest -q tests          # all green, ~1 min
make baselines                      # scores null / naive / rule / oracle on the lite split (seconds)
cat leaderboard/LEADERBOARD.md      # baselines appear as reference rows; oracle must be 100.0
```

## 1. Score a local open-source model (Ollama), no A2A needed
```bash
ollama pull llama3.2:3b
# Ollama's default context window is 4096 tokens; benchmark prompts are ~1k tokens plus tool results and chat history,
# so raise it, then restart Ollama:
export OLLAMA_CONTEXT_LENGTH=16384 && ollama serve         # (or set it in the Ollama app / service environment)
make ollama MODEL=llama3.2:3b                                # lite split (108 scenarios)
make ollama MODEL=llama3.2:3b SPLIT=dev                      # full dev split (832 scenarios; slow on a laptop)
```
Smoke test first with `--limit 3` (`python3 scripts/run_benchmark.py --agent medibuddy_bench.agents.llm_openai_compat:OpenAICompatAgent --data data/lite --tasks T1 --limit 3`
with `OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=none MEDIBUDDY_MODEL=llama3.2:3b`).
Small models often ignore the `<tool_call>` / `<answer>` format; that costs them points (it is part of what is measured), and the
transcript (drop `--no-transcripts`) shows why.

## 2. Full A2A workflow (what students use)
Three terminals, in a venv with `pip install -r requirements-a2a.txt` (a2a-sdk 0.3.x):
```bash
make serve-green SPLIT=lite                                   # 1: the benchmark service on :9009
OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=none MEDIBUDDY_MODEL=llama3.2:3b make serve-purple   # 2: the agent on :9019
python3 scripts/assess.py --green http://localhost:9009 --purple http://localhost:9019 --name my-agent --model llama3.2:3b   # 3: start an assessment
make leaderboard SPLIT=lite
```
Students replace `purple_server.py`'s backend with their own agent (text in, text out; docs/AGENT_INTERFACE.md).

## What counts for the leaderboard
Only runs that cover the **whole** split (all 8 tasks, every scenario, no `--tasks/--tiers/--limit`) on the official data version are
ranked. Everything else shows up under "Not ranked" with the reason. Baselines are reference rows. See docs/LEADERBOARD.md.
