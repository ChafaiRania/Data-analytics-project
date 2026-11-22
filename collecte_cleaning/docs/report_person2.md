# Create Two Layers: ALL and STRICT (Person 2)

*Draft report section. Every number comes from `data/processed/match_report.json` or the executed notebook
`notebooks/02_all_vs_strict.ipynb`.*

## Generic use case

A bibliometric study built on an open database (OpenAlex) has a validity question. Results may depend on
which publications count as "research". Open databases include preprints, repositories, book platforms and
small journals that curated indexes leave out. A common answer is to build two layers of the same corpus:

- **ALL**: everything that passed cleaning;
- **STRICT**: only works published in venues that a curated index (Scopus) covered in the year of publication.

The analysis is then run on both layers. Conclusions that hold in both are robust. Conclusions that hold in
only one layer depend on the inclusion rule and must be reported with that caveat. The same recipe works for
any OpenAlex corpus and any source list that has ISSNs and coverage years.

## Input and output files

| Input | Content |
|---|---|
| `data/processed/works_clean.csv` | 10,208 clean works (Person 1), with `issn_l`, `issn`, `source_name`, `year`, `type` |
| `data/processed/authorships_clean.csv` | 50,726 author–institution rows (Person 1) |
| `data/raw/manual/ext_list_Sep_2026.xlsx` | Scopus Source List, Sep 2026 (downloaded 7 Nov 2026) |
| `data/raw/manual/scimagojr_2020.csv` … `_2025.csv` | SCImago, all subject areas (2025 downloaded 7 Nov 2026; 2020–2024 on 8 Nov 2026) |
| `data/raw/manual/manual_venue_matches.csv` | Decisions for the 50 largest unmatched venues |

| Output | Content |
|---|---|
| `data/processed/works_layers.csv` | All works + `in_scopus`, `match_method`, `scopus_status`, SJR fields, `in_strict` and 4 sensitivity flags |
| `data/processed/authorships_layers.csv` | Authorships + layer flags |
| `data/processed/match_report.json` | Match rates, steps, conflicts, lag table |
| `data/processed/unmatched_venues_top.csv`, `title_fuzzy_candidates.csv` | Hand-check lists |
| `data/processed/title_match_sample.csv`, `no_source_sample.csv` | Random samples for checking by hand |
| `docs/data_dictionary_layers.md` | Definition of every new column |

## Steps

1. **Inspect the manual files before joining.** The Scopus workbook has 7 sheets. The main list has 49,104
   titles with 8-digit print and e-ISSNs, an Active/Inactive status, a discontinued flag and coverage years
   (e.g. `2026; 2023-2024`). SCImago is semicolon-separated, uses decimal commas, and stores several ISSNs
   per cell without hyphens. In SCImago, `H index` and `Coverage` are identical in every year's file, so
   they are snapshot values.
2. **Normalise ISSNs** to `1234-567X` with Person 1's `norm_issn` function, so both sides use one format.
3. **Build the Scopus lookup.** Every print and e-ISSN of the main list and of the serial-conference list maps to a
   Scopus source ID. Each source keeps its status, its discontinuation year and the set of years it was
   covered.
4. **Match on ISSN.** First the work's `issn_l` (5,263 works), then any other ISSN of the work (112 works).
   In 63 works the ISSNs point to two Scopus sources, almost always a journal that changed its name.
   OpenAlex's `issn_l` is often the old title's ISSN. The source that covers the publication year is kept,
   which picked the newer title in 50 of these 63 works.
5. **Check coverage in the publication year.** A work is in STRICT only if its source was covered in that
   year. 162 works are in a Scopus source that was not covered in their year: discontinued journals, or 2025
   volumes not yet indexed.
6. **Exact title fallback** for works without any ISSN. The venue name is normalised (accents removed, lower
   case, punctuation removed) and compared with the main list (`title_main`, 9 works), the serial-conference list
   (`title_serialconf`, 100 works, mostly EDUCON) and the list of conference proceedings volumes
   (`title_allconf`, 0 works). Exact hits for venues that do have an ISSN, just not one found in Scopus, are
   labelled `*_issn_miss` and not accepted (15 venues, 19 works). Inspection showed these are mostly
   different journals with the same name.
7. **Fuzzy candidates and the top-50 list.** Fuzzy title similarity is never accepted automatically. The
   candidates and the 50 largest unmatched venues are written out for checking by hand. Repositories (902
   works) and works without a source (217) are excluded from the list.
8. **Manual decisions.** Each of the 50 venues was searched in every sheet of the workbook, allowing for
   edition numbers, years and renamed conferences. The result was 25 yes (605 works), 23 no and
   2 unsure. A "yes" records only the years with a Scopus volume. "Unsure" counts as not matched.
   Book platforms (Springer, IGI, Cambridge, Emerald eBooks) are "no", because they are platforms, not
   venues. FIE (44 works) is matched only here: OpenAlex gives an ISSN that is not the one Scopus uses.
9. **Attach SCImago** from the file for the publication year, joined on the Scopus source ID (5,303 works) or
   on ISSN (5 works). SJR, the best quartile, the H-index and the categories are added for 5,308 works. No
   file was missing, so the earlier-year fallback was never used.
10. **Build the layers and check them.**
    - The main rule is `in_strict = in_scopus & covered in year`.
    - Sensitivity flags: ISSN only, active sources only, Q1–Q2 only, and a lag-tolerant variant.
    - Assertions check that row counts are unchanged, that every STRICT variant is a subset of `in_scopus`,
      and that the per-method counts add up.
    - 11 works were spot-checked by hand against the raw xlsx and CSV rows, one per method and edge case.

## Final summary

| Layer | Works | Share of ALL |
|---|---|---|
| ALL | 10,208 | 100% |
| In Scopus (any year) | 6,089 | 59.7% |
| **STRICT (main rule)** | **5,927** | **58.1%** |
| STRICT, ISSN matches only | 5,262 | 51.5% |
| STRICT, active sources only | 5,824 | 57.1% |
| STRICT, lag-tolerant | 5,987 | 58.7% |
| STRICT, Q1–Q2 only | 3,886 | 38.1% |

## How much does STRICT change the picture?

### Key numbers

- **Size.** STRICT keeps 58.1% of works. Survival by type:
  - reviews 85.6%, articles 68.4%, conference papers 51.9%, book chapters 22.7%, preprints 0%.

  By year, survival falls from 63.5% (2020) to 53.4% (2025).
- **Countries (EU-27, full counting).** The top 20 is the same set in both layers (Jaccard 1.0), with
  Spearman 0.909. DE, ES and IT stay first to third.
  - France falls from 4 to 8 and Greece from 5 to 7.
  - Finland rises from 6 to 4, the Netherlands from 7 to 5 and Sweden from 10 to 6.
  - Survival ranges from 76.7% (Estonia) to 28.9% (Malta), against 59.9% EU-wide.
- **Institutions.** 13 of the top 20 are shared (Jaccard 0.481), with Spearman 0.640. The top 4 do not move.
  The largest drops are Ioannina (20 → 195), NKUA Athens (19 → 72) and Aarhus (12 → 35).
- **Venues.** Jaccard 0.481 and Spearman 0.362. arXiv, HAL, SSRN, Zenodo and two book platforms leave
  the top 20.
- **Fields.** Medicine rises from 10.1% to 13.9% of works and Computer Science falls from 63.4% to 60.0%.
  In STRICT, 42.4% of works are in Q1 venues and 20.2% in venues with no quartile.
- **Sensitivity.** The country ranking is robust: Spearman between 0.904 and 0.932 in every variant, and
  the same top-20 set except under Q1–Q2. The institution ranking depends on the matching. Spearman with
  ALL is 0.348 with ISSN matches only and 0.640 once the title and manual matches are added. The reason is
  that the share of conference papers kept rises from 29.9% to 51.9%.

### Interpretation

Moving from ALL to STRICT leaves the **country** picture largely intact: the same leaders and the same
set of countries, with moderate reordering in the middle. The **institution** picture changes noticeably,
in two ways.

- **Losses through publishing outside Scopus.** Some groups publish much of their output in journals that
  Scopus does not index, and they lose most of it. Of the 51 works Ioannina loses, 43 are in venues whose
  ISSN is not in Scopus.
- **Losses through repositories and conference venues.** Groups active in conference-based computer
  science lose works through repositories and conference venues. CNRS loses 16 works to repositories
  and 15 to unchecked venues with no ISSN.

Country-level survival is not explained by the share of conference papers (r = 0.09 across 25 countries).
The differences between countries therefore come mostly from which *journals* their researchers use.

### Limitations

- **Conferences without an ISSN.** 920 works lost from STRICT sit in venues with no ISSN that were not
  hand-checked. This long tail (at most 9 works per venue) includes ACM conferences that are probably in
  Scopus, such as CHI Extended Abstracts, Learning @ Scale, UMAP and ACM SAC. These are likely false negatives
  that hit computer-science groups hardest. Extending the hand check beyond 50 venues would reduce them.
- **Indexing lag in 2025.** The source list is from September 2026, and several 2025 conference volumes are
  not yet indexed (E&PDE, SIIE, BEA). The lag-tolerant variant adds only 49 works in 2025, because it cannot
  catch venues that are new to Scopus. The fall in 2025 survival should not be read as a trend.
- **H-index is a snapshot.** SCImago's H index is the same in every year's file, so it describes the venue
  today, not in the publication year. Only SJR and the quartile are year-specific.
- **How the manual check was done.** The 50 decisions (605 works counted as "yes") were drafted from the local
  Scopus workbook, not checked on scopus.com. Five of them are flagged for confirmation online: ITiCSE,
  MIPRO, CSEDU, FIE and ICETA. A "yes" covers only the years with a Scopus volume.
- **Works with no source.** 217 works have no OpenAlex source (86 conference papers, 84 preprints) and can
  never enter STRICT. The random sample in `no_source_sample.csv` shows that some are IEEE conference papers,
  so STRICT slightly undercounts.
- **Counting and statistics.** Rankings use full counting over EU-27 entities. Spearman is computed on the
  union of the two top-20 lists, with absent entities given the bottom rank. The permutation p-values are
  descriptive. Field labels are OpenAlex topics, not the venue's Scopus subject codes.
