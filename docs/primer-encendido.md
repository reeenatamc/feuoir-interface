# Primer encendido

Lista para seguir en orden, de a un paso. Si un paso no da lo esperado, se para ahí: la etapa siguiente supone que la anterior está bien. Diagrama y resistencias en docs/dominio-de-reloj.md.

## Reglas

- Todo cambio de cable, jumper o puente se hace con el USB desenchufado.
- Una sola cosa nueva por etapa.
- Cada valor del multímetro se anota con la hora en mediciones/AAAA-MM-DD-primer-encendido/notas.md. Los informes del firmware los guarda leer_verificacion.py.
- La guitarra no se conecta en ningún paso de esta lista.

## Antes de la noche

- [ ] Compilar el firmware de verificación: firmware/build/verificar_reloj.uf2 (README, sección firmware).
- [ ] Tener abiertos docs/dominio-de-reloj.md y la figura de pines de docs/datasheets/pico-datasheet.pdf.
- [ ] Mesa despejada: sin restos de estaño, sin cables sueltos, sin objetos de metal cerca.
- [ ] Multímetro con pila: en continuidad pita al juntar las puntas.
- [ ] Cable micro-USB que pasa datos, no uno que solo carga.
- [ ] Audífonos y parlantes lejos del DAC.

## Etapa 0: revisión con multímetro, sin nada enchufado

Pico, sola:

- [ ] Continuidad entre VBUS (pin 40) y GND: no pita, o pita un instante y deja de pitar por los capacitores.
- [ ] Lo mismo entre VSYS (pin 39) y GND, y entre 3V3 (pin 36) y GND.
- Si pita sostenido: cortocircuito. No se enchufa esa placa.

Módulo del PCM1808, suelto:

- [ ] Ubicar en la serigrafía qué pin es la alimentación analógica (VCC, 4.5 a 5.5 V), cuál la digital (VDD, 2.7 a 3.6 V) y cuál GND. Si el módulo no lo deja claro, se para acá hasta averiguarlo.
- [ ] Continuidad entre cada alimentación y GND: no pita sostenido.
- [ ] MD1 y MD0 van a alto, FMT a bajo. Medir cómo quedan en el módulo y anotarlo.

Módulo del PCM5102A, suelto:

- [ ] Continuidad entre VIN y GND: no pita sostenido.
- [ ] Mirar el regulador del módulo y decidir con qué se alimenta VIN. Sin regulador, solo 3.3 V: el PCM5102A trabaja de 3.0 a 3.6 V y su máximo absoluto es 3.9 V.
- [ ] Puente de SCK: ABIERTO. Continuidad entre el pin SCK y GND: no tiene que pitar. Si pita, se desuelda el puente antes de seguir. Es la revisión más importante de toda la lista.
- [ ] Puentes 1L, 2L, 3H y 4L: FLT, DEMP y FMT con continuidad a GND; XSMT con continuidad a 3.3 V.

Resistencias, antes de ponerlas:

- [ ] Medir cada una: dos de unos 330 Ω y cuatro de unos 470 Ω.

## Etapa 1: solo el Pico

Conectar:

- [ ] Nada en los pines del Pico. Solo el cable USB.
- [ ] Mantener apretado BOOTSEL, enchufar el USB a la Mac y soltar.

Esperado:

- [ ] Aparece la unidad RPI-RP2 en la Mac en unos segundos.
- Si no aparece: desenchufar, probar otro cable. Si con otro cable tampoco, parar.

Medir, con el Pico enchufado:

- [ ] VBUS (pin 40) contra GND: entre 4.5 y 5.5 V (hoja del Pico, 5 V ± 10 %).
- [ ] 3V3 (pin 36) contra GND: entre 3.0 y 3.6 V, la ventana en la que trabajan los tres integrados. Lo normal es cerca de 3.3 V.
- [ ] Con medidor USB, si hay: cerca de 10 mA en BOOTSEL (hoja del Pico, tabla 3).
- Si VBUS o 3V3 quedan fuera de rango, o el consumo es varias veces ese valor: desenchufar y parar.

Cargar el firmware:

- [ ] Arrastrar verificar_reloj.uf2 a RPI-RP2. El Pico se reinicia solo y la unidad desaparece.
- [ ] En la terminal: ls /dev/cu.usbmodem* muestra un puerto.
- Si no aparece en 10 s: desenchufar, volver a enchufar sin BOOTSEL y mirar de nuevo. Si sigue sin aparecer, parar: el firmware nunca se probó en una placa.

Leer el informe:

- [ ] .venv/bin/python leer_verificacion.py etapa1-pico --puentes "nada conectado"
- Esperado: todos los chequeos del PLL y de GPOUT0 en ok, pll_hz en 61440000 ± 125, y una sola FALLA, en gpio20_hz, con la nota "falta el puente con GPIO21". Esa falla es la esperada.
- Si falla otra cosa: parar. El informe queda guardado en mediciones/.

## Etapa 2: el reloj

- [ ] Desenchufar el USB.
- [ ] Poner R1 (330 Ω) en GP21.
- [ ] Puente de verificación: un cable corto desde el extremo de R1 que no toca GP21 hasta GP20. Nunca directo desde el pin GP21.
- [ ] Enchufar el USB, sin BOOTSEL.
- [ ] .venv/bin/python leer_verificacion.py etapa2-reloj --puentes "GP21 por R1 a GP20"
- Esperado: sin fallas. gpio20_hz en 12288000 ± 125, con diferencia_ppm cerca de 0.
- Si gpio20_hz da 0: el puente no hace contacto. Desenchufar y revisarlo.
- Si da 25000000: el PLL quedó en los 125 MHz de arranque del SDK. Parar.
- Si da cualquier otro valor: anotarlo y parar.
- [ ] Desenchufar y quitar el puente de GP20.

## Etapa 3: el ADC

Conectar, con el USB desenchufado:

- [ ] GND del módulo del PCM1808 a GND del Pico. Siempre primero.
- [ ] Alimentación del módulo según su serigrafía: VCC entre 4.5 y 5.5 V (VBUS, pin 40, sirve) y VDD entre 2.7 y 3.6 V (3V3, pin 36).
- [ ] MD1 y MD0 en alto y FMT en bajo, antes de encender.
- [ ] Jumper de SCKI en 1-2: GP21, por R1, al SCKI del PCM1808.
- [ ] R3, R4 y R5 (470 Ω) pegadas a BCK, LRCK y DOUT del módulo; del otro lado, a GP16, GP17 y GP18.
- [ ] Continuidad de cada cable nuevo contra GND: no pita.

Encender:

- [ ] Enchufar el USB. Acercar el dorso del dedo al módulo durante los primeros 10 s: nada tibio.
- [ ] Con medidor USB: el consumo sube del orden de 15 mA respecto de la etapa 2. La hoja da 8.6 mA analógicos y 5.9 mA digitales típicos. Si sube más de 50 mA, desenchufar.

Medir:

- [ ] .venv/bin/python leer_verificacion.py etapa3-adc --puentes "SCKI desde GP21; sin puente en GP20"
- Esperado: PLL y GPOUT0 en ok con la carga nueva; la única FALLA es gpio20_hz, porque no hay puente.
- [ ] Desenchufar. Puente de verificación desde el extremo de R3 que no toca el módulo hasta GP20. Enchufar.
- [ ] .venv/bin/python leer_verificacion.py etapa3-bck --puentes "GP20 a BCK por R3"
- Esperado: el informe marca FALLA en gpio20_hz porque espera 12.288 MHz, pero el valor tiene que ser 3072000. Eso confirma el modo maestro: BCK a 64 fS.
- Si da 0: el PCM1808 no está en modo maestro o no le llega SCKI. Revisar MD1, MD0 y el jumper de SCKI.
- [ ] Desenchufar. Mover el puente al extremo de R4. Enchufar.
- [ ] .venv/bin/python leer_verificacion.py etapa3-lrck --puentes "GP20 a LRCK por R4"
- Esperado: FALLA en gpio20_hz, con valor 48000.
- [ ] Desenchufar y quitar el puente de GP20.

## Etapa 4: el DAC

Conectar, con el USB desenchufado:

- [ ] Revisar otra vez el puente de SCK del módulo: continuidad entre SCK y GND, no pita.
- [ ] GND del módulo del PCM5102A a GND del Pico, primero.
- [ ] VIN según el regulador que se miró en la etapa 0.
- [ ] Jumper de SCK en 1-2, 4 hilos: SCK del PCM5102A al nodo de SCKI.
- [ ] BCK y LCK del módulo al extremo libre de R3 y de R4.
- [ ] R6 (470 Ω) pegada a GP19; del otro lado, a DIN del módulo.
- [ ] Salidas del DAC sin nada conectado.
- [ ] Continuidad de cada cable nuevo contra GND: no pita. Con el jumper de SCK puesto, SCK contra GND tampoco pita.

Encender:

- [ ] Enchufar el USB. Dorso del dedo sobre los dos módulos durante los primeros 10 s.
- [ ] Con medidor USB: el consumo sube del orden de 20 mA respecto de la etapa 3. La hoja da 7 a 8 mA digitales y 11 mA analógicos típicos. Si sube más de 60 mA, desenchufar.

Medir:

- [ ] Salida izquierda y derecha del módulo contra GND, en continua: cerca de 0 V, porque la salida no usa capacitores de desacople de continua. Si da varios voltios, desenchufar.
- [ ] .venv/bin/python leer_verificacion.py etapa4-dac --puentes "SCK del DAC en SCKI, 4 hilos; sin puente en GP20"
- Esperado: PLL y GPOUT0 en ok con el nodo de SCKI llegando a los dos integrados; la única FALLA es gpio20_hz.
- La prueba de sonido y la de 3 hilos no son parte de este encendido: necesitan firmware de reproducción.

## Oscilador externo, solo cuando se vaya a comparar

- [ ] Compilar el firmware de verificación en firmware/build-externo, con FEUOIR_RELOJ_EXTERNO=ON, y cargarlo.
- [ ] Con el USB desenchufado: R2 (330 Ω) pegada a la salida del oscilador, jumper de SCKI en 2-3, jumper de alimentación del oscilador puesto, puente de verificación desde el extremo libre de R2 hasta GP20.
- [ ] .venv/bin/python leer_verificacion.py oscilador --puentes "SCKI desde el oscilador; GP20 a R2"
- Esperado: gpout0_enable en 0, y gpio20_hz dentro de ± 1000 ppm de 12288000. La diferencia en ppm es la del oscilador contra el cristal del Pico.
- [ ] Al volver a GPOUT0: sacar el jumper de alimentación del oscilador y cargar de nuevo el firmware normal.

## No hacer

- No conectar la guitarra, ni en esta lista ni antes de haber verificado todas las alimentaciones.
- No mover jumpers ni cables con el USB enchufado.
- No cerrar el puente de SCK del módulo del PCM5102A.
- No llevar un puente de verificación a GP20 directo desde un pin de salida: siempre desde el extremo de la resistencia.
- No poner 5 V en un pin de 3.3 V. Los GPIO del RP2040 aguantan como mucho su alimentación más 0.5 V, y el PCM5102A 3.9 V.
- No conectar señales a un módulo sin alimentación: a través de sus diodos de protección se alimentaría por los pines. Todo se enciende junto.
- No dejar un cable con una punta suelta en la protoboard.
- No conectar audífonos ni parlantes al DAC.
- No cargar otro firmware que el de verificación en este encendido.
- No saltar a la etapa siguiente si la actual no dio lo esperado.

## Desconectar el USB de inmediato si

- Algo se calienta: un integrado, un regulador o una resistencia.
- Hay olor a quemado o un chasquido.
- La Mac avisa que un accesorio USB consume demasiada energía, o el Pico se desconecta solo.
- El consumo en el medidor USB salta de golpe o supera por mucho lo esperado de la etapa.
- 3V3 baja de 3.0 V o sube de 3.6 V.
- El Pico no aparece como RPI-RP2 con BOOTSEL, o deja de aparecer el puerto /dev/cu.usbmodem* que aparecía en la etapa anterior.
- Un informe da pll_hz o gpio20_hz en 0 después de haber dado bien en la etapa anterior.
