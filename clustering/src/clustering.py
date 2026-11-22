"""
RQ3: What clusters exist in European AI-in-education research: by topic, by collaboration,
or simply by country?

Usage (from the clustering/ folder):
    python src/clustering.py
    python src/clustering.py --data ../collecte_cleaning/data/processed

Two clusterings of EU institutions, each run on the ALL and the STRICT layer:

  A. Collaboration communities.
     Network: EU institutions with >= 5 papers; an edge when two institutions share a paper.
     Edge weight is fractional (Newman 2001): a paper with n institutions adds 1/(n-1) to each
     pair, so one 80-institution consortium paper does not outweigh years of regular work.
     Method: Louvain modularity maximisation on the largest connected component, 20 seeds,
     best modularity kept, agreement between seeds reported (ARI).

  B. Topic-profile clusters.
     Each EU institution with >= 10 papers is described by the share of its papers in each
     OpenAlex topic (topics with < 30 papers merged into "Other topics"), square-root
     transformed (Hellinger distance). Method: k-means, k chosen by silhouette over k = 2..10,
     checked against Ward hierarchical clustering and against a null model in which the topic
     of each paper is shuffled (same institutions, same topic popularity, no specialisation).

  Both are compared with country:
     NMI and ARI between cluster and country, against a null in which country labels are
     permuted across institutions; modularity of the "country" partition itself; share of
     collaboration weight that stays inside one country.

Inputs (never modified): works_layers.csv, authorships_layers.csv  (Person 1 + Person 2)
Outputs: outputs/tables/*.csv, outputs/summary.json, outputs/figures/*.png
"""

import argparse
import json
from itertools import combinations

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import (adjusted_rand_score, normalized_mutual_info_score,
                             silhouette_score)

import config as C
from viz_style import (CATEGORICAL, GRIDLINE, INK_MUTED, INK_PRIMARY, INK_SECONDARY,
                       SURFACE, apply_style)

SEQ_BLUE = LinearSegmentedColormap.from_list("seq_blue", [SURFACE, "#9ec5f0", "#2a78d6", "#0d3b75"])
OTHER_GREY = "#c9c8c2"


# ----------------------------------------------------------------------------------------
# data
# ----------------------------------------------------------------------------------------

def load(data_dir):
    works = pd.read_csv(data_dir / C.WORKS_FILE,
                        usecols=["work_id", "year", "type", "topic", "in_strict"])
    auth = pd.read_csv(data_dir / C.AUTHORSHIPS_FILE,
                       usecols=["work_id", "institution_id", "institution_name",
                                "institution_country", "is_eu"])
    # one row per paper x institution (two authors from the same university count once)
    pi = (auth.dropna(subset=["institution_id"])
              .drop_duplicates(subset=["work_id", "institution_id"])
              .reset_index(drop=True))
    print(f"works: {len(works):,} | paper x institution rows: {len(pi):,}")
    return works, pi


def layer_data(works, pi, layer):
    w = works if layer == "ALL" else works[works["in_strict"]]
    p = pi[pi["work_id"].isin(w["work_id"])]
    return w, p


def institution_table(p):
    """name, country and paper count of every EU institution in the layer."""
    eu = p[p["is_eu"]]
    return (eu.groupby("institution_id")
              .agg(name=("institution_name", "first"),
                   country=("institution_country", "first"),
                   papers=("work_id", "nunique")))


# ----------------------------------------------------------------------------------------
# A. collaboration network
# ----------------------------------------------------------------------------------------

def build_network(p, inst, min_papers=None):
    """Weighted co-authorship network between EU institutions with enough papers."""
    min_papers = C.MIN_PAPERS_NETWORK if min_papers is None else min_papers
    keep = set(inst.index[inst["papers"] >= min_papers])
    n_inst = p.groupby("work_id").size()                       # all institutions, EU or not
    weights = {}
    for work_id, g in p[p["institution_id"].isin(keep)].groupby("work_id"):
        ids = sorted(g["institution_id"])
        if len(ids) < 2:
            continue
        w = 1.0 / (n_inst[work_id] - 1)
        for a, b in combinations(ids, 2):
            weights[(a, b)] = weights.get((a, b), 0.0) + w
    # nodes and edges are added in sorted order: Louvain's result depends on node order, and
    # Python randomises the order of sets of strings between runs (hash seed)
    G = nx.Graph()
    G.add_nodes_from(sorted(keep))
    G.add_weighted_edges_from((a, b, w) for (a, b), w in sorted(weights.items()))
    lcc = max(nx.connected_components(G), key=len)
    info = {
        "nodes_eligible": len(keep),
        "edges": G.number_of_edges(),
        "isolated_nodes": nx.number_of_isolates(G),
        "lcc_nodes": len(lcc),
        "lcc_share": round(len(lcc) / len(keep), 3),
    }
    H = nx.Graph()
    H.add_nodes_from(n for n in G.nodes if n in lcc)
    H.add_weighted_edges_from((a, b, d["weight"]) for a, b, d in G.edges(data=True) if a in lcc)
    return H, info


def run_louvain(G, resolution=None, n_seeds=None):
    # networkx's Louvain iterates over Python sets internally; with string node names their
    # order (and so the result) changes between runs. Integer node names make it reproducible.
    nodes = sorted(G.nodes)
    to_int = {n: i for i, n in enumerate(nodes)}
    Gi = nx.relabel_nodes(G, to_int)
    runs = []
    resolution = C.LOUVAIN_RESOLUTION if resolution is None else resolution
    for s in range(n_seeds or C.LOUVAIN_SEEDS):
        comms = nx.community.louvain_communities(Gi, weight="weight",
                                                 resolution=resolution, seed=s)
        q = nx.community.modularity(Gi, comms, weight="weight")
        runs.append((q, [{nodes[i] for i in c} for c in comms]))

    def labels(comms):
        lab = {n: i for i, c in enumerate(comms) for n in c}
        return [lab[n] for n in nodes]

    best_q, best = max(runs, key=lambda r: r[0])
    best_lab = labels(best)
    aris = [adjusted_rand_score(best_lab, labels(c)) for _, c in runs]
    # relabel communities by size: 0 = largest
    best = sorted(best, key=lambda c: (-len(c), min(c)))
    membership = pd.Series({n: i for i, c in enumerate(best) for n in c}, name="community")
    stats = {
        "modularity_best": round(best_q, 3),
        "modularity_min_over_seeds": round(min(q for q, _ in runs), 3),
        "n_communities": len(best),
        "n_communities_size_ge_min": sum(len(c) >= C.MIN_COMMUNITY_SIZE for c in best),
        "stability_mean_ari_vs_best": round(float(np.mean(aris)), 3),
        "stability_min_ari_vs_best": round(float(np.min(aris)), 3),
    }
    return membership, stats


def within_country_weight(G, country):
    tot = inside = 0.0
    for a, b, d in G.edges(data=True):
        tot += d["weight"]
        if country[a] == country[b]:
            inside += d["weight"]
    return inside / tot


def compare_with_country(labels, country, rng, G=None):
    """NMI / ARI between a partition and country, with a permutation null for country."""
    labels = np.asarray(labels)
    country = np.asarray(country)
    nmi = normalized_mutual_info_score(country, labels)
    ari = adjusted_rand_score(country, labels)
    null_nmi, null_ari = [], []
    for _ in range(C.N_PERMUTATIONS):
        perm = rng.permutation(country)
        null_nmi.append(normalized_mutual_info_score(perm, labels))
        null_ari.append(adjusted_rand_score(perm, labels))
    out = {
        "nmi_with_country": round(nmi, 3),
        "nmi_null_mean": round(float(np.mean(null_nmi)), 3),
        "nmi_null_p95": round(float(np.percentile(null_nmi, 95)), 3),
        "ari_with_country": round(ari, 3),
        "ari_null_p95": round(float(np.percentile(null_ari, 95)), 3),
        "p_value_nmi": round((1 + sum(x >= nmi for x in null_nmi)) / (1 + C.N_PERMUTATIONS), 4),
    }
    return out


def network_country_tests(G, membership, inst, rng):
    nodes = sorted(G.nodes)
    country = inst.loc[nodes, "country"]
    out = compare_with_country(membership.loc[nodes].values, country.values, rng)

    # modularity of the partition "one community per country": how well country alone
    # explains the network, on the same scale as Louvain's modularity
    by_country = [set(g.index) for _, g in country.groupby(country)]
    out["modularity_country_partition"] = round(
        nx.community.modularity(G, by_country, weight="weight"), 3)

    cmap = country.to_dict()
    obs = within_country_weight(G, cmap)
    null = []
    for _ in range(C.N_PERMUTATIONS):
        perm = dict(zip(nodes, rng.permutation(country.values)))
        null.append(within_country_weight(G, perm))
    out["within_country_weight_share"] = round(obs, 3)
    out["within_country_weight_share_null_mean"] = round(float(np.mean(null)), 3)

    # how "national" is each community: share of its institutions from its main country
    df = pd.DataFrame({"community": membership.loc[nodes].values, "country": country.values})
    big = df.groupby("community").filter(lambda g: len(g) >= C.MIN_COMMUNITY_SIZE)
    main_share = big.groupby("community")["country"].agg(lambda s: s.value_counts(normalize=True).iloc[0])
    out["communities_main_country_share_median"] = round(float(main_share.median()), 3)
    out["communities_over_80pct_one_country"] = int((main_share >= 0.8).sum())
    out["communities_counted"] = int(len(main_share))
    return out


def counts(series):
    """value_counts with ties broken alphabetically, so tables are identical between runs."""
    return series.value_counts().sort_index().sort_values(ascending=False, kind="stable")


def topic_lift(work_ids, w, min_papers=10, top=3):
    """Topics over-represented in a set of papers compared with the whole layer."""
    sub = w[w["work_id"].isin(work_ids)]["topic"].value_counts()
    base = w["topic"].value_counts(normalize=True)
    lift = (sub / sub.sum()) / base.reindex(sub.index)
    lift = lift[sub >= min_papers].sort_values(ascending=False)
    return "; ".join(f"{t} (x{l:.1f}, n={sub[t]})" for t, l in lift.head(top).items())


def community_profiles(G, membership, inst, w, p):
    rows = []
    strength = dict(G.degree(weight="weight"))
    for c, members in membership.groupby(membership):
        ids = sorted(members.index)
        sub = inst.loc[ids]
        countries = counts(sub["country"])
        top_inst = (sub.assign(strength=[strength[i] for i in ids])
                       .sort_values(["papers", "name"], ascending=[False, True]).head(5))
        papers = p[p["institution_id"].isin(ids)]["work_id"].unique()
        rows.append({
            "community": c,
            "institutions": len(ids),
            "papers": len(papers),
            "main_country": countries.index[0],
            "main_country_share": round(countries.iloc[0] / len(ids), 2),
            "countries": "; ".join(f"{k} {v}" for k, v in countries.head(4).items()),
            "n_countries": len(countries),
            "top_institutions": "; ".join(f"{n} ({k})" for n, k in
                                          zip(top_inst["name"], top_inst["papers"])),
            "over_represented_topics": topic_lift(papers, w),
        })
    return pd.DataFrame(rows)


def network_sensitivity(p, inst, layer):
    """Does the 'communities = countries' result depend on the two free choices
    (minimum papers per institution, Louvain resolution)?"""
    rows = []
    for min_papers in C.SENS_MIN_PAPERS:
        G, info = build_network(p, inst, min_papers)
        nodes = sorted(G.nodes)
        country = inst.loc[nodes, "country"]
        by_country = [set(g.index) for _, g in country.groupby(country)]
        q_country = nx.community.modularity(G, by_country, weight="weight")
        for res in C.SENS_RESOLUTIONS:
            memb, st = run_louvain(G, resolution=res, n_seeds=5)
            rows.append({
                "layer": layer, "min_papers": min_papers, "resolution": res,
                "nodes": info["lcc_nodes"], "communities": st["n_communities"],
                "modularity": st["modularity_best"],
                "modularity_country_partition": round(q_country, 3),
                "nmi_with_country": round(normalized_mutual_info_score(country, memb.loc[nodes]), 3),
                "ari_with_country": round(adjusted_rand_score(country, memb.loc[nodes]), 3),
            })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------------------
# B. topic profiles
# ----------------------------------------------------------------------------------------

def topic_matrix(w, p, inst):
    keep = inst.index[inst["papers"] >= C.MIN_PAPERS_TOPIC]
    counts = w["topic"].fillna("No topic").value_counts()
    vocab = set(counts.index[counts >= C.MIN_TOPIC_PAPERS])
    topic = w.set_index("work_id")["topic"].fillna("No topic")
    topic = topic.where(topic.isin(vocab), "Other topics")
    eu = p[p["institution_id"].isin(keep)][["work_id", "institution_id"]]
    eu = eu.assign(topic=eu["work_id"].map(topic))
    shares = pd.crosstab(eu["institution_id"], eu["topic"], normalize="index")
    return shares, eu


def null_shares(long, columns, rng):
    """Null model: shuffle the topic of each paper (all institutions of a paper keep sharing
    one topic). Institution sizes, co-authorships and topic popularity stay the same; only
    the link between an institution and what it works on is broken."""
    papers = long["work_id"].unique()
    topic_of = long.drop_duplicates("work_id").set_index("work_id")["topic"]
    shuffled = pd.Series(rng.permutation(topic_of.loc[papers].values), index=papers)
    t = long["work_id"].map(shuffled)
    return (pd.crosstab(long["institution_id"], t, normalize="index")
              .reindex(columns=columns, fill_value=0.0))


def cluster_topics(shares, long, rng):
    H = np.sqrt(shares.values)                      # Hellinger: Euclidean on sqrt(shares)
    rows = []
    fits = {}
    for k in C.K_RANGE:
        km = KMeans(n_clusters=k, random_state=C.SEED, n_init=10).fit(H)
        sil = silhouette_score(H, km.labels_)
        null_sil = []
        for _ in range(20):
            Hn = np.sqrt(null_shares(long, shares.columns, rng).loc[shares.index].values)
            null_sil.append(silhouette_score(Hn, KMeans(n_clusters=k, random_state=C.SEED,
                                                        n_init=10).fit_predict(Hn)))
        ward = AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(H)
        seeds = [KMeans(n_clusters=k, random_state=s, n_init=1).fit_predict(H)
                 for s in range(C.KMEANS_SEEDS)]
        stab = np.mean([adjusted_rand_score(km.labels_, s) for s in seeds])
        sizes = np.bincount(km.labels_)
        rows.append({
            "k": k, "silhouette": round(sil, 3),
            "silhouette_null_mean": round(float(np.mean(null_sil)), 3),
            "silhouette_null_max": round(float(np.max(null_sil)), 3),
            "inertia": round(km.inertia_, 2),
            "ari_kmeans_vs_ward": round(adjusted_rand_score(km.labels_, ward), 3),
            "stability_ari_seeds": round(float(stab), 3),
            "smallest_cluster": int(sizes.min()),
        })
        fits[k] = km.labels_
    sel = pd.DataFrame(rows)
    # choose k: highest silhouette among k whose silhouette beats every null run and whose
    # smallest cluster has >= 5 institutions (a 2-institution cluster is an outlier, not a group)
    ok = sel[(sel["silhouette"] > sel["silhouette_null_max"]) & (sel["smallest_cluster"] >= 5)]
    best_k = int((ok if len(ok) else sel).sort_values("silhouette", ascending=False)["k"].iloc[0])
    return sel, best_k, fits[best_k], H


def topic_cluster_profiles(shares, labels, inst):
    df = shares.copy()
    df["cluster"] = labels
    mean = df.groupby("cluster").mean()
    overall = shares.mean()
    rows = []
    for c in mean.index:
        members = df.index[df["cluster"] == c]
        sub = inst.loc[members]
        # distinctive = largest gain in share over the average institution (percentage points);
        # a ratio would rank tiny topics first (0.4% vs 0.1% is "x4")
        gain = (mean.loc[c] - overall).drop(["Other topics", "No topic"], errors="ignore")
        top = gain.sort_values(ascending=False).head(3)
        countries = counts(sub["country"])
        rows.append({
            "cluster": c,
            "institutions": len(members),
            "share_AIEd_topic": round(mean.loc[c].get("Artificial Intelligence in Education", 0), 2),
            "distinctive_topics": "; ".join(f"{t} ({mean.loc[c, t]:.0%} vs {overall[t]:.0%})"
                                            for t in top.index),
            "countries": "; ".join(f"{k} {v}" for k, v in countries.head(4).items()),
            "main_country_share": round(countries.iloc[0] / len(members), 2),
            "example_institutions": "; ".join(sub.sort_values(["papers", "name"],
                                                              ascending=[False, True])
                                              ["name"].head(4)),
        })
    return pd.DataFrame(rows), mean


# ----------------------------------------------------------------------------------------
# figures
# ----------------------------------------------------------------------------------------

def community_colors(membership, n_colored=8):
    order = membership.value_counts().index[:n_colored]
    cmap = {c: CATEGORICAL[i] for i, c in enumerate(order)}
    return [cmap.get(c, OTHER_GREY) for c in membership], order


def fig_network(G, membership, inst, layer, path):
    rng_layout = np.random.default_rng(C.SEED)
    pos = nx.spring_layout(G, weight="weight", seed=C.SEED, k=0.15, iterations=200)
    nodes = list(G.nodes)
    colors, order = community_colors(membership.loc[nodes])
    sizes = 6 + 40 * np.sqrt(inst.loc[nodes, "papers"].values / inst["papers"].max())
    fig, ax = plt.subplots(figsize=(9, 8))
    strong = [(a, b) for a, b, d in G.edges(data=True) if d["weight"] >= 1.0]
    nx.draw_networkx_edges(G, pos, edgelist=strong, ax=ax, width=0.4, alpha=0.25,
                           edge_color=INK_MUTED)
    xy = np.array([pos[n] for n in nodes])
    ax.scatter(xy[:, 0], xy[:, 1], s=sizes, c=colors, edgecolors=SURFACE, linewidths=0.6, zorder=3)
    handles = []
    for i, c in enumerate(order):
        sub = inst.loc[membership.index[membership == c], "country"].value_counts()
        ids = membership.index[membership == c]
        lead = inst.loc[ids].sort_values(["papers", "name"], ascending=[False, True])["name"].iloc[0]
        lab = (f"C{c}: {len(ids)} inst., {sub.index[0]} {sub.iloc[0] / sub.sum():.0%}"
               f"  (largest: {lead[:34]})")
        handles.append(plt.Line2D([], [], marker="o", ls="", color=CATEGORICAL[i], label=lab))
    handles.append(plt.Line2D([], [], marker="o", ls="", color=OTHER_GREY, label="smaller communities"))
    ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=7.5, frameon=False,
              title="Community: size, main country (largest institution)", title_fontsize=8)
    ax.set_title(f"Collaboration communities of EU institutions ({layer}, Louvain)")
    ax.set_axis_off()
    fig.text(0.01, 0.01, f"Nodes: EU institutions with >= {C.MIN_PAPERS_NETWORK} papers, "
             f"largest connected component. Edges shown: weight >= 1 (fractional counting).",
             fontsize=7, color=INK_SECONDARY)
    fig.savefig(path)
    plt.close(fig)


def fig_community_country(membership, inst, layer, path, n_comm=12, n_country=14):
    df = pd.DataFrame({"community": membership.values,
                       "country": inst.loc[membership.index, "country"].values})
    top_c = df["community"].value_counts().index[:n_comm]
    top_k = df["country"].value_counts().index[:n_country]
    tab = pd.crosstab(df["community"], df["country"]).loc[top_c]
    other = tab.drop(columns=top_k).sum(axis=1)
    tab = tab[top_k]
    tab["other"] = other
    share = tab.div(tab.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(9, 5.5))
    im = ax.imshow(share.values, cmap=SEQ_BLUE, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(share.shape[1]), share.columns)
    ax.set_yticks(range(share.shape[0]), [f"C{c} (n={tab.loc[c].sum()})" for c in share.index])
    ax.grid(False)
    for i in range(share.shape[0]):
        for j in range(share.shape[1]):
            v = share.values[i, j]
            if v >= 0.15:
                ax.text(j, i, f"{v:.0%}", ha="center", va="center", fontsize=7,
                        color="white" if v > 0.5 else INK_PRIMARY)
    cb = fig.colorbar(im, ax=ax, fraction=0.03)
    cb.set_label("Share of the community's institutions", color=INK_SECONDARY)
    ax.set_title(f"Who is in each collaboration community? ({layer})")
    ax.set_xlabel("Country of institution")
    fig.savefig(path)
    plt.close(fig)


def fig_silhouette(sel, best_k, layer, path):
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.plot(sel["k"], sel["silhouette"], "o-", color=CATEGORICAL[0], lw=2, ms=6,
            label="Real topic profiles")
    ax.plot(sel["k"], sel["silhouette_null_max"], "s--", color=CATEGORICAL[1], lw=2, ms=6,
            label="Paper topics shuffled (null, max of 20 runs)")
    ax.axvline(best_k, color=INK_MUTED, lw=1, ls=":")
    ax.annotate(f"chosen k = {best_k}", (best_k, ax.get_ylim()[1]), fontsize=8,
                color=INK_SECONDARY, xytext=(4, -12), textcoords="offset points")
    ax.set_xlabel("Number of clusters k")
    ax.set_ylabel("Silhouette score")
    ax.set_title(f"Topic clusters: choosing k ({layer})")
    ax.legend(frameon=False, fontsize=8)
    fig.savefig(path)
    plt.close(fig)


def fig_topic_profiles(mean, labels, layer, path, n_topics=14):
    overall = mean.mean()
    cols = (mean.max() - mean.min()).drop(["Other topics", "No topic"], errors="ignore")
    cols = cols.sort_values(ascending=False).index[:n_topics]
    m = mean[cols]
    counts = pd.Series(labels).value_counts()
    fig, ax = plt.subplots(figsize=(10, 0.6 * len(m) + 3))
    vmax = m.values.max()
    im = ax.imshow(m.values, cmap=SEQ_BLUE, vmin=0, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(cols)), [c[:52] for c in cols], rotation=55, ha="right", fontsize=7.5)
    ax.set_yticks(range(len(m)), [f"T{c} (n={counts[c]})" for c in m.index])
    ax.grid(False)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = m.values[i, j]
            if v >= 0.08:
                ax.text(j, i, f"{v:.0%}", ha="center", va="center", fontsize=7,
                        color="white" if v > 0.55 * vmax else INK_PRIMARY)
    cb = fig.colorbar(im, ax=ax, fraction=0.025)
    cb.set_label("Mean share of the institution's papers", color=INK_SECONDARY)
    ax.set_title(f"Topic clusters of EU institutions: mean topic shares ({layer})")
    fig.savefig(path)
    plt.close(fig)


def fig_topic_pca(H, labels, layer, path):
    pca = PCA(n_components=2, random_state=C.SEED).fit(H)
    xy = pca.transform(H)
    fig, ax = plt.subplots(figsize=(6.5, 5))
    for c in sorted(set(labels)):
        m = labels == c
        ax.scatter(xy[m, 0], xy[m, 1], s=18, color=CATEGORICAL[c % 8], edgecolors=SURFACE,
                   linewidths=0.5, label=f"T{c}")
    ev = pca.explained_variance_ratio_
    ax.set_xlabel(f"PC1 ({ev[0]:.0%} of variance)")
    ax.set_ylabel(f"PC2 ({ev[1]:.0%} of variance)")
    ax.set_title(f"Topic clusters, 2-D view for display only ({layer})")
    ax.legend(frameon=False, fontsize=8, title="Cluster", title_fontsize=8)
    fig.savefig(path)
    plt.close(fig)


def fig_country_summary(summary, path):
    """Observed NMI with country vs the permutation null, for each clustering and layer."""
    rows = []
    for layer in C.LAYERS:
        s = summary[layer]
        rows.append((f"Collaboration\n{layer}", s["network_vs_country"]["nmi_with_country"],
                     s["network_vs_country"]["nmi_null_p95"]))
        rows.append((f"Topic\n{layer}", s["topic_vs_country"]["nmi_with_country"],
                     s["topic_vs_country"]["nmi_null_p95"]))
    lab, obs, null = zip(*rows)
    x = np.arange(len(lab))
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(x - 0.18, obs, 0.34, color=CATEGORICAL[0], label="Observed")
    ax.bar(x + 0.18, null, 0.34, color=CATEGORICAL[1], label="Null (countries shuffled), 95th pct.")
    for i, v in enumerate(obs):
        ax.text(i - 0.18, v + 0.01, f"{v:.2f}", ha="center", fontsize=8, color=INK_PRIMARY)
    ax.set_xticks(x, lab)
    ax.set_ylim(0, 1)
    ax.set_ylabel("NMI between cluster and country")
    ax.set_title("How much of each clustering is just country?")
    ax.legend(frameon=False, fontsize=8)
    fig.savefig(path)
    plt.close(fig)


# ----------------------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------------------

def run_layer(works, pi, layer, rng):
    print(f"\n=== {layer} ===")
    w, p = layer_data(works, pi, layer)
    inst = institution_table(p)
    tag = layer.lower()
    out = {"papers": len(w), "eu_institutions": len(inst)}

    # A. collaboration communities
    G, net_info = build_network(p, inst)
    membership, louv = run_louvain(G)
    out["network"] = {**net_info, **louv}
    out["network_vs_country"] = network_country_tests(G, membership, inst, rng)
    prof = community_profiles(G, membership, inst, w, p)
    prof.to_csv(C.TAB_DIR / f"communities_{tag}.csv", index=False)
    sens = network_sensitivity(p, inst, layer)
    sens.to_csv(C.TAB_DIR / f"network_sensitivity_{tag}.csv", index=False)
    out["network_sensitivity_nmi_range"] = [float(sens["nmi_with_country"].min()),
                                            float(sens["nmi_with_country"].max())]
    print(json.dumps(out["network"], indent=1))
    print(json.dumps(out["network_vs_country"], indent=1))

    # B. topic clusters
    shares, long = topic_matrix(w, p, inst)
    sel, best_k, labels, H = cluster_topics(shares, long, rng)
    sel.to_csv(C.TAB_DIR / f"topic_k_selection_{tag}.csv", index=False)
    tprof, mean = topic_cluster_profiles(shares, labels, inst)
    tprof.to_csv(C.TAB_DIR / f"topic_clusters_{tag}.csv", index=False)
    row = sel[sel["k"] == best_k].iloc[0]
    out["topic"] = {
        "institutions": int(len(shares)),
        "topic_columns": int(shares.shape[1]),
        "k_chosen": best_k,
        "silhouette": float(row["silhouette"]),
        "silhouette_null_max": float(row["silhouette_null_max"]),
        "ari_kmeans_vs_ward": float(row["ari_kmeans_vs_ward"]),
        "stability_ari_seeds": float(row["stability_ari_seeds"]),
    }
    out["topic_vs_country"] = compare_with_country(labels, inst.loc[shares.index, "country"].values, rng)
    print(sel.to_string(index=False))

    # A vs B on the institutions that are in both
    t_lab = pd.Series(labels, index=shares.index)
    common = t_lab.index.intersection(membership.index)
    out["topic_vs_collaboration"] = {
        "institutions_in_both": int(len(common)),
        "nmi": round(normalized_mutual_info_score(membership.loc[common], t_lab.loc[common]), 3),
        "ari": round(adjusted_rand_score(membership.loc[common], t_lab.loc[common]), 3),
    }

    # assignments, one row per EU institution
    assign = inst.copy()
    assign["collab_community"] = membership.reindex(assign.index)
    assign["topic_cluster"] = t_lab.reindex(assign.index)
    assign = assign[assign["collab_community"].notna() | assign["topic_cluster"].notna()]
    assign.sort_values("papers", ascending=False).to_csv(
        C.TAB_DIR / f"institution_assignments_{tag}.csv")

    # figures
    fig_network(G, membership, inst, layer, C.FIG_DIR / f"c1_network_{tag}.png")
    fig_community_country(membership, inst, layer, C.FIG_DIR / f"c2_community_country_{tag}.png")
    fig_silhouette(sel, best_k, layer, C.FIG_DIR / f"c3_topic_k_selection_{tag}.png")
    fig_topic_profiles(mean, labels, layer, C.FIG_DIR / f"c4_topic_profiles_{tag}.png")
    fig_topic_pca(H, labels, layer, C.FIG_DIR / f"c5_topic_pca_{tag}.png")
    return out, membership, t_lab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None, help="folder with works_layers.csv and authorships_layers.csv")
    args = ap.parse_args()
    data_dir = C.Path(args.data) if args.data else C.DATA_DIR
    for d in (C.FIG_DIR, C.TAB_DIR):
        d.mkdir(parents=True, exist_ok=True)
    apply_style()
    rng = np.random.default_rng(C.SEED)

    works, pi = load(data_dir)
    summary, memb, tlab = {}, {}, {}
    for layer in C.LAYERS:
        summary[layer], memb[layer], tlab[layer] = run_layer(works, pi, layer, rng)

    # ALL vs STRICT: are they the same clusterings?
    common = memb["ALL"].index.intersection(memb["STRICT"].index)
    common_t = tlab["ALL"].index.intersection(tlab["STRICT"].index)
    summary["ALL_vs_STRICT"] = {
        "collaboration_institutions_in_both": int(len(common)),
        "collaboration_ari": round(adjusted_rand_score(memb["ALL"].loc[common], memb["STRICT"].loc[common]), 3),
        "collaboration_nmi": round(normalized_mutual_info_score(memb["ALL"].loc[common], memb["STRICT"].loc[common]), 3),
        "topic_institutions_in_both": int(len(common_t)),
        "topic_ari": round(adjusted_rand_score(tlab["ALL"].loc[common_t], tlab["STRICT"].loc[common_t]), 3),
        "topic_nmi": round(normalized_mutual_info_score(tlab["ALL"].loc[common_t], tlab["STRICT"].loc[common_t]), 3),
    }
    summary["settings"] = {k: (list(v) if isinstance(v, range) else v) for k, v in vars(C).items()
                           if k.isupper() and k != "ROOT" and not k.endswith(("_DIR", "_FILE"))}
    fig_country_summary(summary, C.FIG_DIR / "c6_nmi_with_country.png")
    (C.OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print("\nALL vs STRICT:", json.dumps(summary["ALL_vs_STRICT"], indent=1))
    print(f"\nDone. Outputs in {C.OUT_DIR}")


if __name__ == "__main__":
    main()
