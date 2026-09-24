# Etapa analógica de entrada

Lo que va entre la guitarra y el PCM1808. El diseño es de Renata; este documento lo describe tal como está decidido y junta lo que hace falta para simularlo y armarlo. Por qué pasó a alimentación partida: docs/bitacora.md, entrada 24. Las condiciones de la simulación: entrada 25.

## Circuito

Alimentación partida de ±9 V, con dos pilas de 9 V en serie y el punto medio como tierra analógica. Un TL072 en DIP-8.

La alimentación partida se apoya en la tabla de condiciones recomendadas de la hoja del TL072 (entrada 24), no en una simulación. La inversión de fase que evita no es simulable con los modelos disponibles: el del TL072 clásico no la muestra y el TL07xH está hecho para no tenerla (entrada 27). Una simulación de 9 V simples que salga limpia no prueba que el problema no exista.

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
- TL072: el modelo de TI del TL072 clásico para todo lo lineal, y el del TL072H solo para el ruido (docs/simulador-spice.md, qué modelo se usa para qué).

## Efectos conocidos

- Offset en continua. Sin C2, la ganancia en continua es la misma que en audio, de 1 a 11. El offset de entrada del TL072, hasta 10 mV en la tabla 5.8 de su hoja, llega a 110 mV en la salida de la etapa A. C3 lo bloquea antes del PCM1808, y sobre ±9 V solo resta un poco de margen.
- Golpe al mover el potenciómetro. Como el offset de salida cambia con la ganancia, al mover el potenciómetro C3 tiene que recargarse contra los 60 kΩ del PCM1808. La constante de tiempo es de 2.2 µF por 60 kΩ, 0.13 s, y se oye como un golpe mientras se ajusta. Es inofensivo y solo pasa al mover la perilla.
- Inversión de fase fuera del rango de modo común. Es el motivo del cambio a ±9 V (entrada 24), y no es simulable con los modelos disponibles (ver al principio, y la entrada 27).

## Qué dio la simulación

Del 2026-09-23, con spice/simulate_input.py (docs/simulador-spice.md, simulaciones de la etapa de entrada), repetida con la resistencia real de las pastillas, 12.6 kΩ, en vez de los 8 kΩ supuestos. Las carpetas están en mediciones/2026-09-23-sim-respuesta-en-frecuencia, 2026-09-23-sim-transitorio-1v5, 2026-09-23-sim-ruido y 2026-09-23-sim-carga-guitarra. Detalle en las entradas 28 y 35.

- Ganancia a 1 kHz: 0, 9.54, 13.97, 18.06 y 20.82 dB con el potenciómetro en 0, 2, 4, 7 y 10 kΩ, lo mismo que 1 + Rpot/R4.
- Forma con ±9 V: no cambia con la ganancia en la banda de audio. Entre ganancia 1 y 11 la diferencia de 20 Hz a 20 kHz es de 0.01 dB como mucho. El corte de abajo queda en 2.18 Hz con cualquier ganancia y el de arriba baja de 33.8 kHz a 33.5 kHz. Las curvas se separan recién por encima de 100 kHz, donde con más ganancia el TL072 tiene menos ancho de banda.
- Forma con 9 V simples: cambia con la ganancia en graves. El corte de abajo pasa de 1.89 Hz con ganancia 1 a 7.89 Hz con ganancia 11, y en 20 Hz la ganancia 11 cae 0.61 dB, contra 0.14 dB de la ganancia 1. Con ±9 V, en 20 Hz cae 0.04 dB con cualquier ganancia.
- Margen de entrada con 1.5 V de pico y ganancia 11, contra los 4 V sobre el riel negativo de la tabla 5.3: +3.46 V con ±9 V y pilas frescas, +1.37 V con ±7 V y pilas gastadas y -1.01 V con 9 V simples, fuera del rango. Con ±7 V el margen sigue sobrando. El modelo consume más que el chip, así que con pilas gastadas el margen real es un poco mayor.
- Ruido de 20 Hz a 20 kHz en la entrada del PCM1808, con ±9 V: con ganancia 1, 21.0 µV al aire y 6.5 µV con la guitarra y 300 pF (-97.1 y -107.3 dBFS); con ganancia 11, 226.8 µV al aire y 56.3 µV con la guitarra (-76.4 y -88.5 dBFS). Con la guitarra conectada hay entre 10 y 13 dB menos ruido que al aire. Con la entrada al aire el modelo exagera el ruido entre 1.2 y 1.3 dB a 1 kHz (docs/simulador-spice.md).
- Carga de la guitarra: con 1 MΩ la pastilla resuena en 3.55 kHz con +13.0 dB (cable de 300 pF) y en 2.69 kHz con +12.6 dB (600 pF). Con 10 kΩ pierde 7.2 dB desde abajo, cae 3 dB más en 737 Hz y no resuena. A 3.55 kHz queda 34 dB por debajo de la carga de 1 MΩ. Con los 8 kΩ supuestos la resonancia daba entre 1.8 y 2.4 dB más alta: la pastilla real se amortigua más.

## Para discutir

Salen de la simulación y no están decididos. No se cambió nada del circuito.

- La entrada del PCM1808 pasa su máximo absoluto. El pin admite de -0.3 V a 5.3 V (tabla 6.1 de su hoja), o sea 2.8 V hacia cada lado de su centro de 2.5 V, y como mucho ±10 mA. Con 1.5 V de pico y ganancia 11 la etapa B entrega a través de C3 ±7.4 V con ±9 V, ±5.3 V con ±7 V y ±2.9 V con 9 V simples. Con ganancia 11 alcanza con 255 mV de pico en la entrada de la etapa para pasar los 2.8 V, y el fondo de escala llega con 136 mV. La simulación no tiene los diodos de protección del PCM1808: en el chip conducirían, con la corriente limitada por el TL072, y la hoja da ±26 mA de cortocircuito para el TL07xH y no la da para el DIP-8. Tampoco se sabe todavía qué trae el módulo en VINL y VINR.
- El ruido de corriente del modelo del TL072H es 8 veces el que da la hoja para el DIP-8. Si hace falta el número exacto, ngspice puede listar cuánto aporta cada fuente de ruido.
