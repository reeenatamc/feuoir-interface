"""Draws the continuity symbol to look for on the multimeter dial, and the fallback range.

Saves simbolo_pitido.png next to this script. Labels in Spanish.

    .venv/bin/python docs/armado/draw_simbolo_pitido.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Arc, FancyBboxPatch, Polygon  # noqa: E402

fig, ax = plt.subplots(figsize=(11, 5.4))
ax.set_aspect("equal")
ax.axis("off")


def waves(cx, cy, s=1.0):
    ax.plot([cx - 0.55 * s, cx - 0.2 * s], [cy, cy], color="black", lw=3 * s, solid_capstyle="round")
    ax.plot(cx - 0.2 * s, cy, "o", color="black", ms=9 * s)
    for k, w in enumerate((0.5, 0.9, 1.3)):
        ax.add_patch(Arc((cx - 0.2 * s, cy), w * s, w * s, angle=0, theta1=-62, theta2=62, lw=3 * s, color="black"))


def diode(cx, cy, s=1.0):
    ax.plot([cx - 0.85 * s, cx - 0.45 * s], [cy, cy], color="black", lw=3 * s, solid_capstyle="round")
    ax.add_patch(Polygon([[cx - 0.45 * s, cy + 0.35 * s], [cx - 0.45 * s, cy - 0.35 * s], [cx + 0.05 * s, cy]],
                         closed=True, fc="none", ec="black", lw=3 * s))
    ax.plot([cx + 0.05 * s, cx + 0.05 * s], [cy - 0.35 * s, cy + 0.35 * s], color="black", lw=3 * s)
    ax.plot([cx + 0.05 * s, cx + 0.5 * s], [cy, cy], color="black", lw=3 * s, solid_capstyle="round")


for x, label in ((-3.2, "así, solito"), (0.6, "o con un triangulito al lado")):
    ax.add_patch(FancyBboxPatch((x - 1.5, -1.2), 3.0, 2.4, boxstyle="round,pad=0.12", fc="#f6f4ef", ec="#bbb"))
    ax.text(x, -1.75, label, ha="center", fontsize=13, color="#555")
waves(-2.9, 0.0, 1.3)
diode(0.0, 0.0, 1.1)
waves(1.5, 0.0, 1.0)

ax.add_patch(FancyBboxPatch((3.6, -1.2), 3.0, 2.4, boxstyle="round,pad=0.12", fc="#fff8e1", ec="#e0b400"))
ax.text(5.1, 0.35, "200", ha="center", fontsize=30, fontweight="bold")
ax.text(5.1, -0.55, "Ω", ha="center", fontsize=26)
ax.text(5.1, -1.75, "si no tienes el de las ondas", ha="center", va="top", fontsize=13, color="#8d6e00")

ax.text(1.0, 2.3, "El dibujito que buscas en la perilla", ha="center", fontsize=20, fontweight="bold")
ax.text(1.0, -3.2, "Con el de las ondas: al juntar las dos puntas metálicas, pita.\n"
                   "Con el de 200 Ω: al juntarlas marca casi cero, y separadas marca 1 o OL.",
        ha="center", va="top", fontsize=13, linespacing=1.5)
ax.set_xlim(-5.4, 7.4)
ax.set_ylim(-4.6, 3.0)
out = Path(__file__).resolve().with_name("simbolo_pitido.png")
fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
print(out)
