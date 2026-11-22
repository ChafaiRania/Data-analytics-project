# Network mapping

*Draft report section. Every number comes from `outputs/network_stats.json` and `outputs/tables/`, produced by
`src/build_networks.py` on Person 1's clean corpus with Person 2's ALL / STRICT flags.*

## Question

The networks show the structure that the research questions ask about: who works with whom (institutions,
authors, countries) and which themes go together (keywords). They supply the maps for the report and the
network that the clustering step (RQ3) partitions.

## Method

- **Four networks**, each on ALL and STRICT:
  - institutions;
  - authors, identified by OpenAlex ID, never by name, because names are ambiguous;
  - countries;
  - keywords.
- **Each entity counts once per paper.** Two authors from one university make the university appear once on
  that paper.
- **Fractional link weights** (Newman 2001). A paper with n institutions adds 1/(n−1) to each pair. Without
  this, the 15 papers with more than 30 institutions would create the strongest links.
- **Map thresholds.** EU institutions with at least 5 papers, the same threshold as the clustering. Authors
  with an EU affiliation and at least 3 papers. Keywords on at least 30 papers (ALL) or 20 (STRICT).
- **Keyword links use association strength** (van Eck & Waltman 2009). The terms of the search query itself
  ("artificial intelligence in education", "machine learning", …) are left off the map, because they co-occur
  with everything. Keyword themes are Louvain communities on that network.
- **VOSviewer files** for every network and layer. The institution map carries the clustering step's
  communities as its clusters, so the two steps show the same groups.

## Results

| | ALL | STRICT |
|---|---|---|
| Institutions, all (EU and non-EU) | 5,683 | 4,557 |
| EU institutions on the map (>= 5 papers) | 764 | 545 |
| ... links between them | 6,354 | 4,374 |
| ... in the largest connected part | 98% | 98% |
| ... density | 0.022 | 0.030 |
| Authors on the map (>= 3 papers) | 1,735 | 1,026 |
| ... in the largest connected part | 37% | 39% |
| Papers with 2+ EU countries | 11.7% | 14.1% |
| Papers with a non-EU partner | 29.8% | 34.4% |
| Keyword themes | 7 | 5 |

**1. Institutions form one connected but sparse network.** 98% of active EU institutions are linked to each
other through some chain of co-authorships. Each one, though, works with only about 2% of the others: 17
partners on average out of 764.

**2. The hubs are not the most productive institutions (Figure n1).**

- The University of Eastern Finland publishes most (169 papers) but has only 46 EU partners.
- The institutions with most partners are large comprehensive universities with medical faculties, and
  French national research bodies:
  - LMU Munich: 108 partners from 109 papers;
  - Sapienza Rome: 104 from 51;
  - CNRS: 100 from 89;
  - Porto: 88 from 55;
  - Bologna: 85 from 57;
  - Naples Federico II: 83 from 42.
- CNRS, LMU and Sapienza also have the highest betweenness: most short paths between other institutions run
  through them, so they are the bridges of the network.
- Productivity and connectedness are therefore two different kinds of leadership. A ranking by papers (RQ1)
  and a ranking by partners name different institutions.

**3. Author collaboration is fragmented.** Among the 1,735 regular EU authors, only 37% belong to the largest
connected group, and 253 have no co-author on the map. Institutions connect through many different people,
not through a small core of researchers. The best-connected authors come from learning analytics (Gašević,
Drachsler, Jivet), with 35–41 partners each.

**4. Cross-border collaboration follows neighbours and size (Figure n2).**

- Only 11.7% of papers link two or more EU countries, while 29.8% have a non-EU partner, most often from the
  United States or the United Kingdom.
- The strongest EU pairs are:
  - Germany–Netherlands, 98 papers;
  - Spain–Italy, 82;
  - Germany–Spain, 77;
  - Germany–Italy, 66;
  - Austria–Germany, 60.
- Next come France–Italy (49), Spain–Portugal (47) and Finland–Sweden (44). The clustering step tests this
  formally: 70% of collaboration weight stays inside one country.

**5. Seven keyword themes, with a clear time order (Figure n3).** Each theme is listed with its largest
keywords and the mean publication year of its papers:

| Theme | Largest keywords | Mean year |
|---|---|---|
| Learning analytics | learning analytics, online learning, academic performance, student performance prediction | 2023.1 |
| Personalised learning | personalized learning, student engagement, intelligent tutoring systems, motivation | 2023.9 |
| Students' attitudes and adoption | university students, gender differences, technology acceptance, trust in AI | 2024.1 |
| Teachers | teacher professional development, teacher perceptions, pre-service teachers, digital skills | 2024.2 |
| ChatGPT and LLMs | ChatGPT, large language models, chatbots, medical education, programming education | 2024.2 |
| Learning practices | critical thinking, student perceptions, cooperative learning, academic writing | 2024.2 |
| Generative AI, ethics and policy | generative AI, higher education, AI ethics, AI literacy, academic integrity | 2024.3 |

Figure n4 shows the same map coloured by year, as VOSviewer's overlay view does: learning analytics (2022.5), online learning and COVID-19 sit in the oldest corner, while generative AI, responsible AI use and prompt engineering (2024.5–2024.6) are the newest. The older core of the field is learning analytics and adaptive tutoring. The newer themes, generative AI,
ethics, academic integrity and teachers, carry most of the growth after 2022 seen in RQ1. Medical education
sits inside the ChatGPT theme: in this corpus it is mostly about LLMs in medical training.

**6. ALL and STRICT agree.** The partner counts of the 545 institutions on both maps correlate at Spearman
0.94, and 12 of the 15 largest hubs are the same. Unlike the RQ1 rankings by papers, the network structure
barely depends on the inclusion rule.

## Limitations

- **Keywords are OpenAlex's.** They are assigned automatically and vary in wording ("generative AI",
  "generative AI in education"). Themes can split or merge with the threshold; STRICT finds 5 themes instead
  of 7.
- **Missing affiliations.** 5.2% of author slots have no institution, so their links are missing.
- **National bodies count as one node.** CNRS and Inserm are many labs, so their partner counts overstate any
  single group's reach.
- **Author IDs.** OpenAlex sometimes splits one person into two IDs, or merges two. Author-level results are
  the least reliable of the four networks.
- **Betweenness** is computed without weights, on who is linked to whom.
