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
| 9 | Hard vs soft preferences (requested by Talha, 2026-10-30): firm requirements are non-negotiable, flexible ones must come with options and a stated trade-off | matches how patients talk; language gaps are rarely all-or-nothing | all-hard (v0.1) |
| 10 | Dev numbers are synthetic; calibrate distributions from real data (see docs/DATA_CARD.md, scripts/import_real_data.py) | synthetic language/interpreter shares are invented | keep fully synthetic |
