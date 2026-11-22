# Project D: clustering (RQ3)

**RQ3:** What clusters exist in European AI-in-education research: by topic, by collaboration, or
simply by country?

This step works on the **same corpus as the rest of the project**: the 10,208 clean works of
Person 1, with the ALL / STRICT layer flags of Person 2. It reads their files and never changes them.
It needs no API key and no internet access.

## Re-run from scratch

Put this folder next to `collecte_cleaning/`:

```
project/
  collecte_cleaning/data/processed/works_layers.csv
  collecte_cleaning/data/processed/authorships_layers.csv
  clustering/            <- this folder
```

```bash
cd clustering
pip install -r requirements.txt
python src/clustering.py                       # about 1 minute
# or, if the data is somewhere else:
python src/clustering.py --data ../collecte_cleaning/data/processed
```

The run is deterministic: two runs give byte-identical tables and `summary.json`, whatever the
Python hash seed. This was checked.

## What it does

Two clusterings of EU institutions, each run on ALL and on STRICT:

| | A. Collaboration communities | B. Topic-profile clusters |
|---|---|---|
| Institutions | EU, >= 5 papers in the layer | EU, >= 10 papers in the layer |
| Data | who co-authors with whom | share of the institution's papers in each OpenAlex topic |
| Method | Louvain community detection on the weighted co-authorship network | k-means on Hellinger-transformed topic shares, k = 2..10 |
| Why this method | Communities in a network are what RQ3 means by "collaboration clusters"; Louvain maximises modularity and needs no k | Topic shares are compositions; the square root (Hellinger) stops the dominant topic from swamping the rest |
| Choice of k / checks | 20 seeds, best modularity kept, stability = agreement between seeds (ARI); sensitivity over min. papers (3/5/10) and resolution (0.5/1/2) | silhouette compared with a null model (paper topics shuffled); agreement with Ward clustering; stability over 20 seeds |
| Edge / feature weights | fractional: a paper with n institutions adds 1/(n-1) to each pair (Newman 2001), so an 80-institution consortium paper does not dominate | one topic per paper (OpenAlex primary topic); topics with < 30 papers merged into "Other topics" |

Both are then compared with **country**:
- NMI and ARI between cluster and country, against 200 permutations of the country labels;
- the modularity of the partition "one community per country", on the same scale as Louvain;
- the share of collaboration weight that stays inside one country, against the same null.

## Files

| File | What it is |
|---|---|
| `src/clustering.py` | The whole pipeline |
| `src/config.py` | Every threshold and setting, with the reason for its value |
| `src/viz_style.py` | Shared figure style (unchanged from the earlier version) |
| `outputs/summary.json` | All headline numbers for both layers |
| `outputs/tables/communities_{all,strict}.csv` | One row per collaboration community: size, countries, top institutions, over-represented topics |
| `outputs/tables/topic_clusters_{all,strict}.csv` | One row per topic cluster: size, distinctive topics, countries |
| `outputs/tables/topic_k_selection_{all,strict}.csv` | Silhouette, null silhouette, Ward agreement and stability for every k |
| `outputs/tables/network_sensitivity_{all,strict}.csv` | Results under other thresholds and resolutions |
| `outputs/tables/institution_assignments_{all,strict}.csv` | Every institution with its community and topic cluster |
| `outputs/figures/c1` … `c6` | Network map, community × country, choice of k, topic profiles, 2-D view, NMI with country |
| `docs/report_clustering.md` | Draft report section: results, interpretation, limitations |
| `AI_USAGE_LOG.md` | How AI was used for this step |

## What changed from the earlier clustering version

The earlier `clustering/` folder could not be kept:

- It used **a different dataset**: its own OpenAlex download (different keyword list, about 1,775 works),
  not the project corpus. The code that produced its `institutions_strict.csv` was not included, and its
  "strict" did not mean Person 2's STRICT layer.
- The 168 institutions it clustered had a **median of 1 paper**. A 1-paper institution has no "profile".
- k was chosen by silhouette on a 2-D PCA projection, with raw citation counts and raw yearly counts as
  features, so clusters mostly reflected size and outliers.
- `config.py` contained an **OpenAlex API key and a personal e-mail in plain text**. They are removed here.
  The key should be revoked at https://openalex.org/settings/api, because it was shared.
