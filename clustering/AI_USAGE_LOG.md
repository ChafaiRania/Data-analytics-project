# AI usage log (clustering, RQ3)

**Tool:** Claude (claude.ai, agent mode with a Linux workspace), model Claude Opus 5.5, default settings.
Claude wrote all the code in `src/`, ran it, and drafted `README.md` and `docs/report_clustering.md`.
The team is responsible for checking and defending the results.

**Compute:** one full run takes about 1 minute on one CPU core (no GPU). Development needed about 10 runs.

## 2026-11-20: review of the whole project

- **Prompt (Tunisian Arabic, translated):** "Here is all our work. Check whether it is right or wrong,
  what the mistakes are, and whether the parts are connected to each other." The project briefing PDF
  and the five team archives were attached.
- **Produced:** a written review. The earlier clustering used a different dataset from the rest of the
  project, it clustered institutions with a median of 1 paper, and its `config.py` exposed an API key.
  The proposed fix was to cluster the collaboration network of the project corpus and compare the
  result with country.

## 2026-11-20: rebuild the clustering

- **Prompt (translated):** "OK, I want you to fix the whole clustering and give me the folder zipped."
- **Produced:**
  - `src/clustering.py` (new). It reads `works_layers.csv` and `authorships_layers.csv` and builds the
    fractional co-authorship network of EU institutions. It runs Louvain with 20 seeds and a stability
    check, and k-means on Hellinger topic shares with a silhouette null model and a Ward check. It compares
    both clusterings with country (NMI, ARI, permutation null, modularity of the country partition,
    within-country weight), runs a sensitivity grid, and writes the tables and figures.
  - `src/config.py` (rewritten): thresholds with reasons, no API key, no e-mail.
  - `README.md`, `docs/report_clustering.md`, `requirements.txt`.
- **Problems found and fixed during development:**
  - networkx's Louvain gave slightly different communities on each run. Python randomises the order of
    sets of strings, and Louvain iterates over sets. Fixed by giving the nodes integer names. Two runs
    with different hash seeds now give byte-identical outputs.
  - The first null model for the topic silhouette (shuffle each column) produced rows of zeros. It was
    replaced by shuffling the topic of each paper, which keeps every row valid and is closer to the
    question.
  - "Distinctive topics" first used a ratio, which ranked topics with 0.4% vs 0.1% first. It now uses the
    gain in percentage points.
  - Figure labels overlapped in the network map, so the institution names were moved into the legend.
- **Checked by:** reading the outputs and the figures; re-running with two hash seeds; comparing the counts
  with Person 3's tables (2,742 institution IDs here against 2,740 name × country pairs there, because two
  pairs of institutions share a name).
- **Files touched:** only files in this `clustering/` folder. Person 1's and Person 2's files were read and
  not modified.
