"""Draws the breadboard layout of the ±9 V input stage, and checks it against spice/netlists/input_stage.cir.

The layout lives in LAYOUT as holes on the board. Before drawing, the script derives the nodes from the board's own
connectivity (the five holes of a row are one node, and the rails are one node each), and verifies that the resulting
circuit is the same one the subcircuit input_stage_split simulates. A wire in the wrong hole fails here, not on the
bench. Saves etapa_entrada_protoboard.png next to this script. Labels in Spanish because Renata follows the picture.

    .venv/bin/python docs/armado/draw_input_stage_breadboard.py
"""
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Arc, FancyBboxPatch, Rectangle  # noqa: E402

HERE = Path(__file__).resolve().parent
NETLIST = HERE.parent.parent / "spice" / "netlists" / "input_stage.cir"

COLS = "abcdefghij"
ROWS = 30
VPOS, VNEG, GND = "riel +9", "riel -9", "riel tierra"

# The TL072 straddles the channel over rows 14 to 17, notch up. Pins 1 to 4 on column e, 5 to 8 on column f.
PINS = {1: ("e", 14), 2: ("e", 15), 3: ("e", 16), 4: ("e", 17),
        5: ("f", 17), 6: ("f", 16), 7: ("f", 15), 8: ("f", 14)}

# Each part, in the order its nodes appear in the netlist. The potentiometer is outside the board: its wiper and one
# end share the hole row of the output, and the other end goes to the inverting input.
LAYOUT = {
    "C1": (("b", 22), ("b", 20)),
    "R1": (("c", 20), ("c", 24)),
    "Rpot": (("a", 14), ("d", 15)),
    "R4": (("c", 15), ("c", 11)),
    "XA": (PINS[3], PINS[2], PINS[8], PINS[4], PINS[1]),
    "R5": (("h", 20), ("h", 24)),
    "C5": (("i", 24), ("i", 26)),
    "XB": (PINS[5], PINS[6], PINS[8], PINS[4], PINS[7]),
    "C3": (("h", 15), ("h", 11)),
    "Cdec_pos": (VPOS, GND),
    "Cdec_neg": (VNEG, GND),
}

# Jumper wires: (hole, hole, what it does). Drawn and used to derive the nodes.
WIRES = [
    (("a", 24), GND, "R1 a tierra"),
    (("d", 20), ("d", 16), "entrada al pin 3"),
    (("a", 11), GND, "R4 a tierra"),
    (("c", 14), ("g", 20), "salida del pin 1 al filtro"),
    (("j", 26), GND, "C5 a tierra"),
    (("g", 24), ("g", 17), "filtro al pin 5"),
    (("g", 15), ("g", 16), "pin 7 con pin 6: seguidor"),
    (("g", 14), VPOS, "pin 8 a +9 V"),
    (("d", 17), VNEG, "pin 4 a -9 V"),
    (("b", 14), ("a", 14), "punta media del potenciómetro"),
]

# Where the outside world lands on the board.
EXTERNAL = [(("a", 22), "punta del cable de la guitarra"), (("j", 11), "al micrófono de la tarjeta USB")]


def parse_subckt(text, name):
    """Returns the parts of a .subckt as {part: (node, ...)}, ignoring values and parameters."""
    body = re.search(rf"^\.subckt\s+{name}\b.*?^\.ends", text, re.S | re.M).group(0)
    parts = {}
    for line in body.splitlines()[1:-1]:
        line = line.split("*")[0].strip()
        if not line:
            continue
        tok = line.split()
        nodes = 4 if tok[0].startswith("X") else 2
        parts[tok[0]] = tuple(tok[1:1 + nodes]) + ((tok[5],) if tok[0].startswith("X") else ())
    return parts


def derive_nodes():
    """Unions the holes the board joins on its own, then the jumper wires, and returns hole -> node id."""
    parent = {}

    def find(h):
        parent.setdefault(h, h)
        while parent[h] != h:
            parent[h] = parent[parent[h]]
            h = parent[h]
        return h

    def union(a, b):
        ra, rb = find(a), find(b)
        parent[ra] = rb

    for row in range(1, ROWS + 1):
        for side in ("abcde", "fghij"):
            for col in side[1:]:
                union((side[0], row), (col, row))
    for a, b, _ in WIRES:
        union(a, b)
    return find


def check():
    """Fails if the board does not build the same circuit as input_stage_split."""
    netlist = parse_subckt(NETLIST.read_text(), "input_stage_split")
    assert set(netlist) == set(LAYOUT), f"faltan o sobran partes: {set(netlist) ^ set(LAYOUT)}"
    find = derive_nodes()
    seen = {}
    for part, spice_nodes in netlist.items():
        board = LAYOUT[part]
        assert len(board) == len(spice_nodes), f"{part}: {len(board)} patas en la tabla y {len(spice_nodes)} en SPICE"
        for spice_node, hole in zip(spice_nodes, board):
            node = find(hole)
            if spice_node in seen:
                assert seen[spice_node] == node, f"{part}: el nodo {spice_node} cae en dos sitios distintos"
            assert node not in seen.values() or seen.get(spice_node) == node, \
                f"{part}: {hole} junta {spice_node} con otro nodo"
            seen[spice_node] = node
    # The netlist grounds through node 0; on the board that is the ground rail.
    assert seen["0"] == find(GND), "la tierra del circuito no es el riel de tierra"
    assert seen["vpos"] == find(VPOS) and seen["vneg"] == find(VNEG), "los rieles de alimentación no cuadran"
    print(f"ok: {len(netlist)} partes y {len(seen)} nodos coinciden con input_stage_split")


X = {c: i + (1.4 if i >= 5 else 0) for i, c in enumerate(COLS)}
RAIL_Y = {VPOS: 2.1, "gnd_arriba": 1.4, "gnd_abajo": -ROWS - 1.4, VNEG: -ROWS - 2.1}
WIRE_COLOR = "#1565c0"
PART_LABEL = {
    "C1": "C1, 100 nF (104)", "R1": "R1, 1 MΩ", "Rpot": "potenciómetro de 10 kΩ", "R4": "R4, 1 kΩ",
    "R5": "R5, 4.7 kΩ", "C5": "C5, 1 nF (102)", "C3": "C3, 2.2 µF",
    "Cdec_pos": "100 nF de +9 V a tierra", "Cdec_neg": "100 nF de -9 V a tierra",
}


def hole_xy(hole):
    """Holes are (column, row); rails answer with the x of the part that reaches them."""
    return X[hole[0]], -hole[1]


def rail_y(rail, row):
    """Ground has a rail on each edge; a hole uses the closer one."""
    if rail == GND:
        return RAIL_Y["gnd_arriba"] if row is not None and row <= ROWS / 2 else RAIL_Y["gnd_abajo"]
    return RAIL_Y[rail]


def draw_board(ax):
    ax.add_patch(FancyBboxPatch((-1.6, -ROWS - 0.6), 13.4, ROWS + 0.2, boxstyle="round,pad=0.25",
                                fc="#f4f1ea", ec="#bbb"))
    ax.text(5.1, 0.95, "columnas", ha="center", fontsize=8, color="#888")
    for c in COLS:
        ax.text(X[c], 0.35, c, ha="center", fontsize=9, color="#666")
    for r in range(1, ROWS + 1):
        for label_x in (-1.1, 11.3):
            ax.text(label_x, -r, str(r), ha="center", va="center", fontsize=6.5, color="#888")
        for c in COLS:
            ax.add_patch(Rectangle((X[c] - 0.12, -r - 0.12), 0.24, 0.24, color="#9a9a9a"))
    for rail, y, color, text in ((VPOS, RAIL_Y[VPOS], "#c62828", "+9 V"),
                                ("gnd_arriba", RAIL_Y["gnd_arriba"], "#000000", "tierra"),
                                ("gnd_abajo", RAIL_Y["gnd_abajo"], "#000000", "tierra"),
                                (VNEG, RAIL_Y[VNEG], "#1565c0", "-9 V")):
        ax.plot([-2.6, 13.2], [y, y], color=color, lw=2.2, solid_capstyle="round")
        ax.text(13.4, y, text, va="center", fontsize=9, color=color)
    ax.plot([-2.6, -2.6], [RAIL_Y["gnd_arriba"], RAIL_Y["gnd_abajo"]], color="#000000", lw=1.6, ls=":")
    ax.text(-3.0, -ROWS / 2, "las dos tierras van unidas", rotation=90, ha="center", va="center", fontsize=7.5)


def draw_chip(ax):
    x0, x1 = X["e"], X["f"]
    ax.add_patch(FancyBboxPatch((x0 - 0.45, -17.5), x1 - x0 + 0.9, 4.0, boxstyle="round,pad=0.05",
                                fc="#2b2b2b", ec="#111"))
    ax.add_patch(Rectangle(((x0 + x1) / 2 - 0.35, -13.7), 0.7, 0.25, fc="#f4f1ea", ec="none"))
    ax.text((x0 + x1) / 2, -15.5, "TL072", color="white", ha="center", va="center", fontsize=9, rotation=90)
    for pin, (col, row) in PINS.items():
        ax.plot(X[col], -row, "o", color="#d4af37", ms=6, zorder=4)
        dx = 0.42 if col == "e" else -0.42
        ax.text(X[col] + dx, -row, str(pin), ha="center", va="center", fontsize=7.5, color="white", zorder=5)
    ax.text((x0 + x1) / 2, -12.7, "la muesca va hacia arriba", ha="center", fontsize=7.5, color="#444")


def draw_part(ax, name, holes):
    """Resistors get a body with a color band block; capacitors a rounded body."""
    if name.startswith(("Cdec", "X")) or name == "Rpot":
        return
    (x1, y1), (x2, y2) = hole_xy(holes[0]), hole_xy(holes[1])
    ax.plot([x1, x2], [y1, y2], color="#8d6e63", lw=1.4, zorder=2)
    ax.plot([x1, x2], [y1, y2], "o", color="#8d6e63", ms=6, zorder=5)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    if name.startswith("R"):
        ax.add_patch(FancyBboxPatch((cx - 0.22, cy - 1.0), 0.44, 2.0, boxstyle="round,pad=0.06",
                                    fc="#e0c9a6", ec="#8d6e63", zorder=3))
    else:
        ax.add_patch(FancyBboxPatch((cx - 0.26, cy - 0.55), 0.52, 1.1, boxstyle="round,pad=0.08",
                                    fc="#f9a825", ec="#8d6e63", zorder=3))


def draw_wire(ax, a, b):
    """A wire between two columns turns in the gap between rows, so it never crosses the chip."""
    xa, ya = hole_xy(a) if isinstance(a, tuple) else (None, None)
    xb, yb = hole_xy(b) if isinstance(b, tuple) else (None, None)
    if xa is None:
        xa, ya = xb, rail_y(a, b[1])
    if xb is None:
        xb, yb = xa, rail_y(b, a[1])
    if abs(ya - yb) < 0.01:
        ax.plot([xa, xb], [ya, yb], color=WIRE_COLOR, lw=2.2, solid_capstyle="round", zorder=6)
    elif abs(xa - xb) < 0.01:
        vertical(ax, xa, ya, yb)
    else:
        ymid = min(ya, yb) - 0.5
        vertical(ax, xa, ya, ymid)
        ax.plot([xa, xb], [ymid, ymid], color=WIRE_COLOR, lw=2.2, solid_capstyle="round", zorder=6)
        vertical(ax, xb, ymid, yb)
    ax.plot([xa, xb], [ya, yb], "o", color=WIRE_COLOR, ms=5.5, zorder=7)


def vertical(ax, x, y1, y2):
    """Draws a vertical run, hopping over any rail it only crosses, so a crossing never looks like a joint."""
    lo, hi = sorted((y1, y2))
    crossed = sorted(y for y in RAIL_Y.values() if lo + 0.3 < y < hi - 0.3)
    cuts = [lo] + [c for y in crossed for c in (y - 0.3, y + 0.3)] + [hi]
    for a, b in zip(cuts[::2], cuts[1::2]):
        ax.plot([x, x], [a, b], color=WIRE_COLOR, lw=2.2, solid_capstyle="round", zorder=6)
    for y in crossed:
        ax.add_patch(Arc((x, y), 0.6, 0.6, theta1=-90, theta2=90, color=WIRE_COLOR, lw=2.2, zorder=6))


def draw():
    check()
    fig, ax = plt.subplots(figsize=(11, 15))
    ax.set_aspect("equal")
    ax.axis("off")
    draw_board(ax)
    draw_chip(ax)
    for a, b, _ in WIRES:
        draw_wire(ax, a, b)
    for name, holes in LAYOUT.items():
        draw_part(ax, name, holes)
    for rail, y in ((VPOS, RAIL_Y[VPOS]), (VNEG, RAIL_Y[VNEG])):
        gy = RAIL_Y["gnd_arriba"] if rail == VPOS else RAIL_Y["gnd_abajo"]
        ax.plot([12.4, 12.4], [y, gy], color="#8d6e63", lw=1.4, zorder=2)
        ax.add_patch(FancyBboxPatch((12.14, (y + gy) / 2 - 0.22), 0.52, 0.44, boxstyle="round,pad=0.08",
                                    fc="#f9a825", ec="#8d6e63", zorder=3))
        ax.text(12.4, (y + gy) / 2 + (0.7 if y > 0 else -0.7), "100 nF", fontsize=7.5, va="center", ha="center")
    for hole, text in EXTERNAL:
        x, y = hole_xy(hole)
        side = -1 if hole[0] in "abcde" else 1
        ax.annotate(text, xy=(x, y), xytext=(x + side * 3.2, y + 1.8), fontsize=8.5, ha="center",
                    arrowprops=dict(arrowstyle="->", color="#2e7d32"), color="#2e7d32")
    ax.annotate("potenciómetro:\ntres cables,\nver la lista", xy=(X["a"], -14), xytext=(X["a"] - 3.2, -9.0),
                fontsize=8.5, ha="center", color="#6a1b9a",
                arrowprops=dict(arrowstyle="->", color="#6a1b9a"), zorder=9)
    for hole in (("a", 14), ("b", 14), ("d", 15)):
        x, y = hole_xy(hole)
        ax.plot(x, y, "o", color="#6a1b9a", ms=6.5, zorder=7)
    ax.set_xlim(-6.0, 15.6)
    ax.set_ylim(-ROWS - 3.4, 3.4)
    ax.set_title("Etapa de entrada de ±9 V sobre la protoboard\nCon las pilas desconectadas mientras se arma",
                 fontsize=12)
    ax.text(5.1, -ROWS - 2.9, "La MB-102 tiene 63 filas: aquí se dibujan solo las 30 primeras.\n"
                              "Cuenta desde el extremo donde la protoboard dice 1.",
            ha="center", fontsize=8.5, color="#555")
    out = HERE / "etapa_entrada_protoboard.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    print(out)


def print_list():
    """The list Renata follows hole by hole."""
    print("\nPartes:")
    for name, holes in LAYOUT.items():
        if name.startswith("X"):
            continue
        if name.startswith("Cdec"):
            print(f"  {PART_LABEL[name]}: de riel a riel, cerca del TL072")
        elif name == "Rpot":
            print(f"  {PART_LABEL[name]}: una punta a a14, la punta del medio a b14, la otra punta a d15")
        else:
            (c1, r1), (c2, r2) = holes
            print(f"  {PART_LABEL[name]}: de {c1}{r1} a {c2}{r2}")
    print("\nCables:")
    for a, b, what in WIRES:
        fmt = lambda h: h if isinstance(h, str) else f"{h[0]}{h[1]}"  # noqa: E731
        print(f"  {fmt(a)} a {fmt(b)}: {what}")
    print("\nLas filas son las que vienen impresas en la MB-102, contando desde el extremo donde dice 1.")
    print("El Pico se queda en su propia protoboard: esta etapa va en la MB-102 vacía.")
    print("\nFuera de la protoboard:")
    for hole, text in EXTERNAL:
        print(f"  {hole[0]}{hole[1]}: {text}")
    print("  la malla del cable de la guitarra y la del cable a la tarjeta: riel de tierra")
    print("  pila 1: + al riel +9 V, - al riel de tierra; pila 2: + al riel de tierra, - al riel -9 V")
    print("\nSin potenciómetro: en su lugar una resistencia fija de a14 a a10 y un cable de b10 a b15.")
    print("  Con 10 kΩ la ganancia queda en 11, con 4.7 kΩ en 5.7 y con 1 kΩ en 2.")


if __name__ == "__main__":
    draw()
    print_list()
