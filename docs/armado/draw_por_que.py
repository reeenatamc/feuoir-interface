"""Draws what each piece of the input stage is for, as the signal flow from the guitar to the USB card.

This one is not a wiring drawing: it explains the why. Saves por_que_cada_pieza.png next to this script.

    .venv/bin/python docs/armado/draw_por_que.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrow, FancyBboxPatch  # noqa: E402

BOXES = [
    ("la guitarra", "Sus cuerdas mueven un imán y eso\nhace un temblorcito eléctrico\nmuy pequeño y muy débil.", "#eceff1"),
    ("la lentejita 104", "Deja pasar solo el temblor.\nCualquier voltaje quieto que\nvenga por el cable lo frena.", "#e3f2fd"),
    ("el tubito de 1 M", "Le dice al circuito dónde\nestá el cero. Sin él la entrada\nqueda al aire y se vuelve loca.", "#e3f2fd"),
    ("la piecita negra,\nprimera mitad", "Copia el temblor pero más grande.\nEsta es la parte que amplifica.", "#fff3e0"),
    ("la perilla\ny el tubito de 1 k", "Entre los dos deciden cuánto\nmás grande. Girando la perilla\nva de 1 vez a 11 veces.", "#fff3e0"),
    ("el tubito de 4.7 k\ny la lentejita 102", "Un colador. Deja pasar la\nguitarra y corta lo muy agudo,\nque es ruido y no es música.", "#e8f5e9"),
    ("la piecita negra,\nsegunda mitad", "No lo hace más grande: lo hace\nfuerte, para que aguante el\ncable hasta la tarjeta.", "#fff3e0"),
    ("el barrilito", "Otra vez solo el temblor.\nLa tarjeta tiene su propio\nvoltaje quieto y no hay que pelear.", "#e3f2fd"),
    ("la tarjeta USB", "Recibe el sonido ya grande\ny limpio, y lo mete\nen la computadora.", "#eceff1"),
]

fig, ax = plt.subplots(figsize=(17, 11))
ax.axis("off")  # deliberately not equal: the boxes are laid out in text units, not board units
W, H, GAP = 4.4, 3.9, 1.5
for i, (title, body, color) in enumerate(BOXES):
    col, row = i % 3, i // 3
    x, y = col * (W + GAP), -row * (H + GAP + 0.6)
    ax.add_patch(FancyBboxPatch((x, y - H), W, H, boxstyle="round,pad=0.18", fc=color, ec="#90a4ae", lw=1.4))
    ax.text(x + W / 2, y - 0.75, title, ha="center", va="center", fontsize=14, fontweight="bold")
    ax.text(x + W / 2, y - H / 2 - 0.85, body, ha="center", va="center", fontsize=11.5, linespacing=1.6)
    if i < len(BOXES) - 1:
        if col < 2:
            ax.add_patch(FancyArrow(x + W + 0.25, y - H / 2, GAP - 0.7, 0, width=0.08, head_width=0.45,
                                    head_length=0.5, color="#546e7a", length_includes_head=True))
        else:  # wrap to the start of the next row, through the empty band between rows
            drop = y - H - 1.05
            ax.plot([x + W / 2, x + W / 2, W / 2, W / 2], [y - H, drop, drop, drop - 0.35],
                    color="#546e7a", lw=2, solid_capstyle="round", solid_joinstyle="round")
            ax.add_patch(FancyArrow(W / 2, drop - 0.35, 0, -0.35, width=0.02, head_width=0.45, head_length=0.55,
                                    color="#546e7a", length_includes_head=True))

y0 = -3 * (H + GAP + 0.6) - 0.6
ax.add_patch(FancyBboxPatch((0, y0 - 4.2), 3 * W + 2 * GAP, 4.0, boxstyle="round,pad=0.18", fc="#fce4ec", ec="#ad1457"))
ax.text((3 * W + 2 * GAP) / 2, y0 - 0.8, "Y las dos cajitas con pilas, que es de donde sale la fuerza",
        ha="center", fontsize=14, fontweight="bold", color="#880e4f")
ax.text((3 * W + 2 * GAP) / 2, y0 - 2.7,
        "El temblor de la guitarra sube y baja alrededor del cero, así que la piecita negra necesita electricidad\n"
        "por arriba y por abajo del cero. Dos pilas en fila: una punta es el +9, la otra el -9, y el punto del medio\n"
        "es el cero, la tierra. Las otras dos lentejitas 104 son un depósito pegado a la piecita, para que no le\n"
        "falte fuerza justo cuando da un golpe seco.",
        ha="center", va="center", fontsize=11.5, linespacing=1.7)

ax.text((3 * W + 2 * GAP) / 2, 2.4, "Por qué va cada pieza", ha="center", fontsize=26, fontweight="bold")
ax.text((3 * W + 2 * GAP) / 2, 1.1,
        "El camino de la señal, de la guitarra a la computadora. Cada cable de la tabla solo junta dos puntos "
        "que tienen que ser el mismo punto.", ha="center", fontsize=13, color="#546e7a")
ax.set_xlim(-0.8, 3 * W + 2 * GAP + 0.8)
ax.set_ylim(y0 - 5.0, 3.4)
out = Path(__file__).resolve().with_name("por_que_cada_pieza.png")
fig.savefig(out, dpi=140, bbox_inches="tight", facecolor="white")
print(out)
