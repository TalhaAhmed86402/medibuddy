# Running MediBuddy-Bench on AgentBeats

MediBuddy-Bench is an A2A **green agent**: it receives one assessment request, talks to the student's **purple agent** over A2A, and
returns the scores. This page maps it onto the public AgentBeats conventions (RDI-Foundation `green-agent-template`,
`agentbeats-gateway` and `agentbeats-leaderboard-template`, read on 2026-11-14).

**Status.** The request format, the result artifact, sharding, the heartbeat and the CLI flags follow those templates and are
tested locally with a2a-sdk 0.3.26 (`tests/test_a2a.py`). Both images are public on ghcr.io and the green agent
(`01a1dc6f-ff30-79c0-8c5b-08b149ef1c3f`) and the reference purple agent (`01a1dc71-691f-7811-82b7-49bfcf06ebef`) were registered on
agentbeats.dev from their manifests on 2026-11-14. The first platform run (leaderboard repository `TalhaAhmed86402/medibuddy-leaderboard`, 2026-11-15, reference purple agent, dev, one shard) took about 11 minutes and returned one row: overall 0.56, ungated 2.25, C1 58, C2 351. The same assessment run locally gives the same numbers. If the course runs its own
platform with a different template, check this page against it first.

## What the platform sends and what the benchmark returns

| | AgentBeats convention | MediBuddy-Bench |
|---|---|---|
| Request | one text message, JSON `{"participants": {role: url}, "config": {...}}` | same; the role is `purple` (any single role name is accepted) |
| Config | free-form; the leaderboard runner adds `shard_index`, `num_shards`, `num_instances` | `tasks`, `tiers`, `limit`, `trials`, `max_tool_calls`, `split`, `name`, `model`, plus the three shard keys; unknown keys are rejected |
| Progress | `TaskState.working` status updates | an update every 10 episodes and at least every 30 s |
| Result | the gateway keeps only JSON parts of the final artifacts (DataPart data, or text that parses as JSON) | artifact `result`: one flat JSON row (a DataPart), the only JSON part sent; `report.json` goes as a file part and `report.md`, `run_id` as plain text, which the gateway ignores |
| Bad request | `reject` | the task ends `rejected` with the reason ("the message must be JSON", "unknown config keys", ...) |
| Image | public, linux/amd64, accepts `--host`, `--port`, `--card-url` | `Dockerfile` (see below); `serve --host --port --card-url` |

### The `result` row

```json
{"id": "20261114-031500-my-agent", "benchmark": "medibuddy-bench", "data_version": "1.2.0", "world_hash": "950858d17f40e76a",
 "split": "dev", "agent": "my-agent", "model": "qwen2.5:7b", "overall": 41.3, "overall_ungated": 55.0, "covered_weight": 100,
 "n_episodes": 832, "tasks": {"T1": 52.1, "T2": 40.0, "...": 0}, "critical": {"C1_missed_red_flag": 3, "...": 0},
 "trials": 1, "shard_index": 0, "num_shards": 1, "pass_hat_k": {"1": 0.31}}
```
Scores are 0-100 and gated (a critical failure zeroes the episode). The gateway (v0.3 `src/assessment.py`, `parse_parts`) turns
every DataPart and every text part that parses as JSON into a row, so the service sends exactly one (tested in
`tests/test_a2a.py` with the same rule). With shards, each shard reports its own row for its share of the episodes.

### Leaderboard query (DuckDB over `results/*.json`)

AgentBeats runs each query over `read_json_auto('results/*.json') AS results`: one row per results file, with columns
`status`, `participants` (role → AgentBeats id, from the scenario's `metadata.agentbeats_ids`) and `results` (the rows above).
**The first column must be the participant's AgentBeats agent id**; `AS` names the columns. The ready-made query is
`agentbeats/queries.json` (paste its content into the green agent's Leaderboard Config → Queries). It shows one line per complete,
unsharded dev run of data version 1.2.0:
```sql
SELECT results.participants.purple AS id, r.overall AS "Overall", r.overall_ungated AS "Ungated",
       r.tasks.T1 AS "T1 Hospital search", ..., r.tasks.T8 AS "T8 Journey",
       r.critical.C1_missed_red_flag AS "Missed emergencies", r.n_episodes AS "Episodes"
FROM results CROSS JOIN UNNEST(results.results) AS u(r)
WHERE results.status = 'completed' AND r.benchmark = 'medibuddy-bench' AND r.data_version = '1.2.0'
  AND r.split = 'dev' AND r.num_shards = 1 AND r.covered_weight = 100
ORDER BY r.overall DESC
```
Sharded runs are left out because a shard row covers only part of the episodes; Quick Submit uses one shard by default
(`num_shards: 1` in the template's `quick-submit.yml`), and one shard of 832 episodes fits the 330-minute job limit for agents
that answer in a few seconds. Checked with DuckDB 2.0.0 on files of the template's shape (`{"status", "participants",
"results": [rows]}`) built from real `result` rows; the platform's own files have not been seen yet.

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
4. **Register the agents on agentbeats.dev** (sign in with GitHub → Register Agent). The form asks for an **Amber Manifest
   URL** (the manifest names the image), not an image: the green agent with
   `https://raw.githubusercontent.com/<owner>/medibuddy/v1.2.0/amber-manifest.json5`, the reference purple agent with
   `https://raw.githubusercontent.com/<owner>/medibuddy/v1.2.0/agentbeats/purple-agent.json5`; Repository Link is this
   repository. Leave the Leaderboard Config (GitHub repo, Queries) empty until step 8. Note each agent's id.
5. **Create the leaderboard repository** from `RDI-Foundation/agentbeats-leaderboard-template` ("Use this template"). In its
   Settings → Actions → General → Workflow permissions, choose **Read and write permissions**.
6. **Add the scenario.** Copy `agentbeats/scenario.json5` to the root of the leaderboard repository (its green agent id,
   `metadata.agentbeats_ids.medibuddy_bench`, is already filled in) and delete the template's old `scenario.toml`. The gateway's participant slots are `purple1`..`purple5` (`purple1` required), and the benchmark's `proxy` slot is bound to `#gateway.proxy` (weak), as in the gateway's own example; the role name `purple` matches `participant_roles` in `amber-manifest.json5`. The manifests are read from this repository at the `v1.2.0`
   tag; if the repository is private, put both manifest files in the leaderboard repository and point `manifest` at
   `./amber-manifest.json5` and `./purple-agent.json5` instead.
7. **Run it once.** Put the reference purple agent's id in `metadata.agentbeats_ids.purple` and push to a branch other
   than `main` (or Actions → Run Scenario → Run workflow). Keep one shard: the query counts only unsharded runs, and one job
   may run 330 minutes. The run summary links a pull
   request with `results/<owner>-<time>.json`; merge it.
8. **Show the leaderboard.** On agentbeats.dev, Edit Agent (the green agent) → Leaderboard Config: GitHub Repo = the
   leaderboard repository, Queries (JSON) = the content of `agentbeats/queries.json`. The reference purple agent scores low on purpose (it uses no model).
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
