"""One entry point for everything:  ``python -m medibuddy_bench <command> [options]``  (or ``medibuddy`` after
``pip install -e .``).  Each command forwards its options to the script of the same purpose, so
``python -m medibuddy_bench run --help`` and ``python scripts/run_benchmark.py --help`` are identical.

    run          score an agent locally                      scripts/run_benchmark.py
    sweep        score many models on one server             scripts/sweep.py
    leaderboard  rebuild the leaderboard from run records    scripts/leaderboard.py
    verify       check data integrity / reproducibility      scripts/verify_data.py
    serve        start the A2A benchmark service (green)     medibuddy_bench/a2a/green_server.py
    agent        start the reference A2A agent (purple)      medibuddy_bench/a2a/purple_server.py
    assess       start an assessment on a running service    scripts/assess.py
    build        regenerate a data split from its seed       medibuddy_bench/gen/build.py
    stats        describe a data split as Markdown           scripts/dataset_stats.py
    twins        fairness check (name/nationality swap)      scripts/fairness_twins.py
    doctor       check this machine (versions, server, data)

It works from a clone of the repository (the scripts live next to the package)."""
from __future__ import annotations

import os
import runpy
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = {"run": "run_benchmark.py", "sweep": "sweep.py", "leaderboard": "leaderboard.py", "verify": "verify_data.py",
           "assess": "assess.py", "stats": "dataset_stats.py", "twins": "fairness_twins.py"}
MODULES = {"serve": "medibuddy_bench.a2a.green_server", "agent": "medibuddy_bench.a2a.purple_server",
           "build": "medibuddy_bench.gen.build"}


def doctor() -> int:
    """Print what is installed and what is missing; exit code 0 when the core benchmark can run."""
    import importlib.metadata as md
    import platform

    from medibuddy_bench import VERSION
    ok = True
    print(f"MediBuddy-Bench {VERSION} | Python {platform.python_version()} | {platform.platform()}")
    if sys.version_info < (3, 10):
        print("  FAIL  Python >= 3.10 is required")
        ok = False
    try:
        v = md.version("a2a-sdk")
        print(f"  {'ok  ' if v.startswith('0.3') else 'WARN'}  a2a-sdk {v}" +
              ("" if v.startswith("0.3") else "  (the A2A service needs 0.3.x; see requirements-a2a.lock)"))
    except md.PackageNotFoundError:
        print("  info  a2a-sdk not installed (only needed for the A2A service: pip install -r requirements-a2a.lock)")
    for split in ("lite", "dev"):
        d = os.path.join(ROOT, "data", split)
        if os.path.isdir(d):
            from medibuddy_bench.verify import check_files
            bad = check_files(d)
            print(f"  {'ok  ' if not bad else 'FAIL'}  data/{split} " + ("intact" if not bad else "; ".join(bad)))
            ok &= not bad
        else:
            print(f"  FAIL  data/{split} missing")
            ok = False
    base = os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1")
    try:
        from medibuddy_bench.sweep import list_models
        names = list_models(base, os.environ.get("OPENAI_API_KEY", "none"), timeout=3)
        print(f"  ok    model server {base}: {len(names)} models ({', '.join(names[:6])}{'...' if len(names) > 6 else ''})")
    except OSError:
        print(f"  info  no model server at {base} (set OPENAI_BASE_URL; not needed for baselines)")
    except ValueError:
        print(f"  info  {base} answered, but not with an OpenAI-style model list (not needed for baselines)")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmds = sorted([*SCRIPTS, *MODULES, "doctor"])
    if not argv or argv[0] in ("-h", "--help"):
        print((__doc__ or "").split("It works from")[0].rstrip())
        return 0 if argv else 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "doctor":
        return doctor()
    sys.path.insert(0, ROOT)
    if cmd in SCRIPTS:
        path = os.path.join(ROOT, "scripts", SCRIPTS[cmd])
        sys.argv = [path, *rest]
        runpy.run_path(path, run_name="__main__")
    elif cmd in MODULES:
        sys.argv = [MODULES[cmd], *rest]
        runpy.run_module(MODULES[cmd], run_name="__main__", alter_sys=True)
    else:
        print(f"unknown command {cmd!r}; choose one of: {', '.join(cmds)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
