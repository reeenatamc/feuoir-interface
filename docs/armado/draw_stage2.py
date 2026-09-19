"""Draws the breadboard layout for stage 2 of docs/primer-encendido.md: R1 from GP21 to a free row, and the
verification wire from that row to GP20. Labels are in Spanish because Renata follows the picture."""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

COLS = "abcdefghij"
ROWS = 26
X = {c: i + (1.2 if i >= 5 else 0) for i, c in enumerate(COLS)}   # the center gap


def xy(col, row):
    return X[col], -row


# Pico pins on the right side, row 1 at the USB end: pin 40 down to pin 21
RIGHT = ["VBUS", "VSYS", "GND", "3V3_EN", "3V3", "ADC_VREF", "GP28", "GND", "GP27", "GP26",
         "RUN", "GP22", "GND", "GP21", "GP20", "GP19", "GP18", "GND", "GP17", "GP16"]

fig, ax = plt.subplots(figsize=(9, 11))
ax.set_aspect("equal"); ax.axis("off")
ax.add_patch(FancyBboxPatch((-1.2, -ROWS - 0.8), 12.6, ROWS + 0.4, boxstyle="round,pad=0.2",
                            fc="#f4f1ea", ec="#bbb"))
for c in COLS:
    ax.text(X[c], 0.2, c, ha="center", fontsize=10, color="#555")
for r in range(1, ROWS + 1):
    ax.text(-0.9, -r, str(r), ha="center", va="center", fontsize=7, color="#777")
    for c in COLS:
        ax.add_patch(Rectangle((X[c] - 0.13, -r - 0.13), 0.26, 0.26, color="#9a9a9a"))

# the Pico over columns c..h, rows 1..20
ax.add_patch(FancyBboxPatch((X["c"] - 0.35, -20.5), X["h"] - X["c"] + 0.7, 20.1, boxstyle="round,pad=0.05",
                            fc="#2e7d32", ec="#1b5e20", alpha=0.92))
ax.add_patch(Rectangle(((X["c"] + X["h"]) / 2 - 0.6, 0.0), 1.2, 0.7, fc="#bdbdbd", ec="#555"))
ax.text((X["c"] + X["h"]) / 2, 1.0, "USB (cable siempre puesto)", ha="center", fontsize=9)
ax.text((X["c"] + X["h"]) / 2, -10.5, "Raspberry\nPi Pico", ha="center", va="center", color="white", fontsize=12)
for i, name in enumerate(RIGHT, start=1):
    ax.plot(*xy("h", i), "o", color="#d4af37", ms=5)
    ax.plot(*xy("c", i), "o", color="#d4af37", ms=5)
    weight = "bold" if name in ("GP20", "GP21") else "normal"
    color = "#c62828" if name == "GND" and i == 13 else ("#000" if weight == "bold" else "#e8f5e9")
    ax.text(X["h"] - 0.35, -i, name, ha="right", va="center", fontsize=7, color=color, fontweight=weight)

# R1: j14 (GP21) to j24 (free row)
x1, y1 = xy("j", 14); x2, y2 = xy("j", 24)
ax.plot([x1, x1 + 0.7, x2 + 0.7, x2], [y1, y1, y2, y2], color="#777", lw=2)
ax.add_patch(Rectangle((x1 + 0.45, y1 - 5.5), 0.5, 3.0, fc="#e0c9a6", ec="#8d6e63", zorder=3))
for k, band in enumerate(["#ef6c00", "#ef6c00", "#6d4c41", "#c9a227"]):
    ax.add_patch(Rectangle((x1 + 0.45, y1 - 2.9 - k * 0.6), 0.5, 0.25, color=band, zorder=4))
ax.plot([x1, x2], [y1, y2], "o", color="#8d6e63", ms=7, zorder=5)
ax.text(x1 + 1.2, y1 - 4.0, "Resistencia 330 Ω\nnaranja, naranja,\ncafé, dorado\n\npata de arriba: j14\npata de abajo: j24",
        va="center", fontsize=9)

# verification wire: i24 to j15 (GP20). The Pico board covers column i in its rows: only j is free there.
x3, y3 = xy("i", 24); x4, y4 = xy("j", 15)
ax.plot([x3, x3, x4 - 0.35, x4], [y3, y4 - 0.45, y4 - 0.45, y4], color="#1565c0", lw=3, solid_capstyle="round")
ax.plot([x3, x4], [y3, y4], "o", color="#1565c0", ms=7)
ax.text(X["f"] - 0.3, -23.6, "Cable: i24 a j15", color="#1565c0", fontsize=9, ha="left")

ax.annotate("GND: aquí NO va nada", xy=(X["j"] + 0.2, -13), xytext=(X["j"] + 1.2, -12.2),
            fontsize=8, color="#c62828", arrowprops=dict(arrowstyle="->", color="#c62828"))
# the board is wider than its pins: it covers columns b and i in its rows
ax.add_patch(Rectangle((X["b"] - 0.3, -20.5), X["c"] - X["b"] + 0.3, 20.1, color="#2e7d32", alpha=0.35))
ax.add_patch(Rectangle((X["h"], -20.5), X["i"] - X["h"] + 0.3, 20.1, color="#2e7d32", alpha=0.35))
ax.text(X["i"], -21.6, "la placa tapa b e i:\nen sus filas solo\nquedan libres a y j", fontsize=7, color="#2e7d32", ha="center")
ax.set_xlim(-1.6, 15.5); ax.set_ylim(-ROWS - 1.2, 1.6)
ax.set_title("Etapa 2: el reloj\nCon el USB desenchufado del lado del adaptador", fontsize=12)
out = Path(__file__).with_name("etapa2.png")
fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
print(out)
