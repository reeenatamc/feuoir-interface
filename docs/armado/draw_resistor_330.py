"""Draws what a 330 ohm resistor looks like, with 4 and 5 bands, so it can be picked out of a kit."""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

ORANGE, BROWN, BLACK, GOLD = "#f57c00", "#6d4c41", "#111111", "#c9a227"


def resistor(ax, y, body, bands, title, names):
    ax.plot([0, 10], [y, y], color="#9e9e9e", lw=4, zorder=1)
    ax.add_patch(FancyBboxPatch((2.5, y - 0.6), 5, 1.2, boxstyle="round,pad=0.15", fc=body, ec="#555", zorder=2))
    for x, c in bands:
        ax.add_patch(Rectangle((x, y - 0.72), 0.35, 1.44, color=c, zorder=3))
    ax.text(5, y + 1.3, title, ha="center", fontsize=14, fontweight="bold")
    ax.text(5, y - 1.5, names, ha="center", fontsize=12)


fig, ax = plt.subplots(figsize=(8, 7))
ax.set_aspect("equal"); ax.axis("off")
resistor(ax, 6, "#e3cfa8", [(3.0, ORANGE), (3.7, ORANGE), (4.4, BROWN), (6.6, GOLD)],
         "Si tiene 4 rayas (cuerpo beige)", "naranja, naranja, café ... dorado")
resistor(ax, 1, "#8ec5e8", [(3.0, ORANGE), (3.6, ORANGE), (4.2, BLACK), (4.8, BLACK), (6.6, BROWN)],
         "Si tiene 5 rayas (cuerpo celeste)", "naranja, naranja, negro, negro ... café")
ax.text(5, -2.2, "Las dos son 330 Ω. La raya separada (dorado o café) va a la derecha.", ha="center", fontsize=11)
ax.set_xlim(-0.5, 10.5); ax.set_ylim(-3, 8)
out = Path(__file__).with_name("resistencia_330.png")
fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
print(out)
