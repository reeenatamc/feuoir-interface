"""A single close-up of the top corner of the board, showing only the three holes the knob goes into."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle  # noqa: E402

COLS = "abcdefghij"
X = {c: i + (1.4 if i >= 5 else 0) for i, c in enumerate(COLS)}
ROWS = 10
TARGET = {3, 5, 7}

fig, ax = plt.subplots(figsize=(9, 8))
ax.set_aspect("equal")
ax.axis("off")
ax.add_patch(FancyBboxPatch((-1.2, -ROWS - 0.6), 12.8, ROWS + 0.2, boxstyle="round,pad=0.25",
                            fc="#f6f4ef", ec="#bbb"))
for c in COLS:
    ax.text(X[c], 0.45, c, ha="center", fontsize=15, color="#444", fontweight="bold" if c == "a" else "normal")
for r in range(1, ROWS + 1):
    ax.text(-0.85, -r, str(r), ha="center", va="center", fontsize=13,
            color="#c62828" if r in TARGET else "#444", fontweight="bold")
    for c in COLS:
        ax.add_patch(Rectangle((X[c] - 0.14, -r - 0.14), 0.28, 0.28, color="#9a9a9a"))
for r in sorted(TARGET):
    ax.add_patch(Circle((X["a"], -r), 0.45, fc="#c62828", ec="#7f1d1d", lw=2, zorder=4))
    ax.text(X["a"] - 1.7, -r, f"a{r}", ha="right", va="center", fontsize=17, color="#c62828", fontweight="bold")
ax.annotate("", xy=(X["a"] + 0.6, -5), xytext=(12.4, -5),
            arrowprops=dict(arrowstyle="->", color="#6a1b9a", lw=2.5))
ax.text(12.8, -5, "las tres patitas\nde la perilla van\nen estos tres\nagujeritos rojos\ny en ninguno más",
        ha="left", va="center", fontsize=15, color="#6a1b9a", linespacing=1.4)
ax.text(5.1, 2.4, "Dónde va la perilla", ha="center", fontsize=19, fontweight="bold")
ax.text(5.1, 1.4, "Esta es la esquina de la tabla donde empiezan los números", ha="center", fontsize=12, color="#555")
ax.text(5.1, -ROWS - 1.8, "Cuenta las filas desde la punta donde la tabla dice 1.\n"
                          "La columna a es la primera, la que está junto a los números.",
        ha="center", va="top", fontsize=13, linespacing=1.5)
ax.set_xlim(-4.2, 21.0)
ax.set_ylim(-ROWS - 4.0, 3.0)
out = Path(__file__).resolve().with_name("perilla_donde_va.png")
fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
print(out)
