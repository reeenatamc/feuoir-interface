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

## Resistencias en serie

Como el diseño se reconfigura con jumpers, un error de armado puede poner una salida contra tierra, contra 3.3 V o contra otra salida. El puente de SCK cerrado con el jumper en 4 hilos es el ejemplo: no es un error de configuración, es una salida del RP2040 quemada. Por eso cada línea digital que cruza entre el Pico y los módulos lleva una resistencia en serie, pegada al pin que maneja la línea.

### Restricción 1: corriente con el destino en corto

En el peor caso la salida es ideal y toda la tensión cae en la resistencia: I = 3.3 V / R. Los límites que dan las hojas:

- RP2040: especifica sus salidas hasta 12 mA, la mayor de sus corrientes de salida (2, 4, 8 o 12 mA, tabla 625). No da un máximo absoluto por pin. La suma de todo lo que entregan o reciben sus GPIO no puede pasar de 50 mA.
- PCM1808: máximo absoluto de ±10 mA en cualquier pin que no sea de alimentación (sección 6.1).

Para las líneas que maneja el RP2040, R ≥ 3.3 V / 12 mA = 275 Ω. Para las que maneja el PCM1808, R ≥ 3.3 V / 10 mA = 330 Ω, y se busca quedar lejos del máximo absoluto.

### Restricción 2: flancos a 12.288 MHz

Ninguna de las tres hojas da la capacitancia de entrada de sus pines. Se usa como carga de referencia la de la hoja del PCM1808, 20 pF, que es la carga máxima con la que especifica sus salidas y mide sus tiempos, y se calcula hasta qué capacitancia sigue valiendo cada valor. Los cables y la protoboard suman a esa cuenta.

La resistencia y la capacitancia forman un filtro RC. SCKI del PCM1808 cambia de nivel a 2.0 V al subir y a 0.8 V al bajar (sección 6.3). Una subida de 0 a 3.3 V llega a 2.0 V en RC·ln(3.3/1.3) = 0.93·RC, y una bajada llega a 0.8 V en RC·ln(3.3/0.8) = 1.42·RC. El nivel alto que ve el integrado dura 0.49·RC más que el que sale del Pico, y el ciclo de trabajo se corre en 0.49·RC / 81.4 ns.

Criterio: que ese corrimiento no pase de 5 puntos, la mitad del margen de 10 puntos que deja DC50 frente al 40 % a 60 % del PCM1808, y que la señal alcance a asentarse en medio periodo. 5 puntos son 4.07 ns, así que RC ≤ 8.4 ns; asentarse al 95 % en 40.7 ns pide RC ≤ 13.6 ns. Manda la primera. Con 20 pF, R ≤ 8.4 ns / 20 pF = 419 Ω.

El SCK del PCM5102A, en 4 hilos, tiene umbrales simétricos (0.7 y 0.3 veces DVDD): el RC retrasa igual las dos transiciones y no corre el ciclo de trabajo.

### Valores elegidos

| Línea | Maneja | Resistencia | Corriente con el destino en corto | Con 20 pF |
|---|---|---|---|---|
| Reloj maestro desde GPOUT0 (R1) | RP2040, GPIO21 | 330 Ω | 10.0 mA | RC de 6.6 ns, ciclo de trabajo corrido 3.9 puntos |
| Reloj maestro desde el oscilador (R2) | oscilador externo | 330 Ω | 10.0 mA | igual que R1 |
| BCK (R3) | PCM1808 | 470 Ω | 7.0 mA | RC de 9.4 ns, BCK corrido 1.4 puntos |
| LRCK (R4) | PCM1808 | 470 Ω | 7.0 mA | irrelevante a 48 kHz |
| DOUT (R5) | PCM1808 | 470 Ω | 7.0 mA | ver márgenes |
| DIN (R6) | RP2040, GPIO19 | 470 Ω | 7.0 mA | ver márgenes |

- Reloj maestro, 330 Ω: queda entre 275 Ω, por corriente, y 419 Ω, por flancos. El corrimiento de 3.9 puntos deja el ciclo de trabajo en 54 % con DC50. Con 330 Ω la restricción de flancos se cumple mientras el nodo sume como mucho 25 pF: los cables del nodo de SCKI tienen que ser cortos. En 4 hilos ese nodo llega a dos entradas, así que es la línea donde más importa.
- R2 limita la corriente a 10 mA, pero el oscilador no está elegido: su hoja tiene que aceptar al menos esa corriente de salida, y si no, se sube R2.
- BCK, LRCK, DOUT y DIN, 470 Ω: 7 mA, lejos de los ±10 mA del PCM1808 y de los 12 mA del RP2040. Van a 3.072 MHz como mucho, con periodos de 325.5 ns, así que admiten más resistencia. Con 470 Ω, el corrimiento de BCK no pasa de 5 puntos hasta 71 pF.
- Márgenes de datos, con 20 pF. DOUT llega válido al Pico unos 29 ns después del flanco de bajada de BCK (los 20 ns de la hoja del PCM1808 más 0.93·RC), y el Pico lo lee 163 ns después: quedan unos 134 ns. DIN cambia unos 80 ns después del flanco de bajada según la estimación del PIO, más 1.20·RC para cruzar el umbral del PCM5102A, unos 91 ns en total: quedan unos 72 ns hasta el flanco de subida.
- Suma en el RP2040 con todo en falla a la vez: 10 mA en GPIO21, 7 mA en GPIO19 y 7 mA en cada una de GPIO16, GPIO17 y GPIO18 si por error quedaran como salidas contra el PCM1808. Son 38 mA, debajo de los 50 mA de la tabla 625.
- Potencia en un corto franco: 3.3² / 330 = 33 mW. Resistencias de 1/4 W alcanzan.

Dónde no hace falta resistencia propia: en la rama de SCK del DAC y en las entradas GPIO16, GPIO17 y GPIO18. Cualquier camino desde una salida hasta una falla pasa por la resistencia de esa salida. Los puentes de verificación hacia GPIO20 salen siempre del lado de la resistencia que no toca el pin.

## Qué implica

- Captura y reproducción van exactamente a la misma fS, salga SCKI de GPOUT0 o del oscilador externo. Del lado USB queda un solo reloj que seguir (docs/audio-usb.md).
- El Pico es esclavo por los dos lados: recibe BCK y LRCK, lee DOUT del PCM1808 y escribe DIN del PCM5102A.
- El jumper de SCKI cambia el reloj de los dos convertidores a la vez: en 3 hilos a través de BCK y en 4 hilos también por SCK.

## Conexiones

```
                          jumper de SCKI
GPIO21 (GPOUT0) --[R1]---o 1
                         o 2 ----+----------------------------> SCKI (6)  PCM1808
salida oscilador --[R2]--o 3     |
                                 |     jumper de SCK
                                 +-----o 1
                                       o 2 --------------------> SCK  (12) PCM5102A
                          GND ---------o 3

PCM1808 BCK  (8) --[R3]---+------------------------------------> BCK  (13) PCM5102A
                          +------------------------------------> GPIO16    Pico
PCM1808 LRCK (7) --[R4]---+------------------------------------> LRCK (15) PCM5102A
                          +------------------------------------> GPIO17    Pico
PCM1808 DOUT (9) --[R5]----------------------------------------> GPIO18    Pico
Pico GPIO19 -------[R6]----------------------------------------> DIN  (14) PCM5102A
```

- R1 y R2: 330 Ω. R3 a R6: 470 Ω. Cada una va pegada al pin que maneja la línea.
- Jumper de SCKI: 1-2 es GPOUT0, 2-3 es el oscilador externo. Jumper de SCK: 1-2 es 4 hilos, 2-3 es 3 hilos.
- Puente de verificación a GPIO20: desde el extremo de R1 que no toca GPIO21, o de R2, R3 o R4 en las pruebas de docs/primer-encendido.md.

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
- Captura. El PCM1808 cambia LRCK y DOUT entre -10 y 20 ns después del flanco de bajada de BCK (temporización en modo maestro de su hoja). Si el Pico lee DOUT en el flanco de subida, queda un margen cercano a 140 ns, unos 134 ns con R5 y 20 pF.
- Reproducción. El PCM5102A toma DIN en el flanco de subida de BCK (sección 9.3.2.1), y su hoja no da tiempos de setup ni de hold para DIN, LRCK o BCK. El Pico tiene que cambiar DIN poco después del flanco de bajada, como hace el PCM1808 con DOUT. Cada entrada del PIO pasa por un sincronizador de dos flip-flops que agrega dos ciclos de latencia, y hay una etapa de registro a la entrada y otra a la salida de cada máquina de estados (hoja del RP2040, secciones 3.5.6.1 y 3.5.6.3). Con clk_sys de 61.44 MHz, 16.3 ns por ciclo, DIN cambiaría unos 4 o 5 ciclos después del flanco de bajada, de 65 a 80 ns, y quedarían unos 80 ns hasta el flanco de subida, unos 72 ns con R6 y 20 pF. Es una estimación que se confirma cuando exista el programa del PIO.

## Pendiente para el banco

- Seguir docs/primer-encendido.md.
- Encender el DAC primero en 4 hilos. Después probar 3 hilos: si a 48 kHz no suena o se corta, la nota del historial de revisiones tenía razón y se queda en 4 hilos.
- Confirmar el margen de DIN con el programa del PIO. Sin osciloscopio, un error de temporización en DIN aparece como distorsión o ruido al reproducir un tono y medirlo con analizador.py.
