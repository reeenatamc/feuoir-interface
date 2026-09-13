# Un solo dominio de reloj para el audio

## Pregunta

Con el PCM1808 en modo maestro, ¿puede el PCM5102A usar ese mismo BCK y LRCK, con su PLL interna y sin reloj maestro propio? Si puede, toda la parte de audio queda en un solo dominio de reloj y el Pico es esclavo por los dos lados.

## Respuesta

Sí. La hoja del PCM5102A (SLAS859C) lo prevé como modo de 3 hilos, con estas condiciones:

- SCK del PCM5102A a tierra. El integrado arranca esperando un reloj en SCK. Si BCK y LRCK arrancan bien mientras SCK sigue en nivel bajo durante 16 periodos seguidos de LRCK, enciende su PLL interna y genera su reloj a partir de BCK. La PLL se apaga en cuanto aparece un SCK externo (sección 9.3.5.3).
- BCK de 32 o 64 fS. A 48 kHz la tabla 11 da 1.536 y 3.072 MHz. El PCM1808 en modo maestro saca siempre 64 BCK por trama (sección 7.3.5.1.1 de su hoja): 3.072 MHz, que es el valor de la tabla.
- El mismo formato. FMT del PCM1808 en bajo es I2S de 24 bits (tabla 3 de su hoja). FMT del PCM5102A en bajo es I2S, y acepta datos de 16, 20, 24 y 32 bits (tabla 2 y sección 9.3.2.2).
- Niveles compatibles. Las salidas del PCM1808 dan al menos 2.8 V en alto y como mucho 0.5 V en bajo, con 4 mA. Las entradas del PCM5102A con DVDD de 3.3 V piden al menos 2.31 V en alto y como mucho 0.99 V en bajo, 0.7 y 0.3 veces DVDD (sección 8.5).

Queda una duda para confirmar en el banco. El historial de revisiones de la hoja dice "Removed 48kHz sample rate with PLL-generated clock", un cambio de la versión original a la revisión A, y sin embargo la revisión vigente, la C, lista 48 kHz en la tabla 11 del modo PLL. Se toma la tabla, pero si el DAC no suena o se corta en modo de 3 hilos a 48 kHz, esa nota es lo primero que hay que revisar.

## Qué implica

- Un solo dominio de reloj. Los dos convertidores trabajan con el LRCK del PCM1808, así que captura y reproducción van exactamente a la misma fS, salga SCKI de GPOUT0 o del oscilador externo. Del lado USB queda un solo reloj que seguir.
- El Pico es esclavo por los dos lados: recibe BCK y LRCK, lee DOUT del PCM1808 y escribe DIN del PCM5102A.
- El jumper de SCKI cambia el reloj de los dos convertidores a la vez, porque el BCK que usa el DAC sale de SCKI.
- Alternativa, también de un solo dominio: llevar SCKI también al SCK del PCM5102A, en modo de 4 hilos. La tabla 10 acepta 12.288 MHz (256 fS) a 48 kHz, y la hoja pide que LRCK y el reloj del sistema estén sincronizados sin una fase fija (sección 9.3.2.1), cosa que se cumple porque BCK y LRCK salen de SCKI. La diferencia es de dónde saca el DAC su reloj interno: de su PLL a partir de BCK o directo de SCKI. Se elige el modo de 3 hilos porque no hace falta llevar 12.288 MHz hasta el DAC, que la hoja presenta como una ventaja de trazado y de interferencia (sección 9.3.5.3). El de 4 hilos queda como opción si más adelante interesa medir el jitter de la salida.

## Conexiones

```
                       jumper de SCKI
GPIO21 (GPOUT0) --------o 1
                        o 2 ----------------------------> SCKI (6)  PCM1808
salida del oscilador ---o 3

PCM1808 BCK  (8) ---+-----------------------------------> BCK  (13) PCM5102A
                    +-----------------------------------> GPIO16    Pico
PCM1808 LRCK (7) ---+-----------------------------------> LRCK (15) PCM5102A
                    +-----------------------------------> GPIO17    Pico
PCM1808 DOUT (9) ---------------------------------------> GPIO18    Pico
Pico GPIO19 --------------------------------------------> DIN  (14) PCM5102A
GND ----------------------------------------------------> SCK  (12) PCM5102A
```

Pines de configuración, con los números de pin de cada integrado:

| Integrado | Pin | Nivel | Qué hace |
|---|---|---|---|
| PCM1808 | MD1 (11) y MD0 (10) | alto los dos | modo maestro a 256 fS (tabla 2); se fijan antes de encender |
| PCM1808 | FMT (12) | bajo | I2S de 24 bits |
| PCM5102A | SCK (12) | a GND | modo de 3 hilos, con la PLL desde BCK |
| PCM5102A | FMT (16) | bajo | I2S |
| PCM5102A | FLT (11) | bajo | filtro de latencia normal |
| PCM5102A | DEMP (10) | bajo | sin de-énfasis |
| PCM5102A | XSMT (17) | alto | sin silencio |

Los GPIO del Pico para BCK, LRCK, DOUT y DIN, del 16 al 19, son una propuesta y se pueden mover a otros libres. GPIO20 y GPIO21 ya están tomados por la verificación del reloj y por GPOUT0. Del módulo del PCM1808 todavía no hay datos: cómo expone MD0, MD1 y FMT se ve cuando llegue.

### Módulo del PCM5102A

No hay hoja oficial del módulo morado. Lo que sigue sale de páginas de la comunidad consultadas el 2026-09-13 y hay que confirmarlo con el módulo en la mano.

- Conector principal: VIN, GND, LCK (el LRCK), DIN, BCK y SCK [1][2].
- Puentes de soldadura atrás, con una almohadilla H y una L cada uno: H1L es FLT, H2L es DEMP, H3L es XSMT y H4L es FMT [3]. La configuración que corresponde a la tabla de arriba es 1L, 2L, 3H y 4L, la misma que recomiendan [1][3][4][5].
- SCK a tierra: el método que se reporta es cerrar con estaño el puente que está al lado del pin SCK [2][7]. Hay reportes de módulos que suenan sin cerrarlo [7] y de otros donde fue obligatorio [8]; la hoja pide SCK en nivel bajo y con SCK flotando no hay garantía.
- El estado de fábrica de los puentes cambia entre vendedores, y en alguna variante también la orientación de los rótulos [1][5][6]. Antes de alimentarlo, con el multímetro en continuidad: cada puente cerrado del lado L tiene que llevar su pin a GND, cada uno del lado H a 3.3 V, y SCK tiene que quedar a GND. Un pin con el puente cerrado no se maneja desde el Pico.
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

- Confirmar que el PCM5102A arranca la PLL a 48 kHz en modo de 3 hilos, por la nota del historial de revisiones.
- Revisar los puentes del módulo con el multímetro antes de alimentarlo.
- Confirmar el margen de DIN con el programa del PIO. Sin osciloscopio, un error de temporización en DIN aparece como distorsión o ruido al reproducir un tono y medirlo con analizador.py.
