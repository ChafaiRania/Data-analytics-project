# Project D: Mapping EU Universities & Research Groups on AI in Education (2020–2025)

Data Analytics (MDE-CO-02), Fall 2026, Constructor University. Prof Mariia Snigireva.

Team: Khaoula Adouli, Rania Chafai, Yacine Fekih Ahmed, Nizar Ben Romdhane, Gantenapalli, Jessika Mahima Raj.

The final report is in [`report/Project_D_Final_Report.pdf`](report/Project_D_Final_Report.pdf).

## Research questions

- **RQ1.** Which EU universities and groups dominate AI-in-education research, and has this shifted over 2020–2025?
- **RQ2.** How much do the results change between all OpenAlex papers (ALL) and papers in Scopus-indexed venues (STRICT)?
- **RQ3.** Do institutions cluster by topic, by collaboration, or simply by country?
- **RQ4.** What does the keyword search miss, and how precise is it?

## Repository layout

The four folders sit side by side. Each has its own README, which explains how to re-run that part.

| Folder | Part | Run | Main outputs |
|---|---|---|---|
| `collecte_cleaning/` | 1–2. Collection, cleaning, Scopus/SCImago enrichment (RQ2) | `python src/collect.py`, `python src/clean.py`, `python src/enrich.py` | `data/processed/works_layers.csv`, `authorships_layers.csv` |
| `collecte_cleaning/notebooks/` | RQ2 and RQ4 checks | execute `02_all_vs_strict.ipynb`, `02_validate_query.ipynb` | `data/validation/relevance_labels.csv` |
| `descriptive/` | 3. Descriptive statistics (RQ1) | execute `notebooks/03_descriptive_statistics.ipynb` | tables t1–t12, figures f1–f6 |
| `clustering/` | 5. Collaboration and topic clustering (RQ3) | `python src/clustering.py` (about 1 min) | `outputs/summary.json`, tables, figures c1–c6 |
| `network_mapping/` | 4. Networks and VOSviewer maps | `python src/build_networks.py` (about 35 s), after the clustering | `outputs/network_stats.json`, tables, VOSviewer files, figures n1–n4 |
| `report/` | Final report | | PDF |

Steps 3–5 only read the two `*_layers.csv` files and never change them. The network step runs after the clustering because the VOSviewer institution map reuses the clustering communities.

## Quick start (from the processed data)

```bash
pip install -r clustering/requirements.txt -r network_mapping/requirements.txt
cd clustering && python src/clustering.py && cd ..
cd network_mapping && python src/build_networks.py && cd ..
```

## Data not stored in this repository

GitHub limits file size. These three files are therefore not stored here; they are needed only to re-run steps 1–2 from scratch:

| File | How to get it |
|---|---|
| `collecte_cleaning/data/raw/works.jsonl.gz` | `python src/collect.py` (OpenAlex API; a free key goes in `OPENALEX_API_KEY`) |
| `collecte_cleaning/data/processed/works.csv` | written by `collect.py` |
| `collecte_cleaning/data/raw/manual/ext_list_Sep_2026.xlsx` | Scopus Source List (September 2026), from Elsevier's Scopus content page |

Every file that the analysis (steps 3–5) reads is included.

## AI usage

Each part keeps an `AI_USAGE_LOG*.md`. Section 13 of the report sums up the logs: tool, model, what the AI did, and how we checked it.
