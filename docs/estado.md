# Estado

Qué parte está hecha, con qué se probó y qué falta por probar. El detalle de cada medición está en
docs/bitacora.md.

| Parte | Estado | Probado | Sin probar |
|---|---|---|---|
| medir.py y dispositivos.py | funcionan en la Mac y en Windows | con la tarjeta USB y la guitarra en la Mac el 2026-09-19 (docs/bitacora.md, entrada 30); en Windows corren por WASAPI a 48 kHz y guardan su carpeta, comprobado con una captura de prueba que no se conservó (docs/bitacora.md, entrada 29) | la guitarra con la carga de la etapa de entrada; la tarjeta de sonido USB y la guitarra en Windows |
| analizador.py | cubre lo que se necesita hasta ahora, y el análisis de la guitarra | calibrar.py: 20 pruebas y 228 chequeos con señales sintéticas; tests/mutaciones.py detecta los 27 errores inyectados; usado con las tomas de guitarra del 2026-09-19 (docs/bitacora.md, entrada 34) | una captura de la interfaz |
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

