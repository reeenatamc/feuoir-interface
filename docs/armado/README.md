# Los dibujos del armado

Todo lo de esta carpeta se genera con matplotlib y schemdraw 0.23 (`.venv/bin/pip install schemdraw==0.23`). Ninguno
se dibujó a mano: los que muestran la protoboard derivan los nodos del propio trazado y los comparan contra
`input_stage_split` de spice/netlists/input_stage.cir, así que una pieza en la fila equivocada falla al generar el
dibujo y no en la mesa.

| Qué | Archivo | Se rehace con |
|---|---|---|
| Esquema de la etapa de entrada de ±9 V | `etapa_entrada.png` y `.pdf` | `draw_input_stage.py` |
| La misma etapa sobre la protoboard, agujero por agujero | `etapa_entrada_protoboard.png` | `draw_input_stage_breadboard.py` |
| La alimentación, que se conecta al final | `etapa_entrada_alimentacion.png` | `draw_input_stage_power.py` |
| Una imagen por paso, con lo ya puesto en gris | `pasos/paso_NN.png` y `etapa_entrada_pasos.pdf` | `draw_input_stage_steps.py` |
| Qué hay en cada agujerito y cuáles quedan libres | `mapa_de_agujeritos.md` | `mapa_agujeritos.py` |
| Para qué sirve cada pieza | `por-que-cada-pieza.md` y `por_que_cada_pieza.png` | `draw_por_que.py` |
| La revisión con el multímetro, antes de las pilas | `prueba_pitido.png` | `draw_prueba_pitido.py` |
| El símbolo de continuidad que hay que buscar en el aparato | `simbolo_pitido.png` | `draw_simbolo_pitido.py` |
| Dónde van las tres patitas del potenciómetro | `perilla_donde_va.png` | `draw_pot_closeup.py` |
| Los tres cables del potenciómetro | `perilla_cables.png` | `draw_pot_wires.py` |

`draw_input_stage_breadboard.py` imprime además la lista de partes y de cables. `draw_input_stage_steps.py` reusa su
trazado y su comprobación, de modo que los pasos no pueden separarse de la placa verificada.

Pendiente: `draw_input_stage_breadboard.py` y `draw_input_stage_power.py` todavía dibujan los cuatro rieles arriba y
abajo; en la MB-102 van por los dos lados largos, como ya los dibuja `draw_input_stage_steps.py`.
