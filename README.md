# feuoir-interface

Interfaz de audio USB propia, para guitarra. Una Raspberry Pi Pico (RP2040) toma el audio de un ADC PCM1808 y lo manda a la Mac por USB, y recibe audio de la Mac para un DAC PCM5102A. Antes de diseñar la parte analógica hay que conocer la señal que va a recibir: cuánto voltaje entrega la guitarra, hasta qué frecuencia tiene energía y cuánto ruido trae. El repo empieza por las herramientas para medir eso y por el diseño de la parte digital, verificado sin hardware.

Las mediciones se hacen en dos máquinas: la Mac, donde empezó el repo, y una laptop ASUS con Windows, con una tarjeta de sonido USB externa. Las dos usan los mismos scripts, y cada medición guarda el sistema operativo, la API de audio y el nivel de entrada, que es lo que hace falta para poder compararlas (docs/configuracion-windows.md).

## Cómo está armado

- El PCM1808 trabaja en modo maestro: genera BCK y LRCK a 48 kHz a partir de su reloj maestro SCKI, de 12.288 MHz.
- SCKI sale del Pico por GPOUT0 (GPIO21), con clk_sys en 61.44 MHz y divisor entero 5. Un jumper permite tomarlo de un oscilador de cristal externo, para comparar el jitter de los dos (docs/reloj.md).
- El PCM5102A usa el mismo BCK y LRCK. Otro jumper pone su SCK a tierra, y el DAC usa su PLL, o en el mismo SCKI. Así todo el audio queda en un solo dominio de reloj y el Pico es esclavo por los dos lados (docs/dominio-de-reloj.md).
- Hacia la Mac, USB Audio Class en modo asíncrono: la captura lleva el ritmo del PCM1808 y la reproducción necesita realimentación (docs/audio-usb.md).

## Estado

Al 2026-09-19 el Pico está probado en placa y la guitarra está medida y analizada. Falta lo que necesita los módulos
del ADC y del DAC, que no han llegado. La tabla parte por parte, con qué se probó cada una y qué queda sin probar,
está en docs/estado.md.

## Estructura

```
medir.py               captura de una entrada de audio, en la Mac o en Windows
analizador.py          análisis y señales de prueba
guitar_report.py       análisis de las tomas de guitarra: zumbido de la red, espectro, caída y nota
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
- El nivel de entrada se anota una vez y no se toca (docs/herramientas.md).


## Cómo se corre

```
python3 -m venv .venv                                              en Windows: py -m venv .venv
.venv/bin/pip install sounddevice numpy matplotlib scipy

.venv/bin/python medir.py                                          capturar una entrada de audio
.venv/bin/python calibrar.py                                       verificar el análisis
.venv/bin/python -m app                                            la app de medición en vivo
.venv/bin/python -m spice.verify                                   verificar el simulador
.venv/bin/python -m spice.simulate_input                           simular la etapa de entrada
```

En Windows el python del entorno está en `.venv/Scripts/python`. Qué hace cada script y qué guarda:
docs/herramientas.md.

## Documentación

- docs/estado.md: qué parte está hecha, con qué se probó y qué falta
- docs/herramientas.md: medir.py, analizador.py, guitar_report.py, calibrar.py, relojes.py, jitter.py y la app
- docs/bitacora.md: qué se midió en cada etapa, en qué condiciones, qué se decidió y por qué
- docs/reloj.md: reloj maestro elegido, respaldo y cómo verificar la frecuencia sin osciloscopio
- docs/dominio-de-reloj.md: un solo dominio de reloj, con el diagrama de conexiones
- docs/audio-usb.md: cómo resuelve USB Audio Class que el reloj de audio no coincida con el de la Mac
- docs/entrada-analogica.md: la etapa analógica de entrada, cómo se simula y qué efectos hay que conocer
- docs/simulador-spice.md: por qué ngspice, cómo se instala sin Homebrew y cómo se corre
- docs/armado/: los dibujos del armado, paso a paso, y el mapa de la protoboard
- docs/aprender-electronica.md: qué estudiar y en qué orden para entender el circuito
- docs/compras.md: lo que pide el diseño
- docs/primer-encendido.md: lista paso a paso para el primer encendido
- docs/configuracion-windows.md: cómo dejar Windows sin tocar la señal antes de medir
- docs/app.md, docs/app-cascara.md, docs/app-ideas.md: la app de medición en vivo
- docs/firmware.md y docs/toolchain-pico.md: el firmware del Pico y cómo compilarlo
- docs/datasheets/: hojas de datos del PCM1808, el PCM5102A, el TL072 y el RP2040
- DECISIONES.md: decisiones de hardware y de método
