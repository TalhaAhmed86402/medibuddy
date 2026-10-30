# Human review guide (needed before the benchmark is trusted)

## Korean (native speaker) – `data/review/korean_phrasebook.csv`
Columns: `speaker, source_text, reference_translation`, then fill `OK? (y/n)`, `native_speaker_correction`, `comment`. For each row judge: (a) natural? (b) meaning identical to the English?
(c) polite register right for a clinic? (d) colloquial variants (L3) realistic? Priorities: negations ("don't drink alcohol"),
frequency ("three times a day"), allergies, and merged L4 utterances.

## Clinical – `data/review/triage_labels.csv`
Columns: `case, benchmark_label, example_text_L1`, then fill `clinician_agrees? (y/n)`, `clinician_label`, `comment`. A clinician or nurse checks each presentation: is the label (emergency / urgent / routine / self-care) defensible for a layperson-facing triage
policy? Any case where reasonable clinicians disagree should be removed or relabelled. Also check the clinical profiles in `gen/encounters.py` (drug-allergy blocks, warning signs).

## How to apply fixes
Edit the templates in `gen/ko.py`, `gen/encounters.py`, `gen/triage.py`, rebuild (`python3 -m medibuddy_bench.gen.build --split dev --seed 1 …`),
run the tests, and bump `VERSION` in `medibuddy_bench/__init__.py` (the data hash changes).
