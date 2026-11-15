# Data card

- **Origin (v1.3.0): real institutions, synthetic layer, synthetic people.** The hospital index is the real one: all 79,075
  institutions of the National Medical Center "nationwide hospital and clinic search" OpenAPI (data.go.kr 15000736; 79,071 with
  coordinates), with real ids (hpid), names, types, addresses, coordinates, phone numbers, weekday, Sunday and holiday hours,
  stated lunch breaks, cleaned departments (the team's representative-group filter), emergency rooms and the 47 tertiary hospitals
  of the 5th designation, in 256 real cities and districts. On top of it, per split and per hospital, synthetic languages,
  interpreter service, ratings, price levels, female doctor, walk-in, verification date, blurb and dated notices. Patients,
  conversations, consultations and memories are synthetic. Provenance and what is real: `data/source/SOURCES.md`.
- **Places:** 30 real campuses (the 29 universities with the most international students and the regional flagship national
  universities) and 36 stations and business districts (OpenStreetMap coordinates); about half of the choice scenarios start at a campus.
- **Travel times (T9):** the team's table: measured with the Kakao Map API around SKKU's Natural Sciences Campus (918 pairs),
  straight-line estimates elsewhere (19,789 pairs). T1-T8 use straight-line distance from real coordinates.
- **Real-world grounding (rules):** referral requirement for tertiary hospitals and its exceptions, the 6-month NHI rule, numbers
  119 / 1339 / 1330 (Invest Korea guidance; public); reception closing 30 minutes before closing (common practice, the team's rule);
  symptoms limited to those not on Annex 1 of the Enforcement Rule of the Emergency Medical Service Act (T1-T3, T7-T9 complaints).
- **World window:** 2026-11-30 … 2027-06-25; holidays 2026-12-25, 2027-01-01, 2027-03-01, 2027-05-05, 2027-06-06.
- **Version:** 1.3.0 (`CHANGELOG.md`). **Sizes:** dev 952 scenarios (T9 120) over the 79,071-institution world; lite 132; hashes in each `manifest.json`; full tables in `docs/DATASET_STATS.md`.
- **Patients:** 25 nationalities weighted like the resident population; a given name common in that country for the patient's sex
  (`NAMES_BY_NATIONALITY` in `knowledge.py`, 6 per sex and country); complaints that need a female patient get one. Each complaint
  has its own sentences (services such as a checkup have no duration; a parent speaks for a sick child).
- **Languages:** hospitals support up to 9 languages (en, zh, ja, vi, ru, mn, ar, th, uz); the patient writes English (multilingual patients = future work); English (patient; paraphrased from pools, including the consultation turns), Korean (doctor; template-generated; 487 distinct phrasebook rows reviewable in `data/review/korean_phrasebook.csv`).
- **Known limits:** English hospital names are romanizations, not official names; the real index lists advertised departments
  (cleaned, 92.5% top-1 accuracy), not the doctors on duty; hours are as registered (lunch breaks only when the record states them);
  T9 travel times outside SKKU's Natural Sciences Campus are estimates; the T9 pool is public, so a hidden T9 split needs new items
  from the team's generator with a secret seed; patient wording comes from author-written paraphrase pools (3-7 variants per sentence, `gen/phrasing.py`), so it is more varied than a single template but less varied than real patients; templated Korean; textbook-only triage; no dialects, no accents/ASR noise, no images; one country; simplified rules. Public resources that could reduce these limits, and what was measured with them: `docs/EXTERNAL_RESOURCES.md`.
- **Sensitive-content handling:** health words appear only as fictional scenario content. T7 bait values (ARC number `990101-1234567`) are fake.
- **Splits:** `dev` public; `test` built by the organiser with a secret seed (never commit it); `mini` for smoke tests.
- **Leakage controls:** public view contains no gold; tested in `tests/test_benchmark.py`.


## Synthetic vs real (what is calibrated, what is assumed)

Until v1.2.0 the whole world was synthetic. Since v1.3.0 the hospital index is real (above); real public data shapes the
synthetic layer:

| Quantity | Source | Status |
|---|---|---|
| Languages named per hospital {1:28, 2:54, 3:72, 4:36, 5:24, 6:19, 7:6}; language shares (en 92.9%, zh 65.3%, ru 59.4%, ja 40.2%, mn 35.6%, vi 17.2%, ar 12.6%) | KHIDI language file, 239 portal hospitals (`scripts/import_real_data.py`) | used for the *international-oriented* hospital population |
| Thai and Uzbek hospital shares (10%, 8%) | not in the KHIDI file | **assumed** |
| Share of hospitals that are international-oriented by tier (10 / 25 / 55 / 90 %), ordinary-hospital language rates | none | **assumed** |
| Resident nationality mix of patients (China ~30, Vietnam ~14, USA ~7, Thailand ~7, Uzbekistan ~5, ...) | Ministry of Justice Dec 2025 via a secondary source (Seoulstart) | approximately followed; tail flattened so every language is exercised |
| Neighbourhood language clusters (e.g. Ansan, Dongdaemun, Incheon Namdong) | general knowledge of resident communities | **assumed**, labelled in `gen/hospitals.py` |
| Tier mix, hours, departments, emergency rooms, tertiary list | National Medical Center index (real since v1.3.0) | **real** |
| Prices (price level), ratings, interpreter shares | none | **assumed** |
| Non-covered prices: flu shot 18-45k won (mode 30k), certificate 10/15/20k won, shockwave 30-175k won (mode 70k) | Dailypharm 2026, fee notice (Medical Times), MTN 2026 (the team's sources) | **rule-based synthetic** |

Consequence: absolute shares of the synthetic attributes (for example "English is supported by 29% of hospitals") describe the
benchmark world and not Korea; counts of institutions, departments, hours and emergency rooms describe Korea.
What is claimed is realism of *structure* (a few international hospitals with many languages, most clinics with none or English
only, tertiary hospitals requiring referral), which is what the tasks test.
