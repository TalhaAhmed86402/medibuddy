# Reproducibility

What is guaranteed, what is not, and how to check.

## Guaranteed (and tested)
| Property | How it is enforced | How to check |
|---|---|---|
| The data splits are identical on every machine | generators are seeded; all hashes are over parsed JSON, independent of line endings and key order | `python -m medibuddy_bench verify --data data/dev --rebuild` (exit code 0) |
| Committed data was not edited or corrupted | `manifest.json` stores a hash of the world and of every task file | `python -m medibuddy_bench verify --data data/dev` |
| Scoring is deterministic | no randomness, no LLM judge, no network | rerun the same episodes: identical scores (`tests/test_benchmark.py`) |
| Same environment | the service's dependencies are pinned in `requirements-a2a.lock`; the Docker image installs only that and **fails to build** if its data differs from the manifest | `docker build -t medibuddy-bench .` |
| Same results across OS and Python | CI runs the whole test suite plus a data rebuild on Linux, macOS and Windows with Python 3.10, 3.12 and 3.13 | `.github/workflows/ci.yml` (locally verified here: Linux, Python 3.11, 3.12, 3.13) |
| An interrupted run does not change the result | checkpoint/resume reproduces the uninterrupted score | `tests/test_resume.py` |

## Not guaranteed
**Model outputs.** Even at temperature 0 with a fixed seed, different hardware, drivers, quantisation files or server versions can
change a model's tokens, so scores of a *model* can differ slightly between machines. This is a property of LLM serving, not of the
benchmark. Mitigations built in:
* every run record stores model name, served model id, server URL, Python and OS, git commit and whether it ran in Docker (`run.json`);
* `--trials 3` reports pass^3, a consistency measure;
* compare models only on the same split and data hash (the leaderboard enforces this and lists mismatches as "stale").

## Checklist for a result you intend to report
1. `git rev-parse HEAD` and `python -m medibuddy_bench verify --data data/dev --rebuild` pass.
2. Note the model **file/digest** (for Ollama: `ollama list` shows the ID), server and version (`ollama --version`), GPU and driver (`nvidia-smi`).
3. Run the whole split (`data/dev`), `--trials 3` if budget allows, with the same server settings for every model you compare
   (context length, quantisation, KV-cache options such as `OLLAMA_FLASH_ATTENTION` and `OLLAMA_KV_CACHE_TYPE`).
4. Keep `results/runs/<run_id>/`; it is the evidence behind the leaderboard row.

## Changing the benchmark
Any change to generators, vocabularies or scorers must bump `VERSION` (`medibuddy_bench/__init__.py` and `pyproject.toml`),
regenerate the splits, and re-run the baselines. Old run records then show as "stale" instead of being compared to new ones.
