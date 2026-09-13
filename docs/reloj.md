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

Los pasos van de menos a más cableado. Los dos primeros los hace firmware/verificar_reloj.c, que imprime un informe por USB cada 2 s y mide con el intervalo de 32 ms del contador (cómo compilarlo y leerlo está en el README). Está escrito y compila, pero no se probó en una placa.

Compilado con FEUOIR_RELOJ_EXTERNO, el mismo firmware sirve para el oscilador externo: espera GPOUT0 apagado y en el paso 2 mide lo que entra por GPIO20, que entonces viene de la salida del oscilador. Da su frecuencia y la diferencia en ppm respecto del cristal del Pico, con una exactitud de 62.5 Hz, unos 5 ppm. Ahí acepta hasta 1000 ppm: detecta un oscilador equivocado, no juzga su exactitud.

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

## Jitter del reloj maestro

Lo anterior optimiza la exactitud de frecuencia, que para un ADC casi no importa: una desviación fija de unas partes por millón solo corre fS en esa misma proporción. Lo que degrada el audio es el jitter, la variación de un periodo a otro, porque mueve el instante en que se toma cada muestra. Un error de tiempo τ al muestrear una senoidal de frecuencia f deja un error de amplitud proporcional a 2π·f·τ, así que el jitter pesa más cuanto más aguda es la señal y no aparece sin señal.

### Qué dicen las hojas de datos

PCM1808. No da ninguna tolerancia de jitter de SCKI en términos de calidad de audio. Lo que sí dice:

- El modulador delta-sigma trabaja a 64 fS y el filtro digital a 128 fS, frecuencias que el integrado saca dividiendo SCKI (sección 7.3.2). Con SCKI a 256 fS, el reloj del modulador es SCKI dividido por 4: sus transiciones son transiciones de SCKI y el jitter pasa tal cual.
- En modo esclavo LRCK tiene que estar sincronizado con SCKI. Si la relación entre los dos se corre más de ±6 BCK dentro de un periodo de muestra por jitter de LRCK o de SCKI, el ADC se detiene y saca ceros hasta resincronizar (sección 7.3.3). Es un límite de funcionamiento, no de calidad.
- En las recomendaciones de diseño (sección 10.1.6) dice que la calidad del reloj del sistema puede influir en el desempeño dinámico, y que puede hacer falta considerar su ciclo de trabajo, su jitter y, en modo esclavo, la diferencia de tiempo entre las transiciones de SCKI y las de BCK o LRCK. Sin números.
- Sus cifras de desempeño (rango dinámico y S/N de 99 dB típicos, ponderados A, y THD+N de -93 dB) están medidas en modo maestro con SCKI a 512 fS.

RP2040. La hoja no da ningún número de jitter ni de ruido de fase, ni del PLL ni de GPOUT. Lo único que dice es cualitativo (sección 2.18.2.1): el jitter es la variación de un ciclo a otro del periodo de salida del PLL; no compromete la estabilidad del sistema porque la lógica tiene margen para el peor caso, pero para audio y video suele hacer falta un reloj muy exacto; y el jitter es menor con el VCO lo más alto posible, que es lo que ya hace la configuración elegida con 1536 MHz. Aparte, la división fraccionaria de los divisores de reloj da un reloj con jitter (sección 2.15.3.3), cosa que la solución elegida evita con divisor entero.

Así que el orden de magnitud del ruido de fase del PLL no sale de la hoja. Lo que sí se puede calcular es cuánto jitter haría falta para que se note con este ADC. El número real lo va a dar la comparación con el oscilador externo.

### Cuánto jitter se notaría

Calculado con jitter.py (simulaciones/2026-09-13-jitter/resultados.json), con un tono a -1 dBFS y el ruido propio del ADC igual al S/N típico del PCM1808. La hoja da ese S/N ponderado A y la simulación usa ruido blanco sin ponderar, así que es una aproximación.

| Tono | Modelo | Jitter RMS que iguala el ruido del ADC | Jitter RMS que sube el ruido 0.5 dB |
|---|---|---|---|
| 10 kHz | muestreo directo a fS | 220 ps | 77 ps |
| 10 kHz | muestreo a 64 fS y decimación | 1.76 ns | 614 ps |
| 20 kHz | muestreo directo a fS | 110 ps | 38 ps |
| 20 kHz | muestreo a 64 fS y decimación | 878 ps | 307 ps |

Con muestreo a 64 fS, como en el modulador del PCM1808, el ruido del jitter se reparte hasta 32 fS y el filtro de decimación deja pasar solo la parte de audio: 18 dB menos. En la simulación, 1 ns de jitter blanco con un tono de 10 kHz da un THD+N de -84.8 dB con muestreo directo y de -102.9 dB con muestreo a 64 fS. Los dos modelos valen para un modulador de tiempo discreto. La hoja no dice si el del PCM1808 es de tiempo discreto o continuo, y uno de tiempo continuo puede ser bastante más sensible, porque el jitter también afecta su realimentación.

Para el experimento: con menos de unos 40 ps el ruido no sube más de 0.5 dB en ninguno de los dos modelos, ni siquiera a 20 kHz, y con más de 1 ns sube en los dos con tonos de 10 kHz o más. Si la comparación no muestra diferencia, eso también es un resultado: el efecto del jitter de GPOUT0 queda por debajo de lo que este sistema puede resolver.

### Cómo se detecta con analizador.py

La idea de buscar faldas alrededor de un tono de prueba y pérdida de SNR se confirma en la simulación, con dos matices.

1. Faldas solo si el jitter es lento. Con 1 ns de jitter concentrado por debajo de 20 Hz y un tono de 10 kHz, el espectro sube 40 dB entre 2 y 20 Hz del tono (-106.3 dBc contra -146.6 dBc sin jitter), 25 dB entre 20 y 200 Hz (-121.1 contra -146.3) y nada más allá de 200 Hz. El jitter blanco no hace faldas: 1 ns levanta el piso parejo, unos 13 dB a cualquier distancia del tono (de -146 a -133 dBc, de 2 Hz a 2 kHz). El jitter periódico hace rayas: 1 ns de pico a 1 kHz deja dos bandas laterales a ±1 kHz del tono de 10 kHz, a -90.1 dBc, justo lo que predice la modulación de fase.

2. La pérdida de SNR solo se ve con tono. snr_db compara la captura con tono contra una sin señal, y sin señal el jitter no tiene nada que correr: da 98.0 dB con y sin 1 ns de jitter. Lo que sí lo ve es thd_n, que mide todo lo que queda al quitar el tono: con 1 ns y un tono de 10 kHz pasa de -98.0 a -84.6 dB. La pérdida por jitter se mide como THD+N con tono, no con el snr_db de dos capturas.

La firma del jitter es que su efecto crece 20 dB por década con la frecuencia del tono: sin ruido del ADC, el mismo 1 ns da -104.8 dB con 1 kHz y -84.8 dB con 10 kHz. Una distorsión que crezca con la frecuencia podría dar un patrón parecido; lo que atribuye la diferencia al reloj es que cambie al mover el jumper.

Procedimiento, cuando funcione la captura por el Pico, en la misma sesión y cambiando solo el jumper:

- thd_n con tonos de 1 kHz y de 10 kHz al mismo nivel. Si empeora el agudo y no el de 1 kHz, hay ruido que depende de la frecuencia del tono.
- snr_db con la entrada sin señal. Tiene que dar lo mismo en las dos posiciones del jumper; si cambia, lo que cambió no es jitter.
- thd_n en una banda angosta alrededor del tono, por ejemplo f ± 200 Hz, para medir las faldas: en la simulación da -84.0 dB con jitter lento contra -114.9 dB sin él. calibrar.py verifica esta medición en test_thd_n_banda_angosta.
- espectro para ver la forma, con cuidado cerca del tono. Si el tono no cae justo en un bin, la fuga de la ventana Hann tapa lo que está a menos de unos 20 Hz: con 10000.37 Hz, la zona de 2 a 20 Hz da -93 dBc con y sin jitter, mientras thd_n en banda angosta sigue viendo la diferencia (-84.1 contra -115.0 dB). Con un tono de la tarjeta USB muestreado por el reloj del Pico, en la práctica el tono no va a caer justo en un bin.
- Misma fuente de tono, mismo nivel y misma duración de captura en las dos posiciones. La fuente también tiene su ruido de fase y sus faldas aparecen igual en las dos mediciones: lo que interesa es la diferencia.

## Oscilador externo de 12.288 MHz, previsto para comparar

El diseño deja un punto de conexión para un oscilador de cristal externo de 12.288 MHz y un jumper para elegir de dónde sale SCKI. No es para usarlo desde el principio: es para medir la diferencia entre GPOUT0 y un oscilador dedicado cuando exista el hardware, con el procedimiento de la sección anterior. Esa comparación es uno de los resultados del proyecto.

### Conexión

- Un oscilador de cristal de 12.288 MHz con salida CMOS de 3.3 V. SCKI acepta un alto desde 2 V y un bajo hasta 0.8 V, y tolera 5 V (hoja del PCM1808, condiciones de operación), así que la salida va directo.
- Un jumper de 3 pines cerca del PCM1808. El pin del medio va a SCKI, un extremo a GPIO21 (GPOUT0) y el otro a la salida del oscilador.
- Un jumper de 2 pines en la alimentación del oscilador, con el desacople que pida la hoja del oscilador. Se quita cuando se usa GPOUT0.
- Un pin de acceso a la salida del oscilador, para llevarla con un cable a GPIO20 y medir su frecuencia con el contador del RP2040.

### Condiciones para que la comparación sea justa

- El PCM1808 va en modo maestro a 256 fS en las dos posiciones del jumper: MD1 y MD0 en alto (tabla 2 de su hoja), fijados antes de encender. En modo esclavo LRCK tiene que estar sincronizado con SCKI (sección 7.3.3), y con un oscilador de otro cristal un LRCK generado por el Pico se iría corriendo hasta perder la sincronización. En modo maestro el PCM1808 genera BCK y LRCK a partir de SCKI, así que funciona igual con las dos fuentes y lo único que cambia es SCKI. Esto fija una condición para el I2S de entrada: el Pico recibe BCK y LRCK del PCM1808.
- El jumper se cambia con la placa sin alimentación. La hoja pide pasar por el reset de reloj detenido al cambiar SCKI (sección 7.4.2).
- La fuente que no se usa va apagada. Con el oscilador externo, el firmware se compila con la opción FEUOIR_RELOJ_EXTERNO y GPOUT0 no se enciende; con GPOUT0, se quita el jumper de alimentación del oscilador. Un reloj de 12.288 MHz conmutando en el pin de al lado podría acoplarse a SCKI, y como las dos fuentes tienen cristales distintos, el batido entre ellas correría los flancos de SCKI a baja frecuencia: justo las bandas laterales que se quieren medir.
- clk_sys queda en 61.44 MHz en los dos casos, porque FEUOIR_RELOJ_EXTERNO no lo cambia. La fuente del tono y el procedimiento de medición son los mismos.
- En la bitácora se anota el modelo exacto del oscilador y el jitter o ruido de fase que declare su hoja, porque el resultado es la comparación contra esa pieza en particular.

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
