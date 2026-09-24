"""Writes mapa_de_agujeritos.md: what sits in every hole of the board, row by row.

The map is generated from the same LAYOUT, WIRES and EXTERNAL that the checked drawing uses, so it cannot drift from
the circuit. Names are physical on purpose: Renata builds by what the piece looks like, not by its part name.

    .venv/bin/python docs/armado/mapa_agujeritos.py
"""
from pathlib import Path

import draw_input_stage_breadboard as base  # noqa: E402  (same folder)
from draw_input_stage_breadboard import COLS, EXTERNAL, GND, LAYOUT, ROWS, VNEG, VPOS, WIRES  # noqa: E402

NAME = {
    "C1": "lentejita 104 de la entrada",
    "R1": "tubito de 1 M",
    "Rpot": "la perilla que gira, una patita del extremo",
    "R4": "tubito de 1 k",
    "XA": "piecita negra de ocho patitas",
    "XB": "piecita negra de ocho patitas",
    "R5": "tubito de 4.7 k",
    "C5": "lentejita 102 del filtro",
    "C3": "barrilito",
}
PIN_OF = {hole: n for n, hole in base.PINS.items()}
RAILS = (VPOS, VNEG, GND)


def occupancy():
    """Returns {(col, row): [what is plugged there]}, in build order."""
    taken = {}

    def put(hole, what):
        if hole not in RAILS:
            taken.setdefault(hole, []).append(what)

    for part, holes in LAYOUT.items():
        if part.startswith("Cdec"):
            continue
        for hole in holes:
            label = NAME[part]
            if part in ("XA", "XB"):
                label = f"{NAME[part]}, patita {PIN_OF[hole]}"
            if label not in taken.get(hole, []):
                put(hole, label)
    put(("a", 5), "la perilla que gira, la patita del medio")  # the wiper, which the two-terminal netlist omits
    for a, b, why in WIRES:
        for hole, other in ((a, b), (b, a)):
            name = other if other in RAILS else "".join(str(x) for x in other)
            put(hole, f"cable a {name} ({why})")
    for hole, why in EXTERNAL:
        put(hole, why)
    return taken


def render(taken):
    lines = ["# Mapa de agujeritos",
             "",
             "Lo generó `mapa_agujeritos.py` con los mismos datos del dibujo revisado contra la simulación, así que",
             "no se puede desfasar del circuito. Cada fila del mismo lado de la zanja es un solo punto: si un",
             "agujerito está ocupado, cualquier otro de esa fila y ese lado sirve igual.",
             "",
             "| Fila | Lado a-e | Lado f-j |",
             "|---|---|---|"]
    for row in range(1, ROWS + 1):
        cells = []
        for half in ("abcde", "fghij"):
            here = [f"**{c}{row}**: {', '.join(taken[(c, row)])}" for c in half if (c, row) in taken]
            cells.append("<br>".join(here) if here else "libre")
        if cells != ["libre", "libre"]:
            lines.append(f"| {row} | {cells[0]} | {cells[1]} |")
    lines += ["", "Las filas que no salen en la tabla están libres enteras.", "",
              "## Libres en las filas que ya se usan", ""]
    for row in range(1, ROWS + 1):
        used = [c for c in COLS if (c, row) in taken]
        if not used:
            continue
        free_l = [c for c in "abcde" if (c, row) not in taken]
        free_r = [c for c in "fghij" if (c, row) not in taken]
        lines.append(f"- fila {row}: libres {', '.join(f'{c}{row}' for c in free_l + free_r) or 'ninguno'}")
    lines += ["", "## Las cuatro tiras del borde", "",
              f"- {GND}: las dos tiras azules, las dos son el mismo punto",
              f"- {VPOS}: la tira roja del lado de las letras f g h i j",
              f"- {VNEG}: la tira roja del lado de las letras a b c d e",
              "", "En una tira entera cualquier agujerito sirve: toda la tira es un mismo punto.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    base.check()
    out = Path(__file__).resolve().with_name("mapa_de_agujeritos.md")
    out.write_text(render(occupancy()))
    print(out)
