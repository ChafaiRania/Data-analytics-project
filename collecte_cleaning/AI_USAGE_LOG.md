# AI usage log (Person 2: enrichment and RQ2)

Tool: Claude Code (Claude Opus 5.5). Each entry gives the date, what was asked, what was produced, and the files touched.
Person 1's files (`src/collect.py`, `src/clean.py`, `src/refine.py`, everything in `data/processed/` they
produced) were not modified or re-run.

## 2026-11-08 — Inspect the manual Scopus / SCImago files (checkpoint 1)
- **Asked:** read README, `clean.py`, `cleaning_log.json`; inspect the Scopus Source List and SCImago
  2020–2025 (sheets, columns, ISSN formats, status/coverage) before writing any join.
- **Produced:** an inspection report (read-only scripts in a temporary folder) and an approved plan. Findings:
  - SCImago is `;`-separated, uses decimal commas, and stores ISSNs as `"15424863, 00079235"`. H index and
    Coverage are the same in every year's file (snapshot values).
  - The 2020 file has ~5k extra rows (no-ISSN proceedings).
  - The Scopus xlsx has 7 sheets. The main list has 8-character ISSN/EISSN, `Active or Inactive`, parseable
    `Coverage` years and a discontinued flag. There is a discontinuation-year sheet and two
    conference sheets.
- **Files touched:** none in the project. The manual files were then moved from `data/raw/` to
  `data/raw/manual/` and renamed (`ext_list_Sep_2026 (1).xlsx` → `ext_list_Sep_2026.xlsx`,
  `scimagojr 2025 (1).csv` → `scimagojr_2025.csv`, etc.; contents unchanged, verified by md5).

## 2026-11-08 — Requirements
- **Asked:** add new packages to requirements.txt.
- **Produced:** appended `openpyxl`, `matplotlib`, `jupyter`.
  - `pip install -r requirements.txt` fails on this machine. The Python is 32-bit and pandas>=2.0 has no 32-bit
    Windows wheel, so the code is written to run on the installed pandas 1.4.1.
  - scipy has no 32-bit Windows wheel either, so Spearman is computed as the Pearson correlation of average
    ranks (its definition), with a numpy permutation p-value. scipy is not required.
- **Files touched:** `requirements.txt` (appended lines only).

## 2026-11-08 — `src/enrich.py`, ISSN stage (checkpoint 2)
- **Asked:** match the corpus to Scopus on issn_l and every ISSN (print + e-ISSN), with coverage in the
  publication year, active vs discontinued status, then the title fallback, manual decisions and SCImago.
- **Produced:** `src/enrich.py` (new). Ran `python src/enrich.py --stage issn`, which prints rates and writes nothing.
  - **Deviation from the plan:** when a work's ISSNs point to two Scopus sources (63 works), the plan kept
    the issn_l one. Inspection showed that OpenAlex's issn_l is often the predecessor title's ISSN. Examples:
    Palgrave Communications for 2023–25 papers in Humanities and Social Sciences Communications; Zeitschrift
    fur Neurologie for Journal of Neurology. The rule is now: keep the source that covers the publication year,
    with issn_l breaking ties. Every case is logged.
- **Files touched:** `src/enrich.py` (new).

## 2026-11-08 — `src/enrich.py`, full run (checkpoint 3)
- **Asked:** continue past checkpoint 2: exact-title fallback, fuzzy candidates (not accepted), SCImago of the
  publication year, layers, outputs, and the top-50 unmatched venues for hand-checking.
- **Produced:** ran `python src/enrich.py` (~2 min).
  - The title fallback is exact after normalisation, for works without any ISSN. It searches the main list,
    the serial-conference list and the conference-proceedings volumes (a volume must exist for that year).
  - Result: +109 works (EDUCON 92). 15 exact hits on venues that DO have a different ISSN were not accepted
    and are listed as candidates (e.g. a different "European Journal of Education").
  - Fix during the run: OpenAlex `source_type == "repository"` sources (DOAJ, Dialnet) are now also kept off
    the hand-check list, alongside Person 1's `is_repository`. This changes no match.
  - Person 1's files: timestamps checked before and after, unchanged. Importing `clean.norm_issn` created
    `src/__pycache__/`.
- **Files touched (new):** `data/processed/works_layers.csv`, `authorships_layers.csv`, `match_report.json`,
  `unmatched_venues_top.csv`, `title_fuzzy_candidates.csv`. Edited: `src/enrich.py`.

## 2026-11-08 — Manual venue file, enrich.py extensions, final run
- **Asked:**
  - add an optional `years` column to the manual file;
  - draft the manual decisions for the top-50 unmatched venues from the local Scopus workbook
    (yes / no / unsure, with years and evidence; mark 5 to confirm online);
  - split `match_method` by sheet and add `_issn_miss`;
  - write a title-match sample and a no-source sample;
  - add an `in_strict_lag` flag;
  - re-run everything.
- **Produced:**
  - `data/raw/manual/manual_venue_matches.csv` (new): 25 yes, 23 no, 2 unsure. Every decision cites the exact
    Scopus title(s) and sheet. Rows are flagged `confirm_on_scopus` for ITiCSE, MIPRO, CSEDU, FIE and ICETA.
    Drafted by Claude from the workbook and **not checked on scopus.com**.
  - `src/enrich.py`:
    - `title_main` / `title_serialconf` / `title_allconf`;
    - `*_issn_miss` recorded but NOT accepted (homonym risk, e.g. a different "European Journal of Education");
    - manual `years`, with `unsure` treated as not matched;
    - `in_strict_lag`, the samples, an FIE entry in the report, and STRICT vs STRICT_lag by year;
    - SJR cleared for works not in Scopus (10 works carried a rejected candidate's SJR).
  - The hand-check list is now built from the automatic result, so adding manual decisions does not change it.
  - Final: STRICT has 5,927 works (58.1%); FIE's 44 works are matched through the manual file.
  - 11 spot checks against the raw xlsx and CSV rows all agreed.
- **Not done:** the request said "re-run under .venv (Python 3.11, pandas 2.x) and the numbers are identical".
  There is no `.venv` and no Python 3.11 on this machine; the only interpreter is the 32-bit Python 3.10 with
  pandas 1.4.1. This check has **not** been run.
- **Files touched:** `src/enrich.py` (edited); new `data/raw/manual/manual_venue_matches.csv`,
  `data/processed/title_match_sample.csv`, `no_source_sample.csv`. All `data/processed/*_layers.csv`,
  `match_report.json`, `unmatched_venues_top.csv` and `title_fuzzy_candidates.csv` were regenerated.

## 2026-11-08 — Data dictionary, RQ2 notebook, README, report draft
- **Asked:** the data dictionary; the executed RQ2 notebook with shows / doesn't show / could overturn notes; the
  README section with run order and download dates; a draft report section using only numbers from the
  report or notebook.
- **Produced:**
  - `notebooks/02_all_vs_strict.ipynb`, executed with nbconvert, no errors. It covers:
    - size by year and type;
    - top-20 institutions, countries and venues with rank changes, Jaccard, and Spearman with a permutation p;
    - country survival, institution losses and a breakdown of why works drop out;
    - fields, subfields and quartiles;
    - the sensitivity table (ISSN only / + title / + manual / active / Q1–Q2 / lag).
  - Charts use the validated reference palette and were checked visually; one label collision was fixed.
  - `docs/data_dictionary_layers.md`, `docs/report_person2.md`, and the README section "Enrichment (Person 2)"
    (appended; Person 1's sections are unchanged, verified with diff).
  - Person 1's files: timestamps checked again, unchanged.
- **Files touched:** `notebooks/02_all_vs_strict.ipynb`, `docs/data_dictionary_layers.md` and
  `docs/report_person2.md` (all new); `README.md` (appended); `AI_USAGE_LOG.md`.
