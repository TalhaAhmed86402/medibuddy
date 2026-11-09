# Setting up a GPU machine from zero (example: RTX 2080, 8 GB VRAM)

Goal: run many open-source models on the benchmark, reproducibly, without depending on the laptop. Everything below is
platform-neutral except where a Windows/Linux difference is noted. Sizes are approximate (4-bit weights plus a 16k-token context).

## 0. What fits in 8 GB
| Model (Ollama tag) | Approx. VRAM at 16k context | Verdict on an 8 GB card |
|---|---|---|
| `llama3.2:3b` | 3-4 GB | comfortable |
| `qwen2.5:3b`, `qwen3:4b`, `gemma3:4b`, `phi4-mini` | 3-5 GB | comfortable |
| `qwen2.5:7b`, `mistral:7b`, `deepseek-r1:7b` | 6-7 GB | fits |
| `llama3.1:8b`, `qwen3:8b`, `exaone3.5:7.8b` | 7-8 GB | tight; if `ollama ps` shows part on CPU it still runs, only slower |
| `gemma3:12b`, `gpt-oss:20b` | 11+ GB | does not fit (skipped by `--max-vram 8`) |

The RTX 2080 has no bfloat16, so use quantised (GGUF/Q4) models as Ollama does by default. If the GPU also drives your display, a
little VRAM is already used.

## 1. Check the GPU
```bash
nvidia-smi                      # must list the RTX 2080 and a driver version; if not, install/update the NVIDIA driver first
```

## 2. Install Ollama (the easiest model server; the benchmark does not depend on it, see section 7)
* **Windows:** download the installer from https://ollama.com/download and run it. It starts in the background and serves on port 11434.
* **Linux:** `curl -fsSL https://ollama.com/install.sh | sh` (installs a service on port 11434).
```bash
ollama --version
curl http://localhost:11434/api/tags       # Windows PowerShell: curl.exe http://localhost:11434/api/tags
```

## 3. Download models
```bash
ollama pull llama3.2:3b
ollama pull qwen2.5:7b
# optional, in this order of interest:
ollama pull qwen3:8b ; ollama pull llama3.1:8b ; ollama pull gemma3:4b ; ollama pull mistral:7b ; ollama pull deepseek-r1:7b
```
Check a tag exists on your Ollama version before pulling; `sweep` skips models the server does not have.

## 4. Get the benchmark
Install Python 3.10+ (Windows: python.org installer, tick "Add to PATH"; Linux: your package manager), then:
```bash
git clone https://github.com/TalhaAhmed86402/medibuddy.git medibuddy-bench && cd medibuddy-bench
python -m medibuddy_bench doctor          # expect: data intact, "ok model server http://localhost:11434/v1 ..."
```
(Prefer a container? `docker build -t medibuddy-bench .`; GPU is not needed inside it, the model server stays on the host.)

## 5. Smoke test one model
```bash
export OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=none      # PowerShell: $env:OPENAI_BASE_URL="http://localhost:11434/v1"
python -m medibuddy_bench run --agent openai:llama3.2:3b --data data/lite --tasks T1 --limit 3
ollama ps                                  # in a second terminal: PROCESSOR should say 100% GPU
```
Ollama's OpenAI endpoint uses a 4096-token context unless the model variant says otherwise. The sweep (next step) creates
`<model>-ctx16k` variants automatically; for a single run do it yourself:
`printf 'FROM qwen2.5:7b\nPARAMETER num_ctx 16384\n' > Modelfile && ollama create qwen2.5-7b-ctx16k -f Modelfile`, then use that name.

## 6. Run the sweep
```bash
python -m medibuddy_bench sweep --list                         # what the server has
python -m medibuddy_bench sweep --data data/lite --max-vram 8  # every configured model that fits; resumable; rebuilds the leaderboard
python -m medibuddy_bench sweep --data data/dev --trials 3     # the official split, once the lite pass looks right (long)
cat leaderboard/LEADERBOARD.md
```
If it stops (sleep, crash, Ctrl-C) run the same command again: finished models are skipped, the current one resumes.
Do not change server settings between models you want to compare (see docs/REPRODUCIBILITY.md).

## 7. Other model servers (nothing else changes)
Any server exposing `GET /v1/models` and `POST /v1/chat/completions` works. Copy `configs/sweep.json`, set `defaults.base_url`
and each `model` to the id that server lists (`curl <base_url>/models`), remove `ollama_ctx`, and pass `--config`.
* **llama.cpp** (Windows/Linux/macOS, CUDA build): `llama-server -m model.gguf -c 16384 -ngl 99 --port 8080 --alias qwen2.5-7b` → `http://localhost:8080/v1`.
* **vLLM** (Linux): `vllm serve Qwen/Qwen2.5-7B-Instruct-AWQ --max-model-len 16384 --dtype half --port 8000` → `http://localhost:8000/v1`
  (Turing GPUs need fp16 and a quantised model to fit 8 GB).
* **LM Studio**: enable its local server → `http://localhost:1234/v1`.
* **Hosted APIs**: set `base_url`, `api_key`; untested against live services.

## 8. Using the GPU box from another computer
Run `python -m medibuddy_bench serve --host 0.0.0.0` on the GPU box, or keep the model server there and point `OPENAI_BASE_URL`
at it (for example through an SSH tunnel: `ssh -L 11434:localhost:11434 user@gpu-box`).
