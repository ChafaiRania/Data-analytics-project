# Data dictionary: ALL / STRICT layers (Person 2)

This file covers the columns that `src/enrich.py` adds. The columns from `works_clean.csv` and
`authorships_clean.csv` are unchanged and are described in the main README.

- **ALL** = every row of `works_layers.csv` (10,208 works).
- **STRICT** = rows where `in_strict` is True.

Read the CSV with `dtype={"scopus_id": str}`, otherwise pandas turns Scopus IDs into floats.

## `data/processed/works_layers.csv` (one row per work, all clean works)

| Column | Definition |
|---|---|
| `scopus_id` | Scopus Sourcerecord ID of the matched source. Empty for `manual`, `title_allconf` (conference volumes have no ID) and `none`. |
| `match_method` | How the venue was matched. Possible values:<br>`issn_l`: the work's linking ISSN is a print or e-ISSN of a Scopus source.<br>`issn`: another ISSN of the work is.<br>`title_main`, `title_serialconf`, `title_allconf`: the venue name equals exactly one Scopus title, after normalisation, in the main list, the serial-conference list or the conference-proceedings list. Used only for works with no ISSN.<br>`title_*_issn_miss`: the same exact hit for a venue whose own ISSN is not in Scopus. Recorded but **not accepted**.<br>`manual`: a "yes" in `data/raw/manual/manual_venue_matches.csv`.<br>`none`: not matched. |
| `manual_decision` | `yes` / `no` / `unsure` from the manual file for this venue; empty if the venue is not in it. `unsure` counts as not matched. |
| `manual_evidence` | The Scopus title(s) and sheet cited for a manual "yes". |
| `scopus_title` | Title of the matched Scopus source. For `manual` it repeats the evidence. For `*_issn_miss` it shows the rejected candidate. |
| `scopus_status` | `active` or `inactive`: the list's Active/Inactive column. `discontinued`: Scopus discontinued the title. `not_reported`: serial-conference sheet, which has no status column. `conf_proceedings`: a conference volume. `manual_check`: a manual "yes". Empty when not in Scopus. |
| `scopus_discontinued_year` | Year from the "Discontinued Titles" sheet, for discontinued sources only. |
| `in_scopus` | True if the venue is in the Scopus list by any accepted method, whatever the year. |
| `scopus_covered_in_year` | True if Scopus covered the source in the work's publication year (the list's `Coverage` years, the year of a proceedings volume, or the manual file's `years`). |
| `sjr` | SJR of the source in the SCImago file for the publication year (decimal comma converted). Empty if the source is not in that year's file or the work is not in Scopus. |
| `sjr_quartile` | SJR best quartile (Q1–Q4) in that year's file: the venue's best quartile across all its categories. Empty if SCImago gives none (`-`). |
| `h_index` | SCImago H index of the source. **A snapshot value:** it is identical in every year's file, so it is not the historical H index. |
| `sjr_categories` | SCImago subject categories with their quartiles, as in the file. |
| `sjr_year_used` | Year of the SCImago file used. Normally the publication year. |
| `sjr_year_flag` | `fallback` if that year's file was missing and the nearest earlier year was used. Empty in this run, because all files for 2020–2025 are present. |
| `in_strict` | **Main STRICT rule:** `in_scopus` and `scopus_covered_in_year`. |
| `in_strict_active` | `in_strict`, excluding sources marked `inactive` or `discontinued` (sensitivity). |
| `in_strict_q12` | `in_strict` and `sjr_quartile` is Q1 or Q2 (sensitivity; removes almost every conference paper). |
| `in_strict_issn_only` | `in_strict` counting only `issn_l` and `issn` matches (sensitivity). |
| `in_strict_lag` | `in_strict`, plus works in an active Scopus source that was covered in the year *before* publication. This tolerates indexing lag, mainly for 2025. |

## `data/processed/authorships_layers.csv`

Same rows as `authorships_clean.csv`, plus `in_strict`, `in_strict_active`, `in_strict_q12`,
`in_strict_issn_only` and `in_strict_lag`, copied from the work.

## Other outputs

| File | Content |
|---|---|
| `match_report.json` | Match rates overall, by year, by type and by method. Also: works added at each step, STRICT vs STRICT_lag by year, ISSN conflicts, rejected title hits, the FIE check and the manual-file log. |
| `unmatched_venues_top.csv` | The 50 largest venues left unmatched by the *automatic* steps. Repositories and works with no source are excluded. This is the list used for the hand check. |
| `title_fuzzy_candidates.csv` | Up to 3 fuzzy Scopus title candidates per unmatched venue, plus exact hits that were not accepted. **Never accepted automatically.** |
| `title_match_sample.csv` | 20 random accepted title matches (seed 42), for checking by hand. |
| `no_source_sample.csv` | 15 random works without any OpenAlex source (seed 42). |

## `data/raw/manual/manual_venue_matches.csv` (hand decisions)

| Column | Definition |
|---|---|
| `source_id` | OpenAlex source ID, copied from `unmatched_venues_top.csv`. |
| `in_scopus` | `yes` / `no` / `unsure`. Anything other than yes or no is read as `unsure`, which counts as not matched. |
| `years` | Optional. The years with Scopus coverage, e.g. `2021;2023-2025`. Empty = all years. |
| `checked_on` | Date of the check. |
| `note` | Reasoning. |
| `evidence` | Exact Scopus title(s) and sheet. |
| `source_name`, `n_works`, `confirm_on_scopus` | For the reader only; the script does not use them. |

## Caveats in one line each

- `in_scopus` ≠ `in_strict`: 162 works are in a Scopus source that was not covered in their publication year.
- A manual "yes" counts the venue as covered in its listed `years`, or in every year if `years` is empty.
- The manual decisions were drafted from the local Scopus workbook (8 Nov 2026). Five are flagged for confirmation on scopus.com.
- SCImago `H index` and `Coverage` are snapshot values. Only `sjr` and `sjr_quartile` are year-specific.
- 217 works have no OpenAlex source and are always outside STRICT, even though some are IEEE conference papers.
