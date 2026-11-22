"""
Clean the flattened OpenAlex tables: one row per real paper, one row per real authorship.

Usage (from the project root, after src/collect.py):
    python src/clean.py

Steps, in order (each one is counted in data/processed/cleaning_log.json):
  1. drop exact duplicate authorship rows (OpenAlex sometimes lists the same author twice);
  2. normalise DOI and ISSN so they can be compared and joined (SCImago / Scopus);
  3. merge versions of the same paper (preprint + published version, v1/v2, repository copies):
     two records are the same paper if they share a DOI, or if they have the same title
     (>= 30 characters, so "Editorial" or "Preface" never match) AND at least one author;
  4. keep research document types only;
  5. apply the stricter relevance rule from src/refine.py (validated in notebook 02).

Outputs (data/processed/):
    works_clean.csv          analysis corpus, one row per paper
    authorships_clean.csv    authorships of those papers
    duplicates_removed.csv   every merged record and the record it was merged into
    cleaning_log.json        row counts after each step
"""

import json
import re
from pathlib import Path

import pandas as pd

from collect import EU27
from refine import is_relevant

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

# document types that report research; editorials, errata, paratext, abstracts etc. are dropped
RESEARCH_TYPES = ["article", "conference-paper", "review", "book-chapter", "preprint"]

# OpenAlex "sources" that are repositories, not peer-reviewed venues
REPOSITORY_SOURCES = ["arXiv", "SSRN", "HAL", "Zenodo", "Research Square", "medRxiv", "bioRxiv",
                      "OSF Preprints", "EdArXiv", "PsyArXiv", "Preprints.org", "TechRxiv"]
REPOSITORY_RE = re.compile("|".join(re.escape(s) for s in REPOSITORY_SOURCES) + r"|repositor",
                           re.I)

# when versions are merged, the published one is kept: lower rank wins
TYPE_RANK = {"article": 0, "review": 0, "conference-paper": 1, "book-chapter": 2, "preprint": 3}

MIN_TITLE_LEN = 30


def norm_doi(doi):
    if not isinstance(doi, str):
        return None
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip().lower()) or None


def norm_issn(issn):
    """'12345678', '1234-5678' and '1234-567x' all become '1234-567X'."""
    s = re.sub(r"[^0-9Xx]", "", str(issn)).upper()
    return f"{s[:4]}-{s[4:]}" if len(s) == 8 else None


def norm_issn_list(issns):
    if not isinstance(issns, str):
        return None
    out = sorted({i for i in map(norm_issn, issns.split("|")) if i})
    return "|".join(out) or None


def norm_title(title):
    t = re.sub(r"\W", "", str(title).lower())
    return t if len(t) >= MIN_TITLE_LEN else None


def is_repository(source_name, work_type):
    return work_type == "preprint" or bool(REPOSITORY_RE.search(str(source_name or "")))


def find_versions(works, auths):
    """Group records that are versions of the same paper (union-find on DOI and title+author)."""
    parent = {w: w for w in works["work_id"]}

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(ids):
        ids = list(ids)
        for other in ids[1:]:
            parent[root(other)] = root(ids[0])

    # same DOI
    for _, g in works.dropna(subset=["doi_norm"]).groupby("doi_norm"):
        if len(g) > 1:
            union(g["work_id"])

    # same title and at least one shared author
    authors = auths.dropna(subset=["author_id"]).groupby("work_id")["author_id"].agg(set)
    for _, g in works.dropna(subset=["title_norm"]).groupby("title_norm"):
        ids = list(g["work_id"])
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if authors.get(a, set()) & authors.get(b, set()):
                    union([a, b])

    return works["work_id"].map(root)


def pick_kept(group):
    """The version we keep: published type, real venue, has ISSN, has abstract, most cited."""
    order = group.assign(
        _type=group["type"].map(TYPE_RANK).fillna(9),
        _repo=group["is_repository"].astype(int),
        _no_issn=group["issn_l"].isna().astype(int),
        _no_abs=group["abstract"].isna().astype(int),
        _cites=-group["cited_by_count"],
    ).sort_values(["_type", "_repo", "_no_issn", "_no_abs", "_cites", "work_id"])
    return order.index[0]


def clean(works, auths):
    log = {"works_downloaded": len(works), "authorship_rows_downloaded": len(auths)}

    # 1. exact duplicate authorship rows
    auths = auths.drop_duplicates().copy()
    log["authorship_rows_after_exact_dedup"] = len(auths)

    # 2. normalised keys
    works = works.copy()
    works["doi_norm"] = works["doi"].map(norm_doi)
    works["issn_l"] = works["issn_l"].map(lambda x: norm_issn(x) if isinstance(x, str) else None)
    works["issn"] = works["issn"].map(norm_issn_list)
    works["title_norm"] = works["title"].map(norm_title)
    works["is_repository"] = [is_repository(s, t) for s, t in zip(works["source_name"], works["type"])]

    # 3. merge versions of the same paper
    works["version_group"] = find_versions(works, auths)
    kept_idx, removed = [], []
    for gid, g in works.groupby("version_group"):
        k = pick_kept(g) if len(g) > 1 else g.index[0]
        kept_idx.append(k)
        for i in g.index.drop(k):
            removed.append({
                "removed_work_id": works.at[i, "work_id"], "removed_type": works.at[i, "type"],
                "removed_source": works.at[i, "source_name"],
                "kept_work_id": works.at[k, "work_id"], "kept_type": works.at[k, "type"],
                "kept_source": works.at[k, "source_name"], "title": works.at[k, "title"],
                "reason": "same DOI" if works.at[i, "doi_norm"] and
                          works.at[i, "doi_norm"] == works.at[k, "doi_norm"] else "same title + author",
            })
        # a published version without abstract borrows it from its preprint
        if pd.isna(works.at[k, "abstract"]):
            abstracts = g["abstract"].dropna()
            if len(abstracts):
                works.at[k, "abstract"] = abstracts.iloc[0]
    works["n_versions"] = works["version_group"].map(works["version_group"].value_counts())
    works = works.loc[sorted(kept_idx)]
    log["works_after_version_merge"] = len(works)

    # 4. research document types
    works = works[works["type"].isin(RESEARCH_TYPES)]
    log["works_after_type_filter"] = len(works)

    # 5. relevance rule
    relevant = [is_relevant(str(t), a if isinstance(a, str) else "")
                for t, a in zip(works["title"], works["abstract"])]
    works = works[relevant].drop(columns=["title_norm", "version_group"]).reset_index(drop=True)
    log["works_after_relevance_rule"] = len(works)

    auths = auths[auths["work_id"].isin(works["work_id"])].reset_index(drop=True)
    auths["is_eu"] = auths["institution_country"].isin(EU27)
    log["authorship_rows_final"] = len(auths)

    log["final_share_missing"] = {
        "abstract": round(works["abstract"].isna().mean(), 3),
        "issn": round(works["issn_l"].isna().mean(), 3),
        "doi": round(works["doi_norm"].isna().mean(), 3),
        "authorship_without_institution": round(auths["institution_id"].isna().mean(), 3),
    }
    return works, auths, pd.DataFrame(removed), log


def main():
    works = pd.read_csv(PROCESSED / "works.csv")
    auths = pd.read_csv(PROCESSED / "authorships.csv")
    works, auths, removed, log = clean(works, auths)

    works.to_csv(PROCESSED / "works_clean.csv", index=False)
    auths.to_csv(PROCESSED / "authorships_clean.csv", index=False)
    removed.to_csv(PROCESSED / "duplicates_removed.csv", index=False)
    (PROCESSED / "cleaning_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
