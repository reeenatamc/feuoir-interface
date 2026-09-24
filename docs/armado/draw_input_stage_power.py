"""Draws how the two 9 V batteries feed the board: which wire goes to which rail and where to put the probes.

This is the picture Renata follows for the supply, so it names nothing by its part name and carries the numbers she
has to read on the meter. Saves etapa_entrada_alimentacion.png next to this script. Labels in Spanish.

    .venv/bin/python docs/armado/draw_input_stage_power.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Arc, Circle, FancyBboxPatch, Rectangle  # noqa: E402

RED, BLUE, BLACK, MUTED = "#c62828", "#1565c0", "#222222", "#666666"
RAILS = [(6.9, RED, "raya roja de arriba", "+9"),
         (6.4, BLUE, "raya azul de arriba", "tierra"),
         (3.1, RED, "raya roja de abajo", "tierra"),
         (2.6, BLUE, "raya azul de abajo", "-9")]


def battery(ax, x, y, name):
    ax.add_patch(FancyBboxPatch((x, y - 0.8), 2.4, 1.6, boxstyle="round,pad=0.08", fc="#2b2b2b", ec="#111"))
    ax.text(x + 1.2, y + 0.2, name, color="white", ha="center", va="center", fontsize=13)
    ax.text(x + 1.2, y - 0.35, "con su pila\ny el botón encendido", color="#bbb", ha="center", va="center",
            fontsize=8.5)


def probes(ax, x, desde, hacia_negra, hacia_roja, texto, va):
    """Two probes coming from outside the board into two rails, with what the meter has to show."""
    for dx, color, hacia in ((0.0, BLACK, hacia_negra), (0.75, RED, hacia_roja)):
        lo, hi = sorted((desde, hacia))
        cruza = [y for y, _, _, _ in RAILS if lo + 0.2 < y < hi - 0.2]
        cortes = [lo] + [c for y in cruza for c in (y - 0.2, y + 0.2)] + [hi]
        for a, b in zip(cortes[::2], cortes[1::2]):
            ax.plot([x + dx, x + dx], [a, b], color=color, lw=3, solid_capstyle="round")
        for y in cruza:
            ax.add_patch(Arc((x + dx, y), 0.4, 0.4, theta1=-90, theta2=90, color=color, lw=3))
        ax.add_patch(Circle((x + dx, hacia), 0.11, color=color))
    ax.text(x + 0.38, desde + (0.25 if va == "bottom" else -0.25), texto, ha="center", va=va, fontsize=12)


def draw():
    fig, ax = plt.subplots(figsize=(13.5, 9.4))
    ax.set_xlim(-0.6, 15.6)
    ax.set_ylim(0.2, 10.2)
    ax.axis("off")

    ax.text(0.2, 9.9, "La alimentación: dos pilas y las cuatro filas de los bordes", fontsize=17, va="top")
    ax.text(0.2, 9.25, "Esto se conecta AL FINAL, cuando todo lo demás ya esté puesto en la tabla.",
            fontsize=11.5, va="top", color=RED)

    ax.add_patch(FancyBboxPatch((4.4, 2.2), 7.4, 5.1, boxstyle="round,pad=0.2", fc="#f4f1ea", ec="#ccc"))
    ax.text(6.3, 4.75, "la tabla blanca", ha="center", va="center", fontsize=13, color="#ccc")
    for y, color, nombre, etiqueta in RAILS:
        ax.plot([4.6, 11.6], [y, y], color=color, lw=3.5, solid_capstyle="round")
        for x in [4.9 + 0.35 * i for i in range(20)]:
            ax.add_patch(Rectangle((x - 0.07, y - 0.22), 0.14, 0.14, color="#9a9a9a"))
        ax.text(11.9, y, f"{nombre}\naquí queda {etiqueta}", va="center", fontsize=10.5, color=color)

    battery(ax, 0.6, 6.65, "cajita 1")
    battery(ax, 0.6, 2.85, "cajita 2")
    for y0, y1, color, label in ((7.0, 6.9, RED, "cable rojo"), (6.3, 6.4, BLACK, "cable negro"),
                                 (3.2, 3.1, RED, "cable rojo"), (2.5, 2.6, BLACK, "cable negro")):
        ax.plot([3.0, 3.8, 3.8, 4.9], [y0, y0, y1, y1], color=color, lw=3, solid_capstyle="round")
        ax.add_patch(Circle((4.9, y1), 0.11, color=color))
        ax.text(3.9, y0 + (0.2 if color == RED else -0.2), label, fontsize=9.5, color=color,
                va="bottom" if color == RED else "top")

    ax.plot([11.2, 11.2], [6.4, 3.1], color=BLACK, lw=3, solid_capstyle="round")
    for y in (6.4, 3.1):
        ax.add_patch(Circle((11.2, y), 0.11, color=BLACK))
    ax.text(10.9, 4.75, "un cable suelto\nune estas dos filas", fontsize=10.5, va="center", ha="right")

    probes(ax, 6.4, 8.3, 6.4, 6.9, "aquí tiene que marcar 9 y algo", "bottom")
    probes(ax, 8.6, 1.4, 3.1, 2.6, "aquí, 9 y algo con un menos adelante", "top")

    ax.text(0.2, 0.75, "La punta negra siempre va en una fila de las que quedan como tierra.\n"
                       "No importa cuál raya esté más al borde: fíjate solo en el color.",
            fontsize=11.5, va="top", color=MUTED)
    out = Path(__file__).with_name("etapa_entrada_alimentacion.png")
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    print(out)


if __name__ == "__main__":
    draw()
