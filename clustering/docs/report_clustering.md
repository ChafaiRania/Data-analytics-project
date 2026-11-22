# Clustering: one community or several? (RQ3)

*Draft report section. Every number comes from `outputs/summary.json` and `outputs/tables/`, produced by
`src/clustering.py` on Person 1's clean corpus with Person 2's ALL / STRICT flags.*

## Question

**RQ3:** What clusters exist in European AI-in-education research: by topic, by collaboration, or simply
by country?

The question names three ways in which institutions might group, so we test them against each other
rather than choosing one. We build a **collaboration clustering** (who works with whom) and a **topic
clustering** (who works on what). We then measure how much of each is explained by **country** alone.

## Data

- **Corpus:** 10,208 papers in ALL and 5,927 in STRICT, with 2,742 EU institutions (OpenAlex IDs).
  Person 3 reports 2,740 because two pairs of distinct institutions share a name.
- **Collaboration network:** EU institutions with at least 5 papers. That is 764 institutions in ALL;
  748 (98%) form one connected network. In STRICT the figures are 545 and 535.
- **Topic profiles:** EU institutions with at least 10 papers: 455 in ALL, 315 in STRICT. Each is described
  by the share of its papers in each OpenAlex topic. ALL has 28 topic columns, STRICT has 15; topics with
  fewer than 30 papers are merged.

The thresholds exist because an institution with one or two papers has no meaningful profile. Its
community would be decided by a single co-authorship.

## Method and why

**Collaboration: Louvain community detection.** A "collaboration cluster" is a group of institutions that
co-author more with each other than with the rest. In network terms, that is a community, and Louvain finds
communities by maximising modularity.

- **Edge weights are fractional.** A paper with *n* institutions adds 1/(*n*−1) to each pair (Newman 2001).
  Without this, the 15 papers with more than 30 institutions would create the strongest links in the
  network.
- **Louvain is randomised.** We run it with 20 seeds and keep the partition with the highest modularity.
  Its agreement with the other runs (ARI) is the stability check.
- **Louvain fits this question better than k-means on the network.** It needs no k, and it uses the links
  directly rather than a summary of them.

**Topic: k-means on Hellinger-transformed topic shares.** Topic shares are proportions that sum to one, and
one topic ("Artificial Intelligence in Education") holds about a third of all papers. Taking the square
root (Hellinger distance) keeps this dominant topic from deciding every distance. k is chosen by silhouette
over k = 2..10, with three checks:

1. **A null model.** The topic of each paper is shuffled, which keeps institution sizes and topic popularity
   but breaks any specialisation. A real cluster structure must beat every one of 20 null runs.
2. **A second method.** Ward hierarchical clustering on the same data.
3. **Stability.** Agreement between 20 k-means seeds.

**Comparison with country.**

- NMI and ARI between each clustering and the institutions' country, against 200 random permutations of the
  country labels.
- The modularity of the partition "one community per country", on the same scale as Louvain's modularity.
- The share of collaboration weight that stays inside one country.

## Results

### Collaboration communities are mostly countries (Figures c1, c2, c6)

| | ALL | STRICT |
|---|---|---|
| Institutions in the network | 748 | 535 |
| Communities found | 15 | 13 |
| Modularity, Louvain | 0.664 | 0.649 |
| Modularity, "one community per country" | 0.613 | 0.590 |
| NMI with country (null 95th percentile) | **0.70** (0.10) | **0.68** (0.12) |
| Collaboration weight inside one country (null) | **70%** (8%) | **70%** (8%) |
| Stability over seeds (mean ARI) | 0.87 | 0.73 |

- **Most collaboration stays at home.** 70% of collaboration weight links two institutions in the same
  country. If partners were chosen regardless of country, about 8% would.
- **Country alone almost explains the network.** Simply grouping institutions by country reaches 92% of the
  modularity that Louvain finds with full freedom (0.613 against 0.664).
- **The communities are recognisably national.** In ALL, 7 of 15 have at least 80% of their members from one
  country:
  - Germany: community C0, 83% German, led by TU Munich and LMU Munich;
  - Spain: C1, 74%, led by Salamanca and Complutense;
  - Italy: C2, 91%;
  - France: C4, 89%, including CNRS, Inserm and Inria;
  - Portugal: C5, 80%;
  - Romania: C9, 79%;
  - Poland: C11, 92%;
  - Ireland: C13, 100%.
- **The result does not depend on our settings.** We varied the minimum papers (3, 5, 10) and the resolution
  (0.5, 1, 2). NMI with country stays between 0.59 and 0.72 in ALL and between 0.57 and 0.69 in STRICT
  (`network_sensitivity_*.csv`).

**What the communities add beyond country.** The communities that are not national are *regional*. They
join neighbouring countries, usually ones that share a language family or a history:

- **Nordic** (C6): Sweden and Finland, with the University of Eastern Finland, Oulu, KTH and Helsinki.
- **Central and Eastern Europe** (C3): Poland, Hungary, Bulgaria and Slovakia, led by Eötvös Loránd, Plovdiv
  and Óbuda.
- **Denmark–Germany–Austria** (C8): Aarhus, Copenhagen, Hamburg and Graz.
- **Benelux** (C10): KU Leuven, Maastricht, Amsterdam and Utrecht.
- **Croatia–Slovenia** (C12): Zagreb, Maribor and Ljubljana.
- **Greece–Cyprus** (C7).

No community spans Europe from west to east or north to south. The one clear exception to the
neighbour rule is individual: Universidad Carlos III de Madrid sits in the German community.

**A data finding: Northern Cyprus.** Near East University, the University of Kyrenia, Cyprus International
University and two other institutions in the northern part of Cyprus form their own community (C14 in ALL).
It is separate from the institutions of the Republic of Cyprus, which sit with Greece. OpenAlex codes all of
them "CY". The network therefore confirms Person 3's caveat that these institutions are not "EU" in
practice. Near East University is rank 9 in the institution ranking.

### Topic clusters: one weak split, not by country (Figures c3, c4, c5)

| | ALL | STRICT |
|---|---|---|
| Chosen k | 2 | 2 |
| Silhouette (best of 20 null runs) | 0.18 (0.12) | 0.23 (0.16) |
| Agreement with Ward clustering (ARI) | 0.60 | 0.39 |
| Stability over seeds (ARI) | 0.96 | 1.00 |
| NMI with country (null 95th percentile) | 0.06 (0.03) | 0.09 (0.04) |
| NMI with collaboration communities | 0.05 | 0.06 |

The silhouette is highest at k = 2 and falls steadily after that. Every k beats the null, but only by a small
margin, and a silhouette of 0.18 is weak: the clusters overlap a great deal. The k = 2 split is real but
coarse:

- **T1, health-oriented (133 institutions in ALL):** on average 32% of their papers are in "Artificial
  Intelligence in Healthcare and Education", against 12% overall. They include universities with large
  medical faculties and research hospitals: TU Munich, LMU Munich, University College Dublin, CNRS.
- **T0, general AI in education (322 institutions):** more "Artificial Intelligence in Education", "Online
  Learning and Analytics" and "Teaching and Learning Programming". This group includes the University of
  Eastern Finland, Oulu, Zagreb and Salamanca.

The same split appears in STRICT: ARI 0.85 between ALL and STRICT on the 315 institutions in both. The
topic clusters are almost unrelated to country (NMI 0.06) and to the collaboration communities (NMI 0.05).

## Interpretation: answer to RQ3

**The research is several communities that talk mostly within their own country, and those communities are
not defined by topic.**

1. **Collaboration is organised by country first, by region second.** Seven in ten collaborations are
   domestic. The communities Louvain finds are largely national research systems, and the cross-border ones
   join neighbours: Nordic, Benelux, Central-Eastern and Balkan groups. "One European community" does not
   describe the data. Nor does "communities that never talk": 98% of active institutions are connected in a
   single network, and 30% of the collaboration weight crosses a border.
2. **Topic does not separate institutions much.** Most institutions spread their papers over the same
   handful of topics. The only robust divide is health and medical education against the rest.
3. **The two structures are independent.** Institutions do not choose partners by topic. A German
   medical-education group and a German computer-science-education group are more likely to be in the same
   collaboration community than a German and a Spanish medical-education group.

**What we cannot tell from this.** Country-based collaboration has several possible causes: national
funding, a shared language, national-language journals, or simply distance. The network shows the
pattern, not which cause produces it.

## Limitations, and what would change the conclusion

- **The topic labels are coarse.** OpenAlex assigns one primary topic per paper, automatically, and one topic
  holds a third of all papers. A finer topic model built from abstracts (for example, TF-IDF with NMF) could
  reveal topic clusters that OpenAlex's labels hide. That would change point 2, not point 1.
- **The health cluster depends on corpus quality.** A spot check of the corpus during review found papers on AI in
  medicine where education is only a side word ("patient education", medical exams). If many such papers
  remain, part of cluster T1 is off-topic medicine rather than medical education. The hand-checked sample
  for RQ4 would show this.
- **Missing affiliations.** 5.2% of author slots have no institution. Their links are missing from the
  network.
- **Institution level.** CNRS, Inserm and similar national bodies count as one node, though they are many
  labs. This strengthens the national pattern for France.
- **STRICT is less stable.** With fewer papers, the communities agree less between seeds (ARI 0.73 against
  0.87), and the regional communities are less clear: the median share of the main country is 59% in
  STRICT against 79% in ALL. The national pattern itself holds (NMI 0.68).
- **What would overturn the main conclusion?** If NMI with country fell to the null level under any
  reasonable setting, or if collaboration weight inside one country dropped near 8%. Neither happens across
  the nine settings tested.
