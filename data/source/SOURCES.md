# Source data (real), since v1.3.0

These files are the real data the benchmark world is built on. They come from two packages made by the team on
2026-11-14 and are imported by `scripts/import_kr_hospitals.py` (deterministic: the same inputs give byte-identical
files). The split folders (`data/dev`, `data/lite`) store only what is synthetic on top of them.

| File | What it is | Origin |
|---|---|---|
| `kr_hospitals.jsonl.gz` | 79,075 Korean medical institutions: hpid, name, type, emergency class, address, coordinates, phone, directions, description, remarks, opening hours for each weekday and public holidays, lunch break (parsed from the remarks when stated, 15,560 records), cleaned department codes | National Medical Center (국립중앙의료원) "nationwide hospital and clinic search" OpenAPI, Public Data Portal [data.go.kr 15000736](https://www.data.go.kr/data/15000736/openapi.do), no use restrictions. Department lists filtered to each institution's representative group by the team's `filter_subjects.py` (92.5% top-1 accuracy in 5-fold cross-validation; see the team's hospital_DB README) |
| `districts.json` | 256 cities and districts (시군구) with Korean name, region and a centroid (median of the institutions' coordinates; the 47 districts of v1.0-1.2 keep their names and centroids) | Derived from the addresses above |
| `tertiary.json` | The 47 tertiary hospitals of the 5th designation (2024-2026), matched by hpid | Ministry of Health and Welfare designation as reported by Financial News, 2023-12-29 (team's `tertiary_5th.csv`) |
| `places.json` | 66 origins: 30 campuses of the 29 universities with 2,000+ international students plus the 9 regional flagship national universities, and 36 schedule places (stations, business districts), with the district each lies in | OpenStreetMap Nominatim, searched 2026-11-14 (team's `places.csv`) |
| `travel.csv.gz` | 20,707 travel times (minutes, shorter of walking and public transit) from each origin to the institutions of its table; `source` = `kakao` (measured with the Kakao Map API on 2026-11-14, origins C18, P12, P13) or `mock` (straight-line estimate: walking = distance x 1.3 at 4.5 km/h, transit = 8 min + 2.5 min per km) | Team's travel collector and table builder |
| `symptoms.json` | 31 mild and moderate symptoms with the department groups that treat them and the evidence | Team's `symptom_departments.csv`; none of the symptoms is on Annex 1 of the Enforcement Rule of the Emergency Medical Service Act |
| `t9_pool.jsonl.gz` | 1,165 clinic-choice items (agent view and gold), the pool task T9 draws from | Team's benchmark build of 2026-11-14 (`benchmark_full_1165`); visit notes were written by an LLM from the visit facts |

What is real and what is synthetic in the world built from these files:

- **Real:** which institutions exist, their ids, names, types, addresses, coordinates, phone numbers, weekly and holiday
  hours, stated lunch breaks, departments, emergency rooms, tertiary status; campus and station locations; Kakao
  travel times around SKKU's Natural Sciences Campus.
- **Synthetic (drawn per split from its seed, per hospital):** languages spoken and interpreter service (calibrated on
  the KHIDI list of foreign-patient-friendly hospitals), rating, price level, female doctor, walk-in, the date the
  record was last verified, the English blurb; dated notices (closures, hour changes, suspended departments).
- **Synthetic but rule-based (the team's rule, fixed per hospital id):** non-covered prices for a flu shot, a medical
  certificate and shockwave therapy.
- **English names** are a translation of known name parts plus a romanization of the rest
  (`medibuddy_bench/romanize.py`), not official English names.

Regenerate (inputs are not committed; they are in the team's packages):

```bash
python3 scripts/import_kr_hospitals.py <hospital_DB>/hospitals_subjects_filtered.json <MediBuddy_benchmark_2026-11-14> data/source
```
