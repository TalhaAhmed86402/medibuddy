# Running MediBuddy-Bench on AgentBeats

MediBuddy-Bench is an A2A **green agent**: it receives one assessment request, talks to the student's **purple agent** over A2A, and
returns the scores. This page maps it onto the public AgentBeats conventions (RDI-Foundation `green-agent-template`,
`agentbeats-gateway` and `agentbeats-leaderboard-template`, read on 2026-11-14).

**Status.** The request format, the result artifact, sharding, the heartbeat and the CLI flags follow those templates and are
tested locally with a2a-sdk 0.3.26 (`tests/test_a2a.py`). The manifests follow the templates' format. The benchmark has **not
yet been registered or run on agentbeats.dev**. If the course runs its
own platform with a different template, check this page against it first.

## What the platform sends and what the benchmark returns

| | AgentBeats convention | MediBuddy-Bench |
|---|---|---|
| Request | one text message, JSON `{"participants": {role: url}, "config": {...}}` | same; the role is `purple` (any single role name is accepted) |
| Config | free-form; the leaderboard runner adds `shard_index`, `num_shards`, `num_instances` | `tasks`, `tiers`, `limit`, `trials`, `max_tool_calls`, `split`, `name`, `model`, plus the three shard keys; unknown keys are rejected |
| Progress | `TaskState.working` status updates | an update every 10 episodes and at least every 30 s |
| Result | the gateway keeps only JSON parts of the final artifacts (DataPart data, or text that parses as JSON) | artifact `result`: a flat JSON row (DataPart, and the same JSON as text); also `report.json`, `report.md` (human-readable, ignored by the gateway) and `run_id` |
| Bad request | `reject` | the task ends `rejected` with the reason ("the message must be JSON", "unknown config keys", ...) |
| Image | public, linux/amd64, accepts `--host`, `--port`, `--card-url` | `Dockerfile` (see below); `serve --host --port --card-url` |

### The `result` row

```json
{"id": "20261114-031500-my-agent", "benchmark": "medibuddy-bench", "data_version": "1.2.0", "world_hash": "950858d17f40e76a",
 "split": "dev", "agent": "my-agent", "model": "qwen2.5:7b", "overall": 41.3, "overall_ungated": 55.0, "covered_weight": 100,
 "n_episodes": 832, "tasks": {"T1": 52.1, "T2": 40.0, "...": 0}, "critical": {"C1_missed_red_flag": 3, "...": 0},
 "trials": 1, "shard_index": 0, "num_shards": 1, "pass_hat_k": {"1": 0.31}}
```
Scores are 0-100 and gated (a critical failure zeroes the episode). With shards, each shard reports its own row; the overall of
the assessment is the episode-weighted combination, which the per-task scores and `n_episodes` allow a leaderboard query to compute.

### Example leaderboard query (DuckDB over `results/*.json`)

The leaderboard template loads every results file as table `results`, whose `results` column holds the rows above. A query whose
first column is `id`:
```sql
SELECT r.id, r.agent, r.model, r.overall, r.tasks.T5 AS interpretation, r.critical.C1_missed_red_flag AS missed_emergencies
FROM (SELECT unnest(results) AS r FROM results) WHERE r.num_shards = 1 AND r.data_version = '1.2.0'
ORDER BY r.overall DESC;
```
Check it locally: `duckdb -c 'CREATE TEMP TABLE results AS SELECT * FROM read_json_auto("results/*.json");' -c '<query>'`.
This query was run with DuckDB 2.0.0 on a file of that shape (`{"status", "participants", "results": [rows]}`) built from
real `result` rows; the shape of the platform's files comes from the public leaderboard template and was not seen on the platform.

## Step by step: from this repository to a running AgentBeats leaderboard

Files used: `Dockerfile` (the benchmark, green), `agentbeats/Dockerfile.purple` (a reference purple agent for testing),
`amber-manifest.json5` (green component manifest), `agentbeats/purple-agent.json5` (purple component manifest),
`agentbeats/scenario.json5` (the leaderboard repository's scenario), `.github/workflows/publish.yml` (pushes both images).
The manifests follow the public templates and validate as JSON5; Amber itself (`amber compile`) runs only in the leaderboard
repository's workflow.

1. **Build and publish the images.** Push the repository with the v1.2.0 commit, check that the CI `docker` job is green, then
   `git tag v1.2.0 && git push --tags`. The `publish-image` workflow builds, smoke-tests (oracle = 100 inside the image) and
   pushes `ghcr.io/<owner>/medibuddy-bench:1.2.0` and `ghcr.io/<owner>/medibuddy-bench-purple:1.2.0` (owner in lower case).
2. **Make both packages public.** GitHub → your profile → Packages → `medibuddy-bench` → Package settings → Change visibility →
   Public; the same for `medibuddy-bench-purple`. AgentBeats pulls images without credentials.
3. **Check the image names** in `amber-manifest.json5` and `agentbeats/purple-agent.json5` (`ghcr.io/talhaahmed86402/...`).
   If the owner differs, change them, commit, and move the tag.
4. **Register the agents on agentbeats.dev** (sign in with GitHub → Register Agent): the green agent with the image
   `ghcr.io/<owner>/medibuddy-bench:1.2.0`, and the reference purple agent with `ghcr.io/<owner>/medibuddy-bench-purple:1.2.0`.
   Note each agent's id.
5. **Create the leaderboard repository** from `RDI-Foundation/agentbeats-leaderboard-template` ("Use this template"). In its
   Settings → Actions → General → Workflow permissions, choose **Read and write permissions**.
6. **Add the scenario.** Copy `agentbeats/scenario.json5` to the root of the leaderboard repository and fill in the green
   agent's id under `metadata.agentbeats_ids.medibuddy_bench`. The manifests are read from this repository at the `v1.2.0`
   tag; if the repository is private, put both manifest files in the leaderboard repository and point `manifest` at
   `./amber-manifest.json5` and `./purple-agent.json5` instead.
7. **Run it once.** Push the change to a branch other than `main` (or Actions → Run Scenario → Run workflow; `num_shards`
   splits the 832 episodes over parallel jobs, at most 20; each job may run 330 minutes). The run summary links a pull
   request with `results/<owner>-<time>.json`; merge it.
8. **Show the leaderboard.** On agentbeats.dev, Edit Agent (the green agent) → leaderboard repository URL and queries (the
   DuckDB example above). The reference purple agent scores low on purpose (it uses no model).
9. **Students** then register their own purple agents and submit with Quick Submit from agentbeats.dev.

**Never publish an image that contains the hidden split or the private seed.** The images carry only `data/lite` and `data/dev`;
the official hidden-split leaderboard is run by the maintainers (`docs/LEADERBOARD.md`). Behind a proxy, `--card-url` (or
`$MEDIBUDDY_PUBLIC_URL`) sets the URL written in the agent card.

If a step looks different on the platform (the templates were moving from `scenario.toml` to `scenario.json5` when this was
written), follow the template's README; the service itself only needs the request and result formats in the table above.

## Purple agents (what students need)

Any A2A agent that answers plain text works. The benchmark opens one `contextId` per episode, so an agent can keep history per
context. The text protocol inside the messages (`<tool_call>`, `<tool_result>`, `<answer>`) is described in
`docs/INTEGRATION.md`; `medibuddy_bench/a2a/purple_server.py` is a reference purple agent (OpenAI-compatible or Anthropic backend).

## a2a-sdk version

The official templates pin a2a-sdk 0.3.20-0.3.22; this project pins 0.3.26 (`requirements-a2a.lock`). a2a-sdk 1.x removed
`a2a.server.apps` and changed the agent card and part types, so the servers stop with a clear message on 1.x. Supporting 1.x means a
second server path built from `a2a.server.routes` with `enable_v0_3_compat=True`; it is not needed while the platform uses 0.3.
