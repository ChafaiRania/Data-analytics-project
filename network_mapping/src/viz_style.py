# viz_style.py
# One shared, colorblind-safe palette and a consistent matplotlib look,
# reused by every figure in the project so the report doesn't look like
# it was made from five different templates.

import matplotlib.pyplot as plt

# Fixed categorical order -- validated for colorblind-safe adjacent
# contrast. Always assign in THIS order; never cycle/reassign per chart.
CATEGORICAL = [
    "#2a78d6",  # 1 blue   -- default single-series color
    "#eb6834",  # 2 orange -- second series in a 2-way comparison
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 green
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 red
]

BLUE = CATEGORICAL[0]
ORANGE = CATEGORICAL[1]

INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
SURFACE = "#fcfcfb"


def apply_style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": GRIDLINE,
        "axes.labelcolor": INK_SECONDARY,
        "axes.titlecolor": INK_PRIMARY,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRIDLINE,
        "grid.linewidth": 0.8,
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "text.color": INK_PRIMARY,
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "savefig.facecolor": SURFACE,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
    })
