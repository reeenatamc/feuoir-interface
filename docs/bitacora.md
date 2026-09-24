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

## Entrada 26: ngspice instalado y verificado contra la teoría (2026-09-14)

Qué se midió: nada en hardware. Se compiló ngspice 47, se lo comparó con la teoría en un divisor resistivo y un filtro RC de primer orden (spice/verify.py), y se comprobó que lee los dos modelos del TL072 de TI, con un seguidor en continua.

Condiciones: macOS 26.5.2 en Intel, Apple clang 21. Paquete fuente ngspice-47.tar.gz con sha256 894e649651f1838a14095e5a5439e7d3aa63e87ede14d283173fda4fcdef675f. ngspice simula a 27 °C. Modelos: TL072.301 de SLOJ067 (sha256 que empieza en 74e89d558163615a) y tl07xh_tl08xh.lib de SLOM513 (f214c2d611ab9d13), los dos con ±9 V.

Resultado:

- La compilación falló dos veces antes de salir. Con OpenMP, que el configurador activa por defecto, falta omp.h en el clang de Apple. Con readline, el configurador toma el readline.h del SDK de Apple, que es libedit, y falla en rl_reset_after_signal. Con las dos cosas desactivadas compiló en 248 s, sin errores y con 1912 avisos.
- La verificación pasa sus 13 chequeos (calibraciones/2026-09-14-spice). El divisor da 1.578947 V, a menos de 1 µV. El filtro RC coincide con la teoría en magnitud y fase de 10 Hz a 10 MHz con un error del orden de 1e-14, y marca -3.0103 dB en el corte. El escalón llega a 0.632081, 0.950208 y 0.993261 V en 1, 3 y 5 constantes de tiempo, contra 0.632121, 0.950213 y 0.993262 V de la teoría. El ruido a 10 Hz da 8.8265 nV/√Hz, igual a la raíz de 4kTR, y el total de 1 Hz a 1 GHz da 2.0351 µV, contra 2.0357 µV de la teoría.
- El modelo del TL072 carga tal como viene. Como seguidor, la salida sigue a la entrada a menos de 0.05 mV con -1, 0, 0.1 y 1 V.
- El modelo del TL072H carga con ngbehavior=ps. Como seguidor sigue a la entrada con la ganancia correcta, pero con un offset fijo de -6.47 mV en las cuatro entradas, más que el máximo de ±4 mV de su hoja (tabla 5.7). La causa no está identificada.
- tests/mutaciones.py suma 4 errores para la verificación: el divisor con la resistencia de abajo cambiada, el filtro con el doble de capacidad, el lector de .raw sin parte imaginaria y la teoría del ruido a 17 °C. Los atrapa, y las 35 mutaciones fallan (calibraciones/2026-09-14-mutaciones). La de la temperatura muestra que el chequeo de ruido distingue un 1.7 %.

Qué se decidió y por qué:

- ngspice queda compilado en ~/spice/ngspice-47, y docs/simulador-spice.md documenta el procedimiento para repetirlo.
- Los resultados de ngspice se leen por nombre de variable, nunca por posición. Al revisar los modelos a mano se leyó por error la primera columna de un .raw, que era el riel de +9 V y no la salida, y pareció que los dos modelos quedaban clavados en 9 V. Releído con el lector del repo, que usa los nombres, el resultado es el de arriba.
- Cuál modelo se usa en el circuito lo decide Renata, antes de simularlo.

## Entrada 27: caracterización de los modelos del TL072 (2026-09-14)

Qué se midió: nada en hardware. Con spice/characterize.py se comparó el ruido del modelo del TL072H con la hoja, se buscó la inversión de fase en el modelo del TL072 clásico y se revisó de dónde sale el offset del modelo del H.

Condiciones: ngspice 47 a 27 °C. Modelos TL072.301 (SLOJ067) y tl07xh_tl08xh.lib (SLOM513) sin modificar, guardados en spice/models/. El ruido y el offset del H, con ngbehavior=ps. Resultados en calibraciones/2026-09-14-modelos-tl072.

Resultado:

- Ruido del modelo del TL072H como seguidor con ±9 V: 37.6 nV/√Hz a 1 kHz, 0.13 dB por encima de los 37 de la hoja (tablas 5.7 y 5.9). A 10 kHz, 22.1 nV/√Hz contra 21. De corriente a 1 kHz, sacado con 1 MΩ en la entrada, 79.2 fA/√Hz contra los 80 del TL07xH (tabla 5.7).
- Inversión de fase con el modelo del TL072 clásico, como seguidor con 9 V simples y la entrada barrida de 0 a 9 V: no aparece. La salida nunca baja mientras la entrada sube (la mayor caída es de 0.014 V), y con la entrada en 0 V se queda en 1.55 V. El modelo sigue a la entrada, a menos de 0.1 V, hasta 1.47 V: no representa el límite de modo común de 4 V por encima del riel negativo que pide la hoja.
- Offset del modelo del H: -6.47 mV con ±9 V, -6.47 mV con 0 y 18 V y la entrada en 9 V, y -2.38 mV con ±15 V. Su biblioteca fija .PARAM DC = -0.0126 en el subcircuito VOS_DRIFT_0.
- Con los cambios al ejecutor (copiar los modelos, modo PSpice y cambio de parámetros), la verificación del simulador sigue pasando sus 13 chequeos (calibraciones/2026-09-14-spice-2).

Qué se decidió y por qué (decisiones de Renata):

- Se usan los dos modelos, cada uno para lo que sabe hacer: el del TL072 clásico para todo lo lineal (respuesta en frecuencia, ganancia, transitorio y margen con pila fresca y gastada) y el del TL072H solo para el ruido. Ningún macromodelo es correcto para todo.
- El ruido sale de un modelo distinto al del resto, y es aceptable: el DIP-8 de TI que se va a comprar figura con 37 nV/√Hz, la misma cifra que el H, así que ese modelo reproduce el ruido que va a tener el circuito aunque por dentro sea otro chip. El chequeo a 1 kHz confirma que se puede usar.
- La inversión de fase no es simulable con los modelos disponibles. La alimentación partida se apoya en la tabla de condiciones recomendadas de la hoja (entrada 24), no en una simulación, y una simulación limpia de 9 V simples no prueba que el problema no exista. Queda escrito junto a esa decisión en docs/entrada-analogica.md.
- El offset del H es del modelo y no de la configuración: sale igual con ±9 V que con 0 y 18 V, cambia con la tensión total, y la biblioteca lo trae fijado. No se persigue, porque en el circuito C3 bloquea la continua.

## Entrada 28: simulación de la etapa de entrada (2026-09-14)

Qué se midió: nada en hardware. Con spice/simulate_input.py se corrieron las cuatro simulaciones que pidió Renata sobre el circuito de docs/entrada-analogica.md: respuesta en frecuencia, transitorio con 1.5 V de pico, ruido con la entrada al aire y con la guitarra, y la guitarra sola con dos cargas.

Condiciones: ngspice 47 a 27 °C. Modelo del TL072 clásico para lo lineal y del TL072H para el ruido. Pilas frescas de 9 V con 2 Ω y gastadas de 7 V con 10 Ω. 60 kΩ de carga detrás de C3. Potenciómetro en 0, 2, 4, 7 y 10 kΩ, con el 0 como 1 mΩ. Guitarra de spice/netlists/guitar.cir con cable de 300 y 600 pF. Resultados en mediciones/2026-09-14-sim-respuesta-en-frecuencia, 2026-09-14-sim-transitorio-1v5, 2026-09-14-sim-ruido y 2026-09-14-sim-carga-guitarra.

Resultado:

- Los 32 chequeos contra el cálculo a mano pasan. Las 10 curvas de respuesta coinciden con el circuito resuelto con opamps ideales a 0.0013 dB hasta 5 kHz, en las dos versiones.
- Con ±9 V la forma de la respuesta no cambia con la ganancia en la banda de audio: 0.01 dB como mucho entre ganancia 1 y 11. Con 9 V simples sí cambia en graves: el corte de abajo pasa de 1.89 Hz a 7.89 Hz, y en 20 Hz la ganancia 11 cae 0.61 dB.
- Margen de entrada con 1.5 V de pico y ganancia 11: +3.46 V con ±9 V, +1.37 V con ±7 V y pilas gastadas y -1.01 V con 9 V simples.
- A la entrada del PCM1808 llegan ±7.4 V con ±9 V, ±5.3 V con ±7 V y ±2.9 V con 9 V simples. Las tres pasan el máximo absoluto del pin, 2.8 V hacia cada lado de su centro.
- Ruido de 20 Hz a 20 kHz con ganancia 11: 226.8 µV al aire y 56.7 µV con la guitarra y 300 pF (-76.4 y -88.4 dBFS). Con la guitarra hay entre 10 y 13 dB menos que al aire, con ganancia 1 y con 11.
- Carga: con 1 MΩ la pastilla resuena en 3.55 kHz con +14.8 dB (300 pF) y en 2.69 kHz con +15.0 dB (600 pF). Con 10 kΩ cae 3 dB en 593 Hz, no resuena, y a 3.55 kHz queda 36 dB por debajo.
- Del modelo del TL072 clásico: consume 8.4 mA por amplificador, contra 1.4 mA típicos de la hoja, por su RP de 2.143 kΩ. Se vio en la corriente de las pilas del transitorio.
- Del modelo del TL072H: su ruido de corriente, 79.2 fA/√Hz, es el del TL07xH, y la tabla 5.9 da 10 fA/√Hz para el DIP-8. Con la entrada al aire exagera el ruido entre 1.2 y 1.3 dB a 1 kHz, según el cálculo a mano.
- Una cuenta rápida a mano de la versión simple dio 0.12 dB de caída en 20 Hz con ganancia 11, y la simulación dio 0.61 dB. La cuenta estaba mal: tomaba el nodo de polarización como tierra, pero la corriente que vuelve por R4 y C2 lo mueve, porque a 20 Hz C4 no es un corto. Con C4 ideal la caída sería de 0.16 dB. El circuito entero resuelto con opamps ideales coincide con la simulación, y ese cálculo quedó como chequeo del script.
- tests/mutaciones.py le inyecta 5 errores a las simulaciones: R4, C4 y R3 cambiados en el circuito, otra bobina en la guitarra y la entrada al aire cargada con 1 MΩ. Los atrapan los chequeos de respuesta, transitorio, carga y ruido, y las 40 mutaciones del repo hacen fallar sus pruebas (calibraciones/2026-09-14-mutaciones-3).

Qué queda abierto (no se cambió nada del diseño):

- La entrada del PCM1808 pasa su máximo absoluto con ganancia alta y señal fuerte: con ganancia 11 alcanza con 255 mV de pico en la entrada de la etapa. La simulación no tiene los diodos de protección del chip ni lo que traiga el módulo en VINL y VINR. Para discutir con Renata (docs/entrada-analogica.md, para discutir).
- Cuánto ruido aporta exactamente la corriente del modelo del H: ngspice lo puede separar por fuente, si hace falta.
## Entrada 29: medir en Windows con la tarjeta USB (2026-09-19)

Qué se midió: nada en hardware todavía. Se comprobó que la cadena de medición corre en la laptop ASUS con Windows 11: dispositivos.py lista las entradas y medir.py graba, analiza y guarda su carpeta. La captura de prueba se hizo con la entrada que Windows trae por defecto y se borró: no es una medición.

Condiciones: Windows 10.0.26200 (Windows 11), Python 3.11.9, entorno nuevo en `.venv` con sounddevice, numpy, scipy, matplotlib y aiohttp. El repo se clonó de GitHub; en la Mac ya estaba subido desde el 2026-09-13.

Resultado:

- medir.py grabó 5 s por WASAPI a 48 kHz, en un canal, y guardó captura.wav, captura.png y condiciones.json con el sistema operativo, el dispositivo con su API y el nivel de entrada.
- dispositivos.py lista 22 entradas en la ASUS, que son 6 aparatos repartidos entre MME, DirectSound, WASAPI y WDM-KS. Solo las de WASAPI dan 48000 Hz por defecto; las de MME y DirectSound dan 44100 Hz.
- Dos entradas de WDM-KS con nombres de más de 90 caracteres traían saltos de línea dentro del nombre y rompían la tabla. Ahora los nombres se pasan a una línea y se recortan a 45 caracteres.
- calibrar.py pasa en Windows sus 13 pruebas y 180 chequeos (calibraciones/2026-09-19-calibracion), así que el análisis da lo mismo en las dos máquinas.
- tests/app_contract.py pasa sus 45 comprobaciones en Windows, con la fuente sintética, ya con la elección de la salida del estímulo que llegó de la Mac mientras esto se escribía.

Qué se decidió y por qué:

- WASAPI es la API con la que se mide en Windows. MME y DirectSound llegan al mismo conversor pero con mezcla y remuestreo del sistema por el medio, y WDM-KS no acepta 48 kHz en la mayoría de las entradas. dispositivos.py marca con un asterisco las filas de la API recomendada de cada sistema y muestra una columna que dice si la entrada acepta un canal a 48 kHz, que es lo que necesita medir.py.
- Cada medición guarda ahora el sistema operativo, la API de audio y el nivel de entrada. Sin esos tres datos una captura de la Mac y una de la ASUS no se pueden poner una al lado de la otra: no se sabría si la diferencia está en la guitarra, en la tarjeta o en la máquina.
- El nivel de entrada se anota a mano en Windows, con --nivel-entrada o con la variable FEUOIR_NIVEL_ENTRADA, y condiciones.json guarda también de dónde salió el número. Leerlo desde Python en Windows pide instalar una dependencia más (pycaw) y tocar la API de audio del sistema; anotarlo cuesta menos y el nivel, de todos modos, no se mueve nunca. En la Mac se sigue leyendo con osascript.
- medir.py avisa y no graba si la entrada no acepta un canal a 48 kHz, en vez de dejar que PortAudio tire un error sin explicación. El aviso manda a docs/configuracion-windows.md.
- El dispositivo se elige con --dispositivo y ya no editando una constante: los índices no son los mismos en la Mac y en la ASUS, así que una constante en el archivo estaría mal en una de las dos máquinas.
- docs/configuracion-windows.md deja escrito el procedimiento para que Windows no toque la señal: Comunicaciones en "No hacer nada", todas las mejoras del micrófono desactivadas, formato en 24 bits y 48000 Hz, sin control exclusivo de aplicaciones, y cerrados los programas de videollamada. El micrófono interno de la ASUS no se usa para caracterizar la guitarra: la entrada que aparece como AI Noise-cancelling Input (ASUS Utility) es ese micrófono con el procesado del fabricante encima.
- medir.py y dispositivos.py pasaron a código en inglés con comentarios y salida en español, y medir.py quedó partido en funciones con un main(). Es la regla de Renata para el repo, la misma que ya seguía la app. Los nombres de los archivos no cambian, porque son los que se escriben en la terminal y los que nombra toda la documentación; las claves de condiciones.json tampoco, porque las comparten la app y leer_verificacion.py.

Errores que aparecieron en el camino:

- platform.platform() reporta "Windows-10" en un Windows 11, porque platform.release() no distingue las dos. El sistema operativo se guarda con el número de build, que sí las distingue: "Windows 10.0.26200".
- tests/mutaciones.py buscaba el python del entorno en .venv/bin/python, que en Windows no existe, y caía al python del sistema, donde no están las dependencias. Ahora elige según el sistema.
- La app abría las carpetas de mediciones/ con el comando open de macOS, que en Windows no existe. Ahora usa open, os.startfile o xdg-open según el sistema.

Lo que sigue sin probar en Windows: leer_verificacion.py, que importa termios y tty y busca el puerto del Pico en /dev/cu.usbmodem*. Nada de eso existe en Windows, donde el Pico aparece como un COM. No se tocó porque hasta que el firmware esté en una placa no hay informe que leer.

## Entrada 30: primeras mediciones con la tarjeta USB y la guitarra (2026-09-19)

Qué se midió: el piso de ruido de la tarjeta de sonido USB, el piso con la guitarra conectada, y la guitarra tocando: rasgueo fuerte, rasgueo suave, cuerda grave y cuerda aguda. Las grabó Claude con medir.py y Renata con la app.

Condiciones: tarjeta USB PnP Sound Device (08bb:2902, se anuncia como C-Media y el ID es el del PCM2902 de TI), entrada de micrófono mono a 48 kHz, ganancia de entrada en 0 dB, el mínimo de su rango de 0 a 23.8 dB. Guitarra por adaptador de 6.35 a 3.5 mm. Desde piso-con-guitarra-4, la Mac a batería con el cargador desenchufado. Modelo de la guitarra, pastilla y cable sin informar.

Cambios en las herramientas antes de medir:

- medir.py elegía la entrada por número, y el 0 era ese día el micrófono del iPhone. Ahora la busca por nombre.
- El volumen de entrada solo se podía leer para la entrada por defecto. device_volume.py lo lee de Core Audio para cualquier dispositivo, junto con la ganancia en dB, y medir.py y la app lo guardan en condiciones.json. La tarjeta marca volumen 0, que es 0 dB de ganancia y no silencio. tests/app_contract.py lo compara con osascript y con la conversión a dB de Core Audio, y tests/mutaciones.py le inyecta 3 errores; las 43 mutaciones fallan (calibraciones/2026-09-19-mutaciones).
- La tarjeta da un golpe de -28.6 dBFS en el primer medio segundo después de abrir la grabación (mediciones/2026-09-19-piso-tarjeta-al-aire). medir.py graba un segundo de más y lo descarta, y lo anota en descartado_al_inicio_s.
- medir.py acepta --segundos: con 5 s y la latencia del chat, el rasgueo quedaba fuera de la toma (rasgueo-fuerte y rasgueo-fuerte-2 no tienen rasgueo completo).

Resultado:

- Piso de la tarjeta sin nada conectado: -73.0, -73.0 y -73.2 dBFS de RMS en tres tomas (piso-tarjeta-al-aire-2, piso-con-guitarra con su corrección, y piso-tarjeta-al-aire-3).
- Con la guitarra conectada en volumen 0 y la Mac con cargador: -42.3 dBFS de RMS, con 60 Hz a -40 dBFS y 120 y 240 Hz más fuertes que 180 Hz. A batería: -60.1 dBFS, con 60 Hz a -57.8 dBFS. Era un lazo de tierra por el cargador (piso-con-guitarra-3 y -4).
- Rasgueo fuerte, desde la app: pico -19.7 dBFS, RMS -41.2 dBFS (captura). Rasgueo suave, 12 s: pico -29.2 dBFS, RMS -42.7 dBFS (rasgueo-suave). Cuerda grave: pico -28.5 dBFS, fundamental en 74.6 Hz, la cuerda estaba en re o floja (captura-2). captura-3: pico -16.4 dBFS con la dominante en 391 Hz, sin saber qué nota fue. captura-4 y captura-5: la cuerda aguda, con la serie armónica en 333, 657, 995, 1321 y 1653 Hz (mi de 329.6 Hz) y RMS de -50.1 y -49.0 dBFS. Ninguna toma satura.
- La tarjeta vacía no capta el sonido del cuarto: con aplausos que el micrófono de la Mac ve hasta -17 dBFS, la tarjeta queda entre -71 y -75 dBFS, igual que en silencio (diagnostico-ruido-ambiente-2, grabado con ambient_check.py). Lo que se mueve en la app sin señal es el ruido propio en el espectro, que se dibuja hasta -140 dBFS.

Qué queda abierto:

- La entrada de micrófono carga la pastilla con pocos kΩ, así que los agudos medidos no son los que va a ver la etapa de entrada con 1 MΩ. La simulación con 10 kΩ predice que desaparece la resonancia de 3.5 kHz.
- La entrada de micrófono suele poner tensión de polarización en la punta; no se midió.
- captura-3, grabada por Renata desde la app: qué nota se tocó. La 4 y la 5 se identificaron por su espectro.
- La app no guarda notas: las condiciones de sus capturas se completaron a mano con lo informado en la sesión.
- Medir siempre con la Mac a batería, o las tomas no se pueden comparar.

## Entrada 31: notas en las mediciones de la app (2026-09-19)

Cierra lo abierto en la entrada 30: la app no guardaba notas y las condiciones de sus capturas se completaban a mano. Ahora el pie de la ventana tiene un campo Notas, y cada medición lo guarda en condiciones.json con la clave notas, igual que medir.py. El servidor lo valida antes de marcar la medición como en curso: texto de hasta 2000 caracteres, con el error en español si no cumple. El contrato sube a la versión 4.

Probado: tests/app_contract.py pasa a 52 comprobaciones, con las notas guardadas, vacías, demasiado largas y de tipo equivocado. tests/mutaciones.py agrega notas_ignoradas; las 44 mutaciones fallan (calibraciones/2026-09-19-mutaciones-2).

## Entrada 32: primer encendido del Pico, etapas 1 y 2 (2026-09-19)

Qué se hizo: las dos primeras etapas de docs/primer-encendido.md, las únicas posibles sin los módulos del ADC y del DAC.

Condiciones: el Pico en la protoboard en las filas 1 a 20, con las patas en las columnas c y h; la placa tapa b e i en esas filas. Alimentado por el cable de la tableta Wacom (USB-A a micro-USB) con adaptador. Sin multímetro: VBUS y 3V3 no se midieron, y así quedó anotado en --puentes. El diagrama del armado de la etapa 2 está en docs/armado/etapa2.png, y sobre una foto de la protoboard en etapa2_sobre_la_foto.jpg.

Resultado:

- Etapa 1, nada conectado (mediciones/2026-09-19-etapa1-pico): el firmware de verificación cargó con BOOTSEL y el informe llegó por USB. PLL y GPOUT0 en ok, pll_hz en 61440000 exactos, y una sola FALLA, gpio20_hz en 0, la esperada sin el puente.
- Etapa 2, R1 de 330 Ω de GP21 (fila 14) a la fila 24 y el puente de la fila 24 a GP20 (fila 15): la primera lectura dio gpio20_hz en 0 (etapa2-reloj). Sin cambiar el circuito, al apretar el Pico, el cable y la resistencia, dio 12288000 Hz con 0.0 ppm y sin fallas (etapa2-reloj-2). Era un falso contacto en la protoboard; la etapa 1 no lo podía detectar porque no usa ninguna conexión de la protoboard.

Qué queda abierto:

- El Pico no entra hasta el fondo: quedan unos 2 mm de pata a la vista. Hizo contacto al apretarlo, pero hay que volver a apretarlo antes de cada etapa y desconfiar primero del contacto si una lectura da 0.
- Hace falta un multímetro antes de la etapa 3.
- R1 quedó puesta en j14 a j24; el puente de GP20 se quitó.

## Entrada 33: el Pico como micrófono USB, con tono de prueba (2026-09-19)

Qué se hizo: el primer paso de la fase 5 sin esperar al ADC. firmware/tono_usb.c hace que la Mac vea al Pico como un micrófono UAC2 llamado feuoir, a 48 kHz, estéreo, 24 bits en subslot de 4 bytes. El Pico genera las muestras: en el canal 1 un seno de 1 kHz a -6 dBFS de pico desde una tabla de 48 muestras, y en el canal 2 ceros exactos. El ritmo lo marca el USB, 48 cuadros por paquete de 1 ms. clk_sys queda en 61.44 MHz con GPOUT0 encendido, como en el firmware final.

Condiciones: el mismo armado de la entrada 32, con R1 puesta y sin el puente de GP20. Cargado con picotool load -f, que reinicia en BOOTSEL al firmware de verificación sin tocar el botón. medir.py acepta ahora --dispositivo y --canal para grabar el Pico; el volumen que reporta el dispositivo es 50, 0.0 dB, y el firmware no lo aplica.

Resultado:

- La Mac lo lista como feuoir con 2 entradas. La primera grabación del canal 1 dio pico -6.0 dBFS y RMS -9.0 dBFS (mediciones/2026-09-19-tono-usb-canal1).
- La segunda apertura falló con PaErrorCode -9986 y el LED dejó de parpadear. Causa, leída en TinyUSB 0.18.0: en el RP2040 los endpoints isócronos no se cierran al pasar a la alternativa 0, el último buffer IN queda marcado disponible en la DPRAM porque el host ya no lo lee, y la próxima transferencia cae en panic("ep 81 was already available") de rp2040_usb.c. El firmware limpia el control de ese buffer en tud_audio_set_itf_close_EP_cb.
- Con el arreglo, tres aperturas seguidas sin error (tono-usb-canal1-2, tono-usb-canal2, tono-usb-canal1-3). Comparadas contra la tabla recalculada en Python, las 240000 muestras de cada toma del canal 1 coinciden todas, sin parte fraccionaria después de escalar por 2^23, y las 240000 del canal 2 son cero. El camino del Pico a la Mac pasa las muestras intactas.

Qué queda abierto:

- Con el ritmo del USB, la frecuencia del tono no dice nada del reloj: la Mac cuenta muestras. La variante con el ritmo del reloj de audio, que ejercita el ajuste de 47, 48 y 49 muestras por paquete de docs/audio-usb.md, queda por hacer.
- La comparación muestra a muestra se hizo a mano en la sesión; no es todavía una herramienta del repo con su prueba y su mutación.
- VID y PID de desarrollo de TinyUSB.

## Entrada 34: análisis de las tomas de guitarra (2026-09-19)

Qué se hizo: el análisis de las tomas de la entrada 30, con funciones nuevas en analizador.py y un script que las recorre, guitar_report.py. Resultado en mediciones/2026-09-19-analisis-guitarra.

Condiciones: las de la entrada 30. Datos de la guitarra informados después de grabar: Yamaha ERG121C, pastillas HSH cerámicas y pasivas. El largo del cable y la posición del selector en cada toma no están registrados.

Cambios en las herramientas:

- analizador.py suma crest_factor_db, averaged_spectrum, rolloff_points, remove_mains, fundamental y note_name. remove_mains ajusta 60 Hz y 40 armónicos por mínimos cuadrados en el tiempo, buscando la frecuencia real de la red, y los resta: así no hay fuga de la FFT hacia el residuo.
- fundamental usa el producto armónico. En captura-5 dio 657.8 Hz, una octava arriba, porque la fundamental estaba 16 dB bajo el segundo armónico. Lleva ahora una corrección de octava: baja si en f/2 hay una línea clara, 20 dB sobre la mediana a su alrededor y a no más de 30 dB del máximo. En esa toma la línea en f/2 estaba 32.9 dB sobre su mediana, y en las tomas donde f/2 no es la fundamental, entre 8.9 y 11.4 dB.
- calibrar.py pasa a 20 pruebas y 228 chequeos (calibraciones/2026-09-19-calibracion-4). tests/mutaciones.py suma 7 errores al analizador, uno por capacidad nueva y otro para la corrección de octava; las 53 mutaciones fallan (calibraciones/2026-09-19-mutaciones-4).

Resultado:

- Tarjeta sola contra guitarra en volumen 0: la tarjeta da -73.1 dBFS de RMS, y la guitarra a batería -60.1, 13.0 dB más. Sin el zumbido de la red la guitarra queda en -71.8, 1.3 dB sobre la tarjeta: la diferencia es casi toda zumbido. Con el cargador, -43.8 y -42.3, y sin el zumbido todavía -64.1 y -60.3: el cargador mete también ruido que no es de la red. En volumen 0 la pastilla queda a tierra, así que ese zumbido entra por el cable y la tarjeta, no por las pastillas.
- La red midió entre 60.01 y 60.05 Hz en las tomas con la guitarra en volumen 0. A batería, 60 Hz a -57.6 dBFS de pico y 120 Hz a -73.7. Con cargador, 60 Hz a -40.2 y 120 Hz a -47.4.
- Factor de cresta: 13.5 dB en el rasgueo suave y 21.5 dB en el fuerte; entre 11.2 y 23.2 dB en las cuerdas sueltas.
- Notas: captura-2 en 74.44 Hz, Re2 +24 cents: la cuerda grave estaba un tono abajo de Mi2. captura-3 en 389.4 Hz, Sol4 -11 cents. captura-4 en 330.3 Hz, Mi4 +4 cents, y captura-5 en 333.1 Hz, Mi4 +18 cents.
- Puntos de caída del espectro promediado sin la red: la cuerda grave cae 20 dB en 223 Hz, 40 dB en 1.8 kHz y 60 dB en 3.1 kHz. La cuerda aguda (captura-4) cae 20 dB en 1.66 kHz y 40 dB en 12.3 kHz, y la caída de 60 dB queda tapada por el piso.
- En los rasgueos los puntos caen entre 17 y 20 kHz. No miden el ancho de banda de la guitarra: el rasgueo fuerte de la app tiene contenido de banda ancha a unos -80 dBFS por bin hasta 18 kHz, 25 dB sobre el piso de la tarjeta, y el punto lo marca una línea aislada.

Qué queda abierto:

- La comparación entre posiciones del selector, para ver si la pastilla simple capta más zumbido que las dobles. Hacen falta tomas nuevas: guitarra en volumen máximo, sin tocar las cuerdas, la Mac a batería, una por posición y con la posición en las notas.
- De dónde sale la banda ancha del rasgueo fuerte: ruido de la púa y las cuerdas, o el preamplificador de micrófono de la tarjeta.
- En los agudos, las tomas de la app bajan a -115 a -120 dBFS por bin, bajo el piso de la tarjeta grabado con medir.py, que está en -107. El piso para comparar tiene que grabarse con la misma herramienta que la toma.
- captura-3: qué se tocó. El análisis dice Sol4.
- El modelo de la guitarra en la simulación no se ajusta con estas tomas: la entrada de micrófono carga la pastilla, así que se esperan los valores de la calibración de la tarjeta.

## Entrada 35: tomas por posición del selector y resistencia de las pastillas (2026-09-19 y 2026-09-23)

Qué se hizo: las tomas que pedía la entrada 34, una por cada posición del selector, y la medida con multímetro de la resistencia de las pastillas. Con esa medida el modelo de la guitarra deja de ser genérico.

Condiciones de las tomas: Yamaha ERG121C, selector de cinco posiciones, volumen y tono al máximo, cuerdas apagadas con la mano, sin tocar el cable entre tomas. Mac a batería, tarjeta USB en 0 dB, cable en la entrada de micrófono, 10 segundos por toma, medir.py. En mediciones/2026-09-19-selector-1 a -5.

Resultado de las tomas:

| Posición | RMS | Residuo sin la red | Zumbido de 60 Hz |
|---|---|---|---|
| 1, mástil | -73.2 dBFS | -73.2 dBFS | -110 dBFS |
| 2 | -72.9 dBFS | -72.9 dBFS | -110 dBFS |
| 3, medio | -73.5 dBFS | -73.6 dBFS | -98 dBFS |
| 4 | -73.4 dBFS | -73.4 dBFS | -99 dBFS |
| 5, puente | -73.1 dBFS | -73.1 dBFS | -94 dBFS |

- El residuo es el mismo en las cinco posiciones y coincide con la tarjeta sola, -73.1 dBFS. El ruido propio de las pastillas queda bajo el piso de la tarjeta: con este aparato no se puede comparar simple contra doble, que era la pregunta abierta de la entrada 34. Hace falta un piso más bajo, o sea la interfaz armada con su ganancia delante del PCM1808.
- El zumbido sí ordena las posiciones: nada del lado del mástil, algo en el medio, más en el puente. Son diferencias de 12 a 16 dB entre extremos, pero todas 20 dB o más bajo el piso, así que sirven para ver que la guitarra estaba conectada, no para comparar pastillas.
- La posición 1 se confirmó tocando una cuerda al aire justo después: Mi4 a 330.1 Hz, 18 dB sobre el piso. En la 2 no se hizo esa comprobación.

Dos fallas de la sesión, las dos por confiar en algo que no se verificó:

- El plug de la guitarra perdió contacto y no se notó. Con mal contacto entra el zumbido por la malla pero no la señal: la toma se ve como guitarra conectada y silenciosa. Se descubrió al tocar una cuerda y ver que no aparecía la nota. La primera toma de la posición 1 se repitió por eso.
- Al conectar y quitar unos audífonos Bluetooth, la Mac reordenó los dispositivos de audio y el índice 1 dejó de ser la tarjeta y pasó a ser el micrófono de la Mac. Dos grabaciones libres y el monitoreo en vivo salieron del micrófono sin que se notara, con acople por las bocinas. Se borraron. La tarjeta se elige siempre por nombre, que es lo que hace medir.py por defecto, y el nombre queda guardado en condiciones.json de cada toma: ahí se verifica.

Resistencia de las pastillas, medida el 2026-09-23 con un multímetro Truper MUT-830 en la escala de 20k, en el plug del cable conectado a la guitarra, con volumen y tono al máximo. Las puntas dan entre 0 y 0.8 Ω:

| Posición | Medida | Qué es |
|---|---|---|
| 1, mástil | 12.18 kΩ | doble sola |
| 2 | 4.96 kΩ | mástil y medio en paralelo |
| 3, medio | 8.16 kΩ | simple sola |
| 4 | 5.02 kΩ | medio y puente en paralelo |
| 5, puente | 12.60 kΩ | doble sola |

Las posiciones 2 y 4 comprueban a las otras tres: 12.18 con 8.16 en paralelo da 4.89 contra 4.96 medido, y 12.60 con 8.16 da 4.95 contra 5.02. Menos de 2% en las dos, contando las puntas y el potenciómetro de volumen.

Cambio en el modelo: spice/netlists/guitar.cir pasa de 8 kΩ fijos a un parámetro rcoil con 12.6 kΩ por defecto, la del puente, que es la que se graba con más ganancia. Las cinco medidas quedan en el comentario del archivo para simular cualquiera. GUITAR_R_OHM de spice/simulate_input.py acompaña el cambio, porque el cálculo a mano tiene que usar el mismo valor.

Simulaciones repetidas con el modelo nuevo, los 32 chequeos contra el cálculo a mano pasan (mediciones/2026-09-23-sim-respuesta-en-frecuencia, -sim-transitorio-1v5, -sim-ruido y -sim-carga-guitarra):

- La resonancia de la pastilla con 1 MΩ baja de +14.8 a +13.0 dB con cable de 300 pF, y de +15.0 a +12.6 dB con 600 pF. Las frecuencias no se mueven, 3.55 y 2.69 kHz: la resistencia amortigua el pico pero no lo corre.
- Con 10 kΩ de carga, la caída de 3 dB pasa de 593 a 737 Hz y la pérdida desde abajo de 5.2 a 7.2 dB. Una entrada de baja impedancia maltrata todavía más a esta guitarra que a la supuesta.
- El ruido casi no cambia: con ganancia 11 y cable de 300 pF, 56.3 µV en vez de 56.7.
- docs/entrada-analogica.md queda con estos números.

Qué queda abierto:

- La bobina de 5 H sigue siendo un supuesto. El MUT-830 no mide inductancia ni capacidad, así que tampoco se midió el cable, que sigue entre 300 y 600 pF. El cable se puede medir con la tarjeta: un tono desde la salida a través de una resistencia conocida y la frecuencia de caída despeja la capacidad. Hace falta una resistencia de 100 kΩ.
- Confirmar la posición 2 tocando una cuerda, como se hizo con la 1.
- La comparación de pastillas por su ruido, cuando haya un piso más bajo que el de la tarjeta.

## Entrada 36: el armado de la etapa de entrada, dibujado y verificado contra la simulación (2026-09-23)

Los módulos no llegan, y la etapa analógica de entrada no los necesita: se puede armar y probar contra la tarjeta USB, comparándola con las tomas de la guitarra conectada directo. Falta decidir cómo entra y sale la señal de la protoboard, que es lo único que no está resuelto.

docs/armado/draw_input_stage_breadboard.py dibuja el armado agujero por agujero y, antes de dibujar, lo comprueba. El dibujo no es una interpretación del esquema: el guion tiene la posición de cada pata en LAYOUT, deriva los nodos de la conectividad de la propia protoboard (las cinco columnas de una fila son un nodo, cada riel es otro) y exige que el circuito resultante sea el mismo que simula input_stage_split, parte por parte y nodo por nodo. Un cable en el agujero equivocado falla ahí. Salen 11 partes y 10 nodos.

Decisiones del armado, que son de trazado y no tocan el diseño:

- La etapa va en la MB-102 que está sin usar. El Pico se queda en su propia protoboard, porque ocupa veinte filas y no cabrían las dos cosas. Las filas del dibujo son las que vienen impresas en la placa.
- El TL072 cruza el canal en las filas 14 a 17, con la muesca hacia arriba.
- El potenciómetro queda fuera de la protoboard, con tres cables: una punta y la del medio al nodo de salida de la etapa A, la otra a la entrada inversora. Así sirve tanto uno de perilla como uno de ajuste. Sin potenciómetro, una resistencia fija entre esos dos nodos deja la ganancia en un valor: 10 kΩ da 11, 4.7 kΩ da 5.7 y 1 kΩ da 2.
- Tierra en los dos rieles de los bordes, unidos entre sí, para que ninguna pata tenga que cruzar la placa.
- Donde un cable cruza un riel sin conectarse, el dibujo salta por encima, para que un cruce no se lea como una unión.

docs/compras.md no tenía las pasivas de la etapa, solo el TL072 y las pilas. Quedan anotadas: 1 MΩ, 1 kΩ y 4.7 kΩ, el potenciómetro de 10 kΩ lineal, y los condensadores de 100 nF, 1 nF y 2.2 µF, con la nota de que el de 2.2 µF es el único que puede venir polarizado y va con el lado marcado hacia el PCM1808.

Verificación por mutaciones con el modelo de guitarra nuevo: las 53 mutaciones hacen fallar sus pruebas (calibraciones/2026-09-23-mutaciones-2). La corrida anterior se había cortado por un control de la app que compara la ganancia en dB de la entrada por defecto con la conversión de Core Audio: con unos audífonos Bluetooth como entrada por defecto, el aparato reporta -2.13 dB por un lado y -9.41 por el otro. No es del repo, pero conviene recordarlo: esa prueba depende de qué entrada tenga el sistema puesta.

## Entrada 37: el armado en una imagen por paso (2026-09-23)

El dibujo completo de la protoboard sirve para comprobar, no para armar: Renata lo mira y ve veinte cosas a la vez. docs/armado/draw_input_stage_steps.py parte el mismo armado en 21 pasos, uno por pieza, y saca una imagen de cada uno en docs/armado/pasos/ más las 21 juntas en docs/armado/etapa_entrada_pasos.pdf. En cada imagen, lo que ya está puesto va en gris claro, la pieza del paso va en color y lo que viene después no se dibuja. Debajo, la frase con los agujeritos exactos.

El guion importa LAYOUT, WIRES y check() de draw_input_stage_breadboard, así que los pasos salen de la misma placa verificada contra input_stage_split y no pueden separarse de ella. El orden es: la piecita negra, las pasivas, los cables, la unión de las dos tierras, el desacoplo, el potenciómetro, las puntas de entrada y salida, y las pilas al final.

Dos cosas que se arrastran al armado: el de 2.2 µF no ha llegado, viene en el pedido 2, y su paso dice que se puede dejar el hueco o poner en su lugar uno de 10 µF, que sí es polarizado y va con la raya hacia h11. Y las etiquetas no nombran componentes: describen la forma, porque es como Renata los distingue en la mesa.

## Entrada 38: el sentido del acoplo de salida estaba al revés (2026-09-23)

El de 2.2 µF no está en la caja, viene en el pedido 2, así que la etapa se arma con uno de 10 µF: el corte baja de 1.21 Hz a 0.27 Hz y no molesta. Al escribir su paso salió a la luz un error que venía de docs/compras.md: decía que el lado marcado del electrolítico va hacia el PCM1808. En un electrolítico de aluminio la raya impresa marca el negativo, y el negativo va del lado del seguidor, que está centrado en 0 V, no del lado del módulo, que está en 2.5 V. Corregido en compras.md y en el paso 7, que ahora dibuja el barrilito en grande con la raya del lado de h15.

De paso, la de 103 que apareció entre las cerámicas es de 10 nF, una de las cinco del pedido, no sirve para ese sitio.

## Entrada 39: el potenciómetro se clava en la protoboard (2026-09-23)

El que llegó dice B10K: 10 kΩ y lineal, el que pedía el diseño, y no trae lengüetas de soldar sino tres patitas rectas separadas 5 mm, que son dos agujeritos de la protoboard. Así que deja de ir por fuera con tres cables sueltos y se clava en la placa.

Va en a3, a5 y a7, una zona vacía y lejos de todo, con la del medio en a5. De ahí salen tres cables: b3 a b14 y b5 a d14, que llevan un extremo y la punta media al nodo de salida de la etapa A, y b7 a b15, que lleva el otro extremo a la entrada inversora. No se puede clavar más cerca del TL072 porque las filas 14 a 17 del lado a..e son sus cuatro primeros pines.

LAYOUT y WIRES de draw_input_stage_breadboard cambiaron con él y la comprobación contra input_stage_split sigue dando 11 partes y 10 nodos, así que el circuito es el mismo. Sin potenciómetro, la alternativa queda más simple que antes: una resistencia fija de a14 a b15 y ningún cable.


## Entrada 40: un mapa de qué hay en cada agujerito

Al armar la etapa de entrada aparecieron dos preguntas seguidas: si b14 daba igual que c14, y qué agujeritos estaban
ya ocupados. Lo primero sí: los cinco agujeritos de una fila del mismo lado de la zanja son un solo punto, así que la
letra la elige quien arma y lo que no se puede cambiar es el número de fila. Lo segundo pedía una lista, y llevarla a
mano se desfasa del circuito al primer cambio.

`docs/armado/mapa_agujeritos.py` la genera de LAYOUT, WIRES y EXTERNAL, los mismos datos que usa el dibujo que se
comprueba contra input_stage_split, y corre esa comprobación antes de escribir. Deja `docs/armado/mapa_de_agujeritos.md`
con una tabla por fila, los dos lados de la zanja separados, y debajo los agujeritos que quedan libres en cada fila
que ya se usa. La patita del medio del potenciómetro, que va en a5, se añade a mano: en la netlist el potenciómetro
tiene dos terminales y el cursor no aparece.
