"""Draws the input stage one step at a time: a picture per piece, in the order Renata puts it on the board.

Reuses the layout and the SPICE check of draw_input_stage_breadboard, so the steps can never drift from the verified
board. What is already placed is drawn pale, the piece of the step in color, and what comes later is not drawn at all.
Saves pasos/paso_NN.png and the whole set as etapa_entrada_pasos.pdf. Labels in Spanish, described by shape and never
by component name, because Renata follows the picture on the bench.

    .venv/bin/python docs/armado/draw_input_stage_steps.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import Arc, FancyBboxPatch, Rectangle  # noqa: E402

import draw_input_stage_breadboard as base  # noqa: E402
from draw_input_stage_breadboard import COLS, GND, LAYOUT, PINS, ROWS, VNEG, VPOS, X, hole_xy, rail_y  # noqa: E402

HERE = Path(__file__).resolve().parent
PALE = "#d2cec7"
WIRE = "#1565c0"
BODY_R, BODY_C = "#e0c9a6", "#f9a825"


def wire_of(text):
    """The WIRES entry whose description starts with text, as (a, b)."""
    for a, b, what in base.WIRES:
        if what.startswith(text):
            return a, b
    raise KeyError(text)


# Each step: (kind, payload, title, the sentence Renata reads).
STEPS = [
    ("chip", None, "La piecita negra de ocho patitas",
     "Pisando la zanja, patitas en las filas 14, 15, 16 y 17.\nLa muesca de media luna mira hacia el lado del 1."),
    ("part", "C1", "Lentejita con 104 impreso",
     "Una patita en b22 y la otra en b20.\nNo tiene lado, da igual cuál patita va en cuál."),
    ("part", "R1", "Tubito de la tira que dice 1M",
     "Una patita en c20 y la otra en c24.\nNo tiene lado."),
    ("part", "R4", "Tubito de la tira que dice 1K",
     "Una patita en c15 y la otra en c11.\nNo tiene lado."),
    ("part", "R5", "Tubito de la tira que dice 4K7",
     "Una patita en h20 y la otra en h24.\nNo tiene lado."),
    ("part", "C5", "Lentejita con 102 impreso",
     "Una patita en i24 y la otra en i26.\nNo tiene lado."),
    ("part", "C3", "La de 2.2 uF (esta todavia no llega)",
     "Va de h15 a h11. Deja el hueco y sigue, o pon en su lugar\nla barrilito de 10 uF: esa SI tiene lado, la raya va en h11."),
    ("wire", wire_of("entrada al pin 3"), "Cable corto", "De d20 a d16."),
    ("wire", wire_of("salida del pin 1"), "Cable", "De c14 a g20."),
    ("wire", wire_of("filtro al pin 5"), "Cable", "De g24 a g17."),
    ("wire", wire_of("pin 7 con pin 6"), "Cable cortito", "De g15 a g16."),
    ("wire", wire_of("R1 a tierra"), "Cable a una raya del borde",
     "De a24 a la raya de tierra de abajo."),
    ("wire", wire_of("R4 a tierra"), "Cable a una raya del borde",
     "De a11 a la raya de tierra de arriba."),
    ("wire", wire_of("C5 a tierra"), "Cable a una raya del borde",
     "De j26 a la raya de tierra de abajo."),
    ("wire", wire_of("pin 8 a +9 V"), "Cable a una raya del borde",
     "De g14 a la raya de +9 de arriba."),
    ("wire", wire_of("pin 4 a -9 V"), "Cable a una raya del borde",
     "De d17 a la raya de -9 de abajo."),
    ("gndlink", None, "Cable largo que une las dos rayas de tierra",
     "De la raya de tierra de arriba a la de abajo.\nUna sola vez, en cualquier punto de cada raya."),
    ("dec", None, "Dos lentejitas mas con 104 impreso",
     "Una entre la raya de +9 y la de tierra de arriba.\nLa otra entre la raya de -9 y la de tierra de abajo."),
    ("pot", None, "La perilla que gira, por fuera de la tabla",
     "Sus tres patitas con tres cables: una punta a a14,\nla del medio a b14, la otra punta a d15."),
    ("ext", None, "La guitarra entra y la senal sale",
     "Vivo de la guitarra a a22, su malla a una raya de tierra.\nSalida j11 al cable de la tarjeta, su malla a tierra."),
    ("bat", None, "Las cajitas con pilas, AL FINAL Y APAGADAS",
     "Cajita 1: rojo a la raya de +9, negro a la de tierra.\nCajita 2: rojo a la raya de tierra, negro a la de -9."),
]


def draw_board(ax):
    ax.add_patch(FancyBboxPatch((-1.6, -ROWS - 0.6), 13.4, ROWS + 0.2, boxstyle="round,pad=0.25",
                                fc="#f6f4ef", ec="#bbb"))
    for c in COLS:
        ax.text(X[c], 0.35, c, ha="center", fontsize=9, color="#666")
    for r in range(1, ROWS + 1):
        big = r % 5 == 0 or r in (1, 11, 14, 15, 16, 17, 20, 22, 24, 26)
        for label_x in (-1.1, 11.3):
            ax.text(label_x, -r, str(r), ha="center", va="center", fontsize=8 if big else 6.5,
                    color="#222" if big else "#999", fontweight="bold" if big else "normal")
        for c in COLS:
            ax.add_patch(Rectangle((X[c] - 0.12, -r - 0.12), 0.24, 0.24, color="#9a9a9a"))
    for y, color, text in ((base.RAIL_Y[VPOS], "#c62828", "raya de +9"),
                           (base.RAIL_Y["gnd_arriba"], "#000000", "raya de tierra"),
                           (base.RAIL_Y["gnd_abajo"], "#000000", "raya de tierra"),
                           (base.RAIL_Y[VNEG], "#1565c0", "raya de -9")):
        ax.plot([-2.6, 13.2], [y, y], color=color, lw=2.2, solid_capstyle="round")
        ax.text(13.4, y, text, va="center", fontsize=8.5, color=color)


def vertical(ax, x, y1, y2, color, lw):
    lo, hi = sorted((y1, y2))
    crossed = sorted(y for y in base.RAIL_Y.values() if lo + 0.3 < y < hi - 0.3)
    cuts = [lo] + [c for y in crossed for c in (y - 0.3, y + 0.3)] + [hi]
    for a, b in zip(cuts[::2], cuts[1::2]):
        ax.plot([x, x], [a, b], color=color, lw=lw, solid_capstyle="round", zorder=6)
    for y in crossed:
        ax.add_patch(Arc((x, y), 0.6, 0.6, theta1=-90, theta2=90, color=color, lw=lw, zorder=6))


def draw_wire(ax, a, b, color, lw=2.4):
    xa, ya = hole_xy(a) if isinstance(a, tuple) else (None, None)
    xb, yb = hole_xy(b) if isinstance(b, tuple) else (None, None)
    if xa is None:
        xa, ya = xb, rail_y(a, b[1])
    if xb is None:
        xb, yb = xa, rail_y(b, a[1])
    if abs(ya - yb) < 0.01:
        ax.plot([xa, xb], [ya, yb], color=color, lw=lw, solid_capstyle="round", zorder=6)
    elif abs(xa - xb) < 0.01:
        vertical(ax, xa, ya, yb, color, lw)
    else:
        ymid = min(ya, yb) - 0.5
        vertical(ax, xa, ya, ymid, color, lw)
        ax.plot([xa, xb], [ymid, ymid], color=color, lw=lw, solid_capstyle="round", zorder=6)
        vertical(ax, xb, ymid, yb, color, lw)
    ax.plot([xa, xb], [ya, yb], "o", color=color, ms=6, zorder=7)


def draw_chip(ax, live):
    fc, ec, txt = ("#2b2b2b", "#111", "white") if live else (PALE, "#bbb", "#f6f4ef")
    x0, x1 = X["e"], X["f"]
    ax.add_patch(FancyBboxPatch((x0 - 0.45, -17.5), x1 - x0 + 0.9, 4.0, boxstyle="round,pad=0.05", fc=fc, ec=ec,
                                zorder=3))
    ax.add_patch(Rectangle(((x0 + x1) / 2 - 0.35, -13.7), 0.7, 0.25, fc="#f6f4ef", ec="none", zorder=4))
    for pin, (col, row) in PINS.items():
        ax.plot(X[col], -row, "o", color="#d4af37" if live else PALE, ms=6, zorder=4)
        ax.text(X[col] + (0.42 if col == "e" else -0.42), -row, str(pin), ha="center", va="center",
                fontsize=7.5, color=txt, zorder=5)


def draw_part(ax, name, live):
    holes = LAYOUT[name]
    (x1, y1), (x2, y2) = hole_xy(holes[0]), hole_xy(holes[1])
    leg = "#8d6e63" if live else PALE
    ax.plot([x1, x2], [y1, y2], color=leg, lw=1.6, zorder=2)
    ax.plot([x1, x2], [y1, y2], "o", color=leg, ms=6.5, zorder=5)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    if name.startswith("R"):
        fc = BODY_R if live else PALE
        ax.add_patch(FancyBboxPatch((cx - 0.22, cy - 1.0), 0.44, 2.0, boxstyle="round,pad=0.06",
                                    fc=fc, ec=leg, zorder=3))
    else:
        fc = BODY_C if live else PALE
        ax.add_patch(FancyBboxPatch((cx - 0.26, cy - 0.55), 0.52, 1.1, boxstyle="round,pad=0.08",
                                    fc=fc, ec=leg, zorder=3))


def draw_gndlink(ax, live):
    color = "#000000" if live else PALE
    vertical(ax, -2.6, base.RAIL_Y["gnd_arriba"], base.RAIL_Y["gnd_abajo"], color, 2.4 if live else 1.8)


def draw_dec(ax, live):
    leg = "#8d6e63" if live else PALE
    fc = BODY_C if live else PALE
    for rail in (VPOS, VNEG):
        y = base.RAIL_Y[rail]
        gy = base.RAIL_Y["gnd_arriba"] if rail == VPOS else base.RAIL_Y["gnd_abajo"]
        ax.plot([12.4, 12.4], [y, gy], color=leg, lw=1.6, zorder=2)
        ax.add_patch(FancyBboxPatch((12.14, (y + gy) / 2 - 0.22), 0.52, 0.44, boxstyle="round,pad=0.08",
                                    fc=fc, ec=leg, zorder=3))


def draw_pot(ax, live):
    color = "#6a1b9a" if live else PALE
    draw_wire(ax, ("b", 14), ("a", 14), color, 2.4 if live else 1.8)
    for hole in (("a", 14), ("b", 14), ("d", 15)):
        x, y = hole_xy(hole)
        ax.plot(x, y, "o", color=color, ms=7, zorder=7)
    if live:
        ax.annotate("la perilla\nva por fuera", xy=(X["a"], -14), xytext=(X["a"] - 3.4, -9.5), fontsize=9,
                    ha="center", color=color, arrowprops=dict(arrowstyle="->", color=color), zorder=9)


def draw_ext(ax, live):
    color = "#2e7d32" if live else PALE
    for hole, text in base.EXTERNAL:
        x, y = hole_xy(hole)
        side = -1 if hole[0] in "abcde" else 1
        ax.plot(x, y, "o", color=color, ms=7, zorder=7)
        if live:
            ax.annotate(text, xy=(x, y), xytext=(x + side * 3.4, y + 2.0), fontsize=9, ha="center",
                        arrowprops=dict(arrowstyle="->", color=color), color=color)


def draw_bat(ax, live):
    """Box 1 sits above the top rails, box 2 below the bottom ones. Red always goes to the more positive rail."""
    if not live:
        return
    boxes = [("cajita 1", base.RAIL_Y[VPOS] + 2.6, base.RAIL_Y[VPOS], base.RAIL_Y["gnd_arriba"]),
             ("cajita 2", base.RAIL_Y[VNEG] - 2.6, base.RAIL_Y["gnd_abajo"], base.RAIL_Y[VNEG])]
    for label, by, red_y, black_y in boxes:
        bx = -6.0
        ax.add_patch(FancyBboxPatch((bx - 1.0, by - 0.45), 2.0, 0.9, boxstyle="round,pad=0.1",
                                    fc="#37474f", ec="#111", zorder=5))
        ax.text(bx, by, label, color="white", ha="center", va="center", fontsize=8.5, zorder=6)
        for lead_x, lead_y, color in ((bx + 0.45, red_y, "#c62828"), (bx - 0.45, black_y, "#111111")):
            ax.plot([lead_x, lead_x, -2.5], [by, lead_y, lead_y], color=color, lw=2.4, zorder=5,
                    solid_capstyle="round")
            ax.plot([-2.5], [lead_y], "o", color=color, ms=6, zorder=6)
        ax.text(bx - 1.3, red_y, "rojo", ha="right", va="center", fontsize=8, color="#c62828")
        ax.text(bx - 1.3, black_y, "negro", ha="right", va="center", fontsize=8, color="#111111")


DRAW = {"chip": lambda ax, live, p: draw_chip(ax, live),
        "part": lambda ax, live, p: draw_part(ax, p, live),
        "wire": lambda ax, live, p: draw_wire(ax, p[0], p[1], WIRE if live else PALE, 2.4 if live else 1.8),
        "gndlink": lambda ax, live, p: draw_gndlink(ax, live),
        "dec": lambda ax, live, p: draw_dec(ax, live),
        "pot": lambda ax, live, p: draw_pot(ax, live),
        "ext": lambda ax, live, p: draw_ext(ax, live),
        "bat": lambda ax, live, p: draw_bat(ax, live)}


def page(i):
    kind, payload, title, sentence = STEPS[i]
    fig, ax = plt.subplots(figsize=(10, 14))
    ax.set_aspect("equal")
    ax.axis("off")
    draw_board(ax)
    for k, p, _, _ in STEPS[:i]:
        DRAW[k](ax, False, p)
    DRAW[kind](ax, True, payload)
    ax.set_xlim(-9.6, 16.0)
    ax.set_ylim(-ROWS - 8.6, 6.4)
    ax.text(4.4, 5.6, f"Paso {i + 1} de {len(STEPS)}", ha="center", fontsize=15, fontweight="bold")
    ax.text(4.4, 4.2, title, ha="center", fontsize=13, color="#1565c0")
    ax.text(4.4, -ROWS - 4.2, sentence, ha="center", va="top", fontsize=13, linespacing=1.6)
    ax.text(4.4, -ROWS - 8.1, "Lo gris claro ya esta puesto. Cuenta las filas desde la punta donde la tabla dice 1.",
            ha="center", fontsize=8.5, color="#777")
    return fig


def main():
    base.check()
    out = HERE / "pasos"
    out.mkdir(exist_ok=True)
    pdf_path = HERE / "etapa_entrada_pasos.pdf"
    with PdfPages(pdf_path) as pdf:
        for i in range(len(STEPS)):
            fig = page(i)
            png = out / f"paso_{i + 1:02d}.png"
            fig.savefig(png, dpi=130, bbox_inches="tight", facecolor="white")
            pdf.savefig(fig, bbox_inches="tight", facecolor="white")
            plt.close(fig)
            print(png)
    print(pdf_path)


if __name__ == "__main__":
    main()
