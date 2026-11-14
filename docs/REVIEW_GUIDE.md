# Human review guide (needed before the benchmark is trusted)

## Korean (native speaker) – `data/review/korean_phrasebook.csv`
487 rows (data v1.2.0). Doctor rows are Korean with an English reference; patient rows are English (several paraphrases of the same
sentence) with the Korean reference the agent's translation is checked against. Columns: `speaker, source_text, reference_translation`,
then fill `OK? (y/n)`, `native_speaker_correction`, `comment`. For each row judge: (a) natural? (b) meaning identical to the English?
(c) polite register right for a clinic? (d) colloquial variants (L3) realistic? Priorities: negations ("don't drink alcohol"),
frequency ("three times a day"), allergies, and merged L4 utterances.

Also review the matching vocabulary the scorer accepts in agents' Korean output (`ko_alias` in `medibuddy_bench/knowledge.py`), in
particular the broader terms accepted since v1.2.0: 해산물 / 조개 for shellfish and 고무 for latex. If a term is too loose or a common
correct rendering is missing, the scorer marks good translations wrong (or wrong ones right).

## Clinical – `data/review/triage_labels.csv`
Columns: `case, benchmark_label, example_text_L1`, then fill `clinician_agrees? (y/n)`, `clinician_label`, `comment`. A clinician or nurse checks each presentation: is the label (emergency / urgent / routine / self-care) defensible for a layperson-facing triage
policy? Any case where reasonable clinicians disagree should be removed or relabelled. Also check the clinical profiles in `gen/encounters.py` (drug-allergy blocks, warning signs).

## How to apply fixes
Edit the templates in `gen/ko.py`, `gen/encounters.py`, `gen/triage.py`, rebuild (`python3 -m medibuddy_bench.gen.build --split dev --seed 1 …`),
run the tests, and bump `VERSION` in `medibuddy_bench/__init__.py` (the data hash changes).
