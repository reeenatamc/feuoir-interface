"""A close-up of the three jumpers that take the knob's pins to the rows the circuit needs.

Only rows 1 to 20 of the a..e half, big enough to count holes. Saves perilla_cables.png next to this script.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle  # noqa: E402

COLS = "abcde"
X = {c: i for i, c in enumerate(COLS)}
ROWS = 20
JUMPERS = [(("b", 3), ("b", 14), "#1565c0", 2.6, -3.0), (("b", 5), ("d", 14), "#2e7d32", 3.3, -6.5),
           (("b", 7), ("b", 15), "#ef6c00", 4.0, -10.0)]
PINS = [3, 5, 7]

fig, ax = plt.subplots(figsize=(9, 12))
ax.set_aspect("equal")
ax.axis("off")
ax.add_patch(FancyBboxPatch((-0.8, -ROWS - 0.6), 5.6, ROWS + 0.2, boxstyle="round,pad=0.25", fc="#f6f4ef", ec="#bbb"))
for c in COLS:
    ax.text(X[c], 0.5, c, ha="center", fontsize=16, color="#444")
for r in range(1, ROWS + 1):
    ax.text(-1.4, -r, str(r), ha="center", va="center", fontsize=13, color="#444", fontweight="bold")
    for c in COLS:
        ax.add_patch(Rectangle((X[c] - 0.14, -r - 0.14), 0.28, 0.28, color="#9a9a9a"))
for r in PINS:
    ax.add_patch(Circle((X["a"], -r), 0.42, fc="#c62828", ec="#7f1d1d", lw=2, zorder=4))
ax.text(X["a"] - 2.2, -5, "la perilla\nya puesta", ha="center", va="center", fontsize=13, color="#c62828")
for (ca, ra), (cb, rb), color, mid, label_y in JUMPERS:
    xa, ya, xb, yb = X[ca], -ra, X[cb], -rb
    ax.plot([xa, mid, mid, xb], [ya, ya, yb, yb], color=color, lw=3.0, solid_capstyle="round",
            solid_joinstyle="round", zorder=5)
    ax.plot([xa, xb], [ya, yb], "o", color=color, ms=10, zorder=6)
    ax.plot([mid, 6.6], [label_y, label_y], color=color, lw=1.2, ls=":", zorder=5)
    ax.text(6.8, label_y, f"de {ca}{ra} a {cb}{rb}", ha="left", va="center", fontsize=15, color=color)
ax.text(3.0, 2.6, "Los tres cables de la perilla", ha="center", fontsize=19, fontweight="bold")
ax.text(3.0, 1.5, "Un cable por cada patita, del color que quieras", ha="center", fontsize=13, color="#555")
ax.text(3.0, -ROWS - 1.6, "Cada punta del cable termina en un pincho metálico.\n"
                          "Ese pincho se empuja derecho dentro del agujerito, hasta el fondo.\n"
                          "Si el cuerpo de la perilla tapa un agujerito de la columna b,\n"
                          "usa c, d o e de esa misma fila: es el mismo punto.",
        ha="center", va="top", fontsize=13, linespacing=1.5)
ax.set_xlim(-5.8, 12.0)
ax.set_ylim(-ROWS - 6.0, 3.4)
out = Path(__file__).resolve().with_name("perilla_cables.png")
fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
print(out)
