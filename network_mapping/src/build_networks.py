"""
Network mapping for Project D: who collaborates with whom, and which themes go together.

Usage (from the network_mapping/ folder):
    python src/build_networks.py
    python src/build_networks.py --data ../collecte_cleaning/data/processed

Four networks, each built on the ALL and on the STRICT layer of Person 2:

  institutions  nodes = institutions (OpenAlex IDs), link = shared paper
  authors       nodes = authors (OpenAlex IDs, never names), link = shared paper
  countries     nodes = countries, link = shared paper
  keywords      nodes = OpenAlex keywords, link = keywords on the same paper

Counting rules
  - Every entity is counted once per paper: two authors from one university make the
    university appear once on that paper (one row per paper x institution).
  - Links carry two weights: `papers` (how many papers the pair shares) and `weight`
    (fractional, Newman 2001: a paper with n entities adds 1/(n-1) to each pair), so a
    paper with 80 institutions does not outweigh years of regular collaboration.
  - Citations of an institution or author = sum of `cited_by_count` over its distinct papers.

Inputs (never modified): works_layers.csv, authorships_layers.csv  (Person 1 + Person 2)
Optional input: clustering/outputs/tables/institution_assignments_{all,strict}.csv  (Person 5)
Outputs: outputs/tables/*.csv, outputs/vosviewer/{all,strict}/*.txt, outputs/figures/*.png,
         outputs/network_stats.json
"""

import argparse
import json
from collections import defaultdict
from itertools import combinations

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

import config as C
from viz_style import (CATEGORICAL, INK_MUTED, INK_PRIMARY, INK_SECONDARY, SURFACE,
                       apply_style)

SEQ_BLUE = LinearSegmentedColormap.from_list("seq_blue", [SURFACE, "#9ec5f0", "#2a78d6", "#0d3b75"])
OTHER_GREY = "#c9c8c2"
ACCENT = CATEGORICAL[0]


# ----------------------------------------------------------------------------------------
# data
# ----------------------------------------------------------------------------------------

def load(data_dir):
    works = pd.read_csv(data_dir / C.WORKS_FILE,
                        usecols=["work_id", "year", "cited_by_count", "keywords", "in_strict"])
    auth = pd.read_csv(data_dir / C.AUTHORSHIPS_FILE,
                       usecols=["work_id", "author_id", "author_name", "institution_id",
                                "institution_name", "institution_country", "is_eu"])
    print(f"works: {len(works):,} | authorship rows: {len(auth):,}")
    return works, auth


def layer(works, auth, name):
    w = works if name == "ALL" else works[works["in_strict"]]
    a = auth[auth["work_id"].isin(w["work_id"])]
    return w.reset_index(drop=True), a.reset_index(drop=True)


# ----------------------------------------------------------------------------------------
# generic network pieces
# ----------------------------------------------------------------------------------------

def pairs(pe, key):
    """Links from a paper x entity table (one row per paper and entity).
    papers = shared papers; weight = fractional, sum of 1/(n-1) over shared papers."""
    papers, weight = defaultdict(int), defaultdict(float)
    for _, ids in pe.groupby("work_id")[key]:
        ids = sorted(set(ids))
        n = len(ids)
        if n < 2:
            continue
        w = 1.0 / (n - 1)
        for a, b in combinations(ids, 2):
            papers[(a, b)] += 1
            weight[(a, b)] += w
    if not papers:
        return pd.DataFrame(columns=["source", "target", "papers", "weight"])
    df = pd.DataFrame([(a, b, papers[(a, b)], weight[(a, b)]) for (a, b) in papers],
                      columns=["source", "target", "papers", "weight"])
    df["weight"] = df["weight"].round(4)
    return df.sort_values(["papers", "weight"], ascending=False).reset_index(drop=True)


def node_counts(pe, key, works):
    """papers, fractional papers, citations and mean year per entity."""
    n = pe.groupby("work_id")[key].transform("size")
    pe = pe.assign(frac=1.0 / n).merge(works[["work_id", "cited_by_count", "year"]], on="work_id")
    return pe.groupby(key).agg(papers=("work_id", "nunique"),
                               papers_fractional=("frac", "sum"),
                               citations=("cited_by_count", "sum"),
                               mean_year=("year", "mean"))


def graph(nodes, edges):
    """Undirected weighted graph, nodes in sorted order (reproducible)."""
    keep = set(nodes)
    G = nx.Graph()
    G.add_nodes_from(sorted(keep))
    e = edges[edges["source"].isin(keep) & edges["target"].isin(keep)]
    G.add_weighted_edges_from(zip(e["source"], e["target"], e["weight"]))
    nx.set_edge_attributes(G, {(s, t): p for s, t, p in zip(e["source"], e["target"], e["papers"])},
                           "papers")
    return G


def graph_stats(G):
    if G.number_of_nodes() == 0:
        return {}
    lcc = max(nx.connected_components(G), key=len)
    return {
        "nodes": G.number_of_nodes(),
        "links": G.number_of_edges(),
        "density": round(nx.density(G), 4),
        "isolated_nodes": nx.number_of_isolates(G),
        "largest_component_nodes": len(lcc),
        "largest_component_share": round(len(lcc) / G.number_of_nodes(), 3),
        "mean_partners": round(2 * G.number_of_edges() / G.number_of_nodes(), 1),
    }


def louvain(G, weight="weight"):
    """Reproducible Louvain: integer node names (networkx iterates over sets internally)."""
    nodes = sorted(G.nodes)
    Gi = nx.relabel_nodes(G, {n: i for i, n in enumerate(nodes)})
    comms = nx.community.louvain_communities(Gi, weight=weight, seed=C.SEED)
    comms = sorted(([nodes[i] for i in c] for c in comms), key=lambda c: (-len(c), min(c)))
    return {n: k for k, c in enumerate(comms) for n in c}


# ----------------------------------------------------------------------------------------
# the four networks
# ----------------------------------------------------------------------------------------

def institutions(w, a, tag):
    pi = (a.dropna(subset=["institution_id"])
            .drop_duplicates(["work_id", "institution_id"])[
                ["work_id", "institution_id", "institution_name", "institution_country", "is_eu"]])
    nodes = node_counts(pi[["work_id", "institution_id"]], "institution_id", w)
    info = pi.groupby("institution_id").agg(name=("institution_name", "first"),
                                            country=("institution_country", "first"),
                                            is_eu=("is_eu", "first"))
    nodes = info.join(nodes)
    edges = pairs(pi, "institution_id")

    # check: citations counted once per paper (the bug of the first version)
    expected = (pi.merge(w[["work_id", "cited_by_count"]], on="work_id")["cited_by_count"].sum())
    assert nodes["citations"].sum() == expected, "citation total does not tie to the papers"

    # partners in the full network (all institutions), then the EU map network
    full = graph(nodes.index, edges)
    nodes["partners_all"] = pd.Series(dict(full.degree()))
    eu_map = nodes.index[nodes["is_eu"] & (nodes["papers"] >= C.MIN_PAPERS_INSTITUTION_MAP)]
    G = graph(eu_map, edges)
    nodes["in_map"] = nodes.index.isin(eu_map)
    nodes["partners_eu_map"] = pd.Series(dict(G.degree()))
    nodes["strength_eu_map"] = pd.Series(dict(G.degree(weight="weight"))).round(2)
    nodes["betweenness_eu_map"] = pd.Series(nx.betweenness_centrality(G)).round(4)

    # communities of the clustering step, if present (same thresholds and weights)
    f = C.CLUSTERING_DIR / f"institution_assignments_{tag}.csv"
    if f.exists():
        comm = pd.read_csv(f, index_col=0)["collab_community"]
        nodes["community_p5"] = comm.reindex(nodes.index)
    return nodes, edges, G


def authors(w, a):
    pa = a.dropna(subset=["author_id"]).drop_duplicates(["work_id", "author_id"])
    nodes = node_counts(pa[["work_id", "author_id"]], "author_id", w)
    by_a = a.dropna(subset=["author_id"])
    info = by_a.groupby("author_id").agg(
        name=("author_name", lambda s: s.mode().iat[0] if s.notna().any() else ""),
        eu_affiliated=("is_eu", "any"),
        main_institution=("institution_name",
                          lambda s: s.dropna().mode().iat[0] if s.notna().any() else ""),
        main_country=("institution_country",
                      lambda s: s.dropna().mode().iat[0] if s.notna().any() else ""))
    nodes = info.join(nodes)
    edges = pairs(pa, "author_id")
    keep = nodes.index[nodes["eu_affiliated"] & (nodes["papers"] >= C.MIN_PAPERS_AUTHOR_MAP)]
    G = graph(keep, edges)
    nodes["in_map"] = nodes.index.isin(keep)
    nodes["partners_map"] = pd.Series(dict(G.degree()))
    return nodes, edges, G


def countries(w, a):
    pc = (a.dropna(subset=["institution_country"])
            .drop_duplicates(["work_id", "institution_country"]))
    nodes = node_counts(pc[["work_id", "institution_country"]], "institution_country", w)
    nodes["is_eu"] = pc.groupby("institution_country")["is_eu"].first()
    edges = pairs(pc, "institution_country")
    G = graph(nodes.index, edges)
    nodes["partners"] = pd.Series(dict(G.degree()))
    # share of papers with 2+ EU countries / with any non-EU country
    eu = pc[pc["is_eu"]].groupby("work_id").size()
    has_non_eu = pc[~pc["is_eu"]]["work_id"].unique()
    extra = {
        "papers_with_2plus_eu_countries": round(float((eu >= 2).mean()), 3),
        "papers_with_non_eu_partner": round(len(has_non_eu) / w["work_id"].nunique(), 3),
    }
    return nodes, edges, G, extra


def keywords(w, name):
    kw = (w[["work_id", "keywords", "cited_by_count", "year"]].dropna(subset=["keywords"])
            .assign(keyword=lambda d: d["keywords"].str.lower().str.split("|"))
            .explode("keyword"))
    kw["keyword"] = kw["keyword"].str.strip()
    kw = kw[kw["keyword"] != ""].drop_duplicates(["work_id", "keyword"])
    nodes = kw.groupby("keyword").agg(papers=("work_id", "nunique"),
                                      citations=("cited_by_count", "sum"),
                                      mean_year=("year", "mean"))
    # link table: keywords with >= 5 papers (rarer ones are mostly one-off phrasings)
    common = nodes.index[nodes["papers"] >= 5]
    edges = pairs(kw[kw["keyword"].isin(common)][["work_id", "keyword"]], "keyword")
    edges = edges.drop(columns="weight")            # co-occurrence = plain counts

    keep = nodes.index[(nodes["papers"] >= C.MIN_KEYWORD_PAPERS[name])
                       & ~nodes.index.isin(C.GENERIC_KEYWORDS)]
    e = edges[edges["source"].isin(keep) & edges["target"].isin(keep)].copy()
    # association strength (van Eck & Waltman 2009): co-occurrences / (occ_i * occ_j),
    # the normalisation VOSviewer uses; raw counts would just put frequent keywords together
    occ = nodes["papers"]
    e["weight"] = e["papers"] / (occ.loc[e["source"]].values * occ.loc[e["target"]].values) \
        * occ.sum()
    G = graph(keep, e)
    themes = louvain(G)
    nodes["in_map"] = nodes.index.isin(keep)
    nodes["theme"] = pd.Series(themes).astype("Int64")
    return nodes, edges, G


# ----------------------------------------------------------------------------------------
# VOSviewer
# ----------------------------------------------------------------------------------------

def write_vos(path_stem, nodes, G, label_col, weights, cluster_col=None):
    """VOSviewer map file (tab-separated: id, label, [cluster], weight<..>, score<..>) and
    network file (id1, id2, link strength). Numeric ids, as VOSviewer requires."""
    ids = {n: i + 1 for i, n in enumerate(sorted(G.nodes))}
    m = nodes.loc[sorted(G.nodes)].copy()
    out = pd.DataFrame({"id": [ids[n] for n in m.index],
                        "label": m[label_col].astype(str).str.replace("\t", " ").values})
    if cluster_col is not None and cluster_col in m and m[cluster_col].notna().any():
        # VOSviewer clusters are numbered from 1; nodes without a community (isolated
        # institutions, outside the clustering's connected network) get one extra cluster
        c = m[cluster_col].astype(float)
        out["cluster"] = (c.fillna(c.max() + 1) + 1).astype(int).values
    for col, title in weights:
        out[title] = m[col].round(1).values
    out["score<Avg. pub. year>"] = m["mean_year"].round(2).values
    out.to_csv(f"{path_stem}_map.txt", sep="\t", index=False)
    with open(f"{path_stem}_network.txt", "w", encoding="utf-8") as f:
        for s, t, d in sorted(G.edges(data=True), key=lambda x: (ids[x[0]], ids[x[1]])):
            f.write(f"{ids[s]}\t{ids[t]}\t{d['weight']:.4f}\n")


# ----------------------------------------------------------------------------------------
# figures
# ----------------------------------------------------------------------------------------

def fig_hubs(inst, name, path):
    m = inst[inst["in_map"]].copy()
    fig, ax = plt.subplots(figsize=(11, 5.6))
    fig.subplots_adjust(right=0.6)
    ax.scatter(m["papers"], m["partners_eu_map"], s=14, color=OTHER_GREY, edgecolors=SURFACE,
               linewidths=0.4, zorder=2)
    hubs = m.sort_values(["partners_eu_map", "papers"], ascending=False).head(6)
    prod = m.sort_values(["papers", "partners_eu_map"], ascending=False).head(3)
    show = pd.concat([hubs, prod[~prod.index.isin(hubs.index)]])
    ax.scatter(hubs["papers"], hubs["partners_eu_map"], s=34, color=ACCENT, edgecolors=SURFACE,
               linewidths=0.8, zorder=3)
    ax.scatter(prod.loc[~prod.index.isin(hubs.index), "papers"],
               prod.loc[~prod.index.isin(hubs.index), "partners_eu_map"],
               s=34, color=INK_SECONDARY, edgecolors=SURFACE, linewidths=0.8, zorder=3)
    # labels in a column right of the plot, ordered like the points, with leader lines
    show = show.sort_values("partners_eu_map", ascending=False)
    for i, (idx, r) in enumerate(show.iterrows()):
        ax.annotate(f"{r['name'][:42]} ({r['country']}): {int(r['papers'])} papers, "
                    f"{int(r['partners_eu_map'])} partners",
                    (r["papers"], r["partners_eu_map"]), xycoords="data",
                    xytext=(1.04, 0.97 - i * 0.085), textcoords="axes fraction",
                    fontsize=7.5, color=INK_PRIMARY, va="center", annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=INK_MUTED, lw=0.5))
    ax.set_xscale("log")
    ax.set_xlabel("Papers (full counting, log scale)")
    ax.set_ylabel("EU partners in the network")
    ax.set_title(f"The best-connected institutions are not the most productive ({name})")
    fig.text(0.01, 0.01, f"EU institutions with >= {C.MIN_PAPERS_INSTITUTION_MAP} papers. "
             "Blue: six with most partners. Dark grey: three with most papers.",
             fontsize=7, color=INK_SECONDARY)
    fig.savefig(path)
    plt.close(fig)


def fig_country_pairs(cn, ce, name, path, n=14):
    eu = cn[cn["is_eu"]].sort_values("papers", ascending=False).index[:n]
    mat = pd.DataFrame(0, index=eu, columns=eu, dtype=float)
    for s, t, p in zip(ce["source"], ce["target"], ce["papers"]):
        if s in eu and t in eu:
            mat.loc[s, t] = mat.loc[t, s] = p
    fig, ax = plt.subplots(figsize=(7.5, 6.4))
    masked = np.ma.masked_where(np.eye(len(eu), dtype=bool), mat.values)
    im = ax.imshow(masked, cmap=SEQ_BLUE, vmin=0)
    ax.set_xticks(range(len(eu)), eu)
    ax.set_yticks(range(len(eu)), eu)
    ax.grid(False)
    vmax = mat.values.max()
    for i in range(len(eu)):
        for j in range(len(eu)):
            v = mat.values[i, j]
            if i != j and v >= 25:
                ax.text(j, i, f"{int(v)}", ha="center", va="center", fontsize=6.5,
                        color="white" if v > 0.55 * vmax else INK_PRIMARY)
    cb = fig.colorbar(im, ax=ax, fraction=0.04)
    cb.set_label("Shared papers", color=INK_SECONDARY)
    top = ce[ce["source"].isin(eu) & ce["target"].isin(eu)].iloc[0]
    ax.set_title(f"EU country pairs by shared papers ({name}); strongest: "
                 f"{top['source']}-{top['target']} ({top['papers']})", fontsize=10)
    fig.text(0.01, 0.01, f"The {n} EU countries with most papers, in that order. "
             "Numbers shown for pairs with >= 25 shared papers.", fontsize=7, color=INK_SECONDARY)
    fig.savefig(path)
    plt.close(fig)


def fig_keywords(kn, G, name, path, n_show=120):
    # the figure shows the n_show largest keywords; the VOSviewer files keep them all
    big = kn.loc[sorted(G.nodes)].sort_values(["papers"], ascending=False).index[:n_show]
    n_all, n_themes = G.number_of_nodes(), kn.loc[sorted(G.nodes), "theme"].nunique()
    G = G.subgraph(big).copy()
    pos = nx.spring_layout(G, weight="weight", seed=C.SEED, k=0.6, iterations=300)
    nodes = sorted(G.nodes)
    theme = kn.loc[nodes, "theme"]
    order = sorted(theme.unique())[:8]
    cmap = {t: CATEGORICAL[i] for i, t in enumerate(order)}
    colors = [cmap.get(t, OTHER_GREY) for t in theme]
    size = 10 + 180 * np.sqrt(kn.loc[nodes, "papers"] / kn.loc[nodes, "papers"].max())
    fig, ax = plt.subplots(figsize=(10, 8.5))
    w = np.array([d["weight"] for _, _, d in G.edges(data=True)])
    thr = np.quantile(w, 0.90) if len(w) else 0
    strong = [(s, t) for s, t, d in G.edges(data=True) if d["weight"] >= thr]
    nx.draw_networkx_edges(G, pos, edgelist=strong, ax=ax, width=0.4, alpha=0.2,
                           edge_color=INK_MUTED)
    xy = np.array([pos[n] for n in nodes])
    ax.scatter(xy[:, 0], xy[:, 1], s=size, c=colors, edgecolors=SURFACE, linewidths=0.6, zorder=3)
    for t in order:
        members = kn.loc[[n for n in nodes if theme[n] == t]].sort_values(
            ["papers"], ascending=False).head(2)
        for k, (kwd, r) in enumerate(members.iterrows()):
            ax.annotate(kwd, pos[kwd], fontsize=7.5, color=INK_PRIMARY, zorder=4,
                        xytext=(5, 5), textcoords="offset points",
                        bbox=dict(boxstyle="round,pad=0.1", fc=SURFACE, ec="none", alpha=0.75))
    handles = []
    for i, t in enumerate(order):
        top = kn[kn["in_map"] & (kn["theme"] == t)].sort_values("papers", ascending=False)
        handles.append(plt.Line2D([], [], marker="o", ls="", color=CATEGORICAL[i],
                                  label=f"T{t}: {len(top)} keywords, e.g. {', '.join(top.index[:2])}"))
    ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=7.5,
              frameon=False, title="Theme (Louvain)", title_fontsize=8)
    ax.set_title(f"Keyword map: {n_themes} themes among {n_all} keywords ({name})")
    ax.set_axis_off()
    fig.text(0.01, 0.01, f"The {n_show} most frequent of the {n_all} keywords on >= "
             f"{C.MIN_KEYWORD_PAPERS[name]} papers (query terms left out); the full map is in "
             "outputs/vosviewer. Links: association strength, strongest 10% drawn.",
             fontsize=7, color=INK_SECONDARY)
    fig.savefig(path)
    plt.close(fig)


def fig_keyword_overlay(kn, G, name, path, n_show=120):
    """VOSviewer's 'overlay visualization': the same keyword map coloured by the mean
    publication year of each keyword's papers (same layout seed as the theme map)."""
    big = kn.loc[sorted(G.nodes)].sort_values(["papers"], ascending=False).index[:n_show]
    G = G.subgraph(big).copy()
    pos = nx.spring_layout(G, weight="weight", seed=C.SEED, k=0.6, iterations=300)
    nodes = sorted(G.nodes)
    yr = kn.loc[nodes, "mean_year"].astype(float)
    size = 10 + 180 * np.sqrt(kn.loc[nodes, "papers"] / kn.loc[nodes, "papers"].max())
    fig, ax = plt.subplots(figsize=(10, 8.5))
    w = np.array([d["weight"] for _, _, d in G.edges(data=True)])
    thr = np.quantile(w, 0.90) if len(w) else 0
    strong = [(s_, t) for s_, t, d in G.edges(data=True) if d["weight"] >= thr]
    nx.draw_networkx_edges(G, pos, edgelist=strong, ax=ax, width=0.4, alpha=0.2, edge_color=INK_MUTED)
    xy = np.array([pos[n] for n in nodes])
    lo, hi = np.floor(yr.quantile(0.05) * 4) / 4, np.ceil(yr.quantile(0.95) * 4) / 4
    sc = ax.scatter(xy[:, 0], xy[:, 1], s=size, c=yr, cmap=SEQ_BLUE, vmin=lo, vmax=hi,
                    edgecolors=INK_MUTED, linewidths=0.4, zorder=3)
    # label the oldest and the newest large keywords
    ranked = kn.loc[nodes].sort_values("papers", ascending=False).head(40)
    show = list(ranked.sort_values("mean_year").index[:5]) + list(ranked.sort_values("mean_year").index[-5:])
    for j, kwd in enumerate(show):
        ax.annotate(f"{kwd} ({kn.at[kwd, 'mean_year']:.1f})", pos[kwd], fontsize=7.5, color=INK_PRIMARY,
                    xytext=(5, 6) if j % 2 == 0 else (5, -13), textcoords="offset points", zorder=4,
                    bbox=dict(boxstyle="round,pad=0.1", fc=SURFACE, ec="none", alpha=0.75))
    cb = fig.colorbar(sc, ax=ax, fraction=0.03, pad=0.01)
    cb.set_label("Mean publication year of the keyword's papers", color=INK_SECONDARY)
    ax.set_title(f"Keyword map, overlay by year: learning analytics is older, generative AI newer ({name})")
    ax.set_axis_off()
    fig.text(0.01, 0.01, f"Same {n_show} keywords and layout as the theme map. Labelled: the five oldest and five "
             "newest of the 40 largest keywords.", fontsize=7, color=INK_SECONDARY)
    fig.savefig(path)
    plt.close(fig)


# ----------------------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------------------

def run_layer(works, auth, name):
    print(f"\n=== {name} ===")
    tag = name.lower()
    vos = C.VOS_DIR / tag
    vos.mkdir(parents=True, exist_ok=True)
    w, a = layer(works, auth, name)
    stats = {"papers": len(w)}

    inst, ie, Gi = institutions(w, a, tag)
    inst.sort_values("papers", ascending=False).to_csv(C.TAB_DIR / f"nodes_institutions_{tag}.csv")
    ie.to_csv(C.TAB_DIR / f"edges_institutions_{tag}.csv", index=False)
    write_vos(vos / "institutions", inst, Gi, "name",
              [("papers", "weight<Papers>"), ("citations", "weight<Citations>")],
              cluster_col="community_p5")
    stats["institutions_all"] = {"nodes": len(inst), "links": len(ie)}
    stats["institutions_eu_map"] = graph_stats(Gi)
    hubs = (inst[inst["in_map"]]
            .sort_values(["partners_eu_map", "papers"], ascending=False)
            .head(C.N_TOP)[["name", "country", "papers", "papers_fractional", "citations",
                            "partners_eu_map", "strength_eu_map", "betweenness_eu_map"]])
    hubs.round(2).to_csv(C.TAB_DIR / f"top_hubs_{tag}.csv")

    au, ae, Ga = authors(w, a)
    au.sort_values("papers", ascending=False).to_csv(C.TAB_DIR / f"nodes_authors_{tag}.csv")
    ae.to_csv(C.TAB_DIR / f"edges_authors_{tag}.csv", index=False)
    write_vos(vos / "authors", au, Ga, "name",
              [("papers", "weight<Papers>"), ("citations", "weight<Citations>")])
    stats["authors_all"] = {"nodes": len(au), "links": len(ae)}
    stats["authors_map"] = graph_stats(Ga)

    cn, ce, Gc, extra = countries(w, a)
    cn.sort_values("papers", ascending=False).to_csv(C.TAB_DIR / f"nodes_countries_{tag}.csv")
    ce.to_csv(C.TAB_DIR / f"edges_countries_{tag}.csv", index=False)
    cn["label"] = cn.index
    write_vos(vos / "countries", cn, Gc, "label", [("papers", "weight<Papers>")])
    eu_pairs = ce[ce["source"].isin(cn.index[cn["is_eu"]]) & ce["target"].isin(cn.index[cn["is_eu"]])]
    eu_pairs.head(C.N_TOP).to_csv(C.TAB_DIR / f"top_eu_country_pairs_{tag}.csv", index=False)
    stats["countries"] = {**graph_stats(Gc), **extra}

    kn, ke, Gk = keywords(w, name)
    kn.sort_values("papers", ascending=False).to_csv(C.TAB_DIR / f"nodes_keywords_{tag}.csv")
    ke.to_csv(C.TAB_DIR / f"edges_keywords_{tag}.csv", index=False)
    kn["label"] = kn.index
    write_vos(vos / "keywords", kn, Gk, "label", [("papers", "weight<Papers>")], cluster_col="theme")
    themes = (kn[kn["in_map"]].reset_index().sort_values("papers", ascending=False)
                .groupby("theme").agg(keywords=("keyword", "size"),
                                      papers_of_top_keyword=("papers", "first"),
                                      top_keywords=("keyword", lambda s: "; ".join(s.head(8)))))
    themes.to_csv(C.TAB_DIR / f"keyword_themes_{tag}.csv")
    stats["keywords_map"] = {**graph_stats(Gk), "themes": int(kn["theme"].nunique())}

    fig_hubs(inst, name, C.FIG_DIR / f"n1_hubs_{tag}.png")
    fig_country_pairs(cn, ce, name, C.FIG_DIR / f"n2_country_pairs_{tag}.png")
    fig_keywords(kn, Gk, name, C.FIG_DIR / f"n3_keyword_map_{tag}.png")
    fig_keyword_overlay(kn, Gk, name, C.FIG_DIR / f"n4_keyword_overlay_{tag}.png")

    print(json.dumps(stats, indent=1))
    print(hubs[["name", "country", "papers", "partners_eu_map", "betweenness_eu_map"]].head(8).to_string())
    print(themes.to_string())
    return stats, inst


def spearman(x, y):
    return float(pd.Series(x).rank().corr(pd.Series(y).rank()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None, help="folder with works_layers.csv and authorships_layers.csv")
    args = ap.parse_args()
    data_dir = C.Path(args.data) if args.data else C.DATA_DIR
    for d in (C.TAB_DIR, C.FIG_DIR, C.VOS_DIR):
        d.mkdir(parents=True, exist_ok=True)
    apply_style()
    works, auth = load(data_dir)

    stats, inst = {}, {}
    for name in C.LAYERS:
        stats[name], inst[name] = run_layer(works, auth, name)

    # ALL vs STRICT: do the same institutions act as hubs?
    a, s = inst["ALL"], inst["STRICT"]
    common = a.index[a["in_map"]].intersection(s.index[s["in_map"]])
    top_a = set(a[a["in_map"]].sort_values("partners_eu_map", ascending=False).index[:C.N_TOP])
    top_s = set(s[s["in_map"]].sort_values("partners_eu_map", ascending=False).index[:C.N_TOP])
    stats["ALL_vs_STRICT"] = {
        "institutions_in_both_maps": int(len(common)),
        "spearman_partners": round(spearman(a.loc[common, "partners_eu_map"],
                                            s.loc[common, "partners_eu_map"]), 3),
        f"top{C.N_TOP}_hubs_shared": len(top_a & top_s),
    }
    stats["settings"] = {k: (sorted(v) if isinstance(v, set) else v) for k, v in vars(C).items()
                         if k.isupper() and k != "ROOT" and not k.endswith("_DIR")
                         and not k.endswith("_FILE")}
    (C.OUT_DIR / "network_stats.json").write_text(json.dumps(stats, indent=2, default=str),
                                                  encoding="utf-8")
    print("\nALL vs STRICT:", stats["ALL_vs_STRICT"])
    print(f"Done. Outputs in {C.OUT_DIR}")


if __name__ == "__main__":
    main()
