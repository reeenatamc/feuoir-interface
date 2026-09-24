# Mapa de agujeritos

Lo generó `mapa_agujeritos.py` con los mismos datos del dibujo revisado contra la simulación, así que
no se puede desfasar del circuito. Cada fila del mismo lado de la zanja es un solo punto: si un
agujerito está ocupado, cualquier otro de esa fila y ese lado sirve igual.

| Fila | Lado a-e | Lado f-j |
|---|---|---|
| 3 | **a3**: la perilla que gira, una patita del extremo<br>**b3**: cable a b14 (un extremo del potenciómetro a la salida) | libre |
| 5 | **a5**: la perilla que gira, la patita del medio<br>**b5**: cable a d14 (la punta media del potenciómetro, al mismo sitio) | libre |
| 7 | **a7**: la perilla que gira, una patita del extremo<br>**b7**: cable a b15 (el otro extremo del potenciómetro a la entrada inversora) | libre |
| 11 | **a11**: cable a riel tierra (R4 a tierra)<br>**c11**: tubito de 1 k | **h11**: barrilito<br>**j11**: al micrófono de la tarjeta USB |
| 14 | **b14**: cable a b3 (un extremo del potenciómetro a la salida)<br>**c14**: cable a g20 (salida del pin 1 al filtro)<br>**d14**: cable a b5 (la punta media del potenciómetro, al mismo sitio)<br>**e14**: piecita negra de ocho patitas, patita 1 | **f14**: piecita negra de ocho patitas, patita 8<br>**g14**: cable a riel +9 (pin 8 a +9 V) |
| 15 | **b15**: cable a b7 (el otro extremo del potenciómetro a la entrada inversora)<br>**c15**: tubito de 1 k<br>**e15**: piecita negra de ocho patitas, patita 2 | **f15**: piecita negra de ocho patitas, patita 7<br>**g15**: cable a g16 (pin 7 con pin 6: seguidor)<br>**h15**: barrilito |
| 16 | **d16**: cable a d20 (entrada al pin 3)<br>**e16**: piecita negra de ocho patitas, patita 3 | **f16**: piecita negra de ocho patitas, patita 6<br>**g16**: cable a g15 (pin 7 con pin 6: seguidor) |
| 17 | **d17**: cable a riel -9 (pin 4 a -9 V)<br>**e17**: piecita negra de ocho patitas, patita 4 | **f17**: piecita negra de ocho patitas, patita 5<br>**g17**: cable a g24 (filtro al pin 5) |
| 20 | **b20**: lentejita 104 de la entrada<br>**c20**: tubito de 1 M<br>**d20**: cable a d16 (entrada al pin 3) | **g20**: cable a c14 (salida del pin 1 al filtro)<br>**h20**: tubito de 4.7 k |
| 22 | **a22**: punta del cable de la guitarra<br>**b22**: lentejita 104 de la entrada | libre |
| 24 | **a24**: cable a riel tierra (R1 a tierra)<br>**c24**: tubito de 1 M | **g24**: cable a g17 (filtro al pin 5)<br>**h24**: tubito de 4.7 k<br>**i24**: lentejita 102 del filtro |
| 26 | libre | **i26**: lentejita 102 del filtro<br>**j26**: cable a riel tierra (C5 a tierra) |

Las filas que no salen en la tabla están libres enteras.

## Libres en las filas que ya se usan

- fila 3: libres c3, d3, e3, f3, g3, h3, i3, j3
- fila 5: libres c5, d5, e5, f5, g5, h5, i5, j5
- fila 7: libres c7, d7, e7, f7, g7, h7, i7, j7
- fila 11: libres b11, d11, e11, f11, g11, i11
- fila 14: libres a14, h14, i14, j14
- fila 15: libres a15, d15, i15, j15
- fila 16: libres a16, b16, c16, h16, i16, j16
- fila 17: libres a17, b17, c17, h17, i17, j17
- fila 20: libres a20, e20, f20, i20, j20
- fila 22: libres c22, d22, e22, f22, g22, h22, i22, j22
- fila 24: libres b24, d24, e24, f24, j24
- fila 26: libres a26, b26, c26, d26, e26, f26, g26, h26

## Las cuatro tiras del borde

- riel tierra: las dos tiras azules, las dos son el mismo punto
- riel +9: la tira roja del lado de las letras f g h i j
- riel -9: la tira roja del lado de las letras a b c d e

En una tira entera cualquier agujerito sirve: toda la tira es un mismo punto.
