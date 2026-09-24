"""Draws the three continuity checks to run before the batteries go in.

Only the four edge strips matter here, so the middle of the board is drawn plain. Saves prueba_pitido.png next to
this script. Labels in Spanish, and the strips are named by the letters beside them so the drawing cannot be read
upside down.

    .venv/bin/python docs/armado/draw_prueba_pitido.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

ROWS = 30
GND_L, VNEG_X, GND_R, VPOS_X = -3.8, -2.6, 12.8, 14.0
STRIPS = [(GND_L, "#1565c0", "azul"), (VNEG_X, "#c62828", "roja"),
          (GND_R, "#1565c0", "azul"), (VPOS_X, "#c62828", "roja")]
CHECKS = [(1, VPOS_X, GND_R, -6, "#7b1fa2"), (2, VPOS_X, VNEG_X, -15, "#00838f"), (3, VNEG_X, GND_L, -24, "#ef6c00")]

fig, ax = plt.subplots(figsize=(11, 10))
ax.set_aspect("equal")
ax.axis("off")
ax.add_patch(FancyBboxPatch((-4.6, -ROWS - 0.8), 19.4, ROWS + 0.4, boxstyle="round,pad=0.3", fc="#f6f4ef", ec="#bbb"))
ax.add_patch(Rectangle((-0.6, -ROWS - 0.2), 10.2, ROWS - 0.2, fc="#eceae4", ec="none"))
ax.text(4.5, -3.5, "todo lo que ya armaste\n(aquí no se toca nada)", ha="center", va="center",
        fontsize=13, color="#888")
for x, color, _ in STRIPS:
    ax.plot([x, x], [-0.8, -ROWS], color=color, lw=2.5)
    for r in range(1, ROWS + 1):
        ax.add_patch(Rectangle((x - 0.14, -r - 0.14), 0.28, 0.28, color="#9a9a9a"))
ax.text(GND_L, 0.9, "tira azul", ha="center", fontsize=12, color="#1565c0")
ax.text(VNEG_X, 0.2, "tira roja", ha="center", fontsize=12, color="#c62828")
ax.text(GND_R, 0.2, "tira azul", ha="center", fontsize=12, color="#1565c0")
ax.text(VPOS_X, 0.9, "tira roja", ha="center", fontsize=12, color="#c62828")
ax.text((GND_L + VNEG_X) / 2, -ROWS - 2.0, "este lado es el de\nlas letras a b c d e", ha="center", fontsize=12)
ax.text((GND_R + VPOS_X) / 2, -ROWS - 2.0, "este lado es el de\nlas letras f g h i j", ha="center", fontsize=12)
for n, x1, x2, y, color in CHECKS:
    ax.plot([x1, x1, x2, x2], [y, y - 1.2, y - 1.2, y], color=color, lw=2.2, zorder=4)
    for x in (x1, x2):
        ax.plot(x, y, "o", color=color, ms=13, zorder=5)
    ax.text((x1 + x2) / 2, y - 2.6, f"medida {n}: no debe pitar", ha="center", fontsize=14, color=color,
            fontweight="bold", zorder=6, bbox=dict(fc="white", ec=color, lw=1.2, boxstyle="round,pad=0.35"))
ax.text(4.5, 3.4, "Las tres medidas antes de las pilas", ha="center", fontsize=20, fontweight="bold")
ax.text(4.5, 2.0, "Un palito en cada punto de color. En las tres, el aparato tiene que quedarse callado.",
        ha="center", fontsize=13, color="#555")
ax.text(4.5, -ROWS - 4.4, "En una tira entera sirve cualquier agujerito: toda la tira es un mismo punto.",
        ha="center", fontsize=13, color="#555")
ax.set_xlim(-6.4, 16.6)
ax.set_ylim(-ROWS - 6.0, 4.6)
out = Path(__file__).resolve().with_name("prueba_pitido.png")
fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
print(out)
