# Reloj maestro del PCM1808

Generado por relojes.py el 2026-09-13 14:45 -0500 (sha256 del script cb05f69ab6f1, Python 3.12.0). Se reescribe completo en cada corrida, no editar a mano. Todas las soluciones exactas, con cada restricción marcada, están en reloj-soluciones.csv.

## Qué hace falta

A fS = 48 kHz el PCM1808 acepta en SCKI 256 fS = 12.288 MHz, 384 fS = 18.432 MHz o 512 fS = 24.576 MHz, con ciclo de trabajo entre 40 % y 60 % y pulsos alto y bajo de al menos 8 ns (hoja del PCM1808, tabla System clock timing). El Pico tiene un cristal de 12 MHz, así que la frecuencia sale de multiplicar con el PLL del sistema y dividir con el divisor del PIO.

## Condiciones de la búsqueda

Se probaron las 941.535 combinaciones de REFDIV, FBDIV, POSTDIV1 y POSTDIV2, y para cada una se calculó el divisor del PIO que haría falta. Una combinación es solución si ese divisor es exactamente representable como entero de 16 bits más fracción/256 y está entre 1 y 65536. Todo el cálculo es en enteros, sin redondeo.

Restricciones del enunciado:

- FREF = 12 MHz, REFDIV de 1 a 63, FBDIV de 16 a 320
- VCO = FREF/REFDIV x FBDIV entre 750 y 1600 MHz
- POSTDIV1 y POSTDIV2 de 1 a 7, sysclk = VCO/(POSTDIV1 x POSTDIV2)
- divisor del PIO = entero + fracción/256

Restricciones que agrega la hoja del RP2040 y que se marcan aparte:

- FREF/REFDIV de al menos 5 MHz (sección 2.18). Con el cristal de 12 MHz eso deja REFDIV en 1 o 2.
- FREF/REFDIV no mayor que VCO/16 (sección 2.18). Equivale a FBDIV >= 16, así que ya se cumple siempre.
- clk_sys de 133 MHz como máximo (secciones 2.15 y 2.18).

El jitter se calcula con el modelo del divisor fraccionario de la hoja del RP2040 (sección 3.5.5): delta-sigma de primer orden que alarga algunos periodos de n a n+1 ciclos de sysclk. Es la parte determinista que agrega el divisor en régimen estable, sin los primeros 256 periodos después de arrancar. El jitter propio del PLL no está incluido.

## Resultado

| Máquina de estados | Soluciones exactas | Con divisor entero | Cumplen la hoja del RP2040 | Cumplen la hoja y tienen divisor entero |
|---|---|---|---|---|
| 12.288 MHz | 4144 | 8 | 1205 | 2 |
| 24.576 MHz | 2416 | 0 | 672 | 0 |

Para 24.576 MHz ninguna combinación da divisor entero, ni con las restricciones del enunciado ni con las de la hoja.

No es un límite de la búsqueda. Para que sysclk/24.576 MHz sea entero, FBDIV tendría que ser múltiplo de 256, o sea 256, y entonces REFDIV x POSTDIV1 x POSTDIV2 tendría que dividir a 125 con REFDIV entre 2 y 4 para que el VCO quede en rango, lo que no pasa.

Las soluciones con divisor entero, sin filtrar:

| Máquina de estados | sysclk (MHz) | Divisor | REFDIV, FBDIV, VCO (MHz), POSTDIV1, POSTDIV2 | REF >= 5 MHz | sysclk <= 133 MHz |
|---|---|---|---|---|---|
| 12.288 MHz | 61.44 | 5 | 1, 128, 1536, 5, 5 | sí | sí |
| 12.288 MHz | 61.44 | 5 | 2, 256, 1536, 5, 5 | sí | sí |
| 12.288 MHz | 307.2 | 25 | 1, 128, 1536, 5, 1 | sí | no |
| 12.288 MHz | 307.2 | 25 | 1, 128, 1536, 1, 5 | sí | no |
| 12.288 MHz | 307.2 | 25 | 2, 256, 1536, 5, 1 | sí | no |
| 12.288 MHz | 307.2 | 25 | 2, 256, 1536, 1, 5 | sí | no |
| 12.288 MHz | 1536 | 125 | 1, 128, 1536, 1, 1 | sí | no |
| 12.288 MHz | 1536 | 125 | 2, 256, 1536, 1, 1 | sí | no |

## Soluciones que cumplen la hoja del RP2040

Una fila por par de sysclk y divisor, ordenadas por la irregularidad que mete el divisor. La configuración de PLL mostrada es la representativa: REFDIV 1, el VCO más alto (la hoja indica que minimiza el jitter) y POSTDIV1 >= POSTDIV2. La columna de configuraciones cuenta cuántas combinaciones de PLL dan el mismo sysclk. Cada tabla muestra las 12 primeras; el resto está en reloj-soluciones.csv.

### Máquina de estados a 12.288 MHz, una instrucción por periodo

207 pares de sysclk y divisor.

| sysclk (MHz) | Divisor | INT | FRAC | Tipo | REFDIV, FBDIV, VCO (MHz), POSTDIV1, POSTDIV2 | Configuraciones | Variación del periodo del SM (ns p-p) |
|---|---|---|---|---|---|---|---|
| 61.44 | 5 | 5 | 0 | entero | 1, 128, 1536, 5, 5 | 2 | 0.000 |
| 132 | 10.7421875 | 10 | 190 | fraccionario | 1, 132, 1584, 4, 3 | 30 | 7.576 |
| 130.8 | 10.64453125 | 10 | 165 | fraccionario | 1, 109, 1308, 5, 2 | 4 | 7.645 |
| 129.6 | 10.546875 | 10 | 140 | fraccionario | 1, 108, 1296, 5, 2 | 4 | 7.716 |
| 128.4 | 10.44921875 | 10 | 115 | fraccionario | 1, 107, 1284, 5, 2 | 4 | 7.788 |
| 127.2 | 10.3515625 | 10 | 90 | fraccionario | 1, 106, 1272, 5, 2 | 4 | 7.862 |
| 126 | 10.25390625 | 10 | 65 | fraccionario | 1, 126, 1512, 4, 3 | 27 | 7.937 |
| 124.8 | 10.15625 | 10 | 40 | fraccionario | 1, 104, 1248, 5, 2 | 4 | 8.013 |
| 123.6 | 10.05859375 | 10 | 15 | fraccionario | 1, 103, 1236, 5, 2 | 4 | 8.091 |
| 122.4 | 9.9609375 | 9 | 246 | fraccionario | 1, 102, 1224, 5, 2 | 4 | 8.170 |
| 121.2 | 9.86328125 | 9 | 221 | fraccionario | 1, 101, 1212, 5, 2 | 4 | 8.251 |
| 120 | 9.765625 | 9 | 196 | fraccionario | 1, 120, 1440, 4, 3 | 22 | 8.333 |

### Máquina de estados a 24.576 MHz, dos instrucciones por periodo

102 pares de sysclk y divisor. Reloj maestro de 12.288 MHz hecho con una instrucción que pone el pin en alto y otra que lo pone en bajo. TIE es el error de tiempo de los flancos de subida respecto de una rejilla ideal de 12.288 MHz. Las métricas son el peor caso entre las dos alineaciones posibles del programa con el patrón del divisor.

| sysclk (MHz) | Divisor | INT | FRAC | Tipo | REFDIV, FBDIV, VCO (MHz), POSTDIV1, POSTDIV2 | Configuraciones | Periodo MCLK (ns p-p) | TIE (ns p-p) | Ciclo de trabajo (%) | Pulso mínimo (ns) | Cumple PCM1808 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 61.44 | 2.5 | 2 | 128 | fraccionario | 1, 128, 1536, 5, 5 | 2 | 0.000 | 0.000 | 40.0 a 60.0 | 32.55 | sí |
| 132 | 5.37109375 | 5 | 95 | fraccionario | 1, 132, 1584, 4, 3 | 30 | 7.576 | 7.517 | 45.5 a 54.5 | 37.88 | sí |
| 129.6 | 5.2734375 | 5 | 70 | fraccionario | 1, 108, 1296, 5, 2 | 4 | 7.716 | 7.595 | 45.5 a 54.5 | 38.58 | sí |
| 127.2 | 5.17578125 | 5 | 45 | fraccionario | 1, 106, 1272, 5, 2 | 4 | 7.862 | 7.800 | 45.5 a 54.5 | 39.31 | sí |
| 124.8 | 5.078125 | 5 | 20 | fraccionario | 1, 104, 1248, 5, 2 | 4 | 8.013 | 7.762 | 45.5 a 54.5 | 40.06 | sí |
| 122.4 | 4.98046875 | 4 | 251 | fraccionario | 1, 102, 1224, 5, 2 | 4 | 8.170 | 8.106 | 44.4 a 55.6 | 32.68 | sí |
| 120 | 4.8828125 | 4 | 226 | fraccionario | 1, 120, 1440, 4, 3 | 22 | 8.333 | 8.203 | 44.4 a 55.6 | 33.33 | sí |
| 117.6 | 4.78515625 | 4 | 201 | fraccionario | 1, 98, 1176, 5, 2 | 4 | 8.503 | 8.437 | 44.4 a 55.6 | 34.01 | sí |
| 115.2 | 4.6875 | 4 | 176 | fraccionario | 1, 96, 1152, 5, 2 | 4 | 8.681 | 7.595 | 44.4 a 55.6 | 34.72 | sí |
| 112.8 | 4.58984375 | 4 | 151 | fraccionario | 1, 94, 1128, 5, 2 | 4 | 8.865 | 8.796 | 44.4 a 55.6 | 35.46 | sí |
| 110.4 | 4.4921875 | 4 | 126 | fraccionario | 1, 92, 1104, 5, 2 | 4 | 9.058 | 8.916 | 44.4 a 55.6 | 36.23 | sí |
| 108 | 4.39453125 | 4 | 101 | fraccionario | 1, 126, 1512, 7, 2 | 26 | 9.259 | 9.187 | 44.4 a 55.6 | 37.04 | sí |

## Solución elegida

- Máquina de estados a 24.576 MHz con dos instrucciones por periodo, reloj maestro de 12.288 MHz
- PLL del sistema: REFDIV 1, FBDIV 128, VCO 1536 MHz, POSTDIV1 5, POSTDIV2 5
- sysclk 61.44 MHz
- Divisor del PIO 2.5 (INT 2, FRAC 128), fraccionario
- Con el SDK 2.3.1: set_sys_clock_pll(1536000000, 5, 5) y pio_sm_set_clkdiv_int_frac8(pio, sm, 2, 128)

## Por qué

Una salida del PIO cambia como mucho una vez por ciclo de la máquina de estados, así que una onda cuadrada necesita al menos dos ciclos por periodo. Con la máquina a 12.288 MHz lo más rápido que sale es 6.144 MHz = 128 fS, que el PCM1808 no acepta. El caso que sirve es el de 24.576 MHz, y ahí no hay divisor entero posible.

La única forma entera que cumple la hoja es a 12.288 MHz: sysclk 61.44 MHz y divisor 5. Sirve si una máquina de estados tiene que correr a 12.288 MHz por otro motivo, pero no para generar el reloj maestro con el PIO.

Entre las fraccionarias que cumplen la hoja del RP2040 y la del PCM1808, es la de menor variación del periodo del reloj maestro. Con divisor 2.5 el delta-sigma alterna periodos de 2 y 3 ciclos de sysclk, y como el programa tiene dos instrucciones, cada periodo del reloj maestro suma uno de cada tipo: siempre 5 ciclos, 81.38 ns. El periodo no varía.

El precio es el ciclo de trabajo, que queda en 40.0 % o 60.0 % según qué instrucción caiga en el periodo corto. La hoja del PCM1808 pide de 40 % a 60 %, así que queda justo en el límite, sin margen para la diferencia entre subida y bajada del pin. Hay que medirlo con osciloscopio cuando exista la placa.

La siguiente opción que cumple las dos hojas (sysclk 132 MHz, divisor 5.37109375) ya varía 7.576 ns pico a pico, un 9 % del periodo del reloj maestro, con ciclo de trabajo de 45.5 % a 54.5 %.

REFDIV 1 porque la hoja del RP2040 lo recomienda con cristales de 5 a 15 MHz, y VCO de 1536 MHz porque indica que el jitter del PLL baja con el VCO más alto.

## Alternativa fuera del PIO

Conviene evaluarla antes de escribir el firmware. El RP2040 puede sacar un reloj generado por GPIO21 (CLOCK GPOUT0 en la tabla de funciones de la hoja), hasta 50 MHz. Ese divisor, con valor entero, no alterna entre dos divisores (la alternancia es como la hoja describe la división fraccionaria), y el bit DC50 de CLK_GPOUT0_CTRL corrige el ciclo de trabajo con divisores impares. Con el mismo sysclk de 61.44 MHz y divisor entero 5 saldrían 12.288 MHz exactos, sin divisor fraccionario y con el ciclo de trabajo corregido.

En el SDK 2.3.1, clock_gpio_init_int_frac8 configura la fuente y el divisor pero no activa DC50: habría que poner CLOCKS_CLK_GPOUT0_CTRL_DC50_BITS a mano. Nada de esto está medido todavía.

## Conclusión de diseño

Con el PIO no hay forma de sacar el reloj maestro de 12.288 MHz del cristal de 12 MHz con divisor entero. La mejor opción fraccionaria mantiene el periodo exacto pero deja el ciclo de trabajo en el borde de la especificación del PCM1808. La salida de reloj por GPIO21 con divisor entero es la alternativa a medir.
