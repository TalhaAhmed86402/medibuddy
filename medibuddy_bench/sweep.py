"""Score many models one after another on any OpenAI-compatible server, resumably, then rebuild the leaderboard.

    python scripts/sweep.py --config configs/sweep.json --data data/lite --max-vram 8
    python scripts/sweep.py --list                      # what is available on the server, what would run
    python scripts/sweep.py --only qwen2.5-7b --data data/dev --trials 3

Nothing here is specific to Ollama, an OS or a GPU: it only needs ``GET <base_url>/models`` and
``POST <base_url>/chat/completions``.  (Optional convenience: for Ollama, ``ollama_ctx`` builds a variant of the model
with a larger context window, because Ollama's OpenAI endpoint cannot set it per request.)"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request

from medibuddy_bench.agents.llm_openai_compat import OpenAICompatAgent
from medibuddy_bench.execute import run_with_checkpoint
from medibuddy_bench.leaderboard import build
from medibuddy_bench.results import load_runs, read_manifest, save_run
from medibuddy_bench.runner import Runner
from medibuddy_bench.scoring.aggregate import aggregate


def list_models(base_url: str, api_key: str = "none", timeout: float = 10.0) -> list[str]:
    """Model ids the server reports (OpenAI-style ``GET /models``); raises OSError if unreachable."""
    req = urllib.request.Request(base_url.rstrip("/") + "/models", headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return [m["id"] for m in json.load(r).get("data", [])]


def has_model(available: list[str], model: str) -> str | None:
    """Return the server's id for `model` (tolerating Ollama's ':latest' suffix) or None."""
    for cand in (model, model + ":latest"):
        if cand in available:
            return cand
    return None


def ollama_variant(model: str, ctx: int, available: list[str]) -> str | None:
    """Create (once) an Ollama variant of `model` with context `ctx`; returns its name, or None if not possible."""
    variant = f"{model.replace(':', '-')}-ctx{ctx // 1024}k"
    if has_model(available, variant):
        return variant
    if not shutil.which("ollama"):
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".Modelfile", delete=False, encoding="utf-8") as f:
        f.write(f"FROM {model}\nPARAMETER num_ctx {ctx}\n")
    try:
        r = subprocess.run(["ollama", "create", variant, "-f", f.name], capture_output=True, text=True, timeout=300)
    finally:
        os.unlink(f.name)
    return variant if r.returncode == 0 else None


def already_scored(runs_dir: str, name: str, data_dir: str) -> bool:
    man, split = read_manifest(data_dir), os.path.basename(os.path.normpath(data_dir))
    return any(r["agent"] == name and r["data"].get("dir") == split and r["coverage"]["full"]
               and r["data"].get("world_hash") == man.get("world_hash") for r in load_runs(runs_dir))


def sweep(config: dict, data_dir: str, runs_dir: str, only=None, max_vram: float | None = None, trials: int = 1,
          force: bool = False, limit: int | None = None, overrides: dict | None = None, ckpt_dir: str = "results/.checkpoints",
          out_dir: str = "leaderboard", listing: bool = False, log=sys.stderr) -> list[dict]:
    """Run the sweep; returns one status dict per configured model (status: scored | skipped | missing | failed)."""
    d = {**config.get("defaults", {}), **(overrides or {})}
    status: list[dict] = []
    served_by: dict[str, list[str] | str] = {}          # base_url -> model ids, or the error text (asked once per server)
    for entry in config["models"]:
        e = {**d, **entry}
        name = e["name"]
        if only and name not in only:
            continue
        if max_vram and e.get("min_vram_gb", 0) > max_vram:
            status.append({"name": name, "status": "skipped", "why": f"needs ~{e['min_vram_gb']} GB > --max-vram {max_vram}"})
            continue
        if e["base_url"] not in served_by:
            try:
                served_by[e["base_url"]] = list_models(e["base_url"], e.get("api_key", "none"))
            except OSError as ex:
                served_by[e["base_url"]] = f"server {e['base_url']} unreachable ({ex}); start it or pass --base-url"
        available = served_by[e["base_url"]]
        if isinstance(available, str):
            status.append({"name": name, "status": "failed", "why": available})
            continue
        served = has_model(available, e["model"])
        if not served:
            status.append({"name": name, "status": "missing", "why": f"server has no '{e['model']}' (pull/download it first)"})
            continue
        if listing:
            status.append({"name": name, "status": "available", "why": ""})
            continue
        if not force and not limit and already_scored(runs_dir, name, data_dir):
            status.append({"name": name, "status": "skipped", "why": "already scored on this data (use --force)"})
            continue
        if e.get("ollama_ctx") and ":11434" in e["base_url"]:
            variant = ollama_variant(served, int(e["ollama_ctx"]), available)
            if variant:
                served = variant
            else:
                print(f"[{name}] could not create a {e['ollama_ctx']}-token variant; using the default context window", file=log)
        print(f"\n=== {name} ({served}) ===", file=log)
        runner = Runner(data_dir, lambda scen, m=served, b=e["base_url"], k=e.get("api_key", "none"): OpenAICompatAgent(m, b, k),
                        name, keep_transcripts=False)
        ck = os.path.join(ckpt_dir, f"{name}-{os.path.basename(os.path.normpath(data_dir))}.jsonl")
        try:
            eps = run_with_checkpoint(runner, data_dir, name, None, None, limit, trials, ck, log)
        except Exception as ex:              # noqa: BLE001  (server crash etc.; the checkpoint keeps the progress)
            status.append({"name": name, "status": "failed", "why": f"{type(ex).__name__}: {ex} (re-run to resume)"})
            continue
        rep = aggregate(eps)
        save_run(runs_dir, name, eps, rep, data_dir, {"limit": limit, "trials": trials}, source="sweep", model=e["model"],
                 notes=e.get("notes", ""), extra={"served_model": served, "base_url": e["base_url"]})
        if os.path.exists(ck):
            os.remove(ck)
        status.append({"name": name, "status": "scored", "why": f"overall {rep['overall']:.1f}"})
    if not listing:
        build(runs_dir, data_dir, out_dir)
    return status
