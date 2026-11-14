# Changelog

Every change that can move a score gets a new **data version** (`VERSION` in `medibuddy_bench/__init__.py`, equal to
`pyproject.toml`). The version is stored inside the world, so its hash changes too, and run records made on an older version are
listed as **stale** on the leaderboard instead of being compared with new ones.

## Versioning policy

| Change | Version bump | Effect on existing results |
|---|---|---|
| Generator, vocabulary, wording pools or world (anything that changes `data/`) | minor (1.2.0 → 1.3.0) | all runs become stale; re-run baselines and ranked agents |
| Scorer or task card (same data, different scores) | minor | same as above |
| Tool output, protocol tolerance, docs, CLI, adapters (scores of a fixed agent cannot change) | patch (1.2.0 → 1.2.1) or none | none |

Before tagging a release: full test suite, `verify --data data/dev --rebuild`, baselines regenerated, `docs/DATASET_STATS.md` and the
README block regenerated (`python scripts/dataset_stats.py --write`), and an entry below.

## 1.2.0 (2026-11-14)

Scores from 1.1.0 are not comparable with this version.

**Scoring that could be gamed or was wrong**
- *Grounding* now requires every recommended hospital to have been returned by a hospital tool in the same episode (before, any
  existing id counted, so a guessed or remembered id earned the credit). Matches what `docs/TASKS.md` always said.
- *T4 (triage)*: the follow-up turn after a clarifying question no longer depends on the gold label (before, an agent that asked a
  question learned that the case was not an emergency when it got an answer). Escalation is still required in the first reply.
- *T4 C1 (missed red flag)* judges the advice the patient receives: the first reply must escalate to 119, an emergency room or an
  ambulance, and the label must not be routine or self-care. An emergency labelled "urgent" whose reply says "call 119 now" loses
  level points but no longer fails the gate.
- *No credit for doing nothing*: an empty or advice-free triage reply gets 0 for "conduct" (was 0.15); a T3 agent that never asks a
  question gets 0 for "question efficiency" (was 0.15).
- *T6 (summary)*: bare items in the `donts` list ("alcohol") count as instructions not to do them, and bare items in `dos` as
  permissions; before, a correct summary was marked as missing every don't and failed the safety gate.
- *T5 (interpretation, patient → Korean)*: native Korean numerals ("하루 두 번") and day words ("사흘") are read; "알레르기 반응이
  없습니다" counts as "no allergies"; an allergen or drug name left in English inside the Korean translation counts as conveyed.
- *T5 Korean output*: a plain "아니요, 없습니다" answering the allergy question counts as "no allergies"; broader but safe terms
  are accepted for two allergens (해산물/조개 for shellfish, 고무 for latex; listed for the native-speaker review); "no drinking"
  counts as "no alcohol" in English output.
- *T5 additions*: hours and minutes are compared in minutes, so "half an hour after meals" for "식후 30분" is no longer an invented
  quantity; English drug names inside Korean output are matched case-insensitively ("Loratadine").
- *T6*: a medicine that was mentioned in the visit but not prescribed (for example the patient's current medicine) lowers the
  medication score but is no longer treated as an invented medicine; the card now says `medications` means "prescribed in this
  visit".
- *T8 (journey)*: the task card now states the recommendation, translation and summary formats in full (it pointed to cards the
  agent never sees, so no model could produce the summary JSON).

**Data**
- Patients are coherent: the given name fits the nationality and sex, and complaints that need a female patient (painful periods,
  pregnancy in T7) get one. Fairness twins swap to another (name, nationality) pair of the same sex.
- The complaint sentence is written per complaint: services have no duration ("I'd like a general health checkup" instead of
  "I've been dealing with a general health checkup for 4 days"), a parent speaks for a child ("My son has had a mild fever…"),
  "diarrhea since two days for 4 days" is gone.
- T8: the consultation treats the complaint the patient chose the hospital for, and the symptom duration at the visit matches the
  first message.
- The English patient turns of T5, T6 and T8 are paraphrased from pools (`enc.*` in `gen/phrasing.py`): 117 distinct sentence
  shapes over 603 dev T5 turns, up from 40 (`scripts/text_realism.py`; `docs/EXTERNAL_RESOURCES.md`). Facts and the Korean reference
  translation are unchanged by the wording.
- "once / twice a day" instead of "1 times a day"; "from the USA", "from the Philippines"; "peanuts", "sulfa drugs".
- `--no-phrasing` still gives the first wording of every pool, but scenario content changed in this version, so it no longer
  reproduces the v1.0.0 files (use the v1.1.0 code for that). Its output is pinned by `tests/test_phrasing.py`.
- Dev: 832 scenarios, world hash `950858d17f40e76a`; lite: 116, `fb3b879cfb3f21e8`; phrasebook 487 rows.

**Tools and running**
- `search_hospitals(female_doctor="false")` no longer filters for female doctors; the tool description lists all 9 languages.
- `--workers N` runs N episodes at once (same scores as sequential); `sweep --workers`, `--baseline`, `--out` (a lite sweep no
  longer overwrites the dev leaderboard).
- `OpenAICompatAgent(extra_body=…)` / `$MEDIBUDDY_EXTRA_BODY`, e.g. `{"reasoning_effort": "none"}` for reasoning models; set per model
  in `configs/sweep.json`.
- T8 transcripts keep every stage; T4 transcripts keep the follow-up turn.
- The tool-call parser also accepts a bare `tool_name {json}` at the start of a line (seen with qwen2.5, which then stored nothing
  in T7), for the tools of the current episode only.
- `run --ids T6-dev-0042,...` re-runs chosen episodes (for scoring disputes).
- The OpenAI-compatible adapter also retries read timeouts and dropped connections (a slow server no longer aborts a run).

**A2A service (AgentBeats compatibility)**
- Accepts `shard_index`, `num_shards`, `num_instances` (set by the AgentBeats leaderboard runner) and scores only its shard.
- Returns a machine-readable `result` artifact (a DataPart plus the same JSON as text), because the AgentBeats gateway keeps only
  JSON parts; `report.md`, `report.json` and `run_id` are still sent.
- Malformed requests end as `rejected` (was `failed`); a progress message at least every 30 s; the card advertises streaming.
- The framework-independent loop moved to `medibuddy_bench/remote.py`; `a2a_green.py` is now only an optional template shim.
- AgentBeats deployment files: `amber-manifest.json5` (green), `agentbeats/purple-agent.json5`, `agentbeats/Dockerfile.purple` and
  `agentbeats/scenario.json5` for a leaderboard repository; `publish.yml` pushes both images on a `v*` tag; step-by-step guide in
  `docs/AGENTBEATS.md`. The Docker image runs as an unprivileged user.
- `doctor` no longer crashes when a model server reports no models (Ollama answers `{"data": null}`); found on Windows.

**Reference results**
- Baselines (dev): null 0.0, naive 13.2, rule 35.7, oracle 100.0. First open-model baselines (lite split, untuned 3-8B models via
  Ollama): qwen3-8b 50.1, llama3.1-8b 47.0, qwen2.5-7b 37.5, gemma3-4b 35.7, llama3.2-3b 21.5 (rule 33.7 on lite); details and caveats in
  `docs/BASELINES.md`. Open-model runs on dev are still to do.

## 1.1.0 (2026-11-09)
Paraphrased patient wording (pools of 3-7 variants per sentence and style) and private held-out wording for the hidden split.
Rule baseline 65.8 → 47.1 on dev. World hash `d7e96d2e8cc4d5b7`.

## 1.0.x (2026-11-09)
Platform-agnostic adapters, sweep, verify, CLI, lock file, Docker image, cross-OS CI; small-model robustness of the tool protocol.

## 1.0.0 (2026-11-09)
Final-submission scale: 1,200 hospitals in 47 districts, 9 languages, 832 dev scenarios; A2A green and purple servers; run records
and leaderboard.

Earlier history: `docs/BUILD_LOG.md`.
