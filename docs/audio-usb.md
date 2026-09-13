# Audio USB con un reloj propio

Arquitectura y opciones para llevar el audio entre el Pico y la Mac con USB Audio Class. No hay firmware todavía.

## El problema

El PCM1808 en modo maestro marca el ritmo de las muestras con SCKI, que sale del cristal del Pico por GPOUT0 o del oscilador externo. La Mac cuenta el tiempo con su propio reloj, el del bus USB, que en velocidad completa manda un inicio de trama (SOF) por milisegundo. Esos dos relojes nunca coinciden exacto. Una diferencia de 50 ppm, por ejemplo, son 2.4 muestras por segundo a 48 kHz, unas 8640 por hora. Sin un mecanismo que lo compense, el búfer se vacía o se desborda.

La deriva no la crea el modo maestro: existiría igual con el Pico como maestro, generando BCK y LRCK desde su cristal, porque ese cristal tampoco es el reloj de la Mac. Lo que el modo maestro descarta es atar el reloj de audio al del bus, algo que con el PLL del RP2040, de divisores enteros, tampoco se podría ajustar de a poco.

Queda el modo asíncrono: el dispositivo usa su propio reloj y le informa a la Mac su ritmo. TN3190 de Apple distingue los endpoints síncronos, que tienen que atar su reloj de audio al SOF, de los asíncronos, cuyo flujo va con el reloj del dispositivo.

## Captura: endpoint IN asíncrono

- Un endpoint de datos asíncrono que manda audio lleva su ritmo implícito en la cantidad de muestras de cada paquete (USB 2.0, sección 5.12.4.1.1). La Mac se adapta.
- No hace falta endpoint de realimentación. El Pico manda en cada paquete lo que el PCM1808 fue entregando: casi siempre 48 muestras, y 47 o 49 cuando su reloj va un poco más lento o más rápido que el de la Mac.
- Tamaño: 49 muestras por 2 canales por 3 bytes son 294 bytes, dentro de los 1023 bytes por milisegundo de un dispositivo de velocidad completa (TN3190).

## El margen sale del diseño, no de la tolerancia del host

TN3190 pide, a 48 kHz, entre 47 y 49 muestras por milisegundo, y remite a la especificación de formatos de audio de UAC2 (sección 2.3.1.1). La de UAC1 (sección 2.2.1) dice lo mismo: cuando el promedio de muestras por paquete es entero, como 48, cada paquete puede llevar una menos, las mismas o una más. Confirmado: no es una tolerancia propia de macOS, es la del estándar.

Aun así, la arquitectura no se apoya en ese número. Si el firmware funciona porque el host tolera justo eso, se rompe con otro host. El margen tiene que salir del diseño:

1. La diferencia entre relojes es chica frente a lo que corrige una muestra. Un paquete con una muestra de más o de menos corrige 1/48, un 2 %. Con 50 ppm de diferencia entre cristales hace falta un ajuste cada 417 ms, uno cada unos 400 paquetes; aun con 1000 ppm sería uno cada 21 ms. Casi todos los paquetes llevan 48 y el ajuste de una muestra es la excepción.
2. Nunca más de una muestra de diferencia con el nominal, y no seguido. TinyUSB 0.18.0 lo hace así: elige entre 47, 48 y 49 según el nivel de su FIFO respecto de la mitad y deja pasar 10 paquetes antes de otro ajuste (audio_device.c, audiod_tx_packet_size).
3. Una FIFO con holgura, regulada a la mitad. TinyUSB pide al menos cuatro veces el tamaño nominal del paquete para que funcione el control de flujo, 4 ms de audio a 48 kHz; el tamaño definitivo se decide midiendo.
4. Arrancar con la FIFO a medio llenar antes del primer paquete, para no depender de que el host acepte ráfagas al inicio.
5. Medir el margen en vez de suponerlo. En cada sesión de captura se guardan, con sus condiciones, el nivel mínimo y máximo de la FIFO y cuántos paquetes salieron con 47 y con 49. Si el diseño tiene margen, el nivel queda cerca de la mitad y los ajustes son raros.
6. Probar con otro host además de la Mac cuando haya uno disponible.

## Reproducción: realimentación

En sentido OUT la Mac manda audio al ritmo de su reloj, así que el dispositivo tiene que decirle cuántas muestras por milisegundo consume en realidad. TN3190 da dos formas:

1. Realimentación explícita: un endpoint isócrono IN aparte, en la misma interfaz que el de datos OUT, que reporta el ritmo. En velocidad completa el valor va en formato 10.14 dentro de 3 bytes (USB 2.0, sección 5.12.4.2), y TN3190 pide exactamente 3 bytes en velocidad completa y 4 en alta velocidad.
2. Realimentación implícita: si la entrada y la salida están en el mismo reloj y el endpoint de datos de entrada se declara con el uso de datos con realimentación implícita, la Mac toma el ritmo de la entrada para la salida (TN3190; USB 2.0, sección 5.12.4.3).

Nuestro caso es el de la implícita. El ADC y el DAC usan el mismo BCK y LRCK del PCM1808 (docs/dominio-de-reloj.md), así que la captura ya lleva el ritmo del reloj de audio y la reproducción lo puede usar sin endpoint extra.

## Decisión: TinyUSB 0.18.0 hasta tener la captura funcionando (2026-09-13)

Se queda la 0.18.0 que trae el pico-sdk 2.3.1. No se cambia de versión.

- La captura por USB, la fase 5, no necesita realimentación: alcanzan el endpoint IN asíncrono y el control de flujo que la 0.18.0 ya tiene.
- La realimentación solo hace falta para la reproducción, la fase 6.
- Por qué: si se cambia de versión ahora y algo falla en la fase 5, no se va a poder separar si fue el I2S, el reloj o el cambio de TinyUSB. En la fase 6 va a haber una base que funciona y está medida, y el cambio se evalúa contra ella.

Lo investigado para esa evaluación, para no repetirlo, revisado en el código de cada versión de audio_device.c:

| | 0.18.0, la del pico-sdk 2.3.1 | 0.19.0 (2025-10-06) | 0.20.0 (2025-11-20) y 0.21.0 (2026-06-30) |
|---|---|---|---|
| Clase | solo UAC2 | solo UAC2 | UAC1 y UAC2 (PR 3270) |
| Captura asíncrona | sí, con control de flujo en el endpoint IN (CFG_TUD_AUDIO_EP_IN_FLOW_CONTROL, activado por defecto) | sí | sí |
| Realimentación explícita en velocidad completa | 10.14 en 3 bytes con CFG_TUD_AUDIO_ENABLE_FEEDBACK_FORMAT_CORRECTION; calculada por el nivel de la FIFO, contando el reloj maestro en cada SOF o a mano | igual que la 0.18.0 | 3 bytes con UAC1 y 4 bytes con UAC2, a cualquier velocidad |
| Realimentación implícita | no: un endpoint IN declarado así no se reconoce como endpoint de datos | sí (PR 3153) | sí |

- En la 0.18.0, el comentario del código marca 10.14 en 3 bytes como el formato que funciona en OSX.
- La 0.19.0 es la única versión con realimentación implícita y a la vez explícita en 3 bytes.
- Desde la 0.20.0, con UAC2 en velocidad completa la explícita va en 4 bytes, y TN3190 pide 3.
- En la rama principal hay cambios de audio posteriores a la 0.21.0, entre ellos un arreglo al control de flujo del endpoint IN (PR 3809), que al 2026-09-13 no están en ninguna versión publicada. Si la captura de la fase 5 muestra problemas de ritmo, conviene leer ese arreglo.

## Opciones para la fase 6

A. UAC2 con realimentación implícita. Encaja con el dominio único de reloj y no necesita endpoint de realimentación ni medir el reloj. Requiere TinyUSB 0.19.0 o posterior. Falta probarla en macOS 26: TN3190 la documenta, pero no hay una prueba propia.

B. UAC2 con realimentación explícita en 3 bytes, con TinyUSB 0.18.0 o 0.19.0 y la corrección de formato, que es lo que pide TN3190. El cálculo por nivel de la FIFO no necesita contar ningún reloj: regula la FIFO de reproducción a la mitad. Es la única que no obliga a cambiar de versión.

C. UAC1 con realimentación explícita en 3 bytes, con TinyUSB 0.20.0 o posterior. 48 kHz en estéreo de 24 bits entra en el límite de UAC1 en velocidad completa.

## Plan

- Fase 5: captura con endpoint IN asíncrono al ritmo del PCM1808, con TinyUSB 0.18.0, y los registros del punto 5 del margen desde la primera sesión.
- Una FIFO por sentido entre el I2S del PIO y USB, regulada a la mitad.
- Fase 6: reproducción, eligiendo entre A, B y C contra la base medida de la fase 5. La B se puede probar sin cambiar de versión; la A y la C requieren cambiarla.
- Prueba larga en cada fase: una hora corriendo, con el nivel de las FIFO registrado, que no tiene que derivar.

## Cómo lo resuelve tierneytim/Pico-USB-audio

Revisado en el commit c72275d, de 2022.

- Es un parlante USB: recibe audio y lo saca con un modulador de densidad de pulsos de cuarto orden por PIO. No tiene ADC (README).
- La versión para Arduino usa el USBAudio de Mbed OS del núcleo Arduino RP2040 (README; SDM/src/pdmRP2040.cpp, línea 109). Ese USBAudio declara UAC1 (bcdADC 0x0100) con dos endpoints isócronos de datos, sin tipo de sincronización y sin endpoint de realimentación.
- No sigue al reloj de la Mac. Si llega un paquete y la cola no tiene lugar, lo descarta entero. Si al PIO se le acaban los datos, repite la última muestra (pdmRP2040.cpp, líneas 48 a 60). No ajusta ningún reloj ni remuestrea.

Sirve como ejemplo de lo que hay que evitar: la diferencia entre relojes se resuelve descartando o repitiendo muestras.

## Fuentes

- USB 2.0, secciones 5.12.4.1.1, 5.12.4.2 y 5.12.4.3 (usb.org, usb_20_20250603.zip).
- USB Device Class Definition for Audio Data Formats 1.0, sección 2.2.1. La 2.0, sección 2.3.1.1, está citada por TN3190.
- Apple TN3190, USB audio device design considerations: https://developer.apple.com/documentation/technotes/tn3190-usb-audio-device-design-considerations
- TinyUSB 0.18.0 en ~/pico/pico-sdk/lib/tinyusb: src/class/audio/audio_device.c y audio_device.h.
- TinyUSB 0.19.0, 0.20.0 y 0.21.0: https://github.com/hathach/tinyusb, PR 3153, 3270 y 3809.
- tierneytim/Pico-USB-audio: https://github.com/tierneytim/Pico-USB-audio
