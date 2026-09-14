# Etapa analógica de entrada

Lo que va entre la guitarra y el PCM1808. El diseño es de Renata; este documento lo describe tal como está decidido y junta lo que hace falta para simularlo y armarlo. Por qué pasó a alimentación partida: docs/bitacora.md, entrada 24. Las condiciones de la simulación: entrada 25.

## Circuito

Alimentación partida de ±9 V, con dos pilas de 9 V en serie y el punto medio como tierra analógica. Un TL072 en DIP-8.

Etapa A, no inversora con ganancia variable:

- C1 = 100 nF de acoplo de entrada.
- R1 = 1 MΩ de la entrada no inversora a tierra.
- R4 = 1 kΩ de la entrada inversora a tierra.
- Potenciómetro de 10 kΩ en la realimentación, de la salida a la entrada inversora. Ganancia 1 + Rpot/R4, de 1 a 11.

Filtro pasivo entre etapas: R5 = 4.7 kΩ en serie y C5 = 1 nF a tierra.

Etapa B: seguidor con la segunda mitad del TL072, ganancia 1, y C3 = 2.2 µF de acoplo hacia el PCM1808.

Desacoplo: 100 nF en cada riel contra tierra.

## Versión de 9 V simples

Es la del diseño original, que se simula para compararla con la partida. Una pila de 9 V, con la polarización en 4.5 V: R2 = R3 = 100 kΩ de divisor y C4 = 47 µF a tierra. R1 va al nodo de polarización, y R4 en serie con C2 = 47 µF también. El resto es igual.

## Frecuencias que salen de los valores

| Qué | De dónde sale | Valor |
|---|---|---|
| Corte de entrada | C1 con R1 | 1.59 Hz |
| Corte de salida | C3 con los 60 kΩ del PCM1808 | 1.21 Hz |
| Filtro entre etapas | R5 con C5 | 33.9 kHz |

## Condiciones de la simulación

- Carga del PCM1808: 60 kΩ detrás de C3, la impedancia de entrada de su hoja.
- Pilas con resistencia interna: 2 Ω con pila fresca. Caso de pila gastada: 7 V con 10 Ω.
- Ganancia en cinco puntos: 1, 3, 5, 8 y 11, con el potenciómetro en 0, 2, 4, 7 y 10 kΩ.
- Guitarra en un archivo aparte: bobina de 5 H en serie con 8 kΩ, 100 pF en paralelo y la capacitancia del cable como parámetro, de 300 a 600 pF.
- TL072: el modelo SPICE de TI, que se revisa antes de usarlo.

## Efectos conocidos

- Offset en continua. Sin C2, la ganancia en continua es la misma que en audio, de 1 a 11. El offset de entrada del TL072, hasta 10 mV en la tabla 5.8 de su hoja, llega a 110 mV en la salida de la etapa A. C3 lo bloquea antes del PCM1808, y sobre ±9 V solo resta un poco de margen.
- Golpe al mover el potenciómetro. Como el offset de salida cambia con la ganancia, al mover el potenciómetro C3 tiene que recargarse contra los 60 kΩ del PCM1808. La constante de tiempo es de 2.2 µF por 60 kΩ, 0.13 s, y se oye como un golpe mientras se ajusta. Es inofensivo y solo pasa al mover la perilla.
- Inversión de fase fuera del rango de modo común. Es el motivo del cambio a ±9 V (entrada 24). La mayoría de los modelos SPICE de TI no la reproducen: si la simulación de 9 V simples sale limpia, eso no prueba que el problema no exista, sino que el modelo no lo incluye.
