# feuoir-interface

Interfaz de audio USB propia, para guitarra. Una Raspberry Pi Pico (RP2040) toma el audio de un ADC PCM1808 y lo manda a la Mac por USB, y recibe audio de la Mac para un DAC PCM5102A. Antes de diseñar la parte analógica hay que conocer la señal que va a recibir: cuánto voltaje entrega la guitarra, hasta qué frecuencia tiene energía y cuánto ruido trae. El repo empieza por las herramientas para medir eso y por el diseño de la parte digital, verificado sin hardware.

Al 2026-09-19 el Pico está probado en una placa: el reloj maestro sale por GP21 y la Mac lo reconoce como micrófono USB con un tono de prueba. Los módulos del ADC y del DAC todavía no llegaron. El diseño y la simulación de la parte analógica van por separado y no están en este repo.

Las mediciones se hacen en dos máquinas: la Mac, donde empezó el repo, y una laptop ASUS con Windows, con una tarjeta de sonido USB externa. Las dos usan los mismos scripts, y cada medición guarda el sistema operativo, la API de audio y el nivel de entrada, que es lo que hace falta para poder compararlas (docs/configuracion-windows.md).

## Cómo está armado

- El PCM1808 trabaja en modo maestro: genera BCK y LRCK a 48 kHz a partir de su reloj maestro SCKI, de 12.288 MHz.
- SCKI sale del Pico por GPOUT0 (GPIO21), con clk_sys en 61.44 MHz y divisor entero 5. Un jumper permite tomarlo de un oscilador de cristal externo, para comparar el jitter de los dos (docs/reloj.md).
- El PCM5102A usa el mismo BCK y LRCK. Otro jumper pone su SCK a tierra, y el DAC usa su PLL, o en el mismo SCKI. Así todo el audio queda en un solo dominio de reloj y el Pico es esclavo por los dos lados (docs/dominio-de-reloj.md).
- Hacia la Mac, USB Audio Class en modo asíncrono: la captura lleva el ritmo del PCM1808 y la reproducción necesita realimentación (docs/audio-usb.md).

## Estado

| Parte | Estado | Probado | Sin probar |
|---|---|---|---|
| medir.py y dispositivos.py | funcionan en la Mac y en Windows | con la tarjeta USB y la guitarra en la Mac el 2026-09-19 (docs/bitacora.md, entrada 30); en Windows corren por WASAPI a 48 kHz y guardan su carpeta, comprobado con una captura de prueba que no se conservó (docs/bitacora.md, entrada 29) | la guitarra con la carga de la etapa de entrada; la tarjeta de sonido USB y la guitarra en Windows |
| analizador.py | cubre lo que se necesita hasta ahora | calibrar.py: 13 pruebas y 180 chequeos con señales sintéticas; tests/mutaciones.py detecta los 20 errores inyectados | nunca se usó con una captura de hardware |
| Reloj maestro | elegido: GPOUT0 con DC50 | búsqueda exhaustiva de configuraciones con relojes.py; firmware/feuoir compila sin avisos | en una placa |
| Verificación del reloj | funciona en la placa | firmware/informe.c con 11 casos en la Mac; leer_verificacion.py con un pseudo terminal, 13 casos; en el Pico el 2026-09-19: PLL en 61440000 Hz y 12288000 Hz en GP20 por R1, con 0.0 ppm (docs/bitacora.md, entrada 32) | con los módulos conectados |
| Jitter | simulado, con la prueba lista | jitter.py: 19 casos contra la teoría; prueba_jitter validada con jitter conocido | la comparación entre GPOUT0 y el oscilador externo |
| Oscilador externo | previsto en el diseño, con jumper | la opción FEUOIR_RELOJ_EXTERNO compila | no está comprado ni montado |
| Dominio de reloj | diseño en papel, con jumper de SCK | revisado contra las hojas del PCM1808, el PCM5102A y el RP2040 | las conexiones, los puentes del módulo y el margen de DIN |
| Resistencias en serie | calculadas: 330 Ω en el reloj maestro y 470 Ω en BCK, LRCK, DOUT y DIN | cálculo contra los límites de corriente y los umbrales de las hojas | sin montar |
| Primer encendido | etapas 1 y 2 hechas el 2026-09-19 | sin fallas inesperadas; un falso contacto en la protoboard dio 0 Hz hasta apretar el Pico (docs/bitacora.md, entrada 32) | las etapas 3 y 4, que necesitan los módulos y un multímetro |
| App de medición en vivo | construida: forma de onda, espectro, nivel con aviso de saturación, cinco mediciones con notas y su salida del estímulo, y la lista de guardadas, en ventana propia | tests/app_contract.py: 53 comprobaciones por WebSocket con la fuente sintética; tests/mutaciones.py detecta los 17 errores inyectados; la ventana abre en la Mac; con el micrófono interno abre a 48 kHz y los cuadros llegan a ritmo real | la tarjeta de sonido USB, la interfaz y las mediciones con el estímulo por cable |
| Simulación del circuito analógico | ngspice 47 compilado en ~/spice y verificado contra la teoría; la etapa de entrada simulada en sus dos versiones: respuesta en frecuencia, transitorio, ruido y carga de la guitarra | spice/verify.py: 13 chequeos con un divisor y un filtro RC en AC, escalón y ruido; spice/simulate_input.py: 32 chequeos contra el cálculo a mano del circuito; tests/mutaciones.py detecta los 9 errores inyectados en spice/; el ruido del modelo del TL072H coincide con la hoja a 0.13 dB | discutir la entrada del PCM1808, que con ganancia alta pasa su máximo absoluto (docs/entrada-analogica.md); comparar con el circuito armado |
| Toolchain | instalado en ~/pico | compila blink y el firmware del proyecto; carga en el Pico con BOOTSEL o con picotool load | nada |
| Fase 5: captura por USB | primer paso: firmware/tono_usb.c, el Pico como micrófono UAC2 con tono de prueba y el ritmo del USB | la Mac lo ve como feuoir; 240000 muestras por toma idénticas a la tabla y el canal de silencio en ceros exactos (docs/bitacora.md, entrada 33) | el ritmo del reloj de audio con 47, 48 y 49 muestras por paquete; el audio del PCM1808 |
| Fase 6: reproducción | no empezada | opciones de realimentación investigadas | todo |

Hasta que lleguen los módulos, el firmware nuevo se prueba en el Pico solo, con señales que genera él mismo.

## Estructura

```
medir.py               captura de una entrada de audio, en la Mac o en Windows
analizador.py          análisis y señales de prueba
calibrar.py            verificación del análisis con señales sintéticas
relojes.py             búsqueda de configuraciones del reloj maestro
jitter.py              simulación del efecto del jitter
leer_verificacion.py   guarda el informe del firmware de verificación
dispositivos.py        lista las entradas con su API y describe el entorno de la medición
device_volume.py       lee el volumen y la ganancia de entrada de cualquier dispositivo, en macOS
app/                   app de medición en vivo; la interfaz está en app/ui
spice/                 simulación con ngspice: ejecutor, netlists, modelos del TL072, verificación y etapa de entrada
tests/                 errores inyectados y pruebas sin placa del firmware, de la lectura y de la app
firmware/              reloj maestro y firmware de verificación para el Pico
docs/                  reloj, dominio de reloj, audio USB, entrada analógica, simulador, compras, primer encendido, app, configuración de Windows, bitácora y hojas de datos
calibraciones/         resultados de calibrar.py, de tests/mutaciones.py y de la verificación del simulador y sus modelos
simulaciones/          resultados de jitter.py
mediciones/            capturas y verificaciones, y las simulaciones de la etapa de entrada
```

## Convenciones

- Cada resultado queda guardado con sus condiciones en una carpeta con fecha. Nada queda solo en la terminal.
- Ninguna función entra a analizador.py sin su prueba en calibrar.py, y cada capacidad nueva entra además con una mutación en tests/mutaciones.py que la ataque.
- Cada decisión queda en docs/bitacora.md, con qué se midió, en qué condiciones y por qué.
- El código va en inglés: archivos, nombres y contratos. Los comentarios y las docstrings van en español, igual que todo lo que ve el usuario: la interfaz, los avisos, la salida de consola y la documentación. La app y los dos scripts de medición ya siguen esta regla; los comentarios de la app y el código anterior a ella todavía están en inglés o en español sin migrar.
- Cada medición guarda el sistema operativo, la API de audio y el nivel de entrada. Sin esos tres datos una medición hecha en la Mac y otra hecha en la ASUS no se pueden comparar.
- El nivel de entrada se anota una vez y no se toca, ver Nivel de entrada.

## Qué mide medir.py

Graba 5 segundos de una entrada de audio a 48 kHz y calcula el pico y el RMS de la señal. Cada corrida guarda el audio, una gráfica con la forma de onda y el espectro en dBFS, y las condiciones en que se hizo:

```
.venv/bin/python medir.py piso-de-ruido --notas "ventana cerrada"              en la Mac
.venv/Scripts/python medir.py piso-de-ruido --dispositivo 18 --nivel-entrada 50    en Windows
```

```
mediciones/2026-09-13-piso-de-ruido/
  captura.wav
  captura.png
  condiciones.json
```

condiciones.json registra fecha y hora, etiqueta, sistema operativo, dispositivo (nombre, índice y API de audio), canal, frecuencia de muestreo, duración, cuánto se descartó al inicio, nivel de entrada con el origen del dato, volumen de entrada del dispositivo y su ganancia en dB, pico y RMS en dBFS, y notas. Si la etiqueta se repite el mismo día, la carpeta nueva termina en -2, -3, etc.

El dispositivo se elige con --dispositivo, por su nombre o por el índice que lista dispositivos.py; sin eso se usa la tarjeta USB (USB PnP Sound Device). Si esa entrada no acepta un canal a 48 kHz, medir.py lo dice y no graba. --canal elige cuál de sus canales se analiza y se guarda, desde 1, y queda en condiciones.json. La tarjeta da un golpe al abrir la grabación: medir.py graba un segundo de más y lo descarta, y lo anota en descartado_al_inicio_s.

El nivel de entrada se pasa con --nivel-entrada, o dejando puesta la variable FEUOIR_NIVEL_ENTRADA. En la Mac también se lee solo, con device_volume.py (Core Audio): vale para cualquier dispositivo, no solo el de por defecto, y guarda el volumen y la ganancia en dB. Windows no expone ese dato, así que ahí se anota a mano. Sin el nivel, medir.py avisa y lo guarda como null: esa captura sirve para mirarla, no para compararla.

El pico, el RMS y el espectro salen de analizador.py, el mismo código que verifica calibrar.py.

Instalación:

```
python3 -m venv .venv                                              en la Mac
.venv/bin/pip install sounddevice numpy matplotlib scipy

py -m venv .venv                                                   en Windows
.venv/Scripts/pip install sounddevice numpy matplotlib scipy
```

En Windows el python del entorno está en `.venv/Scripts/python`, no en `.venv/bin/python`: donde el resto de este README diga `.venv/bin/python`, en Windows va `.venv/Scripts/python`.

## Los valores son dBFS

Pico y RMS están en dBFS, decibeles relativos al fondo de escala del conversor, donde 0 dBFS es la muestra más grande que se puede representar. No son niveles absolutos de presión sonora (dB SPL) ni voltajes. El mismo sonido da otro número con otro dispositivo u otro volumen de entrada, y para pasar a voltios hace falta calibrar la entrada con una señal conocida. El RMS se calcula contra 1.0, así que una senoidal a fondo de escala da -3 dBFS.

## Nivel de entrada

El nivel del control de entrada se anota una vez y no se vuelve a mover. Si cambia, las mediciones dejan de ser comparables entre sí y hay que repetirlas. En la Mac está en 71 y se lee solo. En Windows hay que anotarlo a mano, y en la ASUS es el nivel de la tarjeta de sonido USB, no el del micrófono interno: docs/configuracion-windows.md dice dónde está y qué más hay que apagar para que Windows no toque la señal.

Cada condiciones.json guarda el valor y de dónde salió, para que se vea si el número es leído o anotado.

## Las entradas de audio y sus APIs

```
.venv/bin/python dispositivos.py           en la Mac
.venv/Scripts/python dispositivos.py       en Windows
```

Una fila por entrada, con índice, nombre, API de audio, canales, frecuencia y si acepta un canal a 48 kHz, y marca cuál es la entrada por defecto del sistema.

En Windows el mismo aparato aparece una vez por cada API: MME, DirectSound, WASAPI y WDM-KS son caminos distintos hacia el mismo conversor. La tabla marca con un asterisco las filas de WASAPI, que es la que habla con el driver sin remuestrear ni mezclar por el medio, y es la que hay que elegir. MME además recorta los nombres a 31 caracteres, así que la misma tarjeta puede aparecer con dos nombres. En la Mac hay una sola API, Core Audio, y cada entrada aparece una vez.

medir.py y la app toman de dispositivos.py el sistema operativo, la API de audio y el nivel de entrada que guardan en condiciones.json.

Cada dispositivo tiene su propio volumen. device_volume.py lo lee de Core Audio para cualquier entrada, sea o no la de por defecto, y también la ganancia en dB, porque el volumen solo engaña: la tarjeta USB marca 0, y eso es 0 dB de ganancia, el mínimo de su rango de 0 a 23.8 dB, no silencio. Solo lee, no cambia nada de la Mac. Al 2026-09-19 la tarjeta está en 0 (0 dB) y tampoco se toca.

## analizador.py

El análisis y las señales de prueba. medir.py lo importa y calibrar.py lo verifica.

- pico_dbfs y rms_dbfs: niveles en dBFS.
- espectro, resolucion_hz y picos_espectrales: espectro de amplitud en dBFS con ventana Hann. Una senoidal de amplitud A que cae en un bin da 20·log10(A).
- ajuste_seno: amplitud, fase, continua y frecuencia de una senoidal por mínimos cuadrados (IEEE 1057, 4 parámetros).
- thd_n: THD+N relativo a la fundamental, limitado por defecto a la banda de 20 Hz a 20 kHz. Un armónico con el 1 % de la amplitud de la fundamental da 1.000 %.
- snr_db: relación señal a ruido con dos capturas, una con el tono de prueba en la entrada y otra sin señal.
- respuesta_en_frecuencia: nivel, ganancia y fase de cada tono de un barrido escalonado, relativos a la captura de entrada del circuito.
- prueba_jitter: con una captura por tono de 1 a 10 kHz, mide THD+N en una banda fija alrededor de cada tono, ajusta cuánto crece con la frecuencia y responde si el patrón es compatible con jitter. Da también la pendiente en dB por década y un jitter RMS equivalente.
- tono, barrido_log, frecuencias_log y barrido_escalonado: señales para excitar el circuito cuando exista.

## calibrar.py

Antes de confiar en lo que mide medir.py hay que saber que el análisis está bien. calibrar.py pasa por analizador.py señales sintéticas con resultado conocido y compara:

- senoidal de amplitud A: pico 20·log10(A) y RMS 20·log10(A/√2), también con el pico en la excursión negativa
- senoidal con un armónico al 1 %: THD+N de 1.000 %
- THD+N en una banda angosta alrededor del tono: ve las bandas laterales cercanas y deja afuera lo que está lejos, que es como se mide el ruido cerca de un tono
- prueba de jitter con capturas de jitter conocido: solo jitter de 1 ns (20 dB por década y el jitter de vuelta), solo ruido (sin efecto), ruido con jitter (compatible) y ruido que crece 40 dB por década (no compatible)
- ruido blanco gaussiano y uniforme de varianza conocida: RMS
- dos tonos separados 2 Hz: un solo pico con 0.1 s de captura (resolución de 10 Hz) y dos picos con 2 s (resolución de 0.5 Hz)
- ajuste de senoidal, SNR, THD+N con ruido, generadores de tono y barrido, y respuesta en frecuencia de un filtro Butterworth cuya respuesta exacta se conoce

```
.venv/bin/python calibrar.py
```

Cada corrida guarda en calibraciones/<fecha>-calibracion/resultados.json todos los chequeos con sus condiciones, lo esperado, lo obtenido y la tolerancia, junto con las versiones de Python, numpy y scipy y el sha256 de analizador.py. Si un chequeo se sale de tolerancia, el script lo muestra y termina con código 1. Las funciones test_ también corren con pytest.

Ninguna función entra a analizador.py sin su prueba en calibrar.py, y cada capacidad nueva entra además con al menos una mutación en tests/mutaciones.py que la ataque específicamente.

### Errores inyectados

tests/mutaciones.py comprueba que calibrar.py sigue atrapando errores. Copia analizador.py a una carpeta temporal, le inyecta 20 errores, uno a la vez (RMS sin raíz, pico sin valor absoluto, fase con el signo invertido, entre otros), y corre calibrar.py sobre cada copia: todas tienen que fallar. Antes corre una copia sin cambios como control, que tiene que pasar.

```
.venv/bin/python tests/mutaciones.py
```

Con la app hace lo mismo: copia app/ y tests/app_contract.py, inyecta 15 errores en app/ (un detector de saturación que saltea muestras, un pico que no se sostiene entre bloques, un emisor que espera a cada conexión y deja que una lenta frene a las demás, las notas de la medición ignoradas, entre otros) y corre esa prueba sobre cada copia, después de su propio control.

Guarda el resultado en calibraciones/<fecha>-mutaciones/resultados.json y termina con código 1 si algún error pasa sin detectarse o si un control falla. También falla si se cambia un archivo y el texto que reemplaza una mutación deja de existir; en ese caso hay que actualizar la mutación para que siga inyectando el mismo error. Con la verificación del simulador hace lo mismo sobre spice/: le cambia un valor a un netlist, rompe el lector de .raw o calcula el ruido a otra temperatura, y spice/verify.py tiene que fallar. Con las simulaciones de la etapa de entrada, le cambia R4, C4 o R3 al circuito o la bobina a la guitarra, o carga la entrada al aire con 1 MΩ, y los chequeos de spice/simulate_input.py tienen que fallar. Hay que correrlo cada vez que se toque analizador.py, calibrar.py, app/ o spice/.

## relojes.py

El PCM1808 necesita 12.288 MHz en SCKI y el cristal del Pico es de 12 MHz. relojes.py recorre todas las configuraciones del PLL del RP2040 y, para cada una, el divisor que haría falta en la salida de reloj GPOUT0 y en una máquina de estados del PIO, y se queda con las que dan esa frecuencia exacta. La lista completa va a docs/reloj-soluciones.csv. En docs/reloj.md solo reescribe el bloque entre las marcas de inicio y fin; la solución elegida, el respaldo y la verificación se escriben a mano.

```
.venv/bin/python relojes.py
```

## jitter.py

Simula el efecto del jitter del reloj de muestreo sobre un tono y lo mide con analizador.py, para saber qué buscar al comparar GPOUT0 con un oscilador externo. No mide hardware.

```
.venv/bin/python jitter.py
```

Guarda cada caso con sus condiciones, lo esperado según la teoría y lo medido en simulaciones/<fecha>-jitter/resultados.json, y termina con código 1 si algún caso no coincide. Qué significan los resultados está en docs/reloj.md, en la sección Jitter del reloj maestro.

## App de medición en vivo

Una ventana con la forma de onda, el espectro y el nivel de la entrada en vivo, con aviso de saturación, y un botón por cada medición del analizador: captura de 5 s, THD+N, SNR, respuesta en frecuencia y prueba de jitter. Cada medición guarda su carpeta en mediciones/ con sus condiciones, como medir.py. Desde Guardadas, en el pie de la ventana, se ven todas y cada una se abre en Finder. Python lee el audio y analiza con analizador.py; la interfaz solo dibuja. Sin hardware se usa con la fuente sintética, que hace de conversor.

![La app con la fuente sintética saturando](docs/app-captura.png)

Instalación, una sola vez:

```
.venv/bin/pip install aiohttp==3.14.3 pywebview==6.2.1
cd app/ui && npm install && npm run build
```

Para abrirla, desde la raíz del repo:

```
.venv/bin/python -m app
```

Cómo está hecha, qué calcula, el contrato del WebSocket y las pruebas: docs/app.md.

## Simulación del circuito analógico

El circuito de entrada se simula con ngspice 47 en modo batch, desde Python y dentro del repo. Los netlists son texto plano en spice/netlists/. ngspice se compila una vez desde su código fuente en ~/spice, sin Homebrew; el procedimiento y el porqué de cada opción están en docs/simulador-spice.md.

Antes de creerle en el circuito real, se verifica contra la teoría con un divisor resistivo y un filtro RC de primer orden:

```
.venv/bin/python -m spice.verify
```

Guarda cada chequeo con sus condiciones en calibraciones/<fecha>-spice/resultados.json y termina con código 1 si alguno se sale de tolerancia. Si no pasa, ninguna otra simulación vale.

Se usan los dos modelos del TL072 de TI: el del clásico para todo lo lineal y el del TL072H solo para el ruido. Antes de usarlos se caracterizan: el ruido del H contra la hoja, la inversión de fase del clásico y el offset del H.

```
.venv/bin/python -m spice.characterize
```

Qué modelo se usa para qué y por qué: docs/simulador-spice.md.

Las simulaciones de la etapa de entrada, en sus dos versiones: respuesta en frecuencia con cinco ganancias, transitorio con 1.5 V de pico, ruido con la entrada al aire y con la guitarra, y la guitarra sola cargada con 1 MΩ y con 10 kΩ.

```
.venv/bin/python -m spice.simulate_input
```

Cada una guarda su carpeta en mediciones/<fecha>-sim-<nombre>/ con sus condiciones, los datos, los netlists que corrió y las gráficas, y aparece en Guardadas de la app. Compara cada corrida con cálculos a mano del circuito y termina con código 1 si no coinciden. Qué dieron: docs/entrada-analogica.md.

## firmware

firmware/ configura el reloj maestro: clk_sys en 61.44 MHz y 12.288 MHz por GPIO21 (GPOUT0) con DC50. Además hace parpadear el LED para mostrar que sigue corriendo. Se compila con las mismas variables de entorno que el blink (ver Toolchain del Pico):

```
cd firmware
cmake -S . -B build
make -C build -j4
```

El resultado es firmware/build/feuoir.uf2. No se probó en una placa.

Para medir con el oscilador externo en vez de GPOUT0 (docs/reloj.md, sección del oscilador externo) se compila en otra carpeta con la opción que deja GPOUT0 apagado:

```
cmake -S . -B build-externo -DFEUOIR_RELOJ_EXTERNO=ON
make -C build-externo -j4
```

### Firmware de verificación del reloj

Probado en el Pico el 2026-09-19, en las etapas 1 y 2 del primer encendido (docs/bitacora.md, entrada 32). firmware/verificar_reloj.c hace los pasos 1 y 2 de la verificación sin osciloscopio de docs/reloj.md. Configura el reloj igual que el firmware principal y cada 2 s imprime por USB un informe con:

- los registros del PLL y de GPOUT0 leídos de vuelta: REFDIV, FBDIV, POSTDIV1, POSTDIV2, PLL enganchado, ENABLE, DC50, fuente y divisor de GPOUT0
- la salida del PLL medida con el contador de frecuencia del RP2040, contra el cristal
- la frecuencia que entra por GPIO20, que para el paso 2 va puenteado a GPIO21

Cada línea trae el valor, lo esperado y ok o FALLA, y el informe termina con la cantidad de fallas. Se compila junto con el firmware principal:

```
cd firmware
cmake -S . -B build
make -C build verificar_reloj -j4
```

Se carga firmware/build/verificar_reloj.uf2 y la salida se lee desde la Mac con screen, que viene con macOS. El nombre del puerto depende de la placa:

```
ls /dev/cu.usbmodem*
screen /dev/cu.usbmodemXXXX
```

Compilado en build-externo, espera GPOUT0 apagado y mide en GPIO20 la salida del oscilador externo.

El informe no se copia a mano. leer_verificacion.py lee el puerto, espera un informe completo y lo guarda con sus condiciones en mediciones/<fecha>-<etiqueta>/, igual que medir.py. --puentes es obligatorio, porque el firmware no puede saber cómo están los puentes:

```
.venv/bin/python leer_verificacion.py gpout0-puente --puentes "GPIO21 puenteado a GPIO20"
```

Guarda informe.txt, con las líneas tal como llegaron, y condiciones.json, con fecha, puerto, puentes, notas, modo del firmware y cada chequeo con su valor, lo esperado y el resultado. Termina con código 1 si el informe trae fallas o si no llega uno completo en 10 s. Sin placa se prueba con un pseudo terminal que hace de puerto:

```
.venv/bin/python tests/lectura_sin_placa.py
```

La parte que decodifica los registros y arma el informe (firmware/informe.c) no toca hardware y se prueba en la Mac:

```
.venv/bin/python tests/verificacion_sin_placa.py
```

Lo que solo se puede probar en la placa es la lectura real de los registros y el contador de frecuencia.

### tono_usb

firmware/tono_usb.c hace que la Mac reconozca al Pico como un micrófono USB (UAC2) llamado feuoir y le mande un tono de prueba de 1 kHz por el canal izquierdo, con el derecho en silencio. Todavía no hay ADC: el firmware genera las muestras él mismo. Especificación completa en docs/audio-usb.md. Se compila junto con los otros dos:

```
cd firmware
cmake -S . -B build
make -C build tono_usb -j4
```

Probado en el Pico el 2026-09-19 (docs/bitacora.md, entrada 33). Se carga con BOOTSEL o, si el Pico corre el firmware de verificación, con picotool load -f -x firmware/build/tono_usb.uf2. Para grabarlo:

```
.venv/bin/python medir.py tono-usb --dispositivo feuoir --canal 1
```

## Documentación

- docs/reloj.md: reloj maestro elegido, respaldo, corrección sobre el divisor fraccionario y cómo verificar la frecuencia sin osciloscopio
- docs/bitacora.md: qué se midió en cada etapa de trabajo, en qué condiciones, qué se decidió y por qué
- docs/dominio-de-reloj.md: un solo dominio de reloj para el audio, con el diagrama de conexiones del PCM1808, el PCM5102A y el Pico
- docs/audio-usb.md: cómo se resuelve con USB Audio Class que el reloj de audio no coincida con el de la Mac: captura asíncrona, realimentación para la reproducción y qué soporta TinyUSB
- docs/compras.md: lo que pide el diseño, con las resistencias en serie
- docs/entrada-analogica.md: la etapa analógica de entrada en sus dos versiones, las condiciones para simularla y los efectos que hay que conocer
- docs/simulador-spice.md: por qué ngspice y no LTspice, cómo se instala sin Homebrew, cómo se verifica contra la teoría y qué hay que saber de los modelos del TL072
- docs/primer-encendido.md: lista paso a paso para el primer encendido, con qué medir y qué esperar en cada etapa
- docs/configuracion-windows.md: cómo dejar Windows sin tocar la señal antes de medir, y por qué el nivel de entrada se anota y no se mueve
- docs/app.md: la app de medición en vivo: cómo abrirla, cómo está hecha, qué calcula, sus mediciones, el contrato del WebSocket y las pruebas
- docs/app-cascara.md: por qué la app es una ventana de pywebview con Python detrás, y qué se descartó
- docs/app-ideas.md: ideas para la app, anotadas en vez de construidas
- docs/datasheets/: hojas de datos del PCM1808, el PCM5102A, el TL072 y el RP2040
- DECISIONES.md: decisiones de hardware y de método

## Toolchain del Pico

Procedimiento que funcionó el 2026-09-13 en macOS 26.5.2 (MacBook Pro 2019, Intel), sin la placa conectada. Todo queda en ~/pico, fuera de este repo.

| Componente | Versión |
|---|---|
| pico-sdk | 2.3.1 (commit 079c6f3), con el submódulo lib/tinyusb (86ad6e5) |
| pico-examples | sdk-2.3.1 (commit 0d62f75) |
| Arm GNU Toolchain | 14.2.rel1, arm-none-eabi-gcc 14.2.1 20241119 |
| picotool | 2.3.1 (commit 2041936), con libusb 1.0.30 de Homebrew |
| CMake | 4.4.3 de Homebrew |
| make | /usr/bin/make de macOS |
| Compilador para picotool | AppleClang 21.0.0 |
| Python que encontró el SDK | 3.14.7 de Homebrew |

### 1. CMake

```
brew install cmake
```

### 2. Toolchain de Arm

Arm dejó de publicar builds para Mac Intel después de la 14.2.rel1: la 14.3.rel1 y la 15.2.rel1 solo salen para darwin-arm64. El tar.xz se descarga en una carpeta temporal y no necesita sudo.

```
cd "$(mktemp -d)"
URL=https://armkeil.blob.core.windows.net/developer/Files/downloads/gnu/14.2.rel1/binrel/arm-gnu-toolchain-14.2.rel1-darwin-x86_64-arm-none-eabi.tar.xz
curl -fLO "$URL"
curl -fLO "$URL.sha256asc"
cat arm-gnu-toolchain-14.2.rel1-darwin-x86_64-arm-none-eabi.tar.xz.sha256asc
shasum -a 256 arm-gnu-toolchain-14.2.rel1-darwin-x86_64-arm-none-eabi.tar.xz
mkdir -p ~/pico/toolchain
tar -xJf arm-gnu-toolchain-14.2.rel1-darwin-x86_64-arm-none-eabi.tar.xz -C ~/pico/toolchain
```

Los dos hashes tienen que coincidir: 2d9e717dd4f7751d18936ae1365d25916534105ebcb7583039eff1092b824505. Extraído ocupa 996 MB.

### 3. pico-sdk y pico-examples

Del SDK solo se inicializa el submódulo lib/tinyusb, que es el que da soporte USB. Los demás no hicieron falta para compilar.

```
cd ~/pico
git clone --depth 1 --branch 2.3.1 https://github.com/raspberrypi/pico-sdk.git
git -C pico-sdk submodule update --init --depth 1 lib/tinyusb
git clone --depth 1 --branch sdk-2.3.1 https://github.com/raspberrypi/pico-examples.git
```

### 4. picotool

Desde el SDK 2.0 la conversión de ELF a UF2 la hace picotool. Si el SDK no lo encuentra, lo baja y lo compila dentro de cada proyecto, así que se instala una vez aparte. Usa libusb y pkgconf de Homebrew.

```
cd ~/pico
git clone --depth 1 --branch 2.3.1 https://github.com/raspberrypi/picotool.git
cd picotool && mkdir build && cd build
export PICO_SDK_PATH=$HOME/pico/pico-sdk
cmake .. -DCMAKE_INSTALL_PREFIX=$HOME/pico/picotool-install -DPICOTOOL_FLAT_INSTALL=1
make -j4
make install
~/pico/picotool-install/picotool/picotool version
```

Tiene que responder picotool v2.3.1. Se compila con -j4 y no con todos los núcleos para no llenar la memoria.

### 5. Compilar el blink

Las tres variables se exportan en la terminal donde se compila.

```
export PICO_SDK_PATH=$HOME/pico/pico-sdk
export PICO_TOOLCHAIN_PATH=$HOME/pico/toolchain/arm-gnu-toolchain-14.2.rel1-darwin-x86_64-arm-none-eabi
export picotool_DIR=$HOME/pico/picotool-install/picotool
cd ~/pico/pico-examples && mkdir build && cd build
cmake .. -DPICO_BOARD=pico
cd blink
make -j4
```

Resultado: ~/pico/pico-examples/build/blink/blink.uf2, de 13312 bytes, 26 bloques UF2 para RP2040 en 0x10000000. La configuración tardó 16 s y la compilación 5 s, sin avisos. CMake avisa que se salta ejemplos de RP2350 y los que necesitan Mbed TLS, que no afectan al blink. En CMakeCache.txt, CMAKE_C_COMPILER apunta al gcc de ~/pico/toolchain. No se probó en una placa.
