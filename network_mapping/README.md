# Project D: network mapping

Who collaborates with whom in European AI-in-education research, and which themes go together.

This step works on the **same corpus as the rest of the project**: the 10,208 clean works of Person 1, with
the ALL / STRICT layer flags of Person 2. It reads their files and never changes them. It needs no API key
and no internet access.

## Re-run from scratch

Put this folder next to `collecte_cleaning/` (and `clustering/`, optional):

```
project/
  collecte_cleaning/data/processed/works_layers.csv
  collecte_cleaning/data/processed/authorships_layers.csv
  clustering/outputs/tables/institution_assignments_{all,strict}.csv   <- optional
  network_mapping/          <- this folder
```

```bash
cd network_mapping
pip install -r requirements.txt
python src/build_networks.py                     # about 35 seconds
# or, if the data is somewhere else:
python src/build_networks.py --data ../collecte_cleaning/data/processed
```

If the clustering outputs exist, the institution map for VOSviewer takes its Louvain communities as
clusters, so the map and the clustering show the same groups. Run the clustering first to get them. Without
it, VOSviewer computes its own clusters.

The run is deterministic: two runs with different Python hash seeds give byte-identical tables, VOSviewer
files and `network_stats.json`. This was checked.

## The four networks (each on ALL and STRICT)

| Network | Nodes | Link | Map keeps |
|---|---|---|---|
| Institutions | OpenAlex institution IDs | shared paper | EU institutions with >= 5 papers |
| Authors | OpenAlex author IDs (never names) | shared paper | authors with an EU affiliation and >= 3 papers |
| Countries | country codes | shared paper | all countries |
| Keywords | OpenAlex keywords | on the same paper | keywords on >= 30 papers (ALL) / 20 (STRICT), query terms left out |

**Counting rules.**
- Each entity counts once per paper: two authors from one university make the university appear once on that
  paper.
- Links carry two weights. `papers` is the number of shared papers. `weight` is fractional (Newman 2001): a paper
  with n entities adds 1/(n-1) to each pair, so one 80-institution paper does not outweigh years of regular
  collaboration. The VOSviewer network files use `weight`.
- Keyword links use association strength (van Eck & Waltman 2009), the normalisation VOSviewer uses. With raw
  counts, frequent keywords would simply sit together.
- An institution's citations are the sum of `cited_by_count` over its *distinct* papers. The script asserts
  that the total ties to the papers.

## Files

| File | What it is |
|---|---|
| `src/build_networks.py` | The whole pipeline |
| `src/config.py` | Thresholds and paths, with the reason for each |
| `outputs/network_stats.json` | Size, density, connectivity of every network, both layers, and ALL vs STRICT |
| `outputs/tables/nodes_*_{all,strict}.csv` | Every node: papers (full and fractional), citations, mean year, partners, betweenness |
| `outputs/tables/edges_*_{all,strict}.csv` | Every link with `papers` and `weight` |
| `outputs/tables/top_hubs_{all,strict}.csv` | EU institutions with most partners |
| `outputs/tables/top_eu_country_pairs_{all,strict}.csv` | Strongest EU country pairs |
| `outputs/tables/keyword_themes_{all,strict}.csv` | Keyword themes (Louvain) and their top keywords |
| `outputs/vosviewer/{all,strict}/*_map.txt`, `*_network.txt` | Ready for VOSviewer |
| `outputs/figures/n1` … `n4` | Hubs vs productivity, EU country pairs, keyword map by theme, keyword map by year (VOSviewer's overlay view) |
| `docs/report_network.md` | Draft report section |
| `AI_USAGE_LOG.md` | How AI was used for this step |

## Making the maps in VOSviewer

1. *Create* → *Create a map based on network data* → *Read data from VOSviewer files*.
2. Map file: `outputs/vosviewer/all/institutions_map.txt`; network file: `institutions_network.txt`.
3. Keep the clusters from the map file (they are the clustering step's communities). Size the nodes by
   *Papers*.
4. *Overlay visualization* with the score *Avg. pub. year* shows which parts of the map are recent.
5. Do the same for `keywords_*`, `countries_*` and `authors_*`, and for the `strict/` folder.

## What changed from the first version

- **It now reads Person 2's layers** (`works_layers.csv`), not Person 1's `works_clean.csv`, so every network
  exists for ALL and for STRICT.
- **Citation bug fixed.** The first version merged citations on author × institution rows, so an institution
  with 30 authors on one paper got that paper's citations 30 times. Swansea showed 128,915 citations instead of
  4,675. Rows are now one per paper × institution, and the total is asserted.
- **Foreign files removed.** `edges_coauthorship_clean.csv` and `nodes_authors_clean.csv` were keyed by name,
  and 53% of the names were not in our corpus. No script produced them. `edges_coauthorship_authors.csv` was a
  three-line placeholder. All are replaced by ID-based files built here.
- **Concept network rebuilt.** The first version mixed topic, subfield, field and keywords in one network, so
  "computer science" linked to everything. The new one uses keywords only, leaves out the query terms, and uses
  association strength.
- **Fractional link weights** and **statistics** (density, connectivity, betweenness) were added, with figures.
