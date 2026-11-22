"""
Settings for the clustering step (RQ3). No API key, no network access: this step only reads
the files produced by Person 1 (cleaning) and Person 2 (ALL / STRICT layers).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Input: the processed folder of the collecte_cleaning project.
# Default layout: this folder sits next to collecte_cleaning/.
#   project/
#     collecte_cleaning/data/processed/works_layers.csv
#     clustering/src/clustering.py
# Override with:  python src/clustering.py --data path/to/data/processed
DATA_DIR = ROOT.parent / "collecte_cleaning" / "data" / "processed"
WORKS_FILE = "works_layers.csv"
AUTHORSHIPS_FILE = "authorships_layers.csv"

OUT_DIR = ROOT / "outputs"
FIG_DIR = OUT_DIR / "figures"
TAB_DIR = OUT_DIR / "tables"

LAYERS = ["ALL", "STRICT"]

# --- collaboration network -------------------------------------------------------------
# An EU institution enters the network if it has at least this many papers in the layer.
# Below 5 papers, an institution's links are one or two co-authorships and its community
# is decided by chance.
MIN_PAPERS_NETWORK = 5
# Louvain is randomised: run it with several seeds, keep the partition with the highest
# modularity, and report how much the runs agree (stability).
LOUVAIN_SEEDS = 20
LOUVAIN_RESOLUTION = 1.0
# Communities smaller than this are grouped as "small" in the profiles (not in the metrics).
MIN_COMMUNITY_SIZE = 5

# Sensitivity check: the network step is re-run with these values (5 seeds each).
SENS_MIN_PAPERS = [3, 5, 10]
SENS_RESOLUTIONS = [0.5, 1.0, 2.0]

# --- topic clustering ------------------------------------------------------------------
# A topic profile needs enough papers to be a profile: at least 10 papers per institution.
MIN_PAPERS_TOPIC = 10
# OpenAlex topics with fewer papers than this (in the layer) are merged into "Other topics".
MIN_TOPIC_PAPERS = 30
K_RANGE = range(2, 11)
KMEANS_SEEDS = 20

# --- null models -----------------------------------------------------------------------
N_PERMUTATIONS = 200
SEED = 42
