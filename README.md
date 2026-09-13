# feuoir-interface

Interfaz de audio propia. Antes de diseñar la parte analógica hay que conocer la señal que va a recibir: cuánto voltaje entrega la guitarra, hasta qué frecuencia tiene energía y cuánto ruido trae. Este repo empieza por la herramienta para medir eso.

## Qué mide medir.py

Graba 5 segundos de una entrada de audio a 48 kHz y calcula el pico y el RMS de la señal. Cada corrida guarda el audio, una gráfica con la forma de onda y el espectro en dBFS, y las condiciones en que se hizo:

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

El pico, el RMS y el espectro salen de analizador.py.

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

## analizador.py

El análisis y las señales de prueba. medir.py lo importa.

- pico_dbfs y rms_dbfs: niveles en dBFS.
- espectro, resolucion_hz y picos_espectrales: espectro de amplitud en dBFS con ventana Hann. Una senoidal de amplitud A que cae en un bin da 20·log10(A).
- ajuste_seno: amplitud, fase, continua y frecuencia de una senoidal por mínimos cuadrados (IEEE 1057, 4 parámetros).
- thd_n: THD+N relativo a la fundamental, limitado por defecto a la banda de 20 Hz a 20 kHz. Un armónico con el 1 % de la amplitud de la fundamental da 1.000 %.
- snr_db: relación señal a ruido con dos capturas, una con el tono de prueba en la entrada y otra sin señal.
- respuesta_en_frecuencia: nivel, ganancia y fase de cada tono de un barrido escalonado, relativos a la captura de entrada del circuito.
- tono, barrido_log, frecuencias_log y barrido_escalonado: señales para excitar el circuito cuando exista.
