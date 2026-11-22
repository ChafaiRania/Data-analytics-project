# AI usage log (network mapping)

**Tool:** Claude (claude.ai, agent mode with a Linux workspace), model Claude Opus 5.5, default settings.
Claude rewrote `src/build_networks.py`, ran it, and drafted `README.md` and `docs/report_network.md`.
The team is responsible for checking and defending the results.

**Compute:** one full run takes about 35 seconds on one CPU core (no GPU). Development needed about 8 runs.

## 2026-11-20: review of the first version

- **Prompt (Tunisian Arabic, translated):** "Here is all our work. Check whether it is right or wrong,
  what the mistakes are, and whether the parts are connected to each other."
- **Found in the first version:**
  - It read Person 1's `works_clean.csv` instead of Person 2's layers, so it had no STRICT layer.
  - It summed citations on author × institution rows. Swansea had 128,915 citations instead of 4,675.
  - Two files were keyed by author name and came from another dataset: 53% of the names were not in the
    corpus. One edge file was a three-line placeholder.
  - The concept network mixed topic, subfield, field and keywords.

## 2026-11-21: rebuild

- **Prompt (translated):** "Fix P4's work. I want it connected to the others, and send me the folder zipped."
- **Produced:** `src/build_networks.py` (rewritten), `src/config.py`, `README.md`, `docs/report_network.md`.
  - The pipeline reads `works_layers.csv` and `authorships_layers.csv` (Person 2).
  - It builds institution, author, country and keyword networks on ALL and STRICT, with fractional link
    weights.
  - It asserts that institution citations tie to the papers, and writes the node and edge tables, the
    VOSviewer files, statistics and figures.
  - The VOSviewer institution map optionally takes the clustering step's communities.
- **Problems found and fixed during development:**
  - Hub figure labels collided, so they were moved to a column with leader lines.
  - The keyword map was unreadable with 340 nodes. The figure now shows the 120 largest, and the VOSviewer
    files keep all of them.
  - VOSviewer cluster numbers must start at 1. Isolated institutions, which have no community, get their own
    cluster.
- **Checked by:** a citation-total assertion; re-running with two Python hash seeds (identical outputs);
  comparing the institution network with the clustering step (same 764 / 748 nodes, same 6,354 links) and the
  country pairs with the report.
- **Files touched:** only files in this `network_mapping/` folder. The old output files were not copied over.

## 2026-11-21: overlay map

- **Prompt (translated):** the VOSviewer screenshots were still a placeholder in the report.
- **Produced:** VOSviewer itself could not be downloaded in the workspace (network blocked), so no screenshot
  was taken. `fig_keyword_overlay` was added instead. It draws the keyword map coloured by the mean publication
  year (`outputs/figures/n4_keyword_overlay_*.png`), which is what VOSviewer's overlay visualization shows.
  The VOSviewer files are unchanged.
