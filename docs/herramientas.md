# Las herramientas de medición y análisis

Qué hace cada script, qué guarda y cómo se corre.

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
- crest_factor_db: pico menos RMS. Un seno da 3.01 dB.
- averaged_spectrum: espectro promediado de Welch, en la misma escala que espectro, con menos varianza en capturas con ruido.
- rolloff_points: la frecuencia más alta que sigue a menos de 20, 40 o 60 dB del máximo del espectro. Con el espectro del piso marca los puntos que el piso no deja ver.
- remove_mains: ajusta el zumbido de la red, 60 Hz y 40 armónicos, por mínimos cuadrados en el tiempo y lo resta. Busca la frecuencia real de la red en ±0.3 Hz.
- fundamental: la fundamental de una nota por producto armónico, con una corrección de octava para cuando la fundamental es mucho más débil que el segundo armónico.
- note_name: la nota más cercana a una frecuencia, en solfeo y en inglés, con el desvío en cents.

## guitar_report.py

Analiza las tomas de guitarra del 2026-09-19 y guarda el resultado en mediciones/<fecha>-analisis-guitarra/:

```
.venv/bin/python guitar_report.py
```

Por toma: pico, RMS y factor de cresta; el zumbido de la red y lo que queda sin él; el espectro promediado sin la red, con sus puntos de -20, -40 y -60 dB contra el piso de la tarjeta; y, en las tomas de una sola cuerda, la fundamental y la nota. Compara además la tarjeta sola con la guitarra conectada en volumen 0, a batería y con cargador. La lista de tomas y lo que se tocó en cada una está en el script. Los .wav no se versionan, así que corre en la Mac donde se grabaron.

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

tests/mutaciones.py comprueba que calibrar.py sigue atrapando errores. Copia analizador.py a una carpeta temporal, le inyecta 27 errores, uno a la vez (RMS sin raíz, pico sin valor absoluto, fase con el signo invertido, entre otros), y corre calibrar.py sobre cada copia: todas tienen que fallar. Antes corre una copia sin cambios como control, que tiene que pasar.

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
