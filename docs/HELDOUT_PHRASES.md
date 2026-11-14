# Held-out wording for the hidden test split

**Why.** The generator and its paraphrase pools (`medibuddy_bench/gen/phrasing.py`) are public. An agent, a prompt or a pattern-matching
script tuned on the public wording could look better on `dev` than it is. The hidden `test` split can therefore use **private
paraphrases** that appear nowhere in this repository.

**What it changes.** Only wording. Hospitals, constraints, traps, dates and gold answers come from the seed and are identical with or
without the phrase file.

## Workflow (maintainers)

1. Copy `configs/heldout_phrases.example.json` to a private location, for example `private/heldout_phrases.json` (the `private/` folder is
   git-ignored), and write your own paraphrases. The example file is **only a format illustration**; do not use its sentences as the
   real held-out set, because it is public.
2. Build the hidden split with it:
   ```bash
   python -m medibuddy_bench build --split test --seed <SECRET> --phrases private/heldout_phrases.json --out private/test
   ```
   (`$MEDIBUDDY_PHRASES` works instead of `--phrases`.) The option is accepted for the `test` split only.
3. Keep the seed, the phrase file and the built data private. The same seed, code and phrase file always give identical files.

## File format

A JSON object. Each key is a pool name from `POOLS` and each value is a list of template sentences. For every key you supply, your list
**replaces** the public pool for the test split; keys you leave out keep the public wording.

| Key family | Fields a template can use | Must contain |
|---|---|---|
| `location.plain / formal / terse` | `{pp}` place (e.g. `Mapo-gu`), `{km}` | `{pp}` and `{km}` |
| `time.plain` (L1-L2) | `{wd}` weekday, `{iso}` date, `{t}` time | `{wd}` `{iso}` `{t}` |
| `time.formal` (L3) | `{wd}`, `{month}`, `{day}`, `{t}` | all four |
| `time.terse` (L4) | `{wd}`, `{t}` | `{wd}` `{t}` and the word `coming` (L4 dates are relative to "today") |
| `language.*`, `language.soft.*` | `{lang}` | `{lang}` |
| `price.*`, `price.soft.*` | `{level}` | `{level}` |
| `gender.*`, `gender.soft.*` | none | a clear statement about the doctor |
| `greeting` / `intro` | `{name}` / `{nat}` | the field shown |
| `complaint` | `{symptom}` (the complaint sentence below) | `{symptom}` |
| `symptom.<complaint>` (L1-L3), `symptom.<complaint>.terse` (L4), one pair per key of `COMPLAINTS` | `{dur}` ("3 days") | `{dur}` for symptoms and a child's illness; **no** `{dur}` for services (`checkup`, `blood_pressure`, `skin_wart`) |
| `lead.terse` | `{name}`, `{nat}`, `{symptom}` | all three |
| `closing.plain`, `closing.terse`, `referral` | none | nothing required |
| `avoid` | `{name}` hospital name | `{name}` |
| `hello.memory`, `allergy` | `{name}` / `{names}` | the field shown |
| `enc.symptom.plain / casual` (consultation, patient) | `{body}`, `{dur}` | both |
| `enc.nose.*` | `{dur}` | `{dur}` |
| `enc.fever.yes.*` / `enc.fever.no.*` | `{temp}` / none | `{temp}` for yes |
| `enc.allergy.yes.*` / `enc.allergy.no.*` | `{allergen}` / none | `{allergen}` for yes |
| `enc.curmed.yes.*` / `enc.curmed.no.*` | `{drug}`, `{freq}` ("twice a day") / none | both for yes |
| `enc.q_meal`, `enc.q_coffee`, `enc.thanks` | none | nothing required; keep the meaning (asking to take the medicine before meals; asking about coffee; thanking the doctor) |

`.plain` is the style of tiers L1-L2, `.formal` of L3 and `.terse` of L4 (lower case, abbreviations, no politeness). In the
consultation pools (`enc.*`), `.plain` is L1-L2 and `.casual` is L3-L4. A consultation paraphrase must mean exactly what the Korean
reference translation says (the facts are checked in the agent's Korean output), so do not add or drop information. Keep each
paraphrase in the style of its pool and give it **the same difficulty**: it must still state every fact (district and kilometres, date and
time, price level, language) plainly. Do not hide a fact or make it ambiguous.

## Checks that run for you

`build` validates the file before generating anything and stops with a list of problems if a template misses a required field, uses an
unknown field, repeats another template, or belongs to an unknown pool. `tests/test_phrasing.py` checks the same rules on the public
pools and that held-out wording replaces public wording only for the test split.

## Good practice

* Write at least 3 paraphrases per key you replace; 5 or more is better.
* Have someone who has not seen `phrasing.py` write them, or write them in a different register, so they do not echo the public wording.
* After building, read a few dozen messages from `private/test/T1.jsonl`, `T3.jsonl` and `T7.jsonl` before running any agent on it.
