"""
Enrich the clean corpus with the Scopus Source List and SCImago, and build the ALL / STRICT layers.

Usage (from the project root, after src/clean.py):
    python src/enrich.py               # full run, writes every output below
    python src/enrich.py --stage issn  # only the ISSN match, prints the rates, writes nothing

Inputs (never edited by this script):
    data/processed/works_clean.csv, authorships_clean.csv      Person 1's clean corpus
    data/raw/manual/ext_list_Sep_2026.xlsx                     Scopus Source List (downloaded by hand)
    data/raw/manual/scimagojr_<year>.csv                       SCImago, one file per year, all subject areas
    data/raw/manual/manual_venue_matches.csv  (optional)       hand-checked venues:
                       source_id, in_scopus (yes/no/unsure), years (optional), checked_on, note, evidence

Matching, in order (a work keeps the first method that succeeds):
  1. issn_l            the work's linking ISSN is a print or e-ISSN of a Scopus source;
  2. issn              any other ISSN of the work is;
  3. title_main / title_serialconf / title_allconf
                       works WITHOUT any ISSN: the normalised venue name equals exactly one Scopus
                       title in the main list / serial conference list / conference proceedings list;
     title_*_issn_miss same exact hit for a venue that HAS an ISSN not found in Scopus: recorded, NOT
                       accepted (homonym risk);
  4. manual            a 'yes' in manual_venue_matches.csv (overrides 3 and "none", never 1-2),
                       covered only in its `years` (empty = all years). 'no' and 'unsure' = not matched.
Fuzzy title matches are never accepted; they are written to title_fuzzy_candidates.csv for review.

Layers:
    in_strict            in Scopus AND the source was covered in the publication year (main rule)
    in_strict_active     in_strict, minus sources the list marks Inactive or discontinued
    in_strict_q12        in_strict AND SJR best quartile of the publication year is Q1 or Q2
    in_strict_issn_only  in_strict using ISSN matches only (sensitivity)
    in_strict_lag        in_strict, plus active sources covered the year before publication (indexing lag)

Outputs (data/processed/):
    works_layers.csv, authorships_layers.csv, match_report.json, unmatched_venues_top.csv,
    title_fuzzy_candidates.csv, title_match_sample.csv, no_source_sample.csv
"""

import argparse
import difflib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from clean import norm_issn  # same ISSN normalisation as Person 1 ('1234-567X')

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "raw" / "manual"

SCOPUS_XLSX = MANUAL / "ext_list_Sep_2026.xlsx"
SHEET_MAIN = "Scopus Sources Sep. 2026"
SHEET_DISCONTINUED = "Discontinued Titles Sep. 2026"
SHEET_SERIAL_CONF = "Serial Conf. Proc. with Profile"
SHEET_ALL_CONF = "All Conf. Proceedings Jun. 2026"
SCIMAGO_FILE = "scimagojr_{year}.csv"
MANUAL_MATCHES = MANUAL / "manual_venue_matches.csv"

N_WORKS, N_AUTHORSHIPS = 10208, 50726   # Person 1's final counts (cleaning_log.json)
TOP_UNMATCHED = 50
FUZZY_MIN_SCORE = 0.80
FUZZY_TOP_K = 3
SEED = 42                                           # fixed seed for the hand-check samples
FIE_SOURCE_ID = "https://openalex.org/S4363607793"  # IEEE Frontiers in Education, reported explicitly

# status values that the "active-only" sensitivity rule drops
NOT_ACTIVE = {"inactive", "discontinued"}

# words too common in venue names to say anything about which venue it is (fuzzy pre-filter only)
STOPWORDS = {"of", "the", "and", "on", "in", "for", "a", "an", "to", "at", "de", "la", "et",
             "international", "conference", "proceedings", "journal", "ieee", "acm", "annual",
             "symposium", "workshop", "series", "lecture", "notes", "advances", "research"}


# --------------------------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------------------------

def norm_title(s):
    """Venue name for EXACT comparison: accents removed, lower case, '&' -> 'and',
    every non-alphanumeric character -> space, spaces collapsed. Nothing else is removed,
    so 'ICALT 2020' and 'ICALT' stay different."""
    if not isinstance(s, str):
        return None
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def parse_coverage(cov):
    """'2026; 2023-2024' -> {2023, 2024, 2026}. Every token in the file is YYYY or YYYY-YYYY."""
    years = set()
    if not isinstance(cov, str):
        return years
    for tok in cov.split(";"):
        tok = tok.strip()
        m = re.fullmatch(r"(\d{4})(?:-(\d{4}))?", tok)
        if m:
            start = int(m.group(1))
            end = int(m.group(2) or start)
            years.update(range(start, end + 1))
        elif tok:
            print(f"  ! unparsed coverage token: {tok!r}")
    return years


def first_year(x):
    """Discontinuation 'Year' column has junk such as '2024q' or 'Unable to determine'."""
    m = re.match(r"\s*(\d{4})", str(x))
    return int(m.group(1)) if m else None


def to_bool(x):
    return str(x).strip().lower() in {"yes", "y", "true", "1"}


def rate(mask):
    return round(float(mask.mean()), 4) if len(mask) else None


# --------------------------------------------------------------------------------------------
# 1. Scopus Source List
# --------------------------------------------------------------------------------------------

def load_scopus():
    """Return
        sources : one row per Scopus source (main list + serial conference list)
                  scopus_id, scopus_title, sheet, status, discontinued_year, covered_years
        issn_map: one row per ISSN -> scopus_id
        conf    : conference proceedings volumes, one row per normalised Source Title,
                  with the set of years that have a volume
    """
    print("Reading Scopus Source List (this takes a minute)...")
    main = pd.read_excel(SCOPUS_XLSX, sheet_name=SHEET_MAIN, dtype=str)
    disc = pd.read_excel(SCOPUS_XLSX, sheet_name=SHEET_DISCONTINUED, header=1, dtype=str)
    serial = pd.read_excel(SCOPUS_XLSX, sheet_name=SHEET_SERIAL_CONF, dtype=str)
    allconf = pd.read_excel(SCOPUS_XLSX, sheet_name=SHEET_ALL_CONF, dtype=str,
                            usecols=["Source Title", "Year"])

    # --- main list: status = discontinued (flag column) / active / inactive
    main_src = pd.DataFrame({
        "scopus_id": main["Sourcerecord ID"].str.strip(),
        "scopus_title": main["Source Title"].str.strip(),
        "sheet": "main",
        "status": main["Active or Inactive"].str.strip().str.lower(),
        "covered_years": main["Coverage"].map(parse_coverage),
        "issn_print": main["ISSN"],
        "issn_e": main["EISSN"],
    })
    flagged = main["Titles Discontinued by Scopus"].fillna("").str.strip() != ""
    main_src.loc[flagged, "status"] = "discontinued"

    # discontinuation year from the dedicated sheet (latest year if a title is listed twice)
    disc_year = (disc.assign(y=disc["Year"].map(first_year))
                 .dropna(subset=["y"])
                 .groupby(disc["Sourcerecord ID"].str.strip())["y"].max())
    main_src["discontinued_year"] = main_src["scopus_id"].map(disc_year)

    # --- serial conference proceedings: no status column in the file
    serial_src = pd.DataFrame({
        "scopus_id": serial["Sourcerecord ID"].str.strip(),
        "scopus_title": serial["Source Title"].str.strip(),
        "sheet": "serial_conf",
        "status": "not_reported",
        "covered_years": serial["Coverage"].map(parse_coverage),
        "issn_print": serial["ISSN"],
        "issn_e": serial["EISSN"],
        "discontinued_year": None,
    })
    sources = pd.concat([main_src, serial_src], ignore_index=True)
    assert not sources["scopus_id"].duplicated().any(), "Sourcerecord ID repeated across sheets"

    # --- ISSN -> scopus_id (print and e-ISSN, normalised to 1234-567X)
    issn_map = pd.concat([
        sources[["scopus_id", "issn_print"]].rename(columns={"issn_print": "issn"}),
        sources[["scopus_id", "issn_e"]].rename(columns={"issn_e": "issn"}),
    ])
    issn_map["issn"] = issn_map["issn"].map(lambda x: norm_issn(x) if isinstance(x, str) else None)
    issn_map = issn_map.dropna(subset=["issn"]).drop_duplicates()
    shared = issn_map["issn"].duplicated(keep=False)
    if shared.any():
        # never seen in the Sep 2026 file; if it happens, the main list wins (it comes first)
        print(f"  ! {shared.sum()} ISSN rows shared by two Scopus IDs; keeping the first (main list)")
    issn_map = issn_map.drop_duplicates(subset=["issn"], keep="first").set_index("issn")["scopus_id"]

    # --- conference proceedings volumes: years with a volume, per Source Title
    allconf["norm"] = allconf["Source Title"].map(norm_title)
    allconf["Year"] = pd.to_numeric(allconf["Year"], errors="coerce")
    conf = (allconf.dropna(subset=["norm", "Year"])
            .groupby("norm")
            .agg(scopus_title=("Source Title", "first"),
                 covered_years=("Year", lambda s: set(int(y) for y in s))))

    print(f"  main list {len(main_src):,} | serial conf {len(serial_src):,} | "
          f"ISSNs {len(issn_map):,} | conference titles {len(conf):,}")
    return sources.drop(columns=["issn_print", "issn_e"]).set_index("scopus_id"), issn_map, conf


# --------------------------------------------------------------------------------------------
# 2. ISSN match
# --------------------------------------------------------------------------------------------

def match_issn(works, issn_map, sources):
    """Adds scopus_id and match_method ('issn_l', 'issn' or 'none'). Returns conflicts as a list.

    When a work's ISSNs point to SEVERAL Scopus sources, this is almost always a renamed journal:
    OpenAlex's issn_l is often the predecessor's ISSN (e.g. 'Palgrave Communications' for papers in
    'Humanities and Social Sciences Communications', 'Zeitschrift fur Neurologie' for 'Journal of
    Neurology'). We keep the source that covers the publication year; if several (or none) do,
    the issn_l one, then the first id. Every such case is logged."""
    ids, methods, conflicts = [], [], []
    for wid, issn_l, issn, year in zip(works["work_id"], works["issn_l"], works["issn"], works["year"]):
        tokens = issn.split("|") if isinstance(issn, str) else []
        id_l = issn_map.get(issn_l) if isinstance(issn_l, str) else None
        id_tok = sorted({issn_map[t] for t in tokens if t in issn_map})
        candidates = ([id_l] if id_l else []) + [i for i in id_tok if i != id_l]

        if not candidates:
            ids.append(None)
            methods.append("none")
            continue
        if len(candidates) == 1:
            keep, rule = candidates[0], None
        else:
            covering = [i for i in candidates if year in sources.at[i, "covered_years"]]
            if id_l in covering:
                keep, rule = id_l, "issn_l source covers the year"
            elif len(covering) >= 1:
                keep, rule = covering[0], "other source covers the year (renamed title)"
            else:
                keep, rule = candidates[0], "none covers the year: issn_l / first kept"
            conflicts.append({"work_id": wid, "year": int(year), "kept": keep,
                              "kept_title": sources.at[keep, "scopus_title"],
                              "others": [sources.at[i, "scopus_title"] for i in candidates if i != keep],
                              "rule": rule})
        ids.append(keep)
        methods.append("issn_l" if keep == id_l else "issn")
    works = works.copy()
    works["scopus_id"] = ids
    works["match_method"] = methods
    return works, conflicts


def add_scopus_fields(works, sources, conf):
    """scopus_title / status / discontinued year / covered-in-year for every matched work."""
    works = works.copy()
    titles, status, disc, covered = [], [], [], []
    if "manual_years" not in works:
        works["manual_years"] = None
        works["manual_evidence"] = None
    for sid, conf_key, method, year, m_years, m_evid in zip(
            works["scopus_id"], works["conf_key"], works["match_method"], works["year"],
            works["manual_years"], works["manual_evidence"]):
        if method == "manual":
            # a hand check: covered in the years listed in the manual file (empty = every year)
            titles.append(m_evid); status.append("manual_check"); disc.append(None)
            covered.append(True if not m_years else year in m_years)
        elif isinstance(sid, str):
            s = sources.loc[sid]
            titles.append(s["scopus_title"]); status.append(s["status"])
            disc.append(s["discontinued_year"]); covered.append(year in s["covered_years"])
        elif isinstance(conf_key, str):
            c = conf.loc[conf_key]
            titles.append(c["scopus_title"]); status.append("conf_proceedings")
            disc.append(None); covered.append(year in c["covered_years"])
        else:
            titles.append(None); status.append(None); disc.append(None); covered.append(False)
    works["scopus_title"] = titles
    works["scopus_status"] = status
    works["scopus_discontinued_year"] = pd.to_numeric(pd.Series(disc, index=works.index), errors="coerce")
    works["in_scopus"] = works["match_method"].map(is_accepted)
    # coverage and status only mean something for accepted matches; for a '_issn_miss' work the
    # rejected candidate's title stays visible in scopus_title, nothing else
    works["scopus_covered_in_year"] = pd.Series(covered, index=works.index) & works["in_scopus"]
    works.loc[~works["in_scopus"], ["scopus_status", "scopus_discontinued_year"]] = None
    return works


def covered_in(row, year, sources, conf):
    """Was this work's matched source covered by Scopus in `year`? (used for the lag variant)"""
    if row["match_method"] == "manual":
        return True if not row["manual_years"] else year in row["manual_years"]
    if isinstance(row["scopus_id"], str):
        return year in sources.at[row["scopus_id"], "covered_years"]
    if isinstance(row["conf_key"], str):
        return year in conf.at[row["conf_key"], "covered_years"]
    return False


# --------------------------------------------------------------------------------------------
# 3. Title fallback (exact only) and fuzzy candidates (never accepted)
# --------------------------------------------------------------------------------------------

def build_title_index(sources, conf):
    """normalised title -> list of candidates (sheet, scopus_id or conf key)."""
    index = defaultdict(list)
    for sid, row in sources.iterrows():
        key = norm_title(row["scopus_title"])
        if key:
            index[key].append((row["sheet"], sid))
    for key in conf.index:
        index[key].append(("all_conf", key))
    return index


def resolve_title(cands):
    """Exactly one serial source (main / serial_conf) -> that source.
    Only a conference-proceedings title -> that title.
    More than one serial source with this exact name -> ambiguous (None)."""
    serial_ids = sorted({c[1] for c in cands if c[0] != "all_conf"})
    conf_keys = [c[1] for c in cands if c[0] == "all_conf"]
    if len(serial_ids) == 1:
        return "serial", serial_ids[0]
    if len(serial_ids) > 1:
        return "ambiguous", serial_ids
    if conf_keys:
        return "conf", conf_keys[0]
    return None, None


TITLE_METHOD = {"main": "title_main", "serial_conf": "title_serialconf", "all_conf": "title_allconf"}
ISSN_MISS = "_issn_miss"


def match_title(works, title_index, sources):
    """Exact title fallback. match_method says which sheet matched:
    title_main / title_serialconf / title_allconf.

    Works WITHOUT any ISSN: the match is accepted (counts as in Scopus).
    Works WITH an ISSN that is not in Scopus: the exact hit is recorded with the suffix '_issn_miss'
    (e.g. 'title_main_issn_miss') but NOT accepted. The venue's own ISSN says it is a different
    serial; in this corpus these are homonyms such as a 'European Journal of Education' with another
    ISSN. A manual 'yes' can still promote them."""
    works = works.copy()
    works["conf_key"] = None
    works["venue_norm"] = works["source_name"].map(norm_title)
    no_issn = works["issn_l"].isna() & works["issn"].isna()
    ambiguous, issn_differs = {}, {}

    for i in works.index[(works["match_method"] == "none") & works["venue_norm"].notna()]:
        cands = title_index.get(works.at[i, "venue_norm"])
        if not cands:
            continue
        kind, target = resolve_title(cands)
        if kind == "ambiguous":
            ambiguous[works.at[i, "source_id"]] = (works.at[i, "source_name"], target)
            continue
        suffix = "" if no_issn[i] else ISSN_MISS
        if kind == "serial":
            works.at[i, "scopus_id"] = target
            method = TITLE_METHOD[sources.at[target, "sheet"]]
        else:  # kind == "conf"
            works.at[i, "conf_key"] = target
            method = TITLE_METHOD["all_conf"]
        works.at[i, "match_method"] = method + suffix
        if suffix:
            issn_differs[works.at[i, "source_id"]] = (works.at[i, "source_name"], kind, target)
    return works, ambiguous, issn_differs


def is_accepted(method):
    """True for match methods that count as 'in Scopus'."""
    return method != "none" and not method.endswith(ISSN_MISS)


def fuzzy_candidates(venues, sources, conf):
    """For each unmatched venue, the FUZZY_TOP_K closest Scopus titles with ratio >= FUZZY_MIN_SCORE.
    Pre-filter: candidates must share at least one informative word with the venue name."""
    pool = ([(norm_title(t), t, "main" if sh == "main" else "serial_conf", sid)
             for sid, t, sh in zip(sources.index, sources["scopus_title"], sources["sheet"])]
            + [(k, t, "all_conf", None) for k, t, yrs in
               zip(conf.index, conf["scopus_title"], conf["covered_years"]) if yrs & set(range(2019, 2027))])
    pool = [p for p in pool if p[0]]
    inverted = defaultdict(list)
    for j, (norm, *_rest) in enumerate(pool):
        for tok in set(norm.split()) - STOPWORDS:
            inverted[tok].append(j)

    rows = []
    for _, v in venues.iterrows():
        toks = set(v["venue_norm"].split()) - STOPWORDS
        shared = Counter(j for t in toks for j in inverted.get(t, []))
        scored = []
        for j, _n in shared.most_common(300):
            score = difflib.SequenceMatcher(None, v["venue_norm"], pool[j][0]).ratio()
            if score >= FUZZY_MIN_SCORE:
                scored.append((score, j))
        for score, j in sorted(scored, reverse=True)[:FUZZY_TOP_K]:
            rows.append({"source_id": v["source_id"], "source_name": v["source_name"],
                         "n_works": v["n_works"], "candidate_title": pool[j][1],
                         "candidate_sheet": pool[j][2], "scopus_id": pool[j][3],
                         "score": round(score, 3)})
    return pd.DataFrame(rows, columns=["source_id", "source_name", "n_works", "candidate_title",
                                       "candidate_sheet", "scopus_id", "score"])


# --------------------------------------------------------------------------------------------
# 4. Manual decisions
# --------------------------------------------------------------------------------------------

def parse_years(s):
    """'2021;2023-2025' -> {2021, 2023, 2024, 2025}; empty -> None (= every year)."""
    if not isinstance(s, str) or not s.strip():
        return None
    years = set()
    for tok in re.split(r"[;,]", s):
        tok = tok.strip()
        m = re.fullmatch(r"(\d{4})(?:\s*-\s*(\d{4}))?", tok)
        assert m, f"manual_venue_matches.csv: cannot read years token {tok!r}"
        years.update(range(int(m.group(1)), int(m.group(2) or m.group(1)) + 1))
    return years


def norm_decision(x):
    """yes / no / unsure. Anything that is not clearly yes or no is 'unsure' (= not matched)."""
    s = str(x).strip().lower()
    if s in {"yes", "y", "true", "1"}:
        return "yes"
    if s in {"no", "n", "false", "0"}:
        return "no"
    return "unsure"


def apply_manual(works):
    """Read manual_venue_matches.csv if it exists.
    Columns: source_id, in_scopus (yes / no / unsure), years (optional, '2021;2023-2025', empty = all),
    checked_on, note, evidence (optional).
      yes    -> 'manual' (overrides title_* , *_issn_miss and none); covered only in `years`
      no     -> 'none'   (also undoes a title match)
      unsure -> 'none'   (treated as not matched)
    ISSN matches are never overridden; conflicts are logged."""
    works = works.copy()
    works["manual_decision"] = None
    works["manual_years"] = None
    works["manual_evidence"] = None
    log = {"file_found": MANUAL_MATCHES.exists(), "rows": 0, "decisions": {}, "unknown_source_ids": [],
           "conflicts_with_issn_match": [], "title_match_overridden": []}
    if not MANUAL_MATCHES.exists():
        return works, log

    man = pd.read_csv(MANUAL_MATCHES, dtype=str)
    missing_cols = {"source_id", "in_scopus", "checked_on", "note"} - set(man.columns)
    assert not missing_cols, f"manual_venue_matches.csv is missing columns {missing_cols}"
    for optional in ["years", "evidence"]:
        if optional not in man:
            man[optional] = None
    man = man.dropna(subset=["source_id", "in_scopus"])
    man["source_id"] = man["source_id"].str.strip()
    assert not man["source_id"].duplicated().any(), "a source_id appears twice in manual_venue_matches.csv"
    man["decision"] = man["in_scopus"].map(norm_decision)
    log["rows"] = len(man)
    log["decisions"] = {k: int(v) for k, v in man["decision"].value_counts().items()}
    log["unknown_source_ids"] = sorted(set(man["source_id"]) - set(works["source_id"].dropna()))

    for _, m in man.iterrows():
        sid, decision = m["source_id"], m["decision"]
        rows = works.index[works["source_id"] == sid]
        if len(rows) == 0:
            continue
        works.loc[rows, "manual_decision"] = decision
        methods = set(works.loc[rows, "match_method"])
        if methods & {"issn_l", "issn"}:
            log["conflicts_with_issn_match"].append({"source_id": sid, "manual": decision,
                                                     "methods": sorted(methods)})
            rows = rows[~works.loc[rows, "match_method"].isin(["issn_l", "issn"])]
        if any(x.startswith("title_") for x in methods):
            log["title_match_overridden"].append({"source_id": sid, "manual": decision,
                                                  "methods": sorted(methods)})
        works.loc[rows, "match_method"] = "manual" if decision == "yes" else "none"
        works.loc[rows, ["scopus_id", "conf_key"]] = None
        if decision == "yes":
            years = parse_years(m["years"])
            for r in rows:
                works.at[r, "manual_years"] = years
                works.at[r, "manual_evidence"] = m["evidence"] if isinstance(m["evidence"], str) else None
    for k in ["conflicts_with_issn_match", "title_match_overridden", "unknown_source_ids"]:
        if log[k]:
            print(f"  ! manual file: {k}: {log[k]}")
    return works, log


# --------------------------------------------------------------------------------------------
# 5. SCImago
# --------------------------------------------------------------------------------------------

def load_scimago(years):
    """{file_year: (by_sourceid DataFrame, issn -> Sourceid Series)} for every file that exists."""
    out = {}
    for y in years:
        f = MANUAL / SCIMAGO_FILE.format(year=y)
        if not f.exists():
            print(f"  ! SCImago file for {y} missing")
            continue
        d = pd.read_csv(f, sep=";", dtype=str)
        d = pd.DataFrame({
            "Sourceid": d["Sourceid"].str.strip(),
            "sjr": pd.to_numeric(d["SJR"].str.replace(",", ".", regex=False), errors="coerce"),
            "sjr_quartile": d["SJR Best Quartile"].where(d["SJR Best Quartile"].isin(["Q1", "Q2", "Q3", "Q4"])),
            "h_index": pd.to_numeric(d["H index"], errors="coerce"),
            "sjr_categories": d["Categories"],
            "Issn": d["Issn"],
        })
        issn = (d[["Sourceid", "Issn"]].assign(issn=d["Issn"].fillna("").str.split(","))
                .explode("issn"))
        issn["issn"] = issn["issn"].map(norm_issn)
        issn = issn.dropna(subset=["issn"]).drop_duplicates(subset=["issn"], keep="first")
        out[y] = (d.set_index("Sourceid"), issn.set_index("issn")["Sourceid"])
    return out


def add_scimago(works, scimago):
    """Indicators of the publication year's file. Missing file -> nearest earlier year (flagged).
    Join on Scopus ID when known, otherwise on any ISSN of the work. No borrowing across years."""
    available = sorted(scimago)
    cols = {"sjr": [], "sjr_quartile": [], "h_index": [], "sjr_categories": [],
            "sjr_year_used": [], "sjr_year_flag": [], "sjr_join": []}
    for sid, issn_l, issn, year in zip(works["scopus_id"], works["issn_l"], works["issn"], works["year"]):
        earlier = [y for y in available if y <= year]
        file_year = earlier[-1] if earlier else None
        flag = None if file_year == year else ("fallback" if file_year else "no_file")
        row, how = None, None
        if file_year is not None:
            by_id, by_issn = scimago[file_year]
            if isinstance(sid, str) and sid in by_id.index:
                row, how = by_id.loc[sid], "scopus_id"
            else:
                tokens = ([issn_l] if isinstance(issn_l, str) else []) + \
                         (issn.split("|") if isinstance(issn, str) else [])
                hit = next((by_issn[t] for t in tokens if t in by_issn.index), None)
                if hit is not None:
                    row, how = by_id.loc[hit], "issn"
        cols["sjr"].append(row["sjr"] if row is not None else None)
        cols["sjr_quartile"].append(row["sjr_quartile"] if row is not None else None)
        cols["h_index"].append(row["h_index"] if row is not None else None)
        cols["sjr_categories"].append(row["sjr_categories"] if row is not None else None)
        cols["sjr_year_used"].append(file_year if row is not None else None)
        cols["sjr_year_flag"].append(flag)
        cols["sjr_join"].append(how)
    works = works.copy()
    for c, v in cols.items():
        works[c] = v
    works["sjr"] = pd.to_numeric(works["sjr"], errors="coerce")
    works["h_index"] = pd.to_numeric(works["h_index"], errors="coerce")
    works["sjr_year_used"] = pd.to_numeric(works["sjr_year_used"], errors="coerce").astype("Int64")
    return works


# --------------------------------------------------------------------------------------------
# 6. Reports
# --------------------------------------------------------------------------------------------

def rates_table(works, by):
    g = works.groupby(by)
    return {str(k): {"n": int(len(d)), "in_scopus": rate(d["in_scopus"]), "in_strict": rate(d["in_strict"])}
            for k, d in g}


def print_issn_stage(works):
    """Checkpoint 2: ISSN-only match rates, printed."""
    w = works
    w["in_scopus"] = w["match_method"] != "none"
    w["in_strict"] = w["in_scopus"] & w["scopus_covered_in_year"]
    print("\n=== ISSN match (checkpoint 2) ===")
    print(f"works: {len(w):,} | with any ISSN: {(w.issn_l.notna() | w.issn.notna()).sum():,}")
    print("match_method:", w["match_method"].value_counts().to_dict())
    print(f"in Scopus (ISSN): {w.in_scopus.sum():,} ({w.in_scopus.mean():.1%} of all works; "
          f"{w.in_scopus.sum() / (w.issn_l.notna() | w.issn.notna()).sum():.1%} of works with an ISSN)")
    print(f"covered in publication year: {w.in_strict.sum():,} ({w.in_strict.mean():.1%}); "
          f"in Scopus but NOT covered that year: {(w.in_scopus & ~w.in_strict).sum():,}")
    print("scopus_status of matched works:", w.loc[w.in_scopus, "scopus_status"].value_counts().to_dict())
    print("\nby year:")
    print(w.groupby("year")[["in_scopus", "in_strict"]].agg(["sum", "mean"]).round(3).to_string())
    print("\nby type:")
    t = w.groupby("type")[["in_scopus", "in_strict"]].agg(["sum", "mean"]).round(3)
    t.insert(0, "n", w["type"].value_counts())
    print(t.to_string())
    nc = w[w.in_scopus & ~w.in_strict]
    if len(nc):
        print("\nmatched but not covered in pub. year, top sources:")
        print(nc.groupby(["scopus_title", "scopus_status"]).agg(n=("work_id", "size"),
              years=("year", lambda s: sorted(set(s)))).sort_values("n", ascending=False).head(15).to_string())
    nm = w[(w.issn_l.notna() | w.issn.notna()) & ~w.in_scopus]
    print(f"\nworks WITH an ISSN but not in Scopus: {len(nm):,}; top venues:")
    print(nm.groupby(["source_name", "issn_l"], dropna=False).size().sort_values(ascending=False)
          .head(15).to_string())


def unmatched_venues(works, fuzzy):
    """Top unmatched venues by number of works, repositories and works without a source excluded."""
    u = works[(works["match_method"] == "none") & ~works["_repo"] & works["source_id"].notna()]
    best = (fuzzy.sort_values("score", ascending=False).drop_duplicates("source_id")
            .set_index("source_id")) if len(fuzzy) else pd.DataFrame(columns=["candidate_title", "score"])
    g = u.groupby("source_id")
    out = pd.DataFrame({
        "source_name": g["source_name"].first(),
        "source_type": g["source_type"].first(),
        "issn_l": g["issn_l"].first(),
        "n_works": g.size(),
        "n_by_type": g["type"].agg(lambda s: "; ".join(f"{k}:{v}" for k, v in s.value_counts().items())),
        "years": g["year"].agg(lambda s: ",".join(str(y) for y in sorted(set(s)))),
        "example_doi": g["doi_norm"].agg(lambda s: next((d for d in s if isinstance(d, str)), None)),
    })
    out["best_fuzzy_candidate"] = out.index.map(best["candidate_title"]) if len(best) else None
    out["fuzzy_score"] = out.index.map(best["score"]) if len(best) else None
    out["manual_decision"] = g["manual_decision"].first()
    out = out.reset_index().sort_values(["n_works", "source_name"], ascending=[False, True])
    return out


# --------------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["issn", "all"], default="all")
    stage = ap.parse_args().stage

    works = pd.read_csv(PROCESSED / "works_clean.csv", low_memory=False)
    auths = pd.read_csv(PROCESSED / "authorships_clean.csv", low_memory=False)
    assert len(works) == N_WORKS and works["work_id"].is_unique
    assert len(auths) == N_AUTHORSHIPS
    works["year"] = works["year"].astype(int)
    # repositories are never Scopus sources: Person 1's flag (arXiv, HAL, Zenodo, preprints...) plus
    # sources OpenAlex itself types as 'repository' (DOAJ, Dialnet...). Used only to keep them off the
    # hand-check list; it does not change any match.
    works["_repo"] = works["is_repository"].astype(bool) | (works["source_type"] == "repository")

    sources, issn_map, conf = load_scopus()

    # --- step 1-2: ISSN
    works, issn_conflicts = match_issn(works, issn_map, sources)
    works["conf_key"] = None
    after_issn = works["match_method"].value_counts()
    if stage == "issn":
        print_issn_stage(add_scopus_fields(works, sources, conf))
        print(f"\nworks whose ISSNs point to >1 Scopus source: {len(issn_conflicts)}")
        print(" by rule:", dict(Counter(c["rule"] for c in issn_conflicts)))
        print(" kept <- others (n works):")
        for (k, o), n in Counter((c["kept_title"], tuple(c["others"])) for c in issn_conflicts).most_common(10):
            print(f"   {n:3d}  {k}  <-  {list(o)}")
        return

    # --- step 3: exact title (accepted for works without ISSN; '_issn_miss' recorded, not accepted)
    title_index = build_title_index(sources, conf)
    works, ambiguous, issn_differs = match_title(works, title_index, sources)
    after_title = works["match_method"].value_counts()
    # snapshot of the automatic result: the hand-check list and fuzzy candidates are built from it,
    # so they do not change when manual decisions are added
    works["_method_auto"] = works["match_method"]

    # --- step 4: manual decisions
    works, manual_log = apply_manual(works)
    works = add_scopus_fields(works, sources, conf)

    # --- step 5: SCImago of the publication year
    scimago = load_scimago(range(works["year"].min(), works["year"].max() + 1))
    works = add_scimago(works, scimago)
    # SCImago values only for works counted as in Scopus (a rejected '_issn_miss' candidate keeps its
    # Scopus id for transparency, but must not carry that journal's SJR)
    n_sjr_dropped = int((works["sjr_year_used"].notna() & ~works["in_scopus"]).sum())
    works.loc[~works["in_scopus"], ["sjr", "sjr_quartile", "h_index", "sjr_categories",
                                     "sjr_year_used", "sjr_join"]] = None

    # --- layers
    works["in_strict"] = works["in_scopus"] & works["scopus_covered_in_year"]
    works["in_strict_active"] = works["in_strict"] & ~works["scopus_status"].isin(NOT_ACTIVE)
    works["in_strict_q12"] = works["in_strict"] & works["sjr_quartile"].isin(["Q1", "Q2"])
    works["in_strict_issn_only"] = works["in_strict"] & works["match_method"].isin(["issn_l", "issn"])
    # indexing-lag tolerant variant: also counts a work whose source is in Scopus, is NOT inactive or
    # discontinued, and was covered in the year BEFORE publication. Scopus adds new volumes with a
    # delay (e.g. CSCL/ICLS 2025), so a missing latest year is more likely lag than exclusion.
    covered_prev = pd.Series([covered_in(r, r["year"] - 1, sources, conf) for _, r in works.iterrows()],
                             index=works.index)
    works["in_strict_lag"] = works["in_strict"] | (
        works["in_scopus"] & ~works["scopus_covered_in_year"]
        & ~works["scopus_status"].isin(NOT_ACTIVE) & covered_prev)

    # --- fuzzy candidates and the hand-check list (from the automatic result, before manual decisions)
    auto_unmatched = ~works["_method_auto"].map(is_accepted)
    venues = (works[auto_unmatched & ~works["_repo"] & works["source_id"].notna() & works["venue_norm"].notna()]
              .groupby(["source_id", "source_name", "venue_norm"]).size().rename("n_works").reset_index())
    print(f"Fuzzy search for {len(venues):,} unmatched venues...")
    fuzzy = fuzzy_candidates(venues, sources, conf)
    # exact-title hits that were not accepted (ambiguous, or the venue has a non-Scopus ISSN)
    extra = []
    for sid, (name, ids) in ambiguous.items():
        for i in ids:
            extra.append({"source_id": sid, "source_name": name, "candidate_title": sources.at[i, "scopus_title"],
                          "candidate_sheet": "exact_but_ambiguous", "scopus_id": i, "score": 1.0})
    for sid, (name, kind, target) in issn_differs.items():
        title = sources.at[target, "scopus_title"] if kind == "serial" else conf.at[target, "scopus_title"]
        extra.append({"source_id": sid, "source_name": name, "candidate_title": title,
                      "candidate_sheet": "exact_but_venue_has_other_issn",
                      "scopus_id": target if kind == "serial" else None, "score": 1.0})
    if extra:
        n_by_src = works.groupby("source_id").size()
        extra = pd.DataFrame(extra)
        extra["n_works"] = extra["source_id"].map(n_by_src)
        fuzzy = pd.concat([extra, fuzzy], ignore_index=True)
    fuzzy = fuzzy.sort_values(["n_works", "source_id", "score"], ascending=[False, True, False])
    top = unmatched_venues(works[auto_unmatched],
                           fuzzy[fuzzy["candidate_sheet"].isin(["main", "serial_conf", "all_conf"])])

    # --- samples for hand-checking (fixed seed)
    title_cols = ["work_id", "doi_norm", "title", "year", "type", "source_name", "issn_l",
                  "match_method", "scopus_id", "scopus_title", "scopus_covered_in_year", "in_strict"]
    accepted_title = works[works["match_method"].isin(list(TITLE_METHOD.values()))]
    title_sample = accepted_title.sample(min(20, len(accepted_title)), random_state=SEED)[title_cols]
    no_src = works[works["source_id"].isna()]
    no_source_sample = no_src.sample(min(15, len(no_src)), random_state=SEED)[
        ["work_id", "doi_norm", "title", "year", "type", "is_repository", "cited_by_count"]]

    # --- checks
    assert len(works) == N_WORKS and works["work_id"].is_unique
    assert not (works["in_strict"] & ~works["in_scopus"]).any()
    for c in ["in_strict_q12", "in_strict_active", "in_strict_issn_only"]:
        assert not (works[c] & ~works["in_strict"]).any(), c
    assert not (works["in_strict"] & ~works["in_strict_lag"]).any()
    assert not (works["in_strict_lag"] & ~works["in_scopus"]).any()
    by_method = works["match_method"].value_counts()
    assert by_method[[m for m in by_method.index if is_accepted(m)]].sum() == works["in_scopus"].sum()
    assert works.loc[works["match_method"].str.endswith(ISSN_MISS), "in_scopus"].eq(False).all()
    assert works.loc[works["manual_decision"] == "unsure", "in_scopus"].eq(False).all()

    # --- report
    excluded = works[auto_unmatched & (works["_repo"] | works["source_id"].isna())]
    layers = ["in_scopus", "in_strict", "in_strict_active", "in_strict_q12", "in_strict_issn_only",
              "in_strict_lag"]
    fie = works[works["source_id"] == FIE_SOURCE_ID]
    report = {
        "n_works": len(works),
        "overall": {c: rate(works[c]) for c in layers},
        "counts": {c: int(works[c].sum()) for c in layers},
        "by_match_method": {k: int(v) for k, v in by_method.items()},
        "added_by_step": {
            "1_issn_l": int(after_issn.get("issn_l", 0)),
            "2_issn": int(after_issn.get("issn", 0)),
            "3_title_main": int(after_title.get("title_main", 0)),
            "3_title_serialconf": int(after_title.get("title_serialconf", 0)),
            "3_title_allconf": int(after_title.get("title_allconf", 0)),
            "3_title_issn_miss_not_accepted": int(sum(v for k, v in after_title.items()
                                                      if k.endswith(ISSN_MISS))),
            "4_manual": int(by_method.get("manual", 0)),
            "note": "steps 1-3 are counted before manual decisions; a manual 'no'/'unsure' can undo a title "
                    "match (see manual.title_match_overridden), so final counts are in by_match_method",
        },
        "in_strict_by_match_method": {k: int(v) for k, v in
                                      works[works["in_strict"]]["match_method"].value_counts().items()},
        "in_scopus_not_covered_in_year": int((works["in_scopus"] & ~works["scopus_covered_in_year"]).sum()),
        "scopus_status_of_matched": {k: int(v) for k, v in
                                     works.loc[works["in_scopus"], "scopus_status"].value_counts().items()},
        "by_year": rates_table(works, "year"),
        "by_type": rates_table(works, "type"),
        "strict_vs_strict_lag_by_year": {
            str(y): {"n": int(len(d)), "in_strict": int(d["in_strict"].sum()),
                     "in_strict_lag": int(d["in_strict_lag"].sum()),
                     "added_by_lag": int(d["in_strict_lag"].sum() - d["in_strict"].sum())}
            for y, d in works.groupby("year")},
        "sjr": {
            "works_with_sjr_row": int(works["sjr_year_used"].notna().sum()),
            "in_strict_with_quartile": int((works["in_strict"] & works["sjr_quartile"].notna()).sum()),
            "join": {k: int(v) for k, v in works["sjr_join"].value_counts().items()},
            "year_flags": {k: int(v) for k, v in works["sjr_year_flag"].value_counts().items()},
            "sjr_rows_dropped_not_in_scopus": n_sjr_dropped,
            "note": "SCImago H index and Coverage are identical across the 2020-2025 files: snapshot values",
        },
        "issn_conflicts": issn_conflicts,
        "title_ambiguous_venues": {k: {"name": v[0], "scopus_ids": v[1]} for k, v in ambiguous.items()},
        "title_exact_hit_but_venue_has_other_issn": {
            "venues": len(issn_differs),
            "works": int(sum(v for k, v in after_title.items() if k.endswith(ISSN_MISS)))},
        "excluded_from_review_list": {
            "repository_works": int(excluded["_repo"].sum()),
            "no_source_works": int(excluded["source_id"].isna().sum()),
        },
        "no_source_works": {"n": int(len(no_src)),
                            "by_type": {k: int(v) for k, v in no_src["type"].value_counts().items()}},
        "venue_check_FIE": {
            "source_id": FIE_SOURCE_ID, "n_works": int(len(fie)),
            "automatic_method": sorted(set(fie["_method_auto"])),
            "final_method": sorted(set(fie["match_method"])),
            "in_scopus": int(fie["in_scopus"].sum()), "in_strict": int(fie["in_strict"].sum()),
            "note": "OpenAlex ISSN 0190-5848 is not in the Scopus list; Scopus lists 'Proceedings - Frontiers "
                    "in Education Conference, FIE' (ISSN 1539-4565). The names differ after normalisation, "
                    "so only the manual file can match it.",
        },
        "manual": manual_log,
    }

    # --- write
    drop = ["conf_key", "venue_norm", "sjr_join", "_repo", "_method_auto", "manual_years"]
    works.drop(columns=drop).to_csv(PROCESSED / "works_layers.csv", index=False)
    layer_cols = ["in_strict", "in_strict_active", "in_strict_q12", "in_strict_issn_only", "in_strict_lag"]
    auths_l = auths.merge(works[["work_id"] + layer_cols], on="work_id", how="left", validate="many_to_one")
    assert len(auths_l) == N_AUTHORSHIPS and auths_l["in_strict"].notna().all()
    auths_l.to_csv(PROCESSED / "authorships_layers.csv", index=False)
    top.head(TOP_UNMATCHED).to_csv(PROCESSED / "unmatched_venues_top.csv", index=False)
    fuzzy.to_csv(PROCESSED / "title_fuzzy_candidates.csv", index=False)
    title_sample.to_csv(PROCESSED / "title_match_sample.csv", index=False)
    no_source_sample.to_csv(PROCESSED / "no_source_sample.csv", index=False)
    (PROCESSED / "match_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(json.dumps({k: report[k] for k in ["overall", "counts", "by_match_method", "added_by_step",
                                             "in_scopus_not_covered_in_year", "venue_check_FIE"]}, indent=2))


if __name__ == "__main__":
    main()
