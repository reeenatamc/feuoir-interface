"""Draws the analog input stage, the ±9 V version to build, from the values in spice/netlists/input_stage.cir.

The guitar on the left is the model in spice/netlists/guitar.cir, and the PCM1808 on the right is the 60 kΩ load the
simulations use. Saves etapa_entrada.png and etapa_entrada.pdf next to this script. Labels in Spanish.

    .venv/bin/python docs/armado/draw_input_stage.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import schemdraw  # noqa: E402
import schemdraw.elements as elm  # noqa: E402

HERE = Path(__file__).resolve().parent
MUTED = "#737373"


def draw():
    d = schemdraw.Drawing(show=False)
    d.config(unit=2.4, fontsize=11)

    # Guitar model: pickup voltage, coil, its resistance, and the pickup and cable capacitances.
    d += (emf := elm.SourceSin().up())
    d += elm.Label().at((emf.center[0] - 0.9, emf.center[1])).label("pastilla", halign="right").color(MUTED)
    d += elm.Ground().at(emf.start)
    d += elm.Inductor2().right().at(emf.end).label("5 H").color(MUTED)
    d += elm.Resistor().right().label("8 kΩ").color(MUTED)
    d += elm.Dot()
    guitar_out = d.here
    d += elm.Capacitor().down().at(guitar_out).label("100 pF", loc="bottom").color(MUTED)
    d += elm.Ground()
    d += elm.Line().right(2.4).at(guitar_out)
    d += (cable := elm.Dot())
    d += elm.Capacitor().down().at(cable.center).label("cable\n300 a\n600 pF", loc="bottom").color(MUTED)
    d += elm.Ground()
    d += elm.Line().right(1.2).at(cable.center)
    d += elm.Dot(open=True).label("entrada", loc="top")

    # Stage A: non-inverting, gain 1 + Rpot/R4, from 1 to 11. Flipped so + is on top, in line with the input.
    d += elm.Capacitor().right().label("C1\n100 nF")
    d += (inp := elm.Dot())
    d += elm.Resistor().down().at(inp.center).label("R1\n1 MΩ", loc="bottom")
    d += elm.Ground()
    d += elm.Line().right(1.2).at(inp.center)
    d += (opa := elm.Opamp(leads=True).flip().anchor("in2").label("U1A\nTL072", loc="center", ofst=(-0.3, 0),
                                                                    fontsize=9))
    d += elm.Line().down(1.2).at(opa.in1)
    d += (inn := elm.Dot())
    d += elm.Resistor().down().at(inn.center).label("R4\n1 kΩ", loc="top")
    d += elm.Ground()
    d += elm.Potentiometer().right().at(inn.center).tox(opa.out).label("Rpot 10 kΩ\nganancia 1 a 11", loc="bottom")
    d += elm.Line().up().toy(opa.out)
    d += (outa := elm.Dot())

    # Passive filter between the stages, 33.9 kHz.
    d += elm.Resistor().right().at(outa.center).label("R5\n4.7 kΩ")
    d += (filt := elm.Dot())
    d += elm.Capacitor().down().at(filt.center).label("C5\n1 nF", loc="top")
    d += elm.Ground()

    # Stage B: follower, also with + on top.
    d += elm.Line().right(1.0).at(filt.center)
    d += (opb := elm.Opamp(leads=True).flip().anchor("in2").label("U1B\nTL072", loc="center", ofst=(-0.3, 0),
                                                                    fontsize=9))
    d += elm.Line().down(1.2).at(opb.in1)
    d += elm.Line().right().tox(opb.out)
    d += elm.Line().up().toy(opb.out)
    d += (outb := elm.Dot())

    # Output coupling to the PCM1808, and its input as the simulations model it.
    d += elm.Capacitor(polar=True).right().at(outb.center).label("C3\n2.2 µF")
    d += (adc := elm.Dot())
    d += elm.Line().right(1.0)
    d += elm.Dot(open=True).label("al PCM1808", loc="top")
    d += elm.Resistor().down().at(adc.center).label("60 kΩ\nPCM1808", loc="bottom").color(MUTED)
    d += elm.Ground()

    # Supply: two 9 V batteries in series, the midpoint is the analog ground.
    x0, y0 = emf.start[0] + 1.0, emf.start[1] - 7.0
    d += elm.Battery().up().reverse().at((x0, y0)).label("9 V", loc="bottom")
    d += elm.Line().up(0.6)
    d += (vpos := elm.Dot())
    d += elm.Battery().down().at((x0, y0)).label("9 V", loc="bottom")
    d += elm.Line().down(0.6)
    d += (vneg := elm.Dot())
    d += elm.Dot().at((x0, y0))
    d += elm.Line().right(4.0).at((x0, y0))
    d += (gnd := elm.Dot())
    d += elm.Line().right(1.2).at(gnd.center)
    d += elm.Ground()
    d += elm.Line().right(6.0).at(vpos.center)
    d += elm.Dot(open=True).label("+9 V, pata 8 del TL072", loc="right")
    d += elm.Line().right(6.0).at(vneg.center)
    d += elm.Dot(open=True).label("−9 V, pata 4 del TL072", loc="right")
    d += elm.Capacitor().down().at((x0 + 4.0, vpos.center[1])).toy(gnd.center).label("100 nF")
    d += elm.Capacitor().up().at((x0 + 4.0, vneg.center[1])).toy(gnd.center).label("100 nF", loc="bottom")
    d += elm.Dot().at((x0 + 4.0, vpos.center[1]))
    d += elm.Dot().at((x0 + 4.0, vneg.center[1]))
    d += elm.Label().at((x0 + 14.0, y0)).label(
        "Alimentación: dos pilas de 9 V en serie.\nEl punto medio es la tierra analógica.\n"
        "U1A y U1B son las dos mitades de un solo TL072 (DIP-8).\nLos 100 nF van pegados a las patas 8 y 4.",
        halign="left", fontsize=10)

    top = emf.end[1] + 3.2
    d += elm.Label().at((emf.start[0] - 2.0, top)).label(
        "Etapa de entrada de feuoir, versión de ±9 V (spice/netlists/input_stage.cir)", halign="left", fontsize=14)
    d += elm.Label().at((emf.start[0] - 2.0, top - 0.8)).label(
        "En gris, lo que no se arma: el modelo de la guitarra y la carga del PCM1808 que usa la simulación.\n"
        "Cortes: entrada 1.59 Hz (C1 con R1), filtro 33.9 kHz (R5 con C5), salida 1.21 Hz (C3 con 60 kΩ).",
        halign="left", fontsize=10, color=MUTED)
    return d


if __name__ == "__main__":
    drawing = draw()
    for ext in ("png", "pdf"):
        drawing.save(str(HERE / f"etapa_entrada.{ext}"), dpi=200)
    print(HERE / "etapa_entrada.png")
