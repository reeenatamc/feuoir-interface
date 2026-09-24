# feuoir-interface

Una interfaz de audio USB para guitarra, hecha desde cero: la etapa analógica, la placa, el firmware y las
herramientas para medirla.

Nació de querer meterme en hardware. Programo backend, y una interfaz de audio era la excusa perfecta: es un aparato
que uso, se puede medir todo lo que hace, y obliga a aprender electrónica analógica, relojes digitales y USB en el
mismo proyecto.

No es una copia de una comercial. Está hecha alrededor de mi guitarra, una Yamaha ERG121C de pastillas HSH pasivas:
primero la grabé y la medí, y el circuito de entrada salió de esas medidas. La impedancia de entrada de 1 MΩ y la
ganancia de 1 a 11 están elegidas para lo que entrega esa guitarra, no para un caso general.

## Cómo funciona

La guitarra entra por una etapa analógica propia con un TL072 y ganancia ajustable. Un PCM1808 la digitaliza a 48 kHz
en modo maestro. Una Raspberry Pi Pico le da el reloj y manda el audio a la computadora por USB Audio Class. De
vuelta, un PCM5102A reproduce lo que llega de la computadora, en el mismo dominio de reloj.

## En qué va

Probado en placa: el reloj maestro, con 0.0 ppm de error, y la captura por USB, que la Mac ya reconoce como micrófono.
La guitarra está medida y analizada. La etapa de entrada está simulada contra la teoría y armándose en protoboard.
Faltan los módulos del ADC y del DAC, que no han llegado. El detalle parte por parte está en docs/estado.md.

## Cómo levantarlo

```
python3 -m venv .venv                                    en Windows: py -m venv .venv
.venv/bin/pip install sounddevice numpy matplotlib scipy
```

```
.venv/bin/python -m app                  la app de medición en vivo, en su propia ventana
.venv/bin/python medir.py                capturar una entrada de audio
.venv/bin/python calibrar.py             verificar el análisis con señales sintéticas
.venv/bin/python -m spice.simulate_input simular la etapa de entrada
```

En Windows el python del entorno está en `.venv/Scripts/python`. Para el firmware del Pico hace falta además el
toolchain de Arm: docs/toolchain-pico.md.

## Cómo está organizado

Todo resultado se guarda con sus condiciones en una carpeta con fecha, nunca solo en la terminal. Ninguna función de
análisis entra sin su prueba y sin una mutación que la ataque. Cada decisión queda escrita con su porqué en
docs/bitacora.md. El código va en inglés y todo lo que se lee va en español.

## Documentación

- docs/estado.md: qué está hecho, con qué se probó y qué falta
- docs/herramientas.md: qué hace cada script y qué guarda
- docs/entrada-analogica.md y docs/simulador-spice.md: la etapa analógica y cómo se simula
- docs/reloj.md, docs/dominio-de-reloj.md y docs/audio-usb.md: la parte digital
- docs/firmware.md y docs/toolchain-pico.md: el firmware del Pico
- docs/app.md: la app de medición en vivo
- docs/bitacora.md y DECISIONES.md: qué se midió, qué se decidió y por qué
