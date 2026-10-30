# Build log (how / why / what)

## Order of work
1. Read the Phase-2 requirement and the proposal design; chose 8 tasks mirroring the product journey (search → live info → clarify → triage → interpret → summarise → remember → end to end).
2. Wrote `knowledge.py` (domain lexicons: districts, specialties, complaints, drugs, allergens, diagnoses, tests, Korean/English topic phrases) and `rules.py` (the world's rule document).
3. `world.py`: hospital world, live status, constraint violation logic (`violations`), valid set / near misses / best ordering. One function decides truth for generator, scorer and oracle, so they cannot drift apart.
4. Generators per task (`gen/`), each producing public and gold parts; `build.py` assembles splits and repairs scenarios invalidated by later notices.
5. Fact engine (`scoring/facts.py`) with EN/KO normalisers; then per-task scorers; aggregation with gating and pass^k.
6. Runner, tools, patient simulator, text protocol, baselines and saboteurs.
7. Tests, pilot, docs, A2A adapter.

## Problems found and fixed
| Problem | Fix |
|---|---|
| Korean "이레" matched inside "타이레놀" | lookbehind; dropped ambiguous words |
| "1/2 pill" read as "2 pill" | lookbehind |
| wrong duration classified as missing | day facts do not use `claimed` |
| slow build; T8 could not be repaired | caching; `choice_task` in `finalize_choice` |
| single-turn finality would punish asking agents | a reply naming hospitals is final; 4-turn (8 for T3) caps |
| T7 hygiene checks gave free credit for doing nothing | converted to gates only |
| Triage fallback labelled empty text as self-care | new `none` level scores 0 |
| Rule baseline scored 1.00 on T1–T3, T7 (template-solvable) | tiered phrasing (month-name dates L3, relative dates + informal L4) → T1 0.63, T2 0.62 |
| duplicate scenario id after repair (T1-dev-0039) | renumber ids after repair; `test_ids_unique` |
| a2a-sdk 1.x lacks `a2a.server.apps` | adapter's template imports isolated; documented as unverified |

## Verification
`python3 -W ignore -m unittest discover -s tests` → 12 tests (determinism, leakage, unique ids, solvable gold, oracle/null/naive/ordering, 11 saboteur gates, protocol tool loop) + `tests/test_facts.py` (34).
Saboteur gates observed on dev: flip_freq / drop_negation / add_dose / wrong_allergy_ko → C2 on T5 (and T8); invent_dx / wrong_follow → C2 on T6 (and T8);
canary → C4 on T1/T2/T3/T7/T8; no_escalation → C1 on all 39% emergency T4 cases; keep_deleted / store_id → C3, blood_guess → C2 on T7.

## Not done
LLM baselines; native-speaker and clinician review; paraphrase augmentation; a real A2A server entry point and a live-platform test; `docs/ISSUES.md`.


## v0.2 (2026-10-30) hard vs soft preferences
world.py rewritten with docstrings and runnable examples (52 doctests); soft preferences added to generator, scorer, task card,
rule and oracle agents; dev regenerated (soft: T1 17/40, T2 15/32, T3 6/32). Oracle 1.00 everywhere; rule T1 .65, T2 .63, T3 .81,
pass^1 .61; 46 pytest checks pass. Saboteurs not rerun after this change. Not yet soft: memory (T7), journey (T8).
