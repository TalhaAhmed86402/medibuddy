# External resources for the known limits

This note lists public resources that can reduce each limit named in `DESIGN.md` section 8 and `docs/DATA_CARD.md`, what each one offers, how it can be reached, and what was done with it. It is separate from the build: nothing here is downloaded into the repository or needed to regenerate the data.

Access was tested from the build environment on 2026-11-09. Only GitHub, PyPI and npm were reachable from the command line; web pages could be read through a search and fetch tool, but bulk downloads from Hugging Face, Zenodo, arXiv, NIH, OpenRouter and AI Hub were blocked. Resources marked **manual** need a person with a normal browser.

## Summary

| Limit | Resource | Access | Used here? |
|---|---|---|---|
| Patient wording is less varied than real patients | ACI-Bench (207 encounters, CC BY 4.0) and MTS-Dialog (CC BY 4.0) on GitHub | Reachable | Yes: variety measured (below). Not copied into the repository |
| Korean doctor speech has had no native review | `kiwipiepy` (PyPI) for automatic checks | Reachable | Yes: `scripts/korean_lint.py` |
| Korean doctor speech has had no native review | Washington State DSHS "Medical-Korean" interpreter booklet | **Manual** (scanned PDF, text not extractable) | No |
| Korean doctor speech has had no native review | MedlinePlus Korean pages; Korean Medical Association terminology search | **Manual** (blocked from the build environment) | No |
| Drug instructions in T5/T6 are unchecked against an official source | MFDS "e약은요" drug overview API on data.go.kr | **Manual** (account and key needed; page not fetchable here) | No |
| Triage labels are not clinician-reviewed | Public triage criteria: AHRQ Emergency Severity Index (ESI) handbook; Korean Triage and Acuity Scale (KTAS) descriptions | ESI reachable through archive pages; full KTAS manual **manual** | Partly: a pre-screen of the 29 cases (below) |
| Triage labels are not clinician-reviewed | Semigran et al. 2015 (BMJ), 45 vignettes graded emergent / non-emergent / self-care (CC BY-NC) | **Manual** (appendix not fetchable here) | No |
| No language-model baseline | Free hosted model tiers (OpenRouter, Groq, Cerebras, Google AI Studio, GitHub Models) | **Manual** (keys needed; blocked from the build environment) | No |

## Findings from what was reachable

### Patient wording against real consultations

`scripts/text_realism.py` compares the benchmark's patient text with the patient turns of ACI-Bench and MTS-Dialog (7,520 sentences). The real corpora are spoken clinic conversations, so sentence length and question rate partly reflect genre. Variety is the meaningful measure.

| Text | Sentences | Words per sentence | Distinct shapes per sentence | Distinct word triples (share) | Contraction rate | Hedge or filler rate |
|---|---|---|---|---|---|---|
| Real patient turns (all) | 7520 | 9.8 | 0.96 | 0.77 | 0.29 | 0.29 |
| Real patient turns (800 sampled) | 1108 | 9.8 | 0.99 | 0.92 | 0.28 | 0.31 |
| Benchmark v1.1.0: T1-T3 openings | 2163 | 8.2 | 0.41 | 0.25 | 0.40 | 0.19 |
| Benchmark v1.1.0: T5 patient turns | 570 | 5.1 | 0.07 | 0.07 | 0.31 | 0.01 |
| Benchmark v1.2.0: T1-T3 openings | 2232 | 7.7 | 0.39 | 0.29 | 0.35 | 0.13 |
| Benchmark v1.2.0: T5 patient turns | 580 | 5.1 | 0.20 | 0.22 | 0.22 | 0.04 |

Reading: the hospital-choice openings are still far less varied than real speech. In v1.1.0 the patient turns in T5 (weight 20) were close to templated: 605 turns reduced to 40 distinct shapes. Data v1.2.0 paraphrases them from pools (`enc.*` in `gen/phrasing.py`): 117 distinct shapes over 603 turns, and three times the share of distinct sentence shapes and word triples. Hedges and fillers remain rare (0.04 versus 0.29 in real speech), and the T1-T3 hedge rate fell slightly because the per-complaint sentences of v1.2.0 replaced filler-like openers ("I've been dealing with ..."). Both remain known limits; measured with `scripts/text_realism.py` on 2026-11-14.

Two defects found in the same pass (fixed in v1.2.0): the English patient sentence "I take acetaminophen 1 times a day" was ungrammatical (40 dev T5 and 34 dev T6 scenarios), and the same pattern appeared in the phrasebook reference text.

### Korean text: automatic checks

`scripts/korean_lint.py` (needs `pip install kiwipiepy`) parsed 288 distinct Korean strings from the phrasebook and from every Korean doctor turn in dev. Result: every sentence parses into known words and every sentence ends in a polite speech level; the checker flags plain or impolite endings when tested on a deliberately wrong example. This removes one class of error only. Naturalness, idiom and clinical appropriateness still need the native-speaker review in `docs/REVIEW_GUIDE.md`. A spacing check was tried and dropped because it split drug names and common words (for example 일주일) and produced false alarms.

### Triage labels: pre-screen against public criteria

The 29 cases in `data/review/triage_labels.csv` were compared with the public ESI and KTAS level descriptions. This is a pre-screen by a non-clinician, not a review. All eight emergency cases and all routine and self-care cases are consistent with the criteria. Four urgent cases are worth a clinician's attention first:

| Case | Current label | Why it may differ |
|---|---|---|
| U_child_fever (2-year-old, fever 39.5 C, unusually sleepy, drinking little) | urgent | Lethargy in a toddler is a high-risk sign in ESI; may belong in emergency |
| U_ankle (cannot bear weight after a twist) | urgent | ESI would treat a single-resource injury as lower acuity; may be routine, same-day |
| U_cut (deep gaping cut, bleeding stopped) | urgent | Needs sutures but is stable; same boundary as above |
| U_fever_cough (39.5 C for 3 days, worsening cough, breathing normal) | urgent | Reasonable, but the line between urgent and routine depends on local practice |

## Resources that need a person

1. **Clinician or senior nursing student for triage.** Give them `data/review/triage_labels.csv` together with the table above. A KTAS-trained emergency nurse is the best match for a Korean setting.
2. **Korean speaker for the phrasebook.** `data/review/korean_phrasebook.csv`, 487 rows (data v1.2.0); the automatic checks above already cover parsing and speech level.
3. **KTAS manual.** The full chief-complaint list belongs to the Korean Society of Emergency Medicine (KTAS committee). Search for 한국형 응급환자 분류도구 지침서 and note the licence before reuse.
4. **Drug facts.** The MFDS e약은요 service (data.go.kr, dataset 15075057) gives official Korean patient-facing instructions for each drug in the generator, which can verify frequencies and warnings. It needs a free account and an API key.
5. **Semigran et al. 2015 appendix.** Its 45 graded vignettes are the most widely used public triage set. The licence is non-commercial, which suits coursework but should be stated.
6. **MedlinePlus Korean.** Useful for lay Korean health vocabulary; check the page-level rights before reuse.

## Language-model baselines

The hosted free tiers listed in an OpenRouter comparison dated June 2026 (updated September 2026) offered, per provider: OpenRouter about 50 requests per day on free models, Groq about 1,000 requests per day, Cerebras about 1 million tokens per day, Google AI Studio 20 to 1,500 requests per day depending on model, GitHub Models 150 to 1,000 requests per day. Limits change often and must be rechecked. The runner already accepts any OpenAI-compatible endpoint (`--base-url`, `--api-key`).

Two cautions. A full lite run is roughly a thousand model calls, which suits token-based allowances better than small daily request caps. And the hidden `test` split must never be sent to a provider whose terms allow training on prompts: dev results from third-party APIs are fine, official test runs are not.

## Not downloaded or redistributed

ACI-Bench and MTS-Dialog were cloned to a scratch directory only to measure variety. No text from them is in this repository. Both are CC BY 4.0; any future reuse of their wording requires attribution.
