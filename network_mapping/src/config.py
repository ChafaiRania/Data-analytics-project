"""
Settings for the network-mapping step. No API key and no network access: this step only reads
the files produced by Person 1 (cleaning) and Person 2 (ALL / STRICT layers).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Input: the processed folder of the collecte_cleaning project.
# Default layout: this folder sits next to collecte_cleaning/ and clustering/.
#   project/
#     collecte_cleaning/data/processed/works_layers.csv
#     clustering/outputs/tables/institution_assignments_all.csv   (optional, see below)
#     network_mapping/src/build_networks.py
# Override with:  python src/build_networks.py --data path/to/data/processed
DATA_DIR = ROOT.parent / "collecte_cleaning" / "data" / "processed"
WORKS_FILE = "works_layers.csv"
AUTHORSHIPS_FILE = "authorships_layers.csv"

# Optional: the Louvain communities of the clustering step. If the file exists, the institution
# map for VOSviewer gets those communities as its "cluster" column, so the map and the clustering
# show the same groups. If not, VOSviewer computes its own clusters.
CLUSTERING_DIR = ROOT.parent / "clustering" / "outputs" / "tables"

OUT_DIR = ROOT / "outputs"
TAB_DIR = OUT_DIR / "tables"
FIG_DIR = OUT_DIR / "figures"
VOS_DIR = OUT_DIR / "vosviewer"

LAYERS = ["ALL", "STRICT"]

# --- which nodes go on the VOSviewer maps ---------------------------------------------
# The full node and edge tables keep everything. The maps keep the nodes with enough papers
# to have stable links (same thresholds as the clustering step for institutions).
MIN_PAPERS_INSTITUTION_MAP = 5     # EU institutions only
MIN_PAPERS_AUTHOR_MAP = 3          # authors with at least one EU affiliation in the corpus
MIN_KEYWORD_PAPERS = {"ALL": 30, "STRICT": 20}

# Keywords that restate the search query itself. They co-occur with almost everything, so
# they are kept in the tables but left off the keyword map, where they would hide the structure.
GENERIC_KEYWORDS = {
    "artificial intelligence in education", "artificial intelligence", "education",
    "artificial intelligence in higher education", "ai in education", "machine learning",
    "deep learning", "generative ai in education",
}

SEED = 42
N_TOP = 15
