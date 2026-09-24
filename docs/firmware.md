# Firmware

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

