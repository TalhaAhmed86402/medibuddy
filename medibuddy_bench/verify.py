"""Prove a data split is intact and reproducible on this machine.

``check_files``    recompute the hashes stored in manifest.json from the files (detects edits and corruption).
``check_rebuild``  regenerate the split from its seed in a temporary folder and compare every hash (detects any
                   platform, Python-version or code difference that would change the data).

Hashes are over the parsed JSON (key order and line endings do not matter), so a Windows checkout with CRLF passes."""
from __future__ import annotations

import json
import os
import tempfile

from medibuddy_bench.common import TASKS, stable_hash


def _load(path: str):
    with open(path, encoding="utf-8") as f:
        return f.read()


def check_files(data_dir: str) -> list[str]:
    """-> list of problems (empty = intact)."""
    man = json.loads(_load(os.path.join(data_dir, "manifest.json")))
    problems = []
    if stable_hash(json.loads(_load(os.path.join(data_dir, "world.json")))) != man["world_hash"]:
        problems.append("world.json does not match manifest world_hash")
    for t in TASKS:
        p = os.path.join(data_dir, f"{t}.jsonl")
        if t not in man["hashes"]:
            continue
        items = [json.loads(l) for l in _load(p).splitlines() if l.strip()]
        if len(items) != man["counts"][t]:
            problems.append(f"{t}: {len(items)} scenarios, manifest says {man['counts'][t]}")
        if stable_hash(items) != man["hashes"][t]:
            problems.append(f"{t}.jsonl does not match its manifest hash")
    return problems


def check_rebuild(data_dir: str, seed: int = 1) -> list[str]:
    """Rebuild the split named like `data_dir` (dev, lite, ...) from `seed` and compare with the committed manifest."""
    from medibuddy_bench.gen.build import build, write
    split = os.path.basename(os.path.normpath(data_dir))
    committed = json.loads(_load(os.path.join(data_dir, "manifest.json")))
    with tempfile.TemporaryDirectory() as tmp:
        fresh = write(build(split, seed), tmp)
    problems = []
    if fresh["version"] != committed["version"]:
        problems.append(f"version {fresh['version']} (code) vs {committed['version']} (data)")
    if fresh["world_hash"] != committed["world_hash"]:
        problems.append(f"world hash {fresh['world_hash']} (rebuilt) vs {committed['world_hash']} (committed)")
    for t, h in fresh["hashes"].items():
        if committed["hashes"].get(t) != h:
            problems.append(f"{t} differs after rebuild")
    return problems
