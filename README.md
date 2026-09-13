# feuoir-interface

Interfaz de audio propia. Antes de diseñar la parte analógica hay que conocer la señal que va a recibir: cuánto voltaje entrega la guitarra, hasta qué frecuencia tiene energía y cuánto ruido trae. Este repo empieza por la herramienta para medir eso.

## Qué mide medir.py

Graba 5 segundos de una entrada de audio a 48 kHz y calcula el pico y el RMS de la señal. Cada corrida guarda el audio, una gráfica con la forma de onda y el espectro en dBFS, y las condiciones en que se hizo:

```
.venv/bin/python medir.py piso-de-ruido --notas "ventana cerrada"
```

```
mediciones/2026-09-13-piso-de-ruido/
  captura.wav
  captura.png
  condiciones.json
```

condiciones.json registra fecha y hora, dispositivo (nombre e índice según sounddevice), frecuencia de muestreo, duración, volumen de entrada del sistema, pico y RMS en dBFS, y notas. Si la etiqueta se repite el mismo día, la carpeta nueva termina en -2, -3, etc.

El dispositivo se elige con DISPOSITIVO dentro de medir.py. dispositivos.py lista las entradas con su número.

El pico, el RMS y el espectro salen de analizador.py, el mismo código que verifica calibrar.py.

Instalación:

```
python3 -m venv .venv
.venv/bin/pip install sounddevice numpy matplotlib scipy
```

## Los valores son dBFS

Pico y RMS están en dBFS, decibeles relativos al fondo de escala del conversor, donde 0 dBFS es la muestra más grande que se puede representar. No son niveles absolutos de presión sonora (dB SPL) ni voltajes. El mismo sonido da otro número con otro dispositivo u otro volumen de entrada, y para pasar a voltios hace falta calibrar la entrada con una señal conocida. El RMS se calcula contra 1.0, así que una senoidal a fondo de escala da -3 dBFS.

## Volumen de entrada

El volumen de entrada del sistema está en 71 y no se toca. Si cambia, las mediciones dejan de ser comparables entre sí. Cada condiciones.json guarda el valor que tenía en esa corrida.

## analizador.py

El análisis y las señales de prueba. medir.py lo importa y calibrar.py lo verifica.

- pico_dbfs y rms_dbfs: niveles en dBFS.
- espectro, resolucion_hz y picos_espectrales: espectro de amplitud en dBFS con ventana Hann. Una senoidal de amplitud A que cae en un bin da 20·log10(A).
- ajuste_seno: amplitud, fase, continua y frecuencia de una senoidal por mínimos cuadrados (IEEE 1057, 4 parámetros).
- thd_n: THD+N relativo a la fundamental, limitado por defecto a la banda de 20 Hz a 20 kHz. Un armónico con el 1 % de la amplitud de la fundamental da 1.000 %.
- snr_db: relación señal a ruido con dos capturas, una con el tono de prueba en la entrada y otra sin señal.
- respuesta_en_frecuencia: nivel, ganancia y fase de cada tono de un barrido escalonado, relativos a la captura de entrada del circuito.
- tono, barrido_log, frecuencias_log y barrido_escalonado: señales para excitar el circuito cuando exista.

## calibrar.py

Antes de confiar en lo que mide medir.py hay que saber que el análisis está bien. calibrar.py pasa por analizador.py señales sintéticas con resultado conocido y compara:

- senoidal de amplitud A: pico 20·log10(A) y RMS 20·log10(A/√2), también con el pico en la excursión negativa
- senoidal con un armónico al 1 %: THD+N de 1.000 %
- THD+N en una banda angosta alrededor del tono: ve las bandas laterales cercanas y deja afuera lo que está lejos, que es como se mide el ruido cerca de un tono
- ruido blanco gaussiano y uniforme de varianza conocida: RMS
- dos tonos separados 2 Hz: un solo pico con 0.1 s de captura (resolución de 10 Hz) y dos picos con 2 s (resolución de 0.5 Hz)
- ajuste de senoidal, SNR, THD+N con ruido, generadores de tono y barrido, y respuesta en frecuencia de un filtro Butterworth cuya respuesta exacta se conoce

```
.venv/bin/python calibrar.py
```

Cada corrida guarda en calibraciones/<fecha>-calibracion/resultados.json todos los chequeos con sus condiciones, lo esperado, lo obtenido y la tolerancia, junto con las versiones de Python, numpy y scipy y el sha256 de analizador.py. Si un chequeo se sale de tolerancia, el script lo muestra y termina con código 1. Las funciones test_ también corren con pytest.

Ninguna función entra a analizador.py sin su prueba en calibrar.py.

### Errores inyectados

tests/mutaciones.py comprueba que calibrar.py sigue atrapando errores. Copia analizador.py a una carpeta temporal, le inyecta 16 errores, uno a la vez (RMS sin raíz, pico sin valor absoluto, fase con el signo invertido, entre otros), y corre calibrar.py sobre cada copia: todas tienen que fallar. Antes corre una copia sin cambios como control, que tiene que pasar.

```
.venv/bin/python tests/mutaciones.py
```

Guarda el resultado en calibraciones/<fecha>-mutaciones/resultados.json y termina con código 1 si algún error pasa sin detectarse o si el control falla. También falla si se cambia analizador.py y el texto que reemplaza una mutación deja de existir; en ese caso hay que actualizar la mutación para que siga inyectando el mismo error. Hay que correrlo cada vez que se toque analizador.py o calibrar.py.

## relojes.py

El PCM1808 necesita 12.288 MHz en SCKI y el cristal del Pico es de 12 MHz. relojes.py recorre todas las configuraciones del PLL del RP2040 y, para cada una, el divisor que haría falta en la salida de reloj GPOUT0 y en una máquina de estados del PIO, y se queda con las que dan esa frecuencia exacta. La lista completa va a docs/reloj-soluciones.csv. En docs/reloj.md solo reescribe el bloque entre las marcas de inicio y fin; la solución elegida, el respaldo y la verificación se escriben a mano.

```
.venv/bin/python relojes.py
```

## firmware

firmware/ configura el reloj maestro: clk_sys en 61.44 MHz y 12.288 MHz por GPIO21 (GPOUT0) con DC50. Además hace parpadear el LED para mostrar que sigue corriendo. Se compila con las mismas variables de entorno que el blink (ver Toolchain del Pico):

```
cd firmware
cmake -S . -B build
make -C build -j4
```

El resultado es firmware/build/feuoir.uf2. No se probó en una placa.

## Documentación

- docs/reloj.md: reloj maestro elegido, respaldo, corrección sobre el divisor fraccionario y cómo verificar la frecuencia sin osciloscopio
- docs/bitacora.md: qué se midió en cada fase, en qué condiciones, qué se decidió y por qué
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
