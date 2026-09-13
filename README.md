# feuoir-interface

Interfaz de audio propia. Antes de diseñar la parte analógica hay que conocer la señal que va a recibir: cuánto voltaje entrega la guitarra, hasta qué frecuencia tiene energía y cuánto ruido trae. Este repo empieza por la herramienta para medir eso.

## Qué mide medir.py

Graba 5 segundos de una entrada de audio a 48 kHz y calcula el pico y el RMS de la señal. Cada corrida guarda el audio, una gráfica con la forma de onda y el espectro, y las condiciones en que se hizo:

```
.venv/bin/python medir.py piso-de-ruido --notas "ventana cerrada"
```

```
mediciones/2026-09-13-piso-de-ruido/
  captura.wav
  captura.png
  condiciones.json
```

condiciones.json registra fecha y hora, dispositivo (nombre e índice según sounddevice), frecuencia de muestreo, duración, volumen de entrada del sistema, pico y RMS en dBFS, y notas. Si la etiqueta se repite el mismo día, la carpeta nueva termina en -2, -3, etc.

El dispositivo se elige con DISPOSITIVO dentro de medir.py. dispositivos.py lista las entradas con su número.

Instalación:

```
python3 -m venv .venv
.venv/bin/pip install sounddevice numpy matplotlib scipy
```

## Los valores son dBFS

Pico y RMS están en dBFS, decibeles relativos al fondo de escala del conversor, donde 0 dBFS es la muestra más grande que se puede representar. No son niveles absolutos de presión sonora (dB SPL) ni voltajes. El mismo sonido da otro número con otro dispositivo u otro volumen de entrada, y para pasar a voltios hace falta calibrar la entrada con una señal conocida. El RMS se calcula contra 1.0, así que una senoidal a fondo de escala da -3 dBFS.

## Volumen de entrada

El volumen de entrada del sistema está en 71 y no se toca. Si cambia, las mediciones dejan de ser comparables entre sí. Cada condiciones.json guarda el valor que tenía en esa corrida.

Las decisiones de hardware y de método están en DECISIONES.md.
