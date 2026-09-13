# Un solo dominio de reloj para el audio

## Pregunta

Con el PCM1808 en modo maestro, ¿puede el PCM5102A usar ese mismo BCK y LRCK, con su PLL interna y sin reloj maestro propio? Si puede, toda la parte de audio queda en un solo dominio de reloj y el Pico es esclavo por los dos lados.

## Respuesta

Sí. La hoja del PCM5102A (SLAS859C) lo prevé como modo de 3 hilos, con estas condiciones:

- SCK del PCM5102A a tierra. El integrado arranca esperando un reloj en SCK. Si BCK y LRCK arrancan bien mientras SCK sigue en nivel bajo durante 16 periodos seguidos de LRCK, enciende su PLL interna y genera su reloj a partir de BCK. La PLL se apaga en cuanto aparece un SCK externo (sección 9.3.5.3).
- BCK de 32 o 64 fS. A 48 kHz la tabla 11 da 1.536 y 3.072 MHz. El PCM1808 en modo maestro saca siempre 64 BCK por trama (sección 7.3.5.1.1 de su hoja): 3.072 MHz, que es el valor de la tabla.
- El mismo formato. FMT del PCM1808 en bajo es I2S de 24 bits (tabla 3 de su hoja). FMT del PCM5102A en bajo es I2S, y acepta datos de 16, 20, 24 y 32 bits (tabla 2 y sección 9.3.2.2).
- Niveles compatibles. Las salidas del PCM1808 dan al menos 2.8 V en alto y como mucho 0.5 V en bajo, con 4 mA. Las entradas del PCM5102A con DVDD de 3.3 V piden al menos 2.31 V en alto y como mucho 0.99 V en bajo, 0.7 y 0.3 veces DVDD (sección 8.5).

El historial de revisiones de la hoja dice "Removed 48kHz sample rate with PLL-generated clock", un cambio de la versión original a la revisión A, y sin embargo la revisión vigente, la C, lista 48 kHz en la tabla 11 del modo PLL. Esa duda no se resuelve leyendo sino por diseño: el SCK del PCM5102A tiene su propio jumper y puede recibir el mismo reloj maestro que el ADC.

## Dos configuraciones del DAC con un jumper

El nodo de SCKI, que es la salida del jumper que elige entre GPOUT0 y el oscilador externo, llega también al SCK del PCM5102A a través de un jumper de 3 pines:

- SCK a GND: modo de 3 hilos. El DAC usa su PLL a partir de BCK.
- SCK en el nodo de SCKI: modo de 4 hilos. El DAC usa el mismo reloj maestro que el ADC.

Con cualquiera de las dos posiciones el audio queda en un solo dominio de reloj. La de 4 hilos sigue siendo sincrónica porque BCK y LRCK salen de SCKI, y la hoja solo pide que LRCK y el reloj del sistema estén sincronizados, sin una fase fija (sección 9.3.2.1). Lo que cambia es de dónde saca el DAC su reloj interno: de su PLL o directo de SCKI.

Por qué SCK aguanta ese reloj:

- La tabla 10 acepta 12.288 MHz, 256 fS, a 48 kHz.
- La sección 8.6 pide un ciclo de 20 a 1000 ns y pulsos alto y bajo de al menos 9 ns con DVDD de 3.3 V. 12.288 MHz son 81.4 ns de ciclo; con DC50 cada pulso dura unos 40.7 ns, y sin DC50, en el peor caso de 40 %, 32.6 ns.
- La PLL se apaga en cuanto aparece un SCK externo (sección 9.3.5.3), así que el jumper decide el modo sin tocar nada más.

Condiciones:

- El jumper de SCK se cambia con la placa sin alimentación, igual que el de SCKI.
- En el módulo del PCM5102A, el puente de soldadura que lleva SCK a GND queda abierto. Si estuviera cerrado, la posición de 4 hilos pondría la salida del reloj maestro en cortocircuito a tierra. La conexión a GND la hace el jumper.
- El nodo de SCKI ahora llega a dos entradas: las pistas de SCKI hasta los dos integrados, lo más cortas posible.

Para el primer encendido del DAC conviene la posición de 4 hilos, que no depende de la nota del historial de revisiones. La de 3 hilos queda para probar la PLL después y, si interesa, comparar el jitter de la salida entre las dos.

## Qué implica

- Captura y reproducción van exactamente a la misma fS, salga SCKI de GPOUT0 o del oscilador externo. Del lado USB queda un solo reloj que seguir (docs/audio-usb.md).
- El Pico es esclavo por los dos lados: recibe BCK y LRCK, lee DOUT del PCM1808 y escribe DIN del PCM5102A.
- El jumper de SCKI cambia el reloj de los dos convertidores a la vez: en 3 hilos a través de BCK y en 4 hilos también por SCK.

## Conexiones

```
                        jumper de SCKI
GPIO21 (GPOUT0) --------o 1
                        o 2 ---+------------------------> SCKI (6)  PCM1808
salida del oscilador ---o 3    |
                               |     jumper de SCK
                               +-----o 1
                                     o 2 ---------------> SCK  (12) PCM5102A
                        GND ---------o 3

PCM1808 BCK  (8) ---+-----------------------------------> BCK  (13) PCM5102A
                    +-----------------------------------> GPIO16    Pico
PCM1808 LRCK (7) ---+-----------------------------------> LRCK (15) PCM5102A
                    +-----------------------------------> GPIO17    Pico
PCM1808 DOUT (9) ---------------------------------------> GPIO18    Pico
Pico GPIO19 --------------------------------------------> DIN  (14) PCM5102A
```

Jumper de SCKI: 1-2 es GPOUT0, 2-3 es el oscilador externo. Jumper de SCK: 1-2 es 4 hilos, 2-3 es 3 hilos.

Pines de configuración, con los números de pin de cada integrado:

| Integrado | Pin | Nivel | Qué hace |
|---|---|---|---|
| PCM1808 | MD1 (11) y MD0 (10) | alto los dos | modo maestro a 256 fS (tabla 2); se fijan antes de encender |
| PCM1808 | FMT (12) | bajo | I2S de 24 bits |
| PCM5102A | SCK (12) | jumper de SCK | a GND, 3 hilos con la PLL desde BCK; en SCKI, 4 hilos |
| PCM5102A | FMT (16) | bajo | I2S |
| PCM5102A | FLT (11) | bajo | filtro de latencia normal |
| PCM5102A | DEMP (10) | bajo | sin de-énfasis |
| PCM5102A | XSMT (17) | alto | sin silencio |

Los GPIO del Pico para BCK, LRCK, DOUT y DIN, del 16 al 19, son una propuesta y se pueden mover a otros libres. GPIO20 y GPIO21 ya están tomados por la verificación del reloj y por GPOUT0. Del módulo del PCM1808 todavía no hay datos: cómo expone MD0, MD1 y FMT se ve cuando llegue.

### Módulo del PCM5102A

No hay hoja oficial del módulo morado. Lo que sigue sale de páginas de la comunidad consultadas el 2026-09-13 y hay que confirmarlo con el módulo en la mano.

- Conector principal: VIN, GND, LCK (el LRCK), DIN, BCK y SCK [1][2].
- Puentes de soldadura atrás, con una almohadilla H y una L cada uno: H1L es FLT, H2L es DEMP, H3L es XSMT y H4L es FMT [3]. La configuración que corresponde a la tabla de arriba es 1L, 2L, 3H y 4L, la misma que recomiendan [1][3][4][5].
- SCK: el módulo tiene un puente al lado del pin SCK para llevarlo a GND [2][7]. Con el jumper de SCK ese puente queda abierto, como se explica arriba.
- El estado de fábrica de los puentes cambia entre vendedores, y en alguna variante también la orientación de los rótulos [1][5][6]. Antes de alimentarlo, con el multímetro en continuidad: cada puente cerrado del lado L tiene que llevar su pin a GND, cada uno del lado H a 3.3 V, y el puente de SCK tiene que estar abierto. Un pin con el puente cerrado no se maneja desde el Pico.
- Alimentación por VIN: hay reportes con 5 V a través de un regulador del módulo y otros con 3.3 V [2][7][8]. Se decide mirando el regulador del módulo que llegue.

Referencias:

1. https://github.com/dwhinham/mt32-pi/wiki/GY-PCM5102-DAC-module
2. https://todbot.com/blog/2023/05/16/cheap-stereo-line-out-i2s-dac-for-circuitpython-arduino-synths/
3. https://github.com/pschatzmann/arduino-audio-tools/wiki/External-DAC
4. https://github.com/pschatzmann/arduino-audio-tools/issues/773
5. https://github.com/probonopd/MiniDexed/discussions/521
6. https://github.com/pschatzmann/arduino-audio-tools/discussions/1641
7. https://macsbug.wordpress.com/2021/02/19/web-radio-of-m5stack-pcm5102a-i2s-dac/
8. https://github.com/sle118/squeezelite-esp32/discussions/186

## Temporización del Pico como esclavo

- A 48 kHz con 64 BCK por trama, cada periodo de BCK dura 325.5 ns.
- Captura. El PCM1808 cambia LRCK y DOUT entre -10 y 20 ns después del flanco de bajada de BCK (temporización en modo maestro de su hoja). Si el Pico lee DOUT en el flanco de subida, queda un margen cercano a 140 ns.
- Reproducción. El PCM5102A toma DIN en el flanco de subida de BCK (sección 9.3.2.1), y su hoja no da tiempos de setup ni de hold para DIN, LRCK o BCK. El Pico tiene que cambiar DIN poco después del flanco de bajada, como hace el PCM1808 con DOUT. Cada entrada del PIO pasa por un sincronizador de dos flip-flops que agrega dos ciclos de latencia, y hay una etapa de registro a la entrada y otra a la salida de cada máquina de estados (hoja del RP2040, secciones 3.5.6.1 y 3.5.6.3). Con clk_sys de 61.44 MHz, 16.3 ns por ciclo, DIN cambiaría unos 4 o 5 ciclos después del flanco de bajada, de 65 a 80 ns, y quedarían unos 80 ns hasta el flanco de subida. Es una estimación que se confirma cuando exista el programa del PIO.

## Pendiente para el banco

- Revisar los puentes del módulo con el multímetro antes de alimentarlo, con el de SCK abierto.
- Encender el DAC primero en 4 hilos. Después probar 3 hilos: si a 48 kHz no suena o se corta, la nota del historial de revisiones tenía razón y se queda en 4 hilos.
- Confirmar el margen de DIN con el programa del PIO. Sin osciloscopio, un error de temporización en DIN aparece como distorsión o ruido al reproducir un tono y medirlo con analizador.py.
