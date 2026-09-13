# Reloj maestro del PCM1808

## Qué hace falta

A fS = 48 kHz el PCM1808 acepta en SCKI 256 fS = 12.288 MHz, 384 fS = 18.432 MHz o 512 fS = 24.576 MHz, con ciclo de trabajo entre 40 % y 60 % y pulsos alto y bajo de al menos 8 ns (hoja del PCM1808, tabla System clock timing). El Pico tiene un cristal de 12 MHz, así que la frecuencia sale de multiplicar con el PLL del sistema y dividir después.

## Solución elegida: GPOUT0 por GPIO21 con DC50

Decidida el 2026-09-13. Reemplaza a la del PIO, que queda como respaldo.

- PLL del sistema: REFDIV 1, FBDIV 128, VCO 1536 MHz, POSTDIV1 5, POSTDIV2 5. clk_sys queda en 61.44 MHz.
- Salida de reloj GPOUT0 por GPIO21, con clk_sys como fuente y divisor entero 5: 61.44 / 5 = 12.288 MHz exactos.
- DC50 activado a mano, porque clock_gpio_init_int_frac8 del SDK 2.3.1 no lo activa.
- Código en firmware/reloj_maestro.c: set_sys_clock_pll(1536000000, 5, 5), clock_gpio_init_int_frac8(21, CLOCKS_CLK_GPOUT0_CTRL_AUXSRC_VALUE_CLK_SYS, 5, 0) y después el bit CLOCKS_CLK_GPOUT0_CTRL_DC50_BITS en clocks_hw->clk[clk_gpout0].ctrl.

## Por qué

- Ciclo de trabajo. El divisor de reloj del RP2040 trabaja con los flancos de subida de la fuente, así que dividir por 5 da 40 % (hoja del RP2040, sección 2.15.3.4), justo el mínimo del PCM1808. Con DC50 el flanco de bajada de la salida pasa al flanco de bajada de la fuente y el ciclo de trabajo vuelve a 50 % nominal: dentro de especificación con 10 puntos de margen a cada lado, en vez de rozar el límite.
- Divisor entero. No alterna entre dos divisores, así que no hay nada que discutir sobre su efecto en el reloj.
- Libera una máquina de estados del PIO, que van a hacer falta para el I2S de entrada y el de salida.
- Es la única solución con divisor entero que cumple la hoja del RP2040 (ver la búsqueda al final).

## Margen de CPU

No hay sysclk más alto con divisor entero. En toda la búsqueda, los únicos sysclk con divisor entero son 61.44, 307.2 y 1536 MHz, y solo 61.44 MHz cumple el máximo de 133 MHz de clk_sys. Tampoco aparece otro entre 61.44 y 200 MHz, que es lo que la hoja menciona para 1.15 V.

122.88 MHz no aparece en ninguna solución. El PLL no lo da exacto: haría falta FBDIV 256 con REFDIV x POSTDIV1 x POSTDIV2 = 25, y ninguna de esas combinaciones deja el VCO entre 750 y 1600 MHz. 153.6 MHz sí sale del PLL (VCO de 1536 MHz dividido por 10), pero pasa de 133 MHz y solo funciona con divisor fraccionario: 12.5 para 12.288 MHz y 6.25 para 24.576 MHz.

Si más adelante hace falta más CPU, el precio es volver a un divisor fraccionario.

## Respaldo: PIO a 24.576 MHz con divisor 2.5

Si GPOUT0 no sirviera, por ejemplo porque GPIO21 hiciera falta para otra cosa:

- Mismo PLL, clk_sys de 61.44 MHz.
- Una máquina de estados a 24.576 MHz con un programa de dos instrucciones, una que pone el pin en alto y otra que lo pone en bajo: pio_sm_set_clkdiv_int_frac8(pio, sm, 2, 128).
- Periodo exacto de 5 ciclos de clk_sys, 81.38 ns.
- Ciclo de trabajo de 40/60 %, en el límite del PCM1808.
- Ocupa una máquina de estados del PIO.

## Corrección: el divisor 2.5 del PIO no mete jitter de periodo

Al plantear el reloj se dio por hecho que un divisor fraccionario en el PIO siempre mete jitter en el reloj maestro. En el caso del respaldo no es así, y queda escrito para no arrastrar el malentendido.

Con fracción de exactamente 0.5, el delta-sigma del divisor alterna estrictamente periodos de 2 y 3 ciclos de clk_sys. Un bucle de dos instrucciones toma siempre uno de cada uno, así que cada periodo del reloj maestro dura 5 ciclos, 81.38 ns, sin excepción. El periodo sale exacto y no hay jitter de periodo. El único problema es el ciclo de trabajo asimétrico: 2 ciclos en un nivel y 3 en el otro, 40/60 %.

El jitter de periodo aparece con cualquier otra fracción, porque entonces el patrón del divisor dura 4 ticks o más y deja de coincidir con el bucle de dos instrucciones. Por ejemplo, con clk_sys de 132 MHz y divisor 5.37109375 el periodo varía 7.576 ns pico a pico. Lo que dice la hoja del RP2040 sobre divisores fraccionarios que dan un reloj con jitter (secciones 2.15.3.3 y 3.5.5) vale para esos casos, no para 0.5 con dos instrucciones.

## Cómo verificar la frecuencia sin osciloscopio

Lo que puede fallar. La frecuencia sale del cristal con cuentas enteras, así que si la configuración es correcta la relación con el cristal es exacta. Lo que puede fallar es la configuración (el PLL o el divisor no quedaron como se esperaba, DC50 sin activar, GPIO21 sin la función de reloj) o la conexión hasta el PCM1808. Esos errores mueven la frecuencia en proporciones grandes: si el PLL se quedara en los 125 MHz con que arranca el SDK, por GPIO21 saldrían 25 MHz. No hace falta un instrumento de precisión para verlos, alcanza con distinguir 12.288 MHz de valores cercanos. El error del cristal, en partes por millón, es otro tema y se ve en el paso 3.

Los pasos van de menos a más cableado. Los dos primeros necesitan un firmware de prueba que imprima por USB, que todavía no está escrito.

### 1. Sin cables: la configuración

Leer desde el firmware e imprimir por USB:

- CLK_GPOUT0_CTRL (clocks_hw->clk[clk_gpout0].ctrl): ENABLE y DC50 activos, y la fuente en clk_sys.
- CLK_GPOUT0_DIV: entero 5 y fracción 0.
- La salida del PLL medida con el contador de frecuencia del RP2040 (FC0, sección 2.15.4), que cuenta flancos contra clk_ref, y clk_ref viene del cristal: frequency_count_khz(CLOCKS_FC0_SRC_VALUE_PLL_SYS_CLKSRC_PRIMARY) tiene que dar 61440.

clock_get_hz(clk_sys) no sirve para esto: devuelve el valor que el SDK guardó al configurar, no una medición.

### 2. Un cable: el pin

Puentear GPIO21 con GPIO20, que es la entrada de reloj CLOCK GPIN0. Poner GPIO20 en función de reloj (GPIO_FUNC_GPCK) y medir con frequency_count_khz(CLOCKS_FC0_SRC_VALUE_CLKSRC_GPIN0): tiene que dar 12288. Así se mide la señal que de verdad sale del pin y vuelve a entrar.

frequency_count_khz usa un intervalo de 1 ms, con exactitud de 2 kHz: sobra para distinguir 12.288 MHz de 12 MHz o de 25 MHz. Escribiendo FC0_INTERVAL a mano se llega a 62.5 Hz con 32 ms (tabla 206 de la hoja). Con el cable desde el pin SCKI del PCM1808 hasta GPIO20 se comprueba además que el reloj llega al integrado.

El contador usa el mismo cristal que genera el reloj, así que este paso no dice nada del error del cristal. Solo confirma que la configuración y el pin están bien.

### 3. Contra otro reloj: la tarjeta de sonido USB

Para comparar el cristal del Pico con uno independiente, se compila una versión de prueba con el divisor de GPOUT0 en 81920: 61.44 MHz / 81920 = 750 Hz exactos, y 81920 cabe en el entero de 24 bits del divisor. GPIO21 va a la entrada de micrófono de la tarjeta a través de un divisor resistivo que baje los 3.3 V a unas decenas de mV, por ejemplo 100 kΩ en serie y 1 kΩ a masa. El nivel se ajusta mirando en medir.py que el pico quede por debajo de -6 dBFS.

Se graba con medir.py y se mide la frecuencia con analizador.ajuste_seno(x, 48000, 750). Con 5 s de captura, en simulación con una cuadrada limitada a 20 kHz, el ajuste mide la frecuencia con menos de 0.2 ppm de error con ruido a -40 dBFS, y menos de 0.02 ppm con ruido a -60 dBFS. Lo que se lee entonces es la diferencia entre el cristal del Pico y el de la tarjeta. Un error de configuración se ve como una frecuencia muy distinta: con el PLL en 125 MHz saldrían 1525.88 Hz.

Límite: la tarjeta tiene su propio error de cristal, así que este paso compara los dos relojes y no certifica ninguno. Para el PCM1808 alcanza, porque lo que necesita es que el reloj maestro sea 256 veces fS, y eso lo garantiza que todo salga de clk_sys por cuentas enteras.

### 4. De punta a punta, cuando funcione la captura

Un tono de 1 kHz generado por la tarjeta USB en la entrada del PCM1808, capturado por el Pico y medido con ajuste_seno, tiene que dar 1000 Hz con la misma diferencia en ppm del paso 3 y el signo cambiado, porque ahora genera la tarjeta y mide el Pico. Un error en fS se vería como el mismo desvío en la frecuencia del tono.

## Búsqueda exhaustiva

<!-- inicio del bloque generado por relojes.py -->
Bloque generado por relojes.py el 2026-09-13 15:25 -0500 (sha256 del script c1a1431a0060, Python 3.12.0). Se reescribe en cada corrida; lo que está fuera de las marcas no lo toca. Todas las soluciones exactas, con cada restricción marcada, están en reloj-soluciones.csv.

### Condiciones

Se probaron las 941.535 combinaciones de REFDIV, FBDIV, POSTDIV1 y POSTDIV2 y, para cada una, el divisor que haría falta en cada camino. Una combinación es solución si ese divisor se puede escribir exacto en el registro del camino. Todo el cálculo es en enteros, sin redondeo.

PLL del sistema, restricciones del enunciado:

- FREF = 12 MHz, REFDIV de 1 a 63, FBDIV de 16 a 320
- VCO = FREF/REFDIV x FBDIV entre 750 y 1600 MHz
- POSTDIV1 y POSTDIV2 de 1 a 7, sysclk = VCO/(POSTDIV1 x POSTDIV2)

Divisores:

- PIO: entero de 16 bits más fracción/256, de 1 a 65536 (sección 3.5.5).
- GPOUT0: entero de 24 bits más fracción/256, que divide por 1 o por 2.0 en adelante (sección 2.15.3.3). Salida de hasta 50 MHz (sección 2.15.1).

Restricciones que agrega la hoja del RP2040 y que se marcan aparte:

- FREF/REFDIV de al menos 5 MHz (sección 2.18). Con el cristal de 12 MHz deja REFDIV en 1 o 2.
- FREF/REFDIV no mayor que VCO/16 (sección 2.18). Equivale a FBDIV >= 16, así que se cumple siempre.
- clk_sys de 133 MHz como máximo (secciones 2.15 y 2.18).

Irregularidad del divisor, sin el jitter propio del PLL:

- PIO: delta-sigma de primer orden que alarga algunos periodos de n a n+1 ciclos de sysclk (sección 3.5.5), en régimen estable, sin los primeros 256 periodos después de arrancar.
- GPOUT0: con fracción, cada periodo dura n o n+1 ciclos de la fuente (sección 2.15.3.3); con divisor entero no alterna. Con divisor impar el ciclo de trabajo es floor(n/2)/n, y 50 % con DC50 (sección 2.15.3.4).

### Resultado

| Camino | Soluciones exactas | Con divisor entero | Cumplen la hoja del RP2040 | Cumplen la hoja y tienen divisor entero |
|---|---|---|---|---|
| GPOUT0 por GPIO21 | 4097 | 8 | 1182 | 2 |
| PIO con la máquina a 24.576 MHz, dos instrucciones por periodo | 2416 | 0 | 672 | 0 |
| PIO con la máquina a 12.288 MHz, una instrucción por periodo | 4144 | 8 | 1205 | 2 |

PIO con la máquina a 24.576 MHz, dos instrucciones por periodo: ninguna combinación da divisor entero, ni con las restricciones del enunciado ni con las de la hoja.

No es un límite de la búsqueda. Para que sysclk/24.576 MHz sea entero, FBDIV tendría que ser múltiplo de 256, o sea 256, y entonces REFDIV x POSTDIV1 x POSTDIV2 tendría que dividir a 125 con REFDIV entre 2 y 4 para que el VCO quede en rango, lo que no pasa.

Con divisor entero, en cualquier camino, los únicos sysclk posibles son 61.44, 307.2 y 1536 MHz. Cumple la hoja del RP2040: 61.44 MHz.

Soluciones con divisor entero, sin filtrar:

| Camino | sysclk (MHz) | Divisor | REFDIV, FBDIV, VCO (MHz), POSTDIV1, POSTDIV2 | REF >= 5 MHz | sysclk <= 133 MHz |
|---|---|---|---|---|---|
| GPOUT0 por GPIO21 | 61.44 | 5 | 1, 128, 1536, 5, 5 | sí | sí |
| GPOUT0 por GPIO21 | 61.44 | 5 | 2, 256, 1536, 5, 5 | sí | sí |
| GPOUT0 por GPIO21 | 307.2 | 25 | 1, 128, 1536, 5, 1 | sí | no |
| GPOUT0 por GPIO21 | 307.2 | 25 | 1, 128, 1536, 1, 5 | sí | no |
| GPOUT0 por GPIO21 | 307.2 | 25 | 2, 256, 1536, 5, 1 | sí | no |
| GPOUT0 por GPIO21 | 307.2 | 25 | 2, 256, 1536, 1, 5 | sí | no |
| GPOUT0 por GPIO21 | 1536 | 125 | 1, 128, 1536, 1, 1 | sí | no |
| GPOUT0 por GPIO21 | 1536 | 125 | 2, 256, 1536, 1, 1 | sí | no |
| PIO con la máquina a 12.288 MHz, una instrucción por periodo | 61.44 | 5 | 1, 128, 1536, 5, 5 | sí | sí |
| PIO con la máquina a 12.288 MHz, una instrucción por periodo | 61.44 | 5 | 2, 256, 1536, 5, 5 | sí | sí |
| PIO con la máquina a 12.288 MHz, una instrucción por periodo | 307.2 | 25 | 1, 128, 1536, 5, 1 | sí | no |
| PIO con la máquina a 12.288 MHz, una instrucción por periodo | 307.2 | 25 | 1, 128, 1536, 1, 5 | sí | no |
| PIO con la máquina a 12.288 MHz, una instrucción por periodo | 307.2 | 25 | 2, 256, 1536, 5, 1 | sí | no |
| PIO con la máquina a 12.288 MHz, una instrucción por periodo | 307.2 | 25 | 2, 256, 1536, 1, 5 | sí | no |
| PIO con la máquina a 12.288 MHz, una instrucción por periodo | 1536 | 125 | 1, 128, 1536, 1, 1 | sí | no |
| PIO con la máquina a 12.288 MHz, una instrucción por periodo | 1536 | 125 | 2, 256, 1536, 1, 1 | sí | no |

Las tablas que siguen tienen una fila por par de sysclk y divisor que cumple la hoja del RP2040, ordenadas por la irregularidad que mete el divisor. La configuración de PLL es la representativa: REFDIV 1, el VCO más alto (la hoja indica que minimiza el jitter) y POSTDIV1 >= POSTDIV2. Configuraciones cuenta cuántas combinaciones de PLL dan el mismo sysclk. Cada tabla muestra las 12 primeras; el resto está en reloj-soluciones.csv.

### GPOUT0 por GPIO21

203 pares de sysclk y divisor.

| sysclk (MHz) | Divisor | INT | FRAC | Tipo | REFDIV, FBDIV, VCO (MHz), POSTDIV1, POSTDIV2 | Configuraciones | Variación del periodo (ns p-p) | Ciclo de trabajo |
|---|---|---|---|---|---|---|---|---|
| 61.44 | 5 | 5 | 0 | entero | 1, 128, 1536, 5, 5 | 2 | 0.000 | 50 % con DC50 (40.0 % sin DC50) |
| 132 | 10.7421875 | 10 | 190 | fraccionario | 1, 132, 1584, 4, 3 | 30 | 7.576 | no se calcula |
| 130.8 | 10.64453125 | 10 | 165 | fraccionario | 1, 109, 1308, 5, 2 | 4 | 7.645 | no se calcula |
| 129.6 | 10.546875 | 10 | 140 | fraccionario | 1, 108, 1296, 5, 2 | 4 | 7.716 | no se calcula |
| 128.4 | 10.44921875 | 10 | 115 | fraccionario | 1, 107, 1284, 5, 2 | 4 | 7.788 | no se calcula |
| 127.2 | 10.3515625 | 10 | 90 | fraccionario | 1, 106, 1272, 5, 2 | 4 | 7.862 | no se calcula |
| 126 | 10.25390625 | 10 | 65 | fraccionario | 1, 126, 1512, 4, 3 | 27 | 7.937 | no se calcula |
| 124.8 | 10.15625 | 10 | 40 | fraccionario | 1, 104, 1248, 5, 2 | 4 | 8.013 | no se calcula |
| 123.6 | 10.05859375 | 10 | 15 | fraccionario | 1, 103, 1236, 5, 2 | 4 | 8.091 | no se calcula |
| 122.4 | 9.9609375 | 9 | 246 | fraccionario | 1, 102, 1224, 5, 2 | 4 | 8.170 | no se calcula |
| 121.2 | 9.86328125 | 9 | 221 | fraccionario | 1, 101, 1212, 5, 2 | 4 | 8.251 | no se calcula |
| 120 | 9.765625 | 9 | 196 | fraccionario | 1, 120, 1440, 4, 3 | 22 | 8.333 | no se calcula |

### PIO con la máquina a 24.576 MHz, dos instrucciones por periodo

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

### PIO con la máquina a 12.288 MHz, una instrucción por periodo

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

### Mejor opción de cada camino

- GPOUT0 por GPIO21: sysclk 61.44 MHz (REFDIV 1, FBDIV 128, VCO 1536 MHz, POSTDIV1 5, POSTDIV2 5), divisor 5 entero, sin variación de periodo, ciclo de trabajo de 50 % con DC50 (40.0 % sin DC50) y pulsos de 40.69 ns.
- PIO con la máquina a 24.576 MHz, dos instrucciones por periodo: sysclk 61.44 MHz (REFDIV 1, FBDIV 128, VCO 1536 MHz, POSTDIV1 5, POSTDIV2 5), divisor 2.5 (INT 2, FRAC 128), variación de periodo 0.000 ns, TIE 0.000 ns, ciclo de trabajo de 40.0 % a 60.0 %, en el límite del PCM1808.
- PIO con la máquina a 12.288 MHz, una instrucción por periodo: no genera el reloj maestro. Una salida del PIO cambia como mucho una vez por ciclo de la máquina, así que lo más rápido que sale es 6.144 MHz = 128 fS, y el PCM1808 pide 256, 384 o 512 fS.
<!-- fin del bloque generado por relojes.py -->
