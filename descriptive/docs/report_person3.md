# Descriptive Statistics (Person 3)

*Draft report section. Every number comes from the executed notebook
`notebooks/03_descriptive_statistics.ipynb`; tables are in `outputs/person3/tables/`, figures in
`outputs/person3/figures/`.*

## Question

**RQ1:** Which EU institutions and venues dominate research on AI in education, and has that shifted
since 2020?

## Data and counting rules

The section uses the clean corpus of Person 1 with the layer flags of Person 2: 10,208 papers (ALL), of
which 5,927 (58%) are in STRICT. Author slots are reduced to one row per paper × institution (25,157 rows)
and one row per paper × country (16,822 rows), so an institution with two authors on a paper is counted
once.

- **Full counting:** each institution or country on a paper receives 1. It measures participation.
- **Fractional counting:** a paper is split equally among its institutions. It measures share of output.
- **EU institution:** institution country in the EU-27, as coded by OpenAlex.

## Results

**Composition.** 57% of papers are journal articles and 29% conference papers. OpenAlex places 63% of
papers in Computer Science, 10% each in Social Sciences and Medicine (mostly medical education) and 5% in
Psychology (Table t2).

**Growth (Figure f1).** Output rose from 471 papers in 2020 to 4,492 in 2025. Growth was modest until 2022
(+19%, +13%) and then output doubled in both 2023 and 2024. The break coincides with the release of
ChatGPT in November 2022; the data show the timing, not the cause. The STRICT share is stable at 60–66%
until 2024 and falls to 53% in 2025, partly because 2025 volumes are not yet indexed.

**Countries (Figure f2).** Germany takes part in 17% of papers, Spain in 15% and Italy in 11%, followed by
France, Greece and Finland (about 6% each). These counts are not adjusted for country size. 30% of papers
have at least one non-EU co-author, most often from the United States (796 papers) and the United Kingdom
(552).

**Institutions (Figure f3).** 2,740 EU institutions appear in the corpus. The University of Eastern
Finland leads clearly under both rules (169 papers full, 93 fractional). Below it the ranking depends on
the counting rule: only 9 of the top 15 are shared. Institutions that mainly join large collaborations fall
under fractional counting (CNRS 89 → 18, LMU Munich 109 → 40), while Ioannina, Zagreb and the Bucharest
University of Economic Studies rise. The layer matters less: 11 of the top 15 are the same in ALL and
STRICT. Output is not concentrated. The top 10 institutions hold 5.6% of EU institution–paper links, and
44% of institutions appear on a single paper.

**Shift since 2020 (Table t8).** Only the University of Eastern Finland is in the top 10 both in 2020–2022
and in 2023–2025. The early list was led by Spanish universities (5 of 10); the later one adds German,
Finnish, Irish, Croatian, Romanian and Greek universities. Even the leader's share of papers fell from 3.1%
to 1.4%: the field spread out as it grew. The early period has only 1,670 papers, so its ranking rests on
small counts.

**Venues (Figure f4).** No venue holds more than about 2% of papers. The largest are computer-science book
series (Lecture Notes in Computer Science, 210; Lecture Notes in Networks and Systems, 141), open-access
journals (Education Sciences, Applied Sciences), the IEEE EDUCON conference and the specialised journal
Computers and Education: Artificial Intelligence. Repositories (arXiv, HAL, SSRN, Zenodo; 9% of papers)
are excluded from the ranking because they are not publication venues.

**Citations (Figure f5).** The distribution is highly skewed: mean 19.4, median 3, and 27% of papers are
uncited. The top 1% of papers receive 31% of all citations. The median falls from 12 (2020) to 1 (2025)
because recent papers have had less time to be cited. In 2023 the mean (45) rises while the median falls,
because a few highly cited papers pull the mean up. We therefore report medians and do not compare raw
citations across years.

**Collaboration (Figure f6).** 54% of papers involve two or more institutions, 36% two or more countries,
and the median paper has 3 authors. Collaboration shares fell slightly as the field grew (two or more
institutions: 60% in 2022, 52% in 2025).

## Answer to RQ1

No small group dominates. The University of Eastern Finland is the only stable leader, ahead under both
counting rules, both layers and both periods. The rest of the leadership changed after 2022, when the field
grew fastest, and depends on how co-authored papers are credited. Publication is spread across
computer-science series, conferences and open-access journals rather than a few core journals.

## Limitations, and what would change the conclusion

- **Corpus definition.** All results depend on the keyword search and the relevance rule. A hand-checked
  sample would show how many papers are truly about AI in education; if many are not, the institution
  ranking would change most.
- **Counting rule.** Rankings differ between full and fractional counting; both are reported.
- **Missing affiliations.** 5.2% of author slots have no institution. Those institutions are missing from
  the rankings, and collaboration is slightly underestimated.
- **Country size.** Counts are not normalised by population or research staff, which favours large
  countries.
- **Definition of "EU".** Countries are taken from OpenAlex codes. Near East University (rank 9) is coded
  Cyprus but lies in the northern part of the island, where EU law is suspended.
- **Organisation level.** CNRS and similar national bodies count as one institution, though they contain
  many labs.
- **Recent years.** 2025 is still being indexed, and recent papers have had little time to collect
  citations.
