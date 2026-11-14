# Decisions and defaults

Made without the team (the meeting is Fri 2026-10-30 morning); each is easy to change. Please confirm or overrule.

| # | Decision | Why | Alternative |
|---|---|---|---|
| 1 | Fully synthetic world, no real hospital data | reproducible, no privacy/licensing issues, lets us plant traps with known gold | seed from HIRA open data later |
| 2 | Deterministic scoring, no LLM judge | leaderboard must be cheap, reproducible, un-gameable by judge prompts | optional LLM-judge track for free-text quality |
| 3 | Safety gates zero the score (C1–C4) | one wrong dose or missed emergency should not be averaged away | report-only (no gating); both are reported |
| 4 | Interpretation is the largest weight (20) | most safety-critical and most distinctive for the product | equal weights |
| 5 | Patient speaks English, doctor speaks Korean only | matches the product use case | add other patient languages |
| 6 | Text-only wire protocol with `<tool_call>` / `<answer>` | the AgentBeats template's `talk_to_agent` is text-only | structured A2A parts |
| 7 | Tool budget 25 calls / episode | stops brute-force enumeration while allowing verification | tune after LLM pilots |
| 8 | Triage uses textbook cases only | avoid clinically ambiguous labels we cannot validate | add clinician-curated borderline cases |
| 9 | World dates are in the future (2026-11-30 … 2027-06-25) | models cannot have memorised them | – |
| 10 | Stdlib-only Python ≥ 3.10 | runs anywhere in the course environment | – |
| 11 | Hidden test split from a secret seed | stops overfitting to dev | – |
| 12 | Hygiene checks in T7 are gates, not rewards | doing nothing must not score | – |
| 9a | Hard vs soft preferences (requested by Talha, 2026-10-30): firm requirements are non-negotiable, flexible ones must come with options and a stated trade-off | matches how patients talk; language gaps are rarely all-or-nothing | all-hard (v0.1) |
| 10a | Dev numbers are synthetic; calibrate distributions from real data (see docs/DATA_CARD.md, scripts/import_real_data.py) | synthetic language/interpreter shares are invented | keep fully synthetic |
| 13 | Synthetic data is the final data; real files only calibrate distributions (team decision, 2026-11-09) | scale, diversity and reproducibility; no licence or privacy burden | add real hospital index later |
| 14 | Memory in T7/T8 is provided by the evaluator's memory tools (agents do not bring their own store) | comparable runs; the store can be inspected for the privacy gate | agent-owned memory |
| 15 | T8 excludes the memory step | keeps the journey a single visit | add a two-visit journey |
| 16 | Hospital traps cost points; safety traps (C1-C4) zero the episode. OPEN: should a hospital trap (e.g. recommending a closed hospital) also zero it? | currently only safety harms are catastrophic | gate hospital traps too |
| 17 | Patients write English only in v1.0; hospital-side languages are multilingual | scope; multilingual patients need translated test sets | Phase B: patient-language variants |
| 18 | The benchmark is platform-agnostic: agents plug in through any of OpenAI-compatible server, Python class, HTTP, command line, or A2A; no OS, GPU or serving platform is required | other teams' agents must be able to integrate; Ollama is a convenience, not a dependency | A2A only |
| 19 | The A2A request/response format is defined by this project (docs/AGENT_INTERFACE.md) because no course template was available | a self-contained, tested specification; the evaluation loop is framework-independent so a template shim is small | adopt the course template if one appears |
| 20 | Reproducibility is enforced by seeds, content hashes (`verify`), a pinned lock file, a Docker image that fails on data mismatch, and a cross-OS CI matrix; model outputs are inherently not bit-exact, so run records store the environment | what can be exact is exact; what cannot is documented and measured (pass^k) | none |
| 21 | Hospital facts must come from the benchmark tools; any model or reasoning aid is allowed; `dev` is self-reported, official scores come from the hidden `test` split | the world is synthetic, so outside sources cannot supply correct ids; the benchmark cannot block a student's network | `grounded` and `verified` checks penalise outside facts; maintainers may run the official evaluation with the agent in a container without internet |
| 22 | Patient wording is paraphrased from pools (3-7 variants per sentence and style); the hidden test split may add private held-out paraphrases; T4 texts and the Korean doctor turns stay single-wording until a clinician and a Korean speaker can review changes (the English patient turns of T5/T6/T8 are paraphrased since v1.2.0) | single-template wording lets agents or scripts learn our phrasing instead of the task (the rule agent fell from 65.8 to 47.1 once wording varied) | paraphrase pools are written by us and share our style; extend `gen/phrasing.py`, and have someone else write the held-out file |
| 23 | Scores never reward inaction or unverifiable claims (v1.2.0): grounding needs ids returned by a tool in the episode; an empty triage reply gets no conduct credit; T3 gets no efficiency credit without a revealing question; the T4 follow-up turn is independent of the gold label | an agent that says nothing, or guesses ids, must not collect points, and the runner must not leak the answer | keep the v1.1.0 rules (inflated floor for weak agents) |
| 24 | Data v1.2.0 changes scenario content, not only wording (coherent personas, per-complaint sentences, T8 visit matches the complaint); `--no-phrasing` no longer reproduces v1.0.0 files | realism problems a reviewer would spot in the first scenario ("Ravi from China, painful periods"); fixing them needs new draws | words-only fixes (would leave the incoherent journeys) |
| 25 | The A2A service follows the public AgentBeats conventions: JSON `result` artifact, `shard_index`/`num_shards`, `rejected` on bad input, a2a-sdk 0.3.x (`docs/AGENTBEATS.md`) | the course platform is most likely AgentBeats; its gateway drops non-JSON artifacts and its runner shards assessments | wait for a course template |
| 26 | Maintainers publish open-model results as reference rows (`--baseline`), not as ranked entries; qwen3 runs with thinking switched off | references calibrate difficulty without competing with students; thinking-off keeps runs comparable and affordable | rank them; run reasoning modes |
