"""Draws the input stage one step at a time: a picture per piece, in the order Renata puts it on the board.

Reuses the layout and the SPICE check of draw_input_stage_breadboard, so the steps can never drift from the verified
board. What is already placed is drawn pale, the piece of the step in color, and what comes later is not drawn at all.
The four edge strips are drawn where the MB-102 really has them, running down the two long sides, so the picture can
be laid next to the board and read hole by hole. Saves pasos/paso_NN.png and the set as etapa_entrada_pasos.pdf.
Labels in Spanish, described by shape and never by component name, because Renata follows the picture on the bench.

    .venv/bin/python docs/armado/draw_input_stage_steps.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import Arc, FancyBboxPatch, Rectangle  # noqa: E402

import draw_input_stage_breadboard as base  # noqa: E402
from draw_input_stage_breadboard import COLS, GND, LAYOUT, PINS, ROWS, VNEG, VPOS, X  # noqa: E402

HERE = Path(__file__).resolve().parent
PALE = "#d2cec7"
WIRE = "#1565c0"
BODY_C = "#f9a825"

# The strips run down the long sides. On the MB-102 the left block has its blue line outside and its red line next to
# the letters, and the right block is mirrored, so naming them by the painted line is enough to tell them apart.
GND_L, VNEG_X, GND_R, VPOS_X = -3.8, -2.6, 12.8, 14.0
RAIL_X = {GND: None, VNEG: VNEG_X, VPOS: VPOS_X}
RAILS = [(GND_L, "#1565c0", "tierra"), (VNEG_X, "#c62828", "-9"),
         (GND_R, "#1565c0", "tierra"), (VPOS_X, "#c62828", "+9")]
ALL_RAIL_X = [GND_L, VNEG_X, GND_R, VPOS_X]
TOP, BOTTOM = -0.3, -ROWS - 0.7
RAIL_HOLES = [-(1 + g * 6 + k) for g in range(5) for k in range(5)]


def snap(row):
    """The strip's holes do not line up with the numbered rows, so a wire takes the nearest one."""
    return min(RAIL_HOLES, key=lambda y: abs(y + row))

BAND_COLOR = {"café": "#6d4c41", "negro": "#212121", "rojo": "#c62828", "amarillo": "#fdd835",
              "violeta": "#7b1fa2", "dorada": "#c9a227", "verde": "#2e7d32"}
BANDS5 = {"R1": ["café", "negro", "negro", "amarillo", "café"],
          "R4": ["café", "negro", "negro", "café", "café"],
          "R5": ["amarillo", "violeta", "negro", "café", "café"]}
BANDS4 = {"R1": ["café", "negro", "verde", "dorada"],
          "R4": ["café", "negro", "rojo", "dorada"],
          "R5": ["amarillo", "violeta", "rojo", "dorada"]}
MARK = {"C1": "104", "C5": "102"}


def hole_xy(hole):
    return X[hole[0]], -hole[1]


def rail_x(rail, col):
    """Ground has a strip on each side; a hole uses the one on its own half of the board."""
    if rail == GND:
        return GND_L if col in "abcde" else GND_R
    return RAIL_X[rail]


def wire_of(text):
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
    ("part", "C3", "El barrilito de 10 µF",
     "Va de h15 a h11, y SÍ tiene lado: la patita del lado\nde la raya impresa va en h15, la otra en h11."),
    ("wire", wire_of("entrada al pin 3"), "Cable corto", "De d20 a d16."),
    ("wire", wire_of("salida del pin 1"), "Cable", "De c14 a g20."),
    ("wire", wire_of("filtro al pin 5"), "Cable", "De g24 a g17."),
    ("wire", wire_of("pin 7 con pin 6"), "Cable cortito", "De g15 a g16."),
    ("wire", wire_of("R1 a tierra"), "Cable a una tira del borde",
     "De a24 a la tira AZUL del lado de las letras a b c d e.\nSirve cualquier agujerito de esa tira: usa uno cerca de la fila 24."),
    ("wire", wire_of("R4 a tierra"), "Cable a una tira del borde",
     "De a11 a esa misma tira azul.\nCualquier agujerito de ella: usa uno cerca de la fila 11."),
    ("wire", wire_of("C5 a tierra"), "Cable a una tira del borde",
     "De j26 a la tira AZUL del lado de las letras f g h i j.\nCualquier agujerito de ella: usa uno cerca de la fila 26."),
    ("wire", wire_of("pin 8 a +9 V"), "Cable a una tira del borde",
     "De g14 a la tira ROJA del lado de las letras f g h i j.\nCualquier agujerito de ella: usa uno cerca de la fila 14."),
    ("wire", wire_of("pin 4 a -9 V"), "Cable a una tira del borde",
     "De d17 a la tira ROJA del lado de las letras a b c d e.\nCualquier agujerito de ella: usa uno cerca de la fila 17."),
    ("gndlink", None, "Cable largo que une las dos tiras de tierra",
     "Un cable largo de una tira azul a la otra tira azul,\npor debajo de la tabla. Cualquier agujerito de cada una."),
    ("dec", None, "Dos lentejitas más con 104 impreso",
     "Una con una patita en la tira roja y la otra en la azul\ndel mismo costado. Lo mismo con la otra, en el otro costado."),
    ("pot", None, "La perilla que gira, por fuera de la tabla",
     "Sus tres patitas con tres cables: una punta a a14,\nla del medio a b14, la otra punta a d15."),
    ("ext", None, "La guitarra entra y la señal sale",
     "Vivo de la guitarra a a22, su malla a una tira de tierra.\nSalida j11 al cable de la tarjeta, su malla a tierra."),
    ("bat", None, "Las cajitas con pilas, AL FINAL Y APAGADAS",
     "Cajita 1: rojo a la tira de +9, negro a la tierra de ese lado.\n"
     "Cajita 2: rojo a la tierra del otro lado, negro a la de -9."),
]


def draw_board(ax):
    ax.add_patch(FancyBboxPatch((-1.2, -ROWS - 0.6), 12.8, ROWS + 0.2, boxstyle="round,pad=0.25",
                                fc="#f6f4ef", ec="#bbb"))
    for c in COLS:
        ax.text(X[c], 0.3, c, ha="center", fontsize=10, color="#444")
    for r in range(1, ROWS + 1):
        big = r % 5 == 0 or r in (1, 11, 14, 15, 16, 17, 20, 22, 24, 26)
        for label_x in (-0.75, 11.15):
            ax.text(label_x, -r, str(r), ha="center", va="center", fontsize=8 if big else 6.5,
                    color="#222" if big else "#999", fontweight="bold" if big else "normal", zorder=8,
                    bbox=dict(fc="#f6f4ef", ec="none", pad=0.6))
        for c in COLS:
            ax.add_patch(Rectangle((X[c] - 0.12, -r - 0.12), 0.24, 0.24, color="#9a9a9a"))
    for x, color, text in RAILS:
        ax.plot([x, x], [TOP, BOTTOM], color=color, lw=2.4, solid_capstyle="round")
        for y in RAIL_HOLES:
            ax.add_patch(Rectangle((x - 0.12, y - 0.12), 0.24, 0.24, color="#9a9a9a", zorder=3))
        ax.text(x, 0.5, text, ha="center", va="bottom", fontsize=9, color=color, rotation=90)


def horizontal(ax, y, x1, x2, color, lw):
    """A horizontal run that hops over any strip it only crosses, so a crossing never looks like a joint."""
    lo, hi = sorted((x1, x2))
    crossed = sorted(x for x in ALL_RAIL_X if lo + 0.3 < x < hi - 0.3)
    cuts = [lo] + [c for x in crossed for c in (x - 0.3, x + 0.3)] + [hi]
    for a, b in zip(cuts[::2], cuts[1::2]):
        ax.plot([a, b], [y, y], color=color, lw=lw, solid_capstyle="round", zorder=6)
    for x in crossed:
        ax.add_patch(Arc((x, y), 0.6, 0.6, theta1=0, theta2=180, color=color, lw=lw, zorder=6))


def draw_wire(ax, a, b, color, lw=2.4):
    """Hole to hole turns in the gap between rows; hole to strip goes straight out sideways."""
    if isinstance(a, str) or isinstance(b, str):
        rail, hole = (a, b) if isinstance(a, str) else (b, a)
        x, y = hole_xy(hole)
        rx, ry = rail_x(rail, hole[0]), snap(hole[1])
        horizontal(ax, y, x, rx, color, lw)
        if abs(ry - y) > 0.01:
            ax.plot([rx, rx], [y, ry], color=color, lw=lw, solid_capstyle="round", zorder=6)
        ax.plot([x, rx], [y, ry], "o", color=color, ms=6, zorder=7)
        return
    (xa, ya), (xb, yb) = hole_xy(a), hole_xy(b)
    if abs(xa - xb) < 0.01:
        ax.plot([xa, xb], [ya, yb], color=color, lw=lw, solid_capstyle="round", zorder=6)
    else:
        ymid = min(ya, yb) - 0.5
        ax.plot([xa, xa, xb, xb], [ya, ymid, ymid, yb], color=color, lw=lw, solid_capstyle="round", zorder=6)
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
    (x1, y1), (x2, y2) = hole_xy(LAYOUT[name][0]), hole_xy(LAYOUT[name][1])
    leg = "#8d6e63" if live else PALE
    ax.plot([x1, x2], [y1, y2], color=leg, lw=1.6, zorder=2)
    ax.plot([x1, x2], [y1, y2], "o", color=leg, ms=6.5, zorder=5)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    if name.startswith("R"):
        ax.add_patch(FancyBboxPatch((cx - 0.24, cy - 1.0), 0.48, 2.0, boxstyle="round,pad=0.06",
                                    fc="#cfe0f0" if live else PALE, ec=leg, zorder=3))
        if live:
            for k, ring in enumerate(BANDS5[name]):
                y = cy + [0.72, 0.45, 0.18, -0.09, -0.72][k]
                ax.add_patch(Rectangle((cx - 0.3, y - 0.09), 0.6, 0.18, color=BAND_COLOR[ring], zorder=4))
    else:
        ax.add_patch(FancyBboxPatch((cx - 0.3, cy - 0.6), 0.6, 1.2, boxstyle="round,pad=0.08",
                                    fc=BODY_C if live else PALE, ec=leg, zorder=3))
        if live and name in MARK:
            ax.text(cx, cy, MARK[name], ha="center", va="center", fontsize=7, zorder=4, color="#333")


def draw_gndlink(ax, live):
    color = "#1565c0" if live else PALE
    y, top = -ROWS - 1.8, snap(29)
    ax.plot([GND_L, GND_L, GND_R, GND_R], [top, y, y, top], color=color, lw=2.4 if live else 1.8,
            solid_capstyle="round", zorder=6)
    ax.plot([GND_L, GND_R], [top, top], "o", color=color, ms=6, zorder=7)


def draw_dec(ax, live):
    leg = "#8d6e63" if live else PALE
    for x_a, x_b in ((VPOS_X, GND_R), (VNEG_X, GND_L)):
        y = snap(26)
        ax.plot([x_a, x_b], [y, y], color=leg, lw=1.6, zorder=2)
        ax.plot([x_a, x_b], [y, y], "o", color=leg, ms=6.5, zorder=5)
        cx = (x_a + x_b) / 2
        ax.add_patch(FancyBboxPatch((cx - 0.3, y - 0.45), 0.6, 0.9, boxstyle="round,pad=0.08",
                                    fc=BODY_C if live else PALE, ec=leg, zorder=3))
        if live:
            ax.text(cx, y - 1.1, "104", ha="center", va="top", fontsize=8, color="#555")


def draw_pot(ax, live):
    color = "#6a1b9a" if live else PALE
    draw_wire(ax, ("b", 14), ("a", 14), color, 2.4 if live else 1.8)
    for hole in (("a", 14), ("b", 14), ("d", 15)):
        x, y = hole_xy(hole)
        ax.plot(x, y, "o", color=color, ms=7, zorder=7)
    if live:
        ax.annotate("la perilla\nva por fuera", xy=(X["a"], -14), xytext=(-6.6, -10.0), fontsize=10,
                    ha="center", color=color, arrowprops=dict(arrowstyle="->", color=color), zorder=9)


def draw_ext(ax, live):
    color = "#2e7d32" if live else PALE
    for hole, text in base.EXTERNAL:
        x, y = hole_xy(hole)
        ax.plot(x, y, "o", color=color, ms=7, zorder=7)
        if live:
            tx = -6.6 if hole[0] in "abcde" else 18.0
            ax.annotate(text, xy=(x, y), xytext=(tx, y + 2.2), fontsize=9.5, ha="center",
                        arrowprops=dict(arrowstyle="->", color=color), color=color)


def draw_bat(ax, live):
    """Box 1 feeds the two strips on the f..j side, box 2 the two on the a..e side."""
    if not live:
        return
    boxes = [("cajita 1", 15.6, VPOS_X, GND_R), ("cajita 2", -5.4, GND_L, VNEG_X)]
    for label, bx, red_x, black_x in boxes:
        by = -ROWS - 4.2
        ax.add_patch(FancyBboxPatch((bx - 1.1, by - 0.5), 2.2, 1.0, boxstyle="round,pad=0.1",
                                    fc="#37474f", ec="#111", zorder=5))
        ax.text(bx, by, label, color="white", ha="center", va="center", fontsize=8.5, zorder=6)
        for k, (lead_x, color, name) in enumerate(((red_x, "#c62828", "rojo"), (black_x, "#111111", "negro"))):
            ax.plot([bx, lead_x, lead_x], [by + 0.5, by + 0.5, snap(28)], color=color, lw=2.4, zorder=5,
                    solid_capstyle="round")
            ax.plot([lead_x], [snap(28)], "o", color=color, ms=6, zorder=6)
            ax.text(lead_x + 0.5, BOTTOM - 1.2 - k * 0.9, name, ha="left", va="center", fontsize=9, color=color)


def zoom_tube(ax, cx, cy, rings, title):
    """One little tube drawn big and lying down, with the name of each ring written under it."""
    ax.plot([cx - 2.9, cx + 2.9], [cy, cy], color="#8d6e63", lw=2.0, zorder=2)
    ax.add_patch(FancyBboxPatch((cx - 2.1, cy - 0.62), 4.2, 1.24, boxstyle="round,pad=0.12",
                                fc="#cfe0f0", ec="#8d6e63", zorder=3))
    offsets = [-1.6, -1.1, -0.6, -0.1, 1.5] if len(rings) == 5 else [-1.6, -1.0, -0.4, 1.5]
    for dx, ring in zip(offsets, rings):
        ax.add_patch(Rectangle((cx + dx - 0.16, cy - 0.72), 0.32, 1.44, color=BAND_COLOR[ring], zorder=4))
        ax.text(cx + dx, cy - 0.95, ring, rotation=90, ha="center", va="top", fontsize=8.5, color="#333")
    ax.text(cx, cy + 1.05, title, ha="center", fontsize=9.5, color="#555")


def zoom_disc(ax, cx, cy, mark):
    ax.plot([cx - 0.6, cx - 0.6], [cy - 1.9, cy - 0.7], color="#8d6e63", lw=2.0, zorder=2)
    ax.plot([cx + 0.6, cx + 0.6], [cy - 1.9, cy - 0.7], color="#8d6e63", lw=2.0, zorder=2)
    ax.add_patch(FancyBboxPatch((cx - 1.3, cy - 0.9), 2.6, 2.2, boxstyle="round,pad=0.2",
                                fc=BODY_C, ec="#8d6e63", zorder=3))
    ax.text(cx, cy + 0.2, mark, ha="center", va="center", fontsize=17, color="#333", zorder=4)
    ax.text(cx, cy - 2.4, "impreso en la cara", ha="center", va="top", fontsize=9.5, color="#555")


def zoom_barrel(ax, cx, cy):
    """The little barrel drawn big, with its printed stripe on the h15 side."""
    ax.add_patch(FancyBboxPatch((cx - 1.3, cy - 1.8), 2.6, 3.6, boxstyle="round,pad=0.2",
                                fc="#37474f", ec="#111", zorder=3))
    ax.add_patch(Rectangle((cx - 1.45, cy - 1.9), 0.75, 3.8, color="#cfd8dc", zorder=4))
    for k in range(3):
        ax.text(cx - 1.08, cy + 0.9 - k * 0.9, "-", ha="center", va="center", fontsize=15, color="#37474f", zorder=5)
    ax.text(cx + 0.35, cy, "10", ha="center", va="center", fontsize=13, color="white", zorder=5)
    ax.plot([cx - 0.6, cx - 0.6, cx - 2.1], [cy - 1.9, cy - 2.9, cy - 3.3], color="#8d6e63", lw=2.0, zorder=2)
    ax.plot([cx + 0.6, cx + 0.6, cx + 1.9], [cy - 1.9, cy - 2.9, cy - 3.3], color="#8d6e63", lw=2.0, zorder=2)
    ax.text(cx - 2.1, cy - 3.5, "esta patita\nva en h15", ha="center", va="top", fontsize=9.5, color="#c62828")
    ax.text(cx + 1.9, cy - 3.5, "esta patita\nva en h11", ha="center", va="top", fontsize=9.5, color="#555")
    ax.annotate("la raya\nimpresa", xy=(cx - 1.1, cy + 1.2), xytext=(cx - 1.0, cy + 3.0), fontsize=9.5,
                ha="center", color="#c62828", arrowprops=dict(arrowstyle="->", color="#c62828"))


def draw_zoom(ax, name):
    cx = -7.4
    if name in BANDS5:
        zoom_tube(ax, cx, -9.0, BANDS5[name], "si tiene 5 rayitas")
        zoom_tube(ax, cx, -17.0, BANDS4[name], "si tiene 4 rayitas")
        ax.text(cx, -4.8, "así se ve\nel tubito de\neste paso", ha="center", fontsize=10, color="#1565c0")
    elif name == "C3":
        zoom_barrel(ax, cx, -13.0)
        ax.text(cx, -6.0, "así se ve\nel barrilito", ha="center", fontsize=10, color="#1565c0")
    elif name in MARK:
        zoom_disc(ax, cx, -11.0, MARK[name])
        ax.text(cx, -5.6, "así se ve\nla lentejita de\neste paso", ha="center", fontsize=10, color="#1565c0")


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
    fig, ax = plt.subplots(figsize=(11, 13))
    ax.set_aspect("equal")
    ax.axis("off")
    draw_board(ax)
    for k, p, _, _ in STEPS[:i]:
        DRAW[k](ax, False, p)
    DRAW[kind](ax, True, payload)
    if kind == "part":
        draw_zoom(ax, payload)
    ax.set_xlim(-11.0, 21.0)
    ax.set_ylim(-ROWS - 13.5, 6.0)
    ax.text(5.1, 5.2, f"Paso {i + 1} de {len(STEPS)}", ha="center", fontsize=16, fontweight="bold")
    ax.text(5.1, 3.6, title, ha="center", fontsize=13.5, color="#1565c0")
    ax.text(5.1, -ROWS - 6.2, sentence, ha="center", va="top", fontsize=13, linespacing=1.6)
    ax.text(5.1, -ROWS - 10.4, "Lo gris claro ya está puesto. Cuenta las filas desde la punta donde la tabla dice 1.\n"
            "Los agujeritos de las cuatro tiras de los bordes no coinciden con los números: toda una tira es\n"
            "un mismo punto, así que en ellas sirve cualquier agujerito.",
            ha="center", va="top", fontsize=8.5, color="#777", linespacing=1.5)
    return fig


def main():
    base.check()
    out = HERE / "pasos"
    out.mkdir(exist_ok=True)
    with PdfPages(HERE / "etapa_entrada_pasos.pdf") as pdf:
        for i in range(len(STEPS)):
            fig = page(i)
            fig.savefig(out / f"paso_{i + 1:02d}.png", dpi=130, bbox_inches="tight", facecolor="white")
            pdf.savefig(fig, bbox_inches="tight", facecolor="white")
            plt.close(fig)
    print(f"{len(STEPS)} pasos en {out} y en {HERE / 'etapa_entrada_pasos.pdf'}")


if __name__ == "__main__":
    main()
