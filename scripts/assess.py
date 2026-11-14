#!/usr/bin/env python3
"""Start an assessment on a running green service and print the result.

  python scripts/assess.py --green http://localhost:9009 --purple http://localhost:9019 --name my-agent --model llama3.2:3b
  python scripts/assess.py ... --tasks T1,T4 --limit 5        # quick smoke test (such runs are never ranked)

Needs the packages in requirements-a2a.lock.  Exit code 0 = completed, 1 = failed."""
import argparse, asyncio, json, sys

import httpx
from a2a.client import ClientConfig, ClientFactory, create_text_message_object


async def main(a):
    cfg = {k: v for k, v in {"name": a.name, "model": a.model, "limit": a.limit, "trials": a.trials,
                              "tasks": a.tasks.split(",") if a.tasks else None,
                              "tiers": a.tiers.split(",") if a.tiers else None}.items() if v is not None}
    body = json.dumps({"participants": {"purple": a.purple}, "config": cfg})
    async with httpx.AsyncClient(timeout=None) as http:
        c = await ClientFactory.connect(a.green, client_config=ClientConfig(streaming=False, httpx_client=http))
        last = None
        async for ev in c.send_message(create_text_message_object(content=body)):
            last = ev[0] if isinstance(ev, tuple) else ev
    state = str(last.status.state.value)
    if state != "completed":
        msg = last.status.message.parts[0].root.text if last.status.message else ""
        print(f"assessment {state}: {msg}", file=sys.stderr)
        return 1
    for art in last.artifacts or []:
        if art.name == "report.md":
            print(art.parts[0].root.text)
        if art.name == "run_id":
            print(f"\nrun record: {art.parts[0].root.text}  (python scripts/leaderboard.py to rank it)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--green", default="http://localhost:9009")
    ap.add_argument("--purple", required=True)
    ap.add_argument("--name"); ap.add_argument("--model")
    ap.add_argument("--tasks"); ap.add_argument("--tiers")
    ap.add_argument("--limit", type=int); ap.add_argument("--trials", type=int)
    sys.exit(asyncio.run(main(ap.parse_args())))
