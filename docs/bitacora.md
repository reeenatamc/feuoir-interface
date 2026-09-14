# Bitácora

Una entrada por etapa de trabajo, numeradas en el orden en que se hicieron: qué se midió, en qué condiciones, qué se decidió y por qué. Esa numeración no es la de las fases del proyecto, donde la captura por USB es la fase 5 y la reproducción la fase 6. Los resultados completos están en los archivos que cita cada entrada.

## Entrada 0: herramienta de medición (2026-09-13)

Qué se midió: nada que quedara guardado. medir.py se probó con el micrófono interno de la Mac solo para validar que graba y guarda; no hay capturas en mediciones/.

Condiciones: MacBook Pro 16" 2019, 48 kHz, 5 s por captura, volumen de entrada del sistema en 71.

Qué se decidió y por qué:

- La guitarra entra por una tarjeta de sonido USB con entrada de micrófono de tres contactos. El jack de 3.5 mm de la Mac es combinado de audífonos y micrófono, y un adaptador simple no funciona ahí.
- El micrófono interno no sirve para caracterizar la guitarra: entrega un solo canal ya procesado y ese procesamiento no se puede desactivar.
- El volumen de entrada queda fijo en 71, porque si cambia las mediciones dejan de ser comparables.

Detalle en DECISIONES.md.

## Entrada 1: verificación del análisis (2026-09-13)

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

## Entrada 2: analizador.py (2026-09-13)

Qué se midió: lo mismo que en la entrada 1; cada función de analizador.py tiene su prueba en calibrar.py.

Condiciones: las de la entrada 1.

Qué se decidió y por qué:

- El análisis vive en analizador.py y medir.py lo importa, para que lo que se mide sea exactamente lo que se verificó. medir.py no se podía probar tal cual porque graba apenas se ejecuta.
- El espectro de medir.py pasa a dBFS absolutos en vez de normalizado a su máximo, para poder leer el nivel de cada componente.
- THD+N relativo a la fundamental y limitado a la banda de 20 Hz a 20 kHz. Con esa definición un armónico al 1 % da 1.000 %; relativo al total daría 0.99995 %.
- La fundamental se quita con un ajuste de senoidal por mínimos cuadrados y no con un filtro de muesca, para que el resultado no dependa de que el tono caiga justo en un bin.
- SNR con dos capturas, porque con el circuito la medición va a ser así: una captura con el tono de prueba y otra con la entrada sin señal.
- Respuesta en frecuencia con barrido escalonado (tonos de 0.5 s y se descarta el 20 % de cada borde) en vez de un barrido continuo. Cada punto sale de un ajuste de senoidal y se puede comparar contra una respuesta exacta. El barrido logarítmico también está, como señal de excitación.

## Entrada 3: reloj maestro del PCM1808 (2026-09-13)

Qué se midió: no hay medición, es un cálculo. relojes.py recorrió las 941.535 combinaciones de REFDIV, FBDIV, POSTDIV1 y POSTDIV2 del PLL del RP2040 y se quedó con las que, con el divisor del PIO, dan exactamente 12.288 MHz o 24.576 MHz en la máquina de estados.

Condiciones: cristal de 12 MHz. Restricciones del enunciado (REFDIV de 1 a 63, FBDIV de 16 a 320, VCO de 750 a 1600 MHz, POSTDIV1 y POSTDIV2 de 1 a 7, divisor entero de 16 bits más fracción/256) y, marcadas aparte, las que agrega la hoja del RP2040: referencia de al menos 5 MHz y clk_sys de 133 MHz como máximo. Jitter calculado con el modelo delta-sigma de primer orden del divisor que describe la hoja, en régimen estable y sin el jitter propio del PLL. Del PCM1808 se usó el ciclo de trabajo de 40 % a 60 % y los pulsos de al menos 8 ns.

Resultado: 4144 soluciones exactas para 12.288 MHz, 8 con divisor entero y 2 de ellas dentro de la hoja. 2416 soluciones para 24.576 MHz, ninguna con divisor entero. Detalle en docs/reloj.md y docs/reloj-soluciones.csv.

La primera corrida tenía un error: el cálculo de jitter incluía el primer periodo después de arrancar el divisor, que no sigue el patrón estable, y eso escondía la solución de 61.44 MHz. Se corrigió antes de sacar conclusiones.

Qué se decidió y por qué:

- El reloj maestro se genera con dos instrucciones por periodo y la máquina a 24.576 MHz. Con una sola instrucción el pin cambia como mucho una vez por ciclo, y lo más rápido que sale es 6.144 MHz, que el PCM1808 no acepta.
- sysclk de 61.44 MHz (REFDIV 1, FBDIV 128, VCO 1536 MHz, POSTDIV1 5, POSTDIV2 5) y divisor del PIO de 2.5. El divisor alterna periodos de 2 y 3 ciclos de sysclk y cada periodo del reloj maestro suma uno de cada uno, así que dura siempre 81.38 ns. La siguiente opción ya varía 7.6 ns pico a pico.
- Conclusión de diseño: con el PIO no existe configuración de divisor entero para el reloj maestro. La elegida no tiene variación de periodo, pero su ciclo de trabajo es 40/60 %, justo en el límite del PCM1808.
- Queda pendiente medir ese ciclo de trabajo con osciloscopio y evaluar la salida de reloj por GPIO21 con divisor entero 5 y DC50, que evitaría el divisor fraccionario.

## Entrada 4: toolchain del Pico (2026-09-13)

Qué se midió: que el toolchain compila el ejemplo blink de pico-examples hasta el .uf2, sin placa conectada.

Condiciones: macOS 26.5.2 en Intel, CMake 4.4.3, make de macOS, pico-sdk 2.3.1 con TinyUSB, pico-examples sdk-2.3.1, Arm GNU Toolchain 14.2.rel1, picotool 2.3.1 con libusb 1.0.30, PICO_BOARD=pico y build Release. El procedimiento exacto está en el README.

Resultado: blink.uf2 de 13312 bytes, 26 bloques UF2 para RP2040, con sha256 que empieza en 2a73f7553b4e636e. Sin avisos de compilación; configurar tardó 16 s y compilar 5 s. CMakeCache.txt confirma el compilador de ~/pico/toolchain y la sección .comment del ELF dice GCC 14.2.1 20241119. No se probó en una placa.

Qué se decidió y por qué:

- Arm GNU Toolchain 14.2.rel1, porque es la última versión con build para Mac Intel. La 14.3.rel1 y la 15.2.rel1 solo salen para darwin-arm64, según la lista de toolchains de la extensión de VS Code de Raspberry Pi. El tar.xz se verificó contra el sha256 que publica Arm.
- Todo en ~/pico, fuera del repo, para que el repo no cargue con el SDK ni con el toolchain.
- picotool instalado una vez aparte. Si no, el SDK lo baja y lo compila en cada proyecto; su propio aviso en tools/Findpicotool.cmake recomienda instalarlo.
- Del SDK solo el submódulo lib/tinyusb. Los demás no hicieron falta para compilar.
- Compilación con -j4 y no con todos los núcleos, porque la Mac anda justa de memoria.

## Entrada 5: hojas de datos (2026-09-13)

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

## Entrada 6: reloj maestro por GPOUT0 con DC50 (2026-09-13)

Qué se midió: no hay medición. Se agregó a relojes.py el camino de la salida de reloj GPOUT0 y se compiló el firmware que configura el reloj.

Condiciones: las restricciones de la entrada 3, más las del divisor de GPOUT0 (entero de 24 bits más fracción/256, que divide por 1 o por 2.0 en adelante) y la corrección de ciclo de trabajo DC50 (hoja del RP2040, sección 2.15.3.4). Firmware compilado con el toolchain de la entrada 4 para PICO_BOARD=pico.

Resultado: con divisor entero, la única solución que cumple la hoja sigue siendo clk_sys de 61.44 MHz dividido por 5. firmware/build/feuoir.uf2 compila sin avisos, 14336 bytes en 28 bloques UF2. No se probó en una placa.

Qué se decidió y por qué:

- Reemplaza la decisión de la entrada 3. El reloj maestro sale por GPOUT0 en GPIO21, con clk_sys de 61.44 MHz, divisor entero 5 y DC50. El ciclo de trabajo queda en 50 % nominal, con margen dentro de los 40 % a 60 % del PCM1808 en vez de quedar en el límite; el divisor entero no alterna; y se libera una máquina de estados del PIO para el I2S de entrada y el de salida.
- DC50 se escribe a mano después de clock_gpio_init_int_frac8, porque esa función del SDK 2.3.1 escribe CTRL sin DC50 y lo borraría si se pusiera antes. Sin DC50, dividir por 5 da 40 %. La hoja permite activarlo con el reloj corriendo.
- El PIO a 24.576 MHz con divisor 2.5 queda documentado como respaldo.
- Corrección a lo que se asumió en la entrada 3: con fracción de exactamente 0.5 y un bucle de dos instrucciones, el periodo del PIO sale exacto. No hay jitter de periodo; el problema es solo el ciclo de trabajo asimétrico.
- No hay sysclk más alto con divisor entero. Los únicos son 61.44, 307.2 y 1536 MHz, y solo el primero cumple la hoja. 122.88 MHz no aparece en ninguna solución, y 153.6 MHz solo con divisor fraccionario y por encima de 133 MHz. Si más adelante hace falta CPU, el precio es volver a un divisor fraccionario.
- No hay osciloscopio. La frecuencia se va a verificar con el contador de frecuencia interno del RP2040, primero sobre la salida del PLL y después con GPIO21 puenteado a GPIO20. Contra otro reloj, se usa una versión de prueba a 750 Hz grabada con la tarjeta USB y medida con analizador.py. Detalle en docs/reloj.md.

## Entrada 7: prueba de errores inyectados como script (2026-09-13)

Qué se midió: que calibrar.py atrapa los 15 errores de la entrada 1, ahora con tests/mutaciones.py dentro del repo en lugar de la corrida suelta de esa entrada.

Condiciones: Python 3.12.0, numpy 2.5.3, scipy 1.18.1, macOS 26.5.2 en Intel. analizador.py con sha256 que empieza en 112481eab5b7 y calibrar.py en 65da94a83f2d. Tres calibraciones en paralelo.

Resultado: la copia de control pasó y las 15 copias con errores hicieron fallar la calibración. La corrida tardó 14 s y está en calibraciones/2026-09-13-mutaciones/resultados.json, con las pruebas que atraparon cada error.

Qué se decidió y por qué:

- La prueba vive en tests/mutaciones.py y es ejecutable, para volver a correrla cada vez que alguien toque analizador.py o calibrar.py.
- Corre primero una copia sin cambios como control. Si el control fallara, que fallen las copias con errores no demostraría nada. La corrida suelta de la entrada 1 no tenía control.
- Cada mutación reemplaza un texto que tiene que aparecer exactamente una vez en analizador.py. Si un cambio lo hace desaparecer, el script falla en vez de saltarse esa mutación en silencio, y hay que actualizarla.
- Tres calibraciones en paralelo por defecto, para no llenar la memoria de la Mac.

## 2026-09-13: el espectro de captura.png cambió de escala

Desde el commit e32c257 (Extrae el análisis a analizador.py), el espectro de captura.png está en dBFS absolutos. Antes estaba en dB relativos a su propio máximo. Las gráficas de antes y de después no se pueden comparar entre sí.

- Antes: 0 dB era el pico más alto de cada espectro, así que cada gráfica tenía su propia referencia. El eje vertical decía dB e iba de -100 a 5.
- Después: 0 dBFS es el fondo de escala del conversor, la misma referencia para todas las capturas. El eje vertical dice dBFS y va de -160 a 5.

Para saber de qué lado está una gráfica alcanza con mirar el rótulo del eje vertical. Los valores pico_dbfs y rms_dbfs de condiciones.json no cambiaron: la fórmula es la misma, y en 300 capturas simuladas dieron idénticos a dos decimales con el código de antes y con el de después.

## Entrada 8: THD+N en banda angosta (2026-09-13)

Qué se midió: que thd_n limitado a una banda angosta alrededor del tono ve solo lo que está cerca. Es la medición que se va a usar para las faldas que deja el jitter.

Condiciones: las de la entrada 1. Tono de 1 kHz con bandas laterales a ±100 Hz del 0.1 % de su amplitud, y componentes del 1 % a 500 Hz y a 3 kHz, fuera de la banda de 800 a 1200 Hz.

Resultado: calibrar.py pasa las 12 pruebas con 172 chequeos (calibraciones/2026-09-13-calibracion-3) y tests/mutaciones.py detecta las 16 mutaciones (calibraciones/2026-09-13-mutaciones-2).

Qué se decidió y por qué:

- La prueba nueva cubre un hueco: ninguna prueba usaba el borde inferior de la banda. Con la banda por defecto, de 20 Hz a 20 kHz, no hay nada por debajo de 20 Hz, así que un filtro que no cortara abajo pasaba todas las pruebas. Se comprobó con calibrar.py del commit be2678e y ese error inyectado: la calibración pasaba con código 0. Ahora lo atrapa test_thd_n_banda_angosta.
- Ese error quedó como mutación nueva en tests/mutaciones.py, banda_inferior_ignorada.

## Entrada 9: jitter del reloj maestro (2026-09-13)

Qué se midió: nada en hardware. Se revisaron las hojas del PCM1808 y del RP2040 buscando datos de jitter, y se simuló con jitter.py el efecto del jitter sobre un tono, medido con analizador.py.

Condiciones: tonos a -1 dBFS de 1 y 10 kHz, fS de 48 kHz, capturas de 5 s y ruido del ADC igual al S/N típico del PCM1808 (99 dB, ponderado A en la hoja y blanco en la simulación). Jitter blanco, lento (por debajo de 20 Hz) y periódico (1 kHz), con muestreo directo a fS y a 64 fS con decimación. Los 19 casos coinciden con la teoría; están en simulaciones/2026-09-13-jitter/resultados.json.

Resultado:

- La hoja del PCM1808 no da tolerancia de jitter en términos de audio: solo el límite de sincronización de ±6 BCK en modo esclavo y una recomendación sin números. La del RP2040 no da ningún número de jitter ni de ruido de fase.
- Con este ADC, el jitter empezaría a notarse entre unos 40 ps y 1 ns, según el modelo y la frecuencia del tono.
- snr_db con captura sin señal no ve el jitter; thd_n con tono sí. Las faldas aparecen solo con jitter lento; el jitter blanco levanta el piso parejo y el periódico deja bandas laterales.

Qué se decidió y por qué:

- El jitter se mide con thd_n con tono, a 1 kHz y a 10 kHz, y con thd_n en banda angosta para las faldas. snr_db no sirve para esto.
- El espectro sirve para ver la forma pero no para medir cerca del tono: si el tono no cae justo en un bin, la fuga de la ventana tapa lo que está a menos de 20 Hz.
- El número que las hojas no dan lo va a dar la comparación con un oscilador externo. Si no hay diferencia medible, el efecto del jitter de GPOUT0 queda acotado por debajo de lo que resuelve el sistema.

## Entrada 10: oscilador externo previsto para comparar (2026-09-13)

Qué se midió: nada en hardware. Se compiló el firmware con y sin la opción FEUOIR_RELOJ_EXTERNO, que deja GPOUT0 apagado.

Condiciones: toolchain de la entrada 4 y PICO_BOARD=pico, en firmware/build y firmware/build-externo.

Resultado: las dos variantes compilan sin avisos. En la del oscilador externo el ELF no incluye clock_gpio_init_int_frac16, así que GPOUT0 no se configura; en la de GPOUT0 sí está. No se probó en una placa.

Qué se decidió y por qué:

- El diseño deja un punto de conexión para un oscilador de cristal externo de 12.288 MHz, un jumper de 3 pines para elegir entre él y GPOUT0 como SCKI y un jumper en la alimentación del oscilador. Sirve para medir la diferencia de jitter entre los dos cuando exista el hardware, no para usarlo desde el principio.
- El PCM1808 va en modo maestro a 256 fS en las dos posiciones. En modo esclavo LRCK tiene que estar sincronizado con SCKI, y con un oscilador de otro cristal eso no se cumple. Consecuencia para el I2S de entrada: el Pico recibe BCK y LRCK del PCM1808.
- La fuente que no se usa va apagada, para que su conmutación no se acople a SCKI y meta bandas laterales por el batido entre los dos cristales.
- clk_sys queda en 61.44 MHz con las dos fuentes, para que entre las dos mediciones solo cambie SCKI.
- El jumper se cambia sin alimentación, porque la hoja del PCM1808 pide el reset de reloj detenido al cambiar SCKI.

## Entrada 11: firmware de verificación del reloj (2026-09-13)

Qué se midió: nada en hardware. Se compiló firmware/verificar_reloj.c en las dos variantes y se probó en la Mac la parte que arma el informe.

Condiciones: toolchain de la entrada 4 y PICO_BOARD=pico. La prueba en la Mac compila firmware/informe.c con Apple clang 21.0.0 y corre 11 casos.

Resultado: las dos variantes compilan sin avisos, y los static_assert confirman que los campos de registro de informe.h coinciden con las macros del SDK 2.3.1. Pasan los 11 casos: todo en orden, DC50 sin activar, PLL sin configurar, divisor con fracción, sin puente, frecuencias a cada lado de la tolerancia, contador que no termina y tres casos del oscilador externo. Sin probar en placa: la lectura real de los registros y el contador de frecuencia.

Qué se decidió y por qué:

- La lógica que decodifica y juzga (informe.c) está separada de la lectura de hardware (verificar_reloj.c), para probar en la Mac todo lo que no depende de la placa.
- La medición usa el contador de frecuencia con intervalo de 32 ms, exactitud de 62.5 Hz, y conserva la fracción del resultado. frequency_count_khz del SDK usa 1 ms, con 2 kHz de exactitud, y descarta la fracción.
- La tolerancia es el doble de la exactitud del contador cuando la frecuencia sale del mismo cristal (PLL y GPOUT0), y 1000 ppm con el oscilador externo, que detecta una pieza equivocada sin juzgar su exactitud.
- GPIO20 tiene pull-down para que sin puente lea cero y el informe diga que falta el puente, en vez de medir ruido.
- Cada medición tiene un límite de 1 s, para que un contador que no termina no cuelgue el firmware.

## Entrada 12: lectura del informe de verificación (2026-09-13)

Qué se midió: nada en hardware. Se probó leer_verificacion.py con un pseudo terminal en lugar del puerto USB.

Condiciones: macOS 26.5.2 y Python 3.12.0, solo con la biblioteca estándar. Los informes de prueba salen de firmware/informe.c compilado en la Mac, así que tienen el formato real del firmware.

Resultado: pasan los 13 casos de tests/lectura_sin_placa.py, con un informe sin fallas que llega después de la cola de otro, un informe con DC50 sin activar y un informe incompleto. No se probó con el puerto USB real.

Qué se decidió y por qué:

- El informe del firmware se guarda con un script y no copiándolo a mano: un dato que depende de que alguien se acuerde de copiarlo va contra la convención del proyecto.
- --puentes es obligatorio. El firmware no puede saber cómo están los puentes, y sin ese dato el informe no se puede interpretar.
- Si el puerto se abre a mitad de un informe, ese pedazo se descarta y se espera el siguiente inicio_informe.
- Un informe con fallas igual se guarda, y el script termina con código 1.

## Entrada 13: prueba de jitter por pendiente (2026-09-13)

Qué se midió: la prueba de pendiente de analizador.py contra capturas sintéticas con jitter conocido, armadas con numpy en calibrar.py.

Condiciones: 7 tonos de 1 a 10 kHz a -1 dBFS, 2 s por tono, fS de 48 kHz y banda de ±400 Hz alrededor de cada tono. Cuatro casos: solo jitter blanco de 1 ns, solo ruido blanco de 1e-5 RMS, ruido con 1 ns de jitter, y ruido que crece 40 dB por década sin jitter. Semillas fijas.

Resultado: calibraciones/2026-09-13-calibracion-4 pasa las 13 pruebas con 180 chequeos. Con solo jitter, pendiente de 19.88 dB por década, jitter equivalente de 1.002 ns y compatible_con_jitter. Con solo ruido, pendiente de -0.12 dB por década y sin_efecto_detectable. Con ruido y jitter, 1.004 ns y compatible_con_jitter. Con el ruido de 40 dB por década, no_compatible. tests/mutaciones.py detecta las 20 mutaciones, y las 4 nuevas las atrapa test_prueba_jitter (calibraciones/2026-09-13-mutaciones-3).

Qué se decidió y por qué:

- La pendiente de 20 dB por década pasa a ser un procedimiento con nombre, analizador.prueba_jitter. Es la prueba que se va a correr para comparar GPOUT0 contra el oscilador externo.
- Mide en una banda de ancho fijo alrededor de cada tono y no en toda la banda de audio. Así deja afuera los armónicos, que en los tonos agudos saldrían de la banda y bajarían el THD+N justo donde el jitter lo sube, y el ruido de fondo que entra es el mismo en todos los tonos.
- En vez de una recta ajusta razón² = a·f² + b. Con el ruido del ADC presente, la recta da una pendiente entre 0 y 20 que depende de cuánto domina cada uno; el ajuste separa las dos partes y da un jitter equivalente.
- Tres veredictos y no dos: si el término que crece con f suma menos de 1 dB en el tono más agudo, lo que se puede afirmar es que no hay efecto detectable, no que no hay jitter.
- Capacidad nueva, mutación nueva, como costumbre: 4 mutaciones atacan la pendiente, el término de ruido de fondo, la corrección por ancho de banda y el ancho fijo de la banda. La regla quedó escrita en el README.

## Entrada 14: un solo dominio de reloj para el audio (2026-09-13)

Qué se midió: nada en hardware. Se revisaron las hojas del PCM5102A (SLAS859C), del PCM1808 y del RP2040, y páginas de la comunidad sobre el módulo del PCM5102A.

Condiciones: PCM1808 en modo maestro a 256 fS, con fS de 48 kHz.

Resultado: el PCM5102A puede trabajar con el BCK y el LRCK del PCM1808 en modo de 3 hilos, con SCK a tierra y su PLL generando el reloj desde BCK. 64 BCK por trama a 48 kHz está en la tabla 11 de su hoja y el formato I2S de 24 bits es compatible. Queda una duda: el historial de revisiones dice que en la revisión A se quitó 48 kHz con reloj de la PLL, aunque la revisión C lo lista.

Qué se decidió y por qué:

- El PCM5102A usa el BCK y el LRCK del PCM1808, con SCK a tierra. La parte de audio queda en un solo dominio de reloj y el Pico es esclavo por los dos lados.
- Modo de 3 hilos y no de 4, para no llevar 12.288 MHz hasta el DAC. El de 4 hilos, con SCKI también en el SCK del DAC, sigue siendo un solo dominio y queda como opción.
- Configuración: MD1 y MD0 del PCM1808 en alto y FMT en bajo; en el PCM5102A, FMT, FLT y DEMP en bajo y XSMT en alto. En el módulo, puentes 1L, 2L, 3H y 4L y SCK a GND, a confirmar con multímetro porque vienen de fuentes de la comunidad.
- GPIO16 a GPIO19 del Pico para BCK, LRCK, DOUT y DIN, como propuesta.

Detalle y diagrama de conexiones en docs/dominio-de-reloj.md.

## Entrada 15: audio USB con un reloj propio (2026-09-13)

Qué se midió: nada en hardware. Se revisaron el USB 2.0 (sección 5.12.4), la nota técnica TN3190 de Apple, TinyUSB 0.18.0 (la del pico-sdk 2.3.1) y 0.21.0, y el código de tierneytim/Pico-USB-audio.

Condiciones: Pico en velocidad completa, captura y reproducción a 48 kHz en estéreo de 24 bits, con el reloj de audio del PCM1808 en modo maestro.

Resultado:

- Captura: endpoint IN asíncrono, sin realimentación; la Mac acepta de 47 a 49 muestras por milisegundo.
- Reproducción: necesita realimentación, explícita (10.14 en 3 bytes en velocidad completa) o implícita si entrada y salida comparten reloj, que es nuestro caso.
- TinyUSB 0.18.0 hace UAC2 con captura asíncrona y realimentación explícita en 3 bytes, pero no implícita. La 0.19.0 agrega la implícita y mantiene la explícita en 3 bytes. Desde la 0.20.0 hay UAC1, pero con UAC2 la explícita va en 4 bytes también en velocidad completa, distinto de lo que pide TN3190.
- Pico-USB-audio no sigue al reloj de la Mac: descarta paquetes o repite muestras.

Qué se decidió y por qué:

- Captura con endpoint asíncrono al ritmo del PCM1808.
- Para la reproducción, primero la realimentación implícita, porque ADC y DAC comparten reloj y no hace falta endpoint extra; requiere TinyUSB 0.19.0 o posterior, donde entró. Respaldo: la explícita en 3 bytes, que está en la 0.18.0 y en la 0.19.0. La 0.19.0 permite las dos sin cambiar de versión.
- Queda por verificar en macOS 26 que la implícita funcione: TN3190 la documenta, pero no hay prueba propia.
- Sin firmware todavía. Detalle en docs/audio-usb.md.

## Entrada 16: TinyUSB 0.18.0 para la captura y margen propio del diseño (2026-09-13)

Qué se midió: nada en hardware. Se confirmó en la especificación de formatos de audio de UAC1 (sección 2.2.1) el rango de 47 a 49 muestras por milisegundo a 48 kHz que pide TN3190.

Condiciones: 48 kHz en velocidad completa.

Resultado: el rango no es una tolerancia propia de macOS. Cuando el promedio de muestras por paquete es entero, la especificación permite una muestra menos o una más por paquete.

Qué se decidió y por qué:

- TinyUSB queda en la 0.18.0 del pico-sdk 2.3.1 hasta tener la captura funcionando. La captura, la fase 5, no necesita realimentación; la realimentación solo hace falta para la reproducción, la fase 6. Si se cambia de versión ahora y algo falla en la fase 5, no se sabría si fue el I2S, el reloj o el cambio. En la fase 6 el cambio se evalúa contra una base que funciona y está medida. Lo investigado sobre 0.19.0 y 0.20.0 quedó en docs/audio-usb.md.
- La arquitectura no depende del rango de 47 a 49. El margen sale del diseño: ajustes de una sola muestra y espaciados, una FIFO con holgura regulada a la mitad, arranque con la FIFO a medio llenar y registro por sesión del nivel de la FIFO y de los paquetes de 47 y 49. Con 50 ppm de diferencia entre cristales hace falta un ajuste cada 417 ms.

## Entrada 17: jumper de SCK en el PCM5102A (2026-09-13)

Qué se midió: nada en hardware. Se revisaron los requisitos de SCK en la hoja del PCM5102A.

Condiciones: SCKI de 12.288 MHz, 256 fS a 48 kHz, desde GPOUT0 con DC50 o desde el oscilador externo.

Resultado: SCK acepta ese reloj. La sección 8.6 pide un ciclo de 20 a 1000 ns y pulsos de al menos 9 ns con DVDD de 3.3 V, y 256 fS a 48 kHz está en la tabla 10.

Qué se decidió y por qué:

- El nodo de SCKI, la salida del jumper que elige entre GPOUT0 y el oscilador, llega también al SCK del PCM5102A a través de un jumper de 3 pines que lo pone en SCKI o a GND. La duda del historial de revisiones sobre 48 kHz con la PLL se elimina por diseño en vez de resolverla leyendo.
- Con SCK a GND el DAC usa su PLL desde BCK, en 3 hilos. Con SCK en SCKI usa el mismo reloj maestro que el ADC, en 4 hilos, y sigue siendo sincrónico porque BCK y LRCK salen de SCKI.
- El puente de soldadura de SCK a GND del módulo queda abierto: cerrado, la posición de 4 hilos pondría la salida del reloj maestro en cortocircuito a tierra.
- El primer encendido del DAC va en 4 hilos, que no depende de la nota del historial.

## Entrada 18: resistencias en serie (2026-09-13)

Qué se midió: nada en hardware. Se calcularon las resistencias en serie con los límites de corriente y los umbrales de las hojas del RP2040, el PCM1808 y el PCM5102A.

Condiciones: 3.3 V de lógica, reloj maestro de 12.288 MHz y BCK de 3.072 MHz. Carga de 20 pF por nodo, que es la carga máxima con la que el PCM1808 especifica sus salidas; ninguna de las tres hojas da la capacitancia de entrada.

Resultado:

- Corriente: el RP2040 especifica sus salidas hasta 12 mA y el PCM1808 tiene un máximo absoluto de ±10 mA por pin. Para el RP2040 hace falta R ≥ 275 Ω.
- Flancos a 12.288 MHz: por los umbrales asimétricos de SCKI (2.0 V y 0.8 V), el RC corre el ciclo de trabajo 0.49·RC / 81.4 ns. Para no pasar de 5 puntos, RC ≤ 8.4 ns, o sea R ≤ 419 Ω con 20 pF.
- Valores: 330 Ω en las dos líneas de reloj maestro (10 mA en corto, ciclo de trabajo corrido 3.9 puntos) y 470 Ω en BCK, LRCK, DOUT y DIN (7 mA en corto). Con todo en falla a la vez el RP2040 entregaría 38 mA, debajo de su límite de 50 mA.

Qué se decidió y por qué:

- Una resistencia en serie en cada línea digital entre el Pico y los módulos, pegada al pin que la maneja. Con jumpers, un error de armado puede quemar una salida; la resistencia lo convierte en un error sin consecuencias.
- Dos valores y no uno. En el reloj manda la restricción de flancos y en las demás líneas la de corriente; un único valor de 470 Ω dejaría el reloj con 5.7 puntos de corrimiento.
- El nodo de SCKI tiene que sumar como mucho 25 pF con 330 Ω, así que sus cables son cortos.
- Los puentes de verificación hacia GPIO20 salen del lado de la resistencia que no toca el pin.
- No había lista de compras en el repo: se creó docs/compras.md a partir del diseño.

## Entrada 19: lista para el primer encendido (2026-09-13)

Qué se midió: nada en hardware. Se armó docs/primer-encendido.md con los valores de las hojas del Pico, el RP2040, el PCM1808 y el PCM5102A.

Condiciones: alimentación por el USB del Pico. Valores esperados: VBUS de 5 V ± 10 % y consumo cerca de 10 mA en BOOTSEL (hoja del Pico); 3V3 entre 3.0 y 3.6 V, que es la ventana en la que trabajan los tres integrados; PCM1808 con 8.6 mA analógicos y 5.9 mA digitales típicos, y PCM5102A con 7 a 8 mA digitales y 11 mA analógicos típicos, a 48 kHz.

Qué se decidió y por qué:

- Revisión con multímetro antes de enchufar nada, con el puente de SCK del módulo del PCM5102A como la revisión más importante.
- Encendido por etapas, de a una cosa: el Pico solo, el reloj, el ADC y el DAC. Cada cambio con el USB desenchufado.
- El firmware de verificación sirve en todas las etapas. En la del reloj, con el puente de GP21 a GP20 desde el extremo de R1. En la del ADC, el mismo puente llevado a BCK y a LRCK mide 3.072 MHz y 48 kHz sin firmware nuevo: el informe marca FALLA porque espera 12.288 MHz, pero el valor medido confirma el modo maestro.
- El DAC se enciende en 4 hilos, sin nada en sus salidas. La prueba de sonido queda para cuando haya firmware de reproducción.
- La lista tiene qué no hacer y qué síntomas obligan a desenchufar, escrita para seguirla de noche.

## Entrada 20: cáscara de la app de medición en vivo (2026-09-13)

Qué se midió: nada. Se revisaron la documentación de Tauri 2 y de Electron, los paquetes de PyPI y las herramientas instaladas en la Mac.

Condiciones: macOS 26.5.2 en Intel, Python 3.12.0, Node 24, Rust 1.97.1. Python es la única fuente de verdad y TypeScript solo dibuja, conectados por WebSocket.

Resultado: las tres opciones funcionan en Intel. Tauri usa la webview del sistema pero corre Python como sidecar empaquetado con PyInstaller. Electron embebe Chromium y Node.js. aiohttp y pywebview tienen paquetes para Python 3.12 en Intel.

Qué se decidió y por qué:

- Python sirve la página y el WebSocket con aiohttp desde el mismo proceso que lee el audio y analiza, y pywebview la muestra en una ventana propia. Un solo proceso, dos paquetes más en el .venv y un comando para arrancar.
- Se descartó Tauri por el segundo proceso empaquetado y la cáscara en Rust, a cambio de un .app que no hace falta, y Electron por el costo de memoria de Chromium en una Mac que ya anda al límite.
- La prueba del contrato del WebSocket corre sin ventana, con un cliente de aiohttp y la fuente sintética.
- Detalle en docs/app-cascara.md. Queda por decidir dónde vive la app y con qué se dibuja.

## Entrada 21: app de medición en vivo (2026-09-13)

Qué se midió: nada en hardware. La app se probó con la fuente sintética: tests/app_sin_ventana.py por WebSocket, capturas de la interfaz con Chrome sin pantalla en modo claro y oscuro, y la ventana de pywebview abierta en la Mac.

Condiciones: macOS 26.5.2 en Intel, Python 3.12.0 con aiohttp 3.14.3 y pywebview 6.2.1, Node 24 con Vite 8.3.0 y TypeScript 6.0.3. Fuente sintética a 48 kHz en bloques de 1024 muestras, con ruido blanco de -100 dBFS RMS y cuantización a 24 bits.

Resultado:

- Un seno de 1 kHz a -6 dBFS llega como pico del espectro en 1 kHz y -6.0 dBFS, con RMS de -9.01 dBFS. Un tono entre dos bins, a 1002.5 Hz, también marca -6.0 dBFS con la ventana flat-top; con Hann marcaría hasta 1.42 dB menos.
- Un seno de +2 dBFS recortado marca el fundamental en +1.0 dBFS, RMS de -2.0 dBFS y armónicos impares.
- Con la fuente sintética, THD+N da cerca de 0.0025 % (-92 dB) a 1 kHz, que es el ruido de -100 dBFS dentro de la banda. La respuesta en frecuencia da 30 tonos planos en -6 dBFS, y la prueba de jitter, sin efecto detectable.
- Armar un cuadro lleva de 1 a 5 ms.
- Con el micrófono interno de la Mac como entrada, la app abre a 48 kHz y en 4 s llegan 110 cuadros con 3.97 s de audio, sin saturación; el sonido de la sala da picos de -63 a -22 dBFS. El volumen de entrada del sistema siguió en 71.
- tests/app_sin_ventana.py pasa sus 36 comprobaciones. tests/mutaciones.py suma 7 errores inyectados en app/ y la prueba atrapa los 7; con los 20 del analizador, las 27 mutaciones fallan (calibraciones/2026-09-13-mutaciones-4). Dos de ellas, la medición marcada tarde y el emisor que espera a cada conexión, las atrapa el tiempo límite de la prueba: el mensaje que se esperaba no llega.

Qué se decidió y por qué:

- Espectro en vivo con ventana flat-top sobre 200 ms, reducido a 512 puntos que se quedan con el máximo de su tramo: el nivel del pico no depende de dónde cae el tono y ningún tono se pierde al reducir. A cambio, el piso de ruido se ve unos 4 dB más alto.
- El eje del espectro llega a +10 dBFS, porque el fundamental de un seno recortado pasa de 0 dBFS.
- Un bloque satura si alguna de sus muestras llega a menos de un código de 16 bits del fondo de escala. El aviso queda marcado con cuántos bloques saturaron y hace cuánto, hasta borrarlo, para que un recorte corto entre dos cuadros no se pierda.
- La fuente sintética hace de conversor, con ruido, cuantización y recorte: las mediciones dan números finitos y la saturación se puede provocar.
- Las mediciones con estímulo lo hacen sonar: dentro del conversor simulado con la fuente sintética, y por la salida por defecto de la Mac con una entrada real.
- Menús y ajustes con el registro de feuoir: rótulos de 10 px en mayúsculas con tracking de 0.26 em, campos con línea fina y la línea de fuego en lo elegido. Modo claro y oscuro con los tokens de los modos de feuoir, siguiendo al sistema.
- Buscar entradas de nuevo reinicia PortAudio solo con la fuente sintética, porque con una entrada real abierta cortaría el audio.

Errores que aparecieron en el camino:

- Una segunda medición pedida enseguida no se rechazaba: la medición en curso se marcaba al arrancar la tarea y no al recibir el pedido. Ahora se marca antes de crear la tarea.
- Una conexión que no lee frenaba los cuadros de todas, porque el emisor esperaba cada envío. Lo mostraron las capturas, con los gráficos congelados; la prueba no lo veía porque su cliente siempre lee. Ahora cada conexión tiene su tarea de escritura y guarda solo el último cuadro. La prueba suma una conexión que no lee, y la mutación cuadros_esperando_a_cada_conexion reproduce el error original.
- La prueba esperaba 31 tonos en la respuesta en frecuencia, pero frecuencias_log de 20 Hz a 20 kHz con 3 por octava da 30. Ahora la prueba toma el número de frecuencias_log.

## Entrada 22: mediciones guardadas, modo oscuro y código en inglés (2026-09-13)

Qué se midió: nada en hardware. Renata probó la app con el micrófono interno de la Mac. La app se revisó con tests/app_contract.py, con capturas en Chrome sin pantalla y leyendo los píxeles del canvas dentro de la ventana real de pywebview.

Condiciones: las de la Entrada 21, con la Mac en modo oscuro.

Resultado:

- Las mediciones hechas con el micrófono quedaron guardadas con sus condiciones. Muestran que la cadena funciona de punta a punta con una entrada real, pero no son mediciones: el estímulo sale por el parlante de la Mac y lo toma el micrófono.
- En modo oscuro, en la ventana de pywebview, la forma de onda y el espectro no se veían: el canvas dibujaba con la tinta del modo claro sobre el fondo oscuro, porque los colores se leían una sola vez al arrancar. Ahora se leen en cada cuadro. En la ventana real, en modo oscuro, los 9625 píxeles pintados de la forma de onda son claros y ninguno oscuro.
- tests/app_contract.py pasa sus 38 comprobaciones. tests/mutaciones.py suma dos errores para Guardadas, la lista de la más vieja a la más reciente y abrir cualquier carpeta que exista, y las 29 mutaciones fallan (calibraciones/2026-09-13-mutaciones-5). La segunda la atrapa el tiempo límite de la prueba: el error que se esperaba no llega.

Qué se decidió y por qué:

- Guardadas, en el pie de la ventana, lista las mediciones con fecha, resumen y entrada, y abre cada carpeta en Finder. No suma pestañas ni vistas, para no salirse del alcance de la primera versión; ver el resultado dentro de la app queda en docs/app-ideas.md.
- Python solo abre carpetas que estén directamente dentro de mediciones/: la interfaz no puede pedir que se abra cualquier ruta de la Mac.
- El código de la app pasó a inglés y las etiquetas siguen en español, porque es la regla de Renata para todos sus repos. Cambiaron los archivos (app/sources.py, app/processing.py, app/measurements.py, app/server.py, app/ui/ y tests/app_contract.py) y el contrato del WebSocket, que pasó a la versión 2.
- El formato de mediciones/ no cambia: carpetas, archivos y claves de los JSON siguen en español porque los comparten medir.py y leer_verificacion.py.
- El código anterior a la app sigue en español hasta decidir si se traduce. analizador.py tiene además la regla de no reescribirse.

## Entrada 23: salida del estímulo elegible (2026-09-13)

Qué se midió: nada en hardware. La app se probó con tests/app_contract.py y con capturas del menú de la señal.

Condiciones: las de la Entrada 21. En la prueba, las listas de dispositivos y la entrada real son falsas: la entrada falsa tiene una fuente sintética adentro y anota por qué salida pidió sonar cada estímulo, así nada suena por los parlantes.

Resultado:

- Con una entrada real, el menú de la señal lista las salidas de la Mac, con la de por defecto primero. La elegida se valida contra la frecuencia de muestreo, y condiciones.json guarda por cuál sonó el estímulo.
- tests/app_contract.py pasa sus 44 comprobaciones. tests/mutaciones.py suma dos errores: el estímulo que suena por la salida por defecto aunque se haya elegido otra, y la entrada real que no le dice a sounddevice por qué salida sonar. Las 31 mutaciones fallan (calibraciones/2026-09-13-mutaciones-6).

Qué se decidió y por qué:

- La salida se elige en el menú de la señal y no en la barra: solo importa para las mediciones con estímulo, y solo con una entrada real.
- Elegirla no cambia la salida por defecto del sistema. La app le pasa el dispositivo a sounddevice solo cuando reproduce.
- Sirve para sacar el estímulo por la tarjeta de sonido USB hacia la etapa analógica y medir lo que vuelve, y en la fase 6 para medir el camino completo de la interfaz con un cable de su salida a su entrada.
- Buscar de nuevo busca entradas y salidas, y el contrato del WebSocket pasa a la versión 3.

## Entrada 24: rango de entrada del TL072 y alimentación partida (2026-09-14)

Qué se midió: nada en hardware. Se revisó la hoja del TL072 del repo (TI SLOS080W, revisión de julio de 2025) contra el circuito de entrada que pasó Renata, antes de simularlo.

Condiciones: circuito original con una pila de 9 V. Polarización en 4.5 V con R2 = R3 = 100 kΩ y C4 = 47 µF a tierra. R1 = 1 MΩ de la entrada no inversora al nodo de polarización. Realimentación con un potenciómetro de 10 kΩ, y R4 = 1 kΩ con C2 = 47 µF hacia el nodo de polarización. Señal de prueba de 1.5 V de pico en la entrada.

Qué dice la hoja:

- Tabla 5.3, condiciones de operación recomendadas. Alimentación de 10 a 30 V para las cápsulas NS y PS y las variantes TL07xM, y de 4.5 a 40 V para todas las demás. Tensión de entrada de (VCC−) + 2 V a (VCC+) + 0.1 V para NS, PS y TL07xM, y de (VCC−) + 4 V a (VCC+) + 0.1 V para todas las demás.
- Tabla 5.7, características eléctricas del TL07xH: modo común de (VCC−) + 1.5 V a VCC+.
- Tabla 5.8, características de TL07xC, TL07xAC, TL07xBC, TL07xI y TL07xM con ±15 V: modo común mínimo de ±11 V y típico de −12 V a 15 V. El borde inferior queda 4 V por encima del riel negativo como mínimo garantizado, y 3 V en el valor típico.
- Tabla 5.9, ruido de entrada a 1 kHz: 18 nV/√Hz para las cápsulas PS y NS y las TL07xM, y 37 nV/√Hz para todas las demás, que incluyen el DIP-8 (P) de TI. La lista de características de la primera página dice 37, y el historial de revisiones anota el cambio de 18 a 37.
- La figura 5-26, "No Phase Reversal", está en la sección 5.10, que es solo del TL07xH. En la sección 5.11, la del resto de las variantes, no hay nada equivalente.

Dónde se contradice: las filas de tensión de entrada de la tabla 5.3 no coinciden con las tablas eléctricas. Para "todas las demás", que incluyen al TL07xH, la 5.3 pide la entrada por encima de (VCC−) + 4 V, pero la 5.7 garantiza modo común desde (VCC−) + 1.5 V. Para NS, PS y TL07xM, la 5.3 permite desde (VCC−) + 2 V, pero la 5.8 solo garantiza ±11 V con ±15 V, o sea desde (VCC−) + 4 V. Las dos filas parecen intercambiadas. Es una inferencia: la hoja no lo aclara.

Por qué el diseño original lo violaba:

- Con 9 V simples y la polarización en 4.5 V, 1.5 V de pico llevan la entrada no inversora a 3.0 V, es decir, 3.0 V por encima del riel negativo.
- Eso queda por debajo de (VCC−) + 4 V, que es lo que pide la tabla 5.3 para todas las demás variantes y lo que garantiza como mínimo la 5.8, y por debajo de los 3 V típicos de la 5.8. Solo entra en el (VCC−) + 1.5 V del TL07xH.
- Fuera del rango de modo común, el TL072 clásico hace inversión de fase, que es peor que recortar. Lo señaló Renata; la hoja actual no lo describe para el clásico y solo muestra la ausencia de inversión en el TL07xH.
- Con 9 V tampoco se cumple el mínimo recomendado de 10 V para las cápsulas NS y PS y las TL07xM, y una pila baja con el uso.

Qué se decidió (decisión de Renata):

- Alimentación partida de ±9 V, con dos pilas de 9 V en serie y el punto medio como tierra analógica.
- Salen R2, R3, C4 y C2. R1 = 1 MΩ va de la entrada no inversora a tierra, y R4 = 1 kΩ de la entrada inversora a tierra, con el potenciómetro de 10 kΩ en la realimentación: la ganancia sigue de 1 a 11.
- Lo demás no cambia: C1 = 100 nF de acoplo de entrada, filtro de R5 = 4.7 kΩ con C5 = 1 nF, seguidor con la segunda mitad del TL072, C3 = 2.2 µF de acoplo hacia el PCM1808 y 100 nF de desacoplo en cada riel contra tierra.
- Con ±9 V la entrada queda centrada en 0 V: 1.5 V de pico la llevan a −1.5 V, 7.5 V por encima del riel negativo, dentro del rango de todas las tablas. Los 18 V totales entran en 10 a 30 V y en 4.5 a 40 V.
- El circuito se simula en las dos versiones, 9 V simples y ±9 V, porque la comparación es un resultado del proyecto. Se suma un transitorio con 1.5 V de pico en las dos. Si el modelo de TI no reproduce la inversión de fase, se anota: los modelos no siempre incluyen ese comportamiento.
- TL072 clásico en DIP-8, el de 18 nV/√Hz y no el TL072H, y una pila de 9 V más con su portapilas en docs/compras.md.

Pendiente: según la tabla 5.9, los 18 nV/√Hz corresponden a las cápsulas PS y NS y a las TL07xM de TI, y el DIP-8 de TI figura con 37 nV/√Hz. Hay que confirmar con qué fabricante y número de parte se consigue el clásico en DIP-8.

## Entrada 25: ruido del TL072 en DIP-8 y condiciones para simular la entrada (2026-09-14)

Qué se midió: nada en hardware. Se revisó la cuenta de ruido de Renata y se fijaron las condiciones de la simulación del circuito de entrada.

Condiciones: TL072 en DIP-8 con 37 nV/√Hz a 1 kHz (tabla 5.9 de la hoja de TI) y el circuito de ±9 V de la entrada 24.

Resultado, sumando en cuadratura el ruido térmico de la pastilla con el del TL072:

- Con 12 nV/√Hz de la pastilla quedan 21.6 nV/√Hz con 18 y 38.9 nV/√Hz con 37: una diferencia de 5.1 dB.
- Con 29 nV/√Hz de la pastilla quedan 34.1 y 47.0 nV/√Hz: 2.8 dB.
- El amplificador solo, de 18 a 37 nV/√Hz, son 6.3 dB.

Qué se decidió y por qué (decisiones de Renata):

- Se aceptan los 37 nV/√Hz y se sigue con el DIP-8. La fuente no es un cable sino una pastilla, y su impedancia a frecuencias de audio ya aporta entre 12 y 29 nV/√Hz de ruido térmico. Sumando en cuadratura, la diferencia entre 18 y 37 queda en unos 3 dB, entre 2.8 y 5.1 dB según la cuenta de arriba. El montaje en protoboard va a costar entre 20 y 30 dB, así que esa diferencia queda enterrada.
- Cuando se pase a PCB y el montaje deje de ser el límite, vale la pena revisarlo. Con zócalos se cambia el chip y se mide la diferencia con el analizador propio, en vez de decidir por una cifra de catálogo.
- A la tienda se le pregunta qué fabricante manejan y se pide su hoja. No frena el pedido. Con esto queda resuelto el pendiente de la entrada 24.
- Carga del PCM1808 en la simulación: 60 kΩ detrás de C3, según su hoja. Con 2.2 µF da un corte en 1.2 Hz, que tiene que aparecer en la respuesta en frecuencia.
- Pilas con resistencia interna: 2 Ω con pila fresca, y un caso de pila gastada de 7 V con 10 Ω. Es una condición real de operación, y sirve para comprobar que con ±7 V el margen de entrada sigue sobrando.
- Ganancia barrida en cinco puntos, 1, 3, 5, 8 y 11, para ver si cambia la forma de la respuesta y no solo el nivel.
- El modelo SPICE de TI se revisa antes de usarlo, incluido si reproduce la inversión de fase. La mayoría de los modelos de TI no la reproducen: si la versión de 9 V simples sale limpia, no significa que el problema no exista. Eso va escrito junto a la gráfica.
- Se acepta el offset amplificado: 110 mV sobre ±9 V no molesta. Queda documentado en docs/entrada-analogica.md el golpe que produce al mover el potenciómetro, mientras C3 se recarga con una constante de tiempo de 0.13 s.
