# Lista de compras

Lo que pide el diseño documentado en docs/. Hasta el 2026-09-13 no había lista en el repo; esta sale de los documentos y hay que marcar lo que ya está pedido.

## Placas y módulos

| Qué | Cantidad | Para qué | Nota |
|---|---|---|---|
| Raspberry Pi Pico (RP2040) | 1 | control, reloj maestro y USB | con conector micro-USB |
| Módulo PCM1808 | 1 | ADC | ver cómo expone MD0, MD1 y FMT |
| Módulo PCM5102A (el morado) | 1 | DAC | puente de SCK abierto (docs/dominio-de-reloj.md) |
| Oscilador de cristal de 12.288 MHz, salida CMOS de 3.3 V | 1 | comparar jitter contra GPOUT0 | su hoja tiene que aceptar al menos 10 mA de salida; anotar el jitter que declare |
| Tarjeta de sonido USB con entrada de micrófono de tres contactos | 1 | medir la guitarra y la prueba de 750 Hz | DECISIONES.md |
| Adaptador de 6.35 a 3.5 mm | 1 | guitarra a la tarjeta USB | DECISIONES.md |

## Etapa analógica de entrada

Alimentación partida de ±9 V con dos pilas en serie y el punto medio como tierra analógica (docs/bitacora.md, entrada 24).

| Qué | Cantidad | Para qué | Nota |
|---|---|---|---|
| TL072 en DIP-8, no TL072H | 1 | etapa de ganancia y seguidor de salida | se aceptan 37 nV/√Hz; ver la nota debajo |
| Pila de 9 V | 2 | alimentación de +9 V y de -9 V | la segunda se suma por la alimentación partida |
| Portapilas o broche de 9 V | 2 | uno por pila | |

Nota sobre el TL072: en la hoja de TI (SLOS080W, julio 2025, tabla 5.9) los 18 nV/√Hz a 1 kHz figuran para las cápsulas PS y NS y para TL07xM; para todas las demás, que incluyen el DIP-8 (P) de TI, figuran 37 nV/√Hz. Se aceptan los 37 nV/√Hz y se sigue con el DIP-8 (docs/bitacora.md, entrada 25). Al pedirlo, preguntarle a la tienda qué fabricante manejan y pedir su hoja de datos. No frena el pedido.

## Resistencias

Todas de 1/4 W. Cálculo en docs/dominio-de-reloj.md, sección Resistencias en serie.

| Valor | Hacen falta | Comprar | Dónde van |
|---|---|---|---|
| 330 Ω | 2 | 10 | R1 en GPIO21 (GPOUT0) y R2 en la salida del oscilador |
| 470 Ω | 4 | 10 | R3 en BCK, R4 en LRCK y R5 en DOUT, del lado del PCM1808; R6 en GPIO19 (DIN) |
| 100 kΩ | 1 | 2 | divisor de la prueba de 750 Hz contra la tarjeta USB (docs/reloj.md) |
| 1 kΩ | 1 | 2 | divisor de la prueba de 750 Hz |

## Jumpers y cableado

| Qué | Cantidad | Para qué |
|---|---|---|
| Tira de pines macho de 2.54 mm | 1 | jumpers de SCKI y SCK (3 pines cada uno) y alimentación del oscilador (2 pines) |
| Puentes de 2.54 mm (shunts) | 3 y repuestos | los tres jumpers |
| Protoboard | 1 | armado |
| Cables dupont macho-macho cortos | un juego | el nodo de SCKI tiene que ser corto |
| Cable micro-USB con datos | 1 | uno que solo carga no deja que el Pico aparezca en la Mac |

## Para el primer encendido

| Qué | Cantidad | Para qué |
|---|---|---|
| Multímetro con continuidad | 1 | revisión antes de alimentar (ya debería estar) |
| Medidor de corriente USB en línea | 1, opcional | leer el consumo de cada etapa sin abrir el circuito |

## Pendiente de definir

- El capacitor de desacople del oscilador: el que pida su hoja.
- Lo que haga falta según cómo lleguen los módulos, por ejemplo resistencias para fijar MD0, MD1 y FMT si el módulo del PCM1808 no las trae.
