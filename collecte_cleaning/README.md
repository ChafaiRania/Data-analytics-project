# Project D: data collection and cleaning

OpenAlex works on AI in education, 2020–2025, with at least one author at an institution in an
EU-27 country.

## Re-run from scratch

```bash
pip install -r requirements.txt
python src/collect.py   # download → data/raw/, flatten → data/processed/works.csv, authorships.csv
python src/clean.py     # clean → data/processed/*_clean.csv
```

`collect.py` caches every page in `data/raw/pages/`, so a re-run only downloads what is missing.
Without an API key OpenAlex allows about 100 requests per day; the download needs about 101. A free
key (https://openalex.org/settings/api) goes in `OPENALEX_API_KEY` or in a local `.env` file
(git-ignored, never shared).

## Files

| File | What it is |
|---|---|
| `src/collect.py` | Download from the OpenAlex API and flatten to tables |
| `src/clean.py` | Cleaning steps (below) |
| `src/refine.py` | Stricter relevance rule used by `clean.py` |
| `data/raw/works.jsonl.gz` | Raw API records, never edited by hand |
| `data/raw/query_meta.json` | Exact filter, download date, counts per year |
| `data/processed/works.csv`, `authorships.csv` | Flattened raw data |
| `data/processed/works_clean.csv` | **Clean corpus**, one row per paper |
| `data/processed/authorships_clean.csv` | **Clean authorships** (work × author × institution) |
| `data/processed/duplicates_removed.csv` | Every merged duplicate and why |
| `data/processed/cleaning_log.json` | Row counts after each step |

## Collection filter

- Publication years 2020–2025 (2026 excluded: incomplete year)
- At least one author affiliated with an institution in an EU-27 country
- Title or abstract matches `(AI terms) AND (education terms)`; exact query in `src/collect.py`
  and `query_meta.json`. The bare word `learning` is excluded: it matched every "machine learning"
  paper (~219k works instead of ~27k).

## Cleaning steps

| Step | Works |
|---|---|
| Downloaded | 20,057 |
| Versions of the same paper merged | 19,716 |
| Research document types only (article, conference paper, review, chapter, preprint) | 17,933 |
| Passes the stricter relevance rule | **10,208** |

1. **Duplicate authorship rows.** 280 exact duplicate author–institution rows dropped.
2. **Normalised keys.** DOI lower-cased without the `doi.org` prefix; ISSN as `1234-567X`, so the
   SCImago and Scopus lists can be joined.
3. **Versions of the same paper.** Records are merged when they share a DOI, or have the same title
   (at least 30 characters, so "Editorial" never matches) and at least one shared author. The
   published version is kept and takes the preprint's abstract if it has none. 341 records merged.
4. **Document types.** Editorials, errata, abstracts, paratext, datasets and similar are dropped.
5. **Relevance rule.** An AI term and an education term must both be central: in the title, or at
   least twice in the abstract, after removing false-positive phrases such as "curriculum learning".

Missing data in the clean corpus: 10.6% of works have no abstract, 24.2% no ISSN, 4.1% no DOI, and
5.2% of author slots have no institution.

## Enrichment (Person 2)

This step adds Scopus and SCImago data to the clean corpus and builds two layers:
- **ALL**: every clean work.
- **STRICT**: works whose venue is in Scopus and was covered by Scopus in the publication year.

It also answers RQ2: how much does the picture change between ALL and STRICT? Person 1's files are read
but never modified.

### Manual inputs (`data/raw/manual/`, downloaded by hand)

| File | Source | Downloaded |
|---|---|---|
| `ext_list_Sep_2026.xlsx` | Scopus Source List, September 2026 | 7 Nov 2026 |
| `scimagojr_2025.csv` | SCImago Journal Rank 2025, all subject areas | 7 Nov 2026 |
| `scimagojr_2020.csv` … `scimagojr_2024.csv` | SCImago Journal Rank 2020–2024, all subject areas | 8 Nov 2026 |
| `manual_venue_matches.csv` | Hand decisions for the 50 largest unmatched venues | drafted 8 Nov 2026 |

### Run order

```bash
pip install -r requirements.txt     # see the note below about 32-bit Python
python src/enrich.py                # ~2 min → data/processed/*_layers.csv, match_report.json, review files
# optional: edit data/raw/manual/manual_venue_matches.csv, then run enrich.py again
jupyter nbconvert --to notebook --execute --inplace notebooks/02_all_vs_strict.ipynb
```

`python src/enrich.py --stage issn` prints the ISSN match rates only and writes nothing.

### Files

| File | What it is |
|---|---|
| `src/enrich.py` | Scopus / SCImago matching and the layer flags |
| `data/processed/works_layers.csv` | All clean works + `in_scopus`, `match_method`, SJR, `in_strict` and sensitivity flags |
| `data/processed/authorships_layers.csv` | Clean authorships + the layer flags of their work |
| `data/processed/match_report.json` | Match rates, steps, conflicts, STRICT vs STRICT_lag |
| `data/processed/unmatched_venues_top.csv`, `title_fuzzy_candidates.csv` | Hand-check lists |
| `data/processed/title_match_sample.csv`, `no_source_sample.csv` | Random samples for checking by hand (seed 42) |
| `docs/data_dictionary_layers.md` | One-line definition of every new column |
| `notebooks/02_all_vs_strict.ipynb` | RQ2 analysis (executed) |
| `docs/report_person2.md` | Draft report section |

### Environment note

`enrich.py` and the notebook were run with Python 3.10 (32-bit) and pandas 1.4.1. On that interpreter
`pip install -r requirements.txt` fails, because pandas>=2.0 has no 32-bit Windows wheel. scipy is not
needed: Spearman is computed from ranks with numpy. The code has **not yet been run under pandas 2.x**.
