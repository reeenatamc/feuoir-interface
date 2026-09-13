# Bitácora

Una entrada por fase: qué se midió, en qué condiciones, qué se decidió y por qué. Los resultados completos están en los archivos que cita cada entrada.

## Fase 0: herramienta de medición (2026-09-13)

Qué se midió: nada que quedara guardado. medir.py se probó con el micrófono interno de la Mac solo para validar que graba y guarda; no hay capturas en mediciones/.

Condiciones: MacBook Pro 16" 2019, 48 kHz, 5 s por captura, volumen de entrada del sistema en 71.

Qué se decidió y por qué:

- La guitarra entra por una tarjeta de sonido USB con entrada de micrófono de tres contactos. El jack de 3.5 mm de la Mac es combinado de audífonos y micrófono, y un adaptador simple no funciona ahí.
- El micrófono interno no sirve para caracterizar la guitarra: entrega un solo canal ya procesado y ese procesamiento no se puede desactivar.
- El volumen de entrada queda fijo en 71, porque si cambia las mediciones dejan de ser comparables.

Detalle en DECISIONES.md.

## Fase 1: verificación del análisis (2026-09-13)

Qué se midió: el código de análisis, con señales sintéticas de resultado conocido y sin hardware. calibrar.py corre 11 pruebas con 170 chequeos:

- pico y RMS de senoidales de amplitud 1, 0.5, 0.1 y 0.001, y un caso con el pico en la excursión negativa
- THD+N de una senoidal con un armónico al 1 %, con el segundo y el tercer armónico y con una fundamental que no cae en un bin
- RMS de ruido gaussiano y uniforme de varianza conocida
- resolución de la FFT con dos tonos iguales separados 2 Hz
- ajuste de senoidal, SNR, THD+N con ruido, generadores de tono y barrido, y respuesta en frecuencia de un Butterworth de orden 2 en 1 kHz

Condiciones: Python 3.12.0, numpy 2.5.3, scipy 1.18.1, macOS 26.5.2 en Intel. Frecuencias de muestreo de 48 kHz y 44.1 kHz. Semillas fijas; en las pruebas con ruido la tolerancia es de 4 errores estándar del estimador. analizador.py con sha256 que empieza en 112481eab5b7.

Resultado: pasaron todas las pruebas en las dos corridas guardadas, calibraciones/2026-09-13-calibracion (169 chequeos) y calibraciones/2026-09-13-calibracion-2 (170, ya con el caso del pico negativo). Ningún chequeo usó más de la mitad de su tolerancia; los que más se acercaron fueron los de SNR, que dependen del ruido, al 50 %.

Como todo pasó a la primera, se comprobó que las pruebas detectan errores: se corrió calibrar.py contra 15 copias de analizador.py, cada una con un error inyectado (RMS sin raíz, pico sin valor absoluto, espectro sin el factor 2, resolución al doble, picos sin umbral, ajuste sin refinar la frecuencia, fase con signo invertido, THD+N sin la raíz de 2, banda superior ignorada, SNR en potencia, amplitud del tono mal escalada, rampa final sin invertir, barrido con log10, una frecuencia de más en frecuencias_log y fase de la respuesta invertida). Las 15 hicieron fallar la calibración con código 1. Esa corrida se hizo fuera del repo y solo queda este resumen.

Qué se decidió y por qué:

- Se agregó el caso del pico en la excursión negativa. Sin él, un pico calculado como max(x) en vez de max(|x|) pasaba todas las pruebas, porque en una senoidal los dos dan lo mismo.
- Las señales de las pruebas se arman con numpy dentro de calibrar.py, sin usar los generadores de analizador.py, para que un error en un generador no tape un error en el análisis. Los generadores se verifican aparte.

## Fase 2: analizador.py (2026-09-13)

Qué se midió: lo mismo que en la fase 1; cada función de analizador.py tiene su prueba en calibrar.py.

Condiciones: las de la fase 1.

Qué se decidió y por qué:

- El análisis vive en analizador.py y medir.py lo importa, para que lo que se mide sea exactamente lo que se verificó. medir.py no se podía probar tal cual porque graba apenas se ejecuta.
- El espectro de medir.py pasa a dBFS absolutos en vez de normalizado a su máximo, para poder leer el nivel de cada componente.
- THD+N relativo a la fundamental y limitado a la banda de 20 Hz a 20 kHz. Con esa definición un armónico al 1 % da 1.000 %; relativo al total daría 0.99995 %.
- La fundamental se quita con un ajuste de senoidal por mínimos cuadrados y no con un filtro de muesca, para que el resultado no dependa de que el tono caiga justo en un bin.
- SNR con dos capturas, porque con el circuito la medición va a ser así: una captura con el tono de prueba y otra con la entrada sin señal.
- Respuesta en frecuencia con barrido escalonado (tonos de 0.5 s y se descarta el 20 % de cada borde) en vez de un barrido continuo. Cada punto sale de un ajuste de senoidal y se puede comparar contra una respuesta exacta. El barrido logarítmico también está, como señal de excitación.

## Fase 3: reloj maestro del PCM1808 (2026-09-13)

Qué se midió: no hay medición, es un cálculo. relojes.py recorrió las 941.535 combinaciones de REFDIV, FBDIV, POSTDIV1 y POSTDIV2 del PLL del RP2040 y se quedó con las que, con el divisor del PIO, dan exactamente 12.288 MHz o 24.576 MHz en la máquina de estados.

Condiciones: cristal de 12 MHz. Restricciones del enunciado (REFDIV de 1 a 63, FBDIV de 16 a 320, VCO de 750 a 1600 MHz, POSTDIV1 y POSTDIV2 de 1 a 7, divisor entero de 16 bits más fracción/256) y, marcadas aparte, las que agrega la hoja del RP2040: referencia de al menos 5 MHz y clk_sys de 133 MHz como máximo. Jitter calculado con el modelo delta-sigma de primer orden del divisor que describe la hoja, en régimen estable y sin el jitter propio del PLL. Del PCM1808 se usó el ciclo de trabajo de 40 % a 60 % y los pulsos de al menos 8 ns.

Resultado: 4144 soluciones exactas para 12.288 MHz, 8 con divisor entero y 2 de ellas dentro de la hoja. 2416 soluciones para 24.576 MHz, ninguna con divisor entero. Detalle en docs/reloj.md y docs/reloj-soluciones.csv.

La primera corrida tenía un error: el cálculo de jitter incluía el primer periodo después de arrancar el divisor, que no sigue el patrón estable, y eso escondía la solución de 61.44 MHz. Se corrigió antes de sacar conclusiones.

Qué se decidió y por qué:

- El reloj maestro se genera con dos instrucciones por periodo y la máquina a 24.576 MHz. Con una sola instrucción el pin cambia como mucho una vez por ciclo, y lo más rápido que sale es 6.144 MHz, que el PCM1808 no acepta.
- sysclk de 61.44 MHz (REFDIV 1, FBDIV 128, VCO 1536 MHz, POSTDIV1 5, POSTDIV2 5) y divisor del PIO de 2.5. El divisor alterna periodos de 2 y 3 ciclos de sysclk y cada periodo del reloj maestro suma uno de cada uno, así que dura siempre 81.38 ns. La siguiente opción ya varía 7.6 ns pico a pico.
- Conclusión de diseño: con el PIO no existe configuración de divisor entero para el reloj maestro. La elegida no tiene variación de periodo, pero su ciclo de trabajo es 40/60 %, justo en el límite del PCM1808.
- Queda pendiente medir ese ciclo de trabajo con osciloscopio y evaluar la salida de reloj por GPIO21 con divisor entero 5 y DC50, que evitaría el divisor fraccionario.

## Fase 4: toolchain del Pico (2026-09-13)

Qué se midió: que el toolchain compila el ejemplo blink de pico-examples hasta el .uf2, sin placa conectada.

Condiciones: macOS 26.5.2 en Intel, CMake 4.4.3, make de macOS, pico-sdk 2.3.1 con TinyUSB, pico-examples sdk-2.3.1, Arm GNU Toolchain 14.2.rel1, picotool 2.3.1 con libusb 1.0.30, PICO_BOARD=pico y build Release. El procedimiento exacto está en el README.

Resultado: blink.uf2 de 13312 bytes, 26 bloques UF2 para RP2040, con sha256 que empieza en 2a73f7553b4e636e. Sin avisos de compilación; configurar tardó 16 s y compilar 5 s. CMakeCache.txt confirma el compilador de ~/pico/toolchain y la sección .comment del ELF dice GCC 14.2.1 20241119. No se probó en una placa.

Qué se decidió y por qué:

- Arm GNU Toolchain 14.2.rel1, porque es la última versión con build para Mac Intel. La 14.3.rel1 y la 15.2.rel1 solo salen para darwin-arm64, según la lista de toolchains de la extensión de VS Code de Raspberry Pi. El tar.xz se verificó contra el sha256 que publica Arm.
- Todo en ~/pico, fuera del repo, para que el repo no cargue con el SDK ni con el toolchain.
- picotool instalado una vez aparte. Si no, el SDK lo baja y lo compila en cada proyecto; su propio aviso en tools/Findpicotool.cmake recomienda instalarlo.
- Del SDK solo el submódulo lib/tinyusb. Los demás no hicieron falta para compilar.
- Compilación con -j4 y no con todos los núcleos, porque la Mac anda justa de memoria.

## Fase 5: hojas de datos (2026-09-13)

Qué se bajó, a docs/datasheets/:

| Archivo | Documento | Revisión | Páginas | sha256, primeros 16 | Fuente |
|---|---|---|---|---|---|
| pcm1808.pdf | PCM1808 | SLES177B, agosto 2015 | 32 | 4ac1a7ec0c05ee97 | ti.com/lit/ds/symlink/pcm1808.pdf |
| pcm5102a.pdf | PCM510xA | SLAS859C, mayo 2015 | 44 | a522083606b8e994 | ti.com/lit/ds/symlink/pcm5102a.pdf |
| tl072.pdf | TL07xx | SLOS080W, julio 2025 | 89 | 40b14981bad45917 | ti.com/lit/ds/symlink/tl072.pdf |
| rp2040-datasheet.pdf | RP2040 | build 2025-02-20, 3184e62 | 642 | be56fbb75ba0ae9e | datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf |

Condiciones: descargadas el 2026-09-13.

Qué se decidió y por qué:

- Las restricciones del PLL del enunciado coinciden con la sección 2.18 de la hoja del RP2040. La hoja agrega dos más (referencia de al menos 5 MHz y clk_sys de 133 MHz como máximo) y relojes.py las marca aparte en vez de mezclarlas, para que se vea qué descarta cada una.
- Del PCM1808 salen los requisitos de SCKI que usa relojes.py: 256, 384 o 512 fS, ciclo de trabajo de 40 % a 60 % y pulsos de al menos 8 ns.

## Fase 6: reloj maestro por GPOUT0 con DC50 (2026-09-13)

Qué se midió: no hay medición. Se agregó a relojes.py el camino de la salida de reloj GPOUT0 y se compiló el firmware que configura el reloj.

Condiciones: las restricciones de la fase 3, más las del divisor de GPOUT0 (entero de 24 bits más fracción/256, que divide por 1 o por 2.0 en adelante) y la corrección de ciclo de trabajo DC50 (hoja del RP2040, sección 2.15.3.4). Firmware compilado con el toolchain de la fase 4 para PICO_BOARD=pico.

Resultado: con divisor entero, la única solución que cumple la hoja sigue siendo clk_sys de 61.44 MHz dividido por 5. firmware/build/feuoir.uf2 compila sin avisos, 14336 bytes en 28 bloques UF2. No se probó en una placa.

Qué se decidió y por qué:

- Reemplaza la decisión de la fase 3. El reloj maestro sale por GPOUT0 en GPIO21, con clk_sys de 61.44 MHz, divisor entero 5 y DC50. El ciclo de trabajo queda en 50 % nominal, con margen dentro de los 40 % a 60 % del PCM1808 en vez de quedar en el límite; el divisor entero no alterna; y se libera una máquina de estados del PIO para el I2S de entrada y el de salida.
- DC50 se escribe a mano después de clock_gpio_init_int_frac8, porque esa función del SDK 2.3.1 escribe CTRL sin DC50 y lo borraría si se pusiera antes. Sin DC50, dividir por 5 da 40 %. La hoja permite activarlo con el reloj corriendo.
- El PIO a 24.576 MHz con divisor 2.5 queda documentado como respaldo.
- Corrección a lo que se asumió en la fase 3: con fracción de exactamente 0.5 y un bucle de dos instrucciones, el periodo del PIO sale exacto. No hay jitter de periodo; el problema es solo el ciclo de trabajo asimétrico.
- No hay sysclk más alto con divisor entero. Los únicos son 61.44, 307.2 y 1536 MHz, y solo el primero cumple la hoja. 122.88 MHz no aparece en ninguna solución, y 153.6 MHz solo con divisor fraccionario y por encima de 133 MHz. Si más adelante hace falta CPU, el precio es volver a un divisor fraccionario.
- No hay osciloscopio. La frecuencia se va a verificar con el contador de frecuencia interno del RP2040, primero sobre la salida del PLL y después con GPIO21 puenteado a GPIO20. Contra otro reloj, se usa una versión de prueba a 750 Hz grabada con la tarjeta USB y medida con analizador.py. Detalle en docs/reloj.md.

## Fase 7: prueba de errores inyectados como script (2026-09-13)

Qué se midió: que calibrar.py atrapa los 15 errores de la fase 1, ahora con tests/mutaciones.py dentro del repo en lugar de la corrida suelta de esa fase.

Condiciones: Python 3.12.0, numpy 2.5.3, scipy 1.18.1, macOS 26.5.2 en Intel. analizador.py con sha256 que empieza en 112481eab5b7 y calibrar.py en 65da94a83f2d. Tres calibraciones en paralelo.

Resultado: la copia de control pasó y las 15 copias con errores hicieron fallar la calibración. La corrida tardó 14 s y está en calibraciones/2026-09-13-mutaciones/resultados.json, con las pruebas que atraparon cada error.

Qué se decidió y por qué:

- La prueba vive en tests/mutaciones.py y es ejecutable, para volver a correrla cada vez que alguien toque analizador.py o calibrar.py.
- Corre primero una copia sin cambios como control. Si el control fallara, que fallen las copias con errores no demostraría nada. La corrida suelta de la fase 1 no tenía control.
- Cada mutación reemplaza un texto que tiene que aparecer exactamente una vez en analizador.py. Si un cambio lo hace desaparecer, el script falla en vez de saltarse esa mutación en silencio, y hay que actualizarla.
- Tres calibraciones en paralelo por defecto, para no llenar la memoria de la Mac.
