# Quickstart

The complete, platform-neutral guide is the [README](../README.md). This page is the 5-minute version.

```bash
python -m medibuddy_bench doctor                                   # 1. is everything in place?
python -m medibuddy_bench run --agent oracle --data data/lite --no-transcripts   # 2. must print 100.0
export OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=none              # 3. any OpenAI-compatible server
python -m medibuddy_bench sweep --list                             # 4. which configured models does it have?
python -m medibuddy_bench sweep --data data/lite --max-vram 8      # 5. score them; resumable; writes leaderboard/LEADERBOARD.md
```
* One model only: `python -m medibuddy_bench run --agent openai:<model> --name <label> --model <model> --data data/lite --no-transcripts --save-run results/runs`
* Your own agent (Python, HTTP, command line, A2A): `docs/INTEGRATION.md`
* A fresh GPU machine: `docs/SETUP_GPU_MACHINE.md`
* Why results can differ between machines and how to check: `docs/REPRODUCIBILITY.md`

`make` targets (`make help`) wrap the same commands on Linux/macOS.
