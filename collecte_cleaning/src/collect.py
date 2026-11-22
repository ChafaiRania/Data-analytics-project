"""
Download AI-in-education works with at least one EU-affiliated author from OpenAlex.

Usage (from the project root):
    python src/collect.py --limit 1000     # quick test
    python src/collect.py                  # full download

Set your free OpenAlex key first (https://openalex.org/settings/api):
    PowerShell:  $env:OPENALEX_API_KEY = "your-key"
    Bash:        export OPENALEX_API_KEY=your-key

Outputs (data/raw/):
    works.jsonl.gz      raw API records, one per line (never edited by hand)
    query_meta.json     the exact filter, date of download and count
Outputs (data/processed/):
    works.csv           one row per work
    authorships.csv     one row per (work, author, institution)
"""

import argparse
import gzip
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

API = "https://api.openalex.org/works"

# EU-27 member states (ISO 3166-1 alpha-2, as used by OpenAlex). GR = Greece.
EU27 = [
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE",
    "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
]

# Keyword query on title + abstract. The bare word "learning" is deliberately left out:
# it matches every "machine learning" paper and inflated the result from ~27k to ~219k.
AI_TERMS = [
    '"artificial intelligence"', '"machine learning"', '"deep learning"', "chatgpt",
    '"generative AI"', '"large language model"', '"learning analytics"',
    '"intelligent tutoring"', '"educational data mining"',
]
EDU_TERMS = [
    "education", "teaching", "student", '"higher education"', "school", "classroom",
    "curriculum", "teacher",
]
QUERY = f"({' OR '.join(AI_TERMS)}) AND ({' OR '.join(EDU_TERMS)})"

# Complete years only: 2026 is still being published and indexed, so including it
# would make the last point of every trend look artificially low (or high).
FIRST_YEAR, LAST_YEAR = 2020, 2025
PER_PAGE = 200

FIELDS = [
    "id", "doi", "title", "publication_year", "publication_date", "type", "language",
    "cited_by_count", "authorships", "primary_location", "primary_topic", "keywords",
    "abstract_inverted_index",
]


def build_filter(year=None):
    years = f"publication_year:{year}" if year else f"publication_year:{FIRST_YEAR}-{LAST_YEAR}"
    return ",".join([
        years,
        f"authorships.institutions.country_code:{'|'.join(EU27)}",
        f"title_and_abstract.search:{QUERY}",
    ])


def api_key():
    """OPENALEX_API_KEY from the environment, or from a local .env file (never committed)."""
    if os.environ.get("OPENALEX_API_KEY"):
        return os.environ["OPENALEX_API_KEY"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("OPENALEX_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None


def get(params, retries=5):
    key = api_key()
    if key:
        params = {**params, "api_key": key}
    for attempt in range(retries):
        r = requests.get(API, params=params, timeout=60)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (429, 500, 502, 503):
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 401:
            raise SystemExit(
                "OpenAlex returned 401: paging past the first page needs an API key.\n"
                "Get a free one at https://openalex.org/settings/api and set OPENALEX_API_KEY."
            )
        r.raise_for_status()
    raise RuntimeError(f"OpenAlex failed after {retries} retries: {r.status_code} {r.text[:300]}")


def download(limit=None):
    """Download year by year with page-based paging (works without an API key, max
    10 000 results per filter, so one filter per year). Every page is cached in
    data/raw/pages/, so if the free daily budget runs out the next run resumes."""
    pages_dir = RAW / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    complete = True
    for year in range(FIRST_YEAR, LAST_YEAR + 1):
        n_pages = 1
        page_no = 1
        while page_no <= n_pages:
            cache = pages_dir / f"{year}_{page_no:03d}.json.gz"
            if cache.exists():
                with gzip.open(cache, "rt", encoding="utf-8") as f:
                    page = json.load(f)
            elif not complete:
                break
            else:
                try:
                    page = get({
                        "filter": build_filter(year),
                        "select": ",".join(FIELDS),
                        "sort": "publication_date",
                        "per_page": PER_PAGE,
                        "page": page_no,
                    })
                except RuntimeError as e:
                    print(f"\nStopped at {year} page {page_no}: {str(e)[:120]}")
                    print("Cached pages are kept; re-run later (budget resets at midnight UTC).")
                    complete = False
                    break
                with gzip.open(cache, "wt", encoding="utf-8") as f:
                    json.dump(page, f, ensure_ascii=False)
            counts[year] = page["meta"]["count"]
            n_pages = -(-counts[year] // PER_PAGE)
            if limit:
                n_pages = min(n_pages, -(-limit // PER_PAGE))
            print(f"\r{year}: page {page_no}/{n_pages}   ", end="", flush=True)
            page_no += 1
        print()

    # merge cached pages, dropping duplicates (page-based paging can repeat a
    # record at a page boundary when many works share a publication date)
    out = RAW / "works.jsonl.gz"
    seen = set()
    with gzip.open(out, "wt", encoding="utf-8") as f:
        for cache in sorted(pages_dir.glob("*.json.gz")):
            if int(cache.name[:4]) not in counts:
                continue
            with gzip.open(cache, "rt", encoding="utf-8") as g:
                for w in json.load(g)["results"]:
                    if w["id"] not in seen:
                        seen.add(w["id"])
                        f.write(json.dumps(w, ensure_ascii=False) + "\n")

    meta = {
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "filter": build_filter(),
        "query": QUERY,
        "count_reported_by_api_per_year": counts,
        "count_reported_by_api": sum(counts.values()),
        "count_downloaded_unique": len(seen),
        "complete": complete,
        "limit_per_year": limit,
    }
    (RAW / "query_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return out


def abstract_from_index(inv):
    """OpenAlex stores abstracts as {word: [positions]}; rebuild the plain text."""
    if not inv:
        return None
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def flatten(raw_file):
    PROCESSED.mkdir(parents=True, exist_ok=True)
    works, auths = [], []
    with gzip.open(raw_file, "rt", encoding="utf-8") as f:
        for line in f:
            w = json.loads(line)
            loc = w.get("primary_location") or {}
            src = loc.get("source") or {}
            topic = w.get("primary_topic") or {}
            countries = set()
            for a in w.get("authorships") or []:
                insts = a.get("institutions") or []
                countries.update(a.get("countries") or [])
                # an author with no institution still gets one row, so missing
                # affiliations stay visible instead of silently disappearing
                for inst in insts or [{}]:
                    auths.append({
                        "work_id": w["id"],
                        "author_id": (a.get("author") or {}).get("id"),
                        "author_name": (a.get("author") or {}).get("display_name"),
                        "author_position": a.get("author_position"),
                        "institution_id": inst.get("id"),
                        "institution_name": inst.get("display_name"),
                        "institution_country": inst.get("country_code"),
                        "institution_type": inst.get("type"),
                    })
            works.append({
                "work_id": w["id"],
                "doi": w.get("doi"),
                "title": w.get("title"),
                "year": w.get("publication_year"),
                "date": w.get("publication_date"),
                "type": w.get("type"),
                "language": w.get("language"),
                "cited_by_count": w.get("cited_by_count"),
                "n_authors": len(w.get("authorships") or []),
                "countries": "|".join(sorted(countries)),
                "n_countries": len(countries),
                "source_id": src.get("id"),
                "source_name": src.get("display_name"),
                "source_type": src.get("type"),
                "issn_l": src.get("issn_l"),
                "issn": "|".join(src.get("issn") or []),
                "topic": topic.get("display_name"),
                "subfield": (topic.get("subfield") or {}).get("display_name"),
                "field": (topic.get("field") or {}).get("display_name"),
                "keywords": "|".join(k.get("display_name", "") for k in w.get("keywords") or []),
                "abstract": abstract_from_index(w.get("abstract_inverted_index")),
            })
    pd.DataFrame(works).to_csv(PROCESSED / "works.csv", index=False)
    pd.DataFrame(auths).to_csv(PROCESSED / "authorships.csv", index=False)
    print(f"works.csv: {len(works):,} rows | authorships.csv: {len(auths):,} rows")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="stop after ~N works per year (for testing)")
    ap.add_argument("--skip-download", action="store_true", help="only re-flatten existing raw file")
    args = ap.parse_args()
    raw = RAW / "works.jsonl.gz" if args.skip_download else download(args.limit)
    flatten(raw)
