# Dejar Windows sin tocar la señal

Windows, por defecto, procesa el micrófono: le baja el nivel cuando cree que hay una llamada, le
mete cancelación de ruido y de eco, y lo remuestrea. Todo eso cambia la señal antes de que llegue a
medir.py, así que lo que se mediría no es la tarjeta de sonido ni la guitarra, sino el procesado de
Windows. Antes de la primera medición hay que apagarlo, y después no se vuelve a tocar.

La tarjeta de sonido USB externa se configura aparte del micrófono interno de la ASUS: son dos
dispositivos distintos y cada uno tiene sus propias casillas. Lo que sigue va sobre la tarjeta USB,
con la tarjeta ya conectada.

## Dónde está el panel

El panel de sonido de siempre, el que tiene las pestañas, no es el de Ajustes de Windows 11. Se
abre con Win+R y:

```
mmsys.cpl
```

Desde ahí: pestaña **Grabar**, la tarjeta USB, **Propiedades**.

## Los cinco cambios

1. **Comunicaciones en "No hacer nada".** En `mmsys.cpl`, pestaña **Comunicaciones**, la opción
   "Cuando Windows detecte actividad de comunicaciones" va en **No hacer nada**. Si queda en
   cualquier otra, Windows baja el nivel de todo lo demás en cuanto un programa abre el micrófono, y
   una medición hecha así no se puede comparar con ninguna otra. Esta pestaña es una sola para todo
   el sistema, no por dispositivo.

2. **Todas las mejoras del micrófono, desactivadas.** En Propiedades de la tarjeta, pestaña
   **Mejoras** (o **Avanzadas**, según el driver): marcar **Deshabilitar todos los efectos de
   sonido** y dejar sin marcar cancelación de ruido, cancelación de eco, control automático de
   ganancia y refuerzo de agudos. Si el driver trae su propio panel, hay que apagarlas también ahí:
   lo de Windows no desactiva lo del driver.

3. **Formato en 24 bits y 48000 Hz.** En Propiedades, pestaña **Avanzadas**, **Formato
   predeterminado**: `24 bits, 48000 Hz`. 48000 Hz es la frecuencia a la que graba medir.py y a la
   que va a trabajar el PCM1808; si Windows queda en otra, remuestrea, y el remuestreo se ve en el
   espectro. Si el desplegable no ofrece 24 bits, se deja en el mayor que ofrezca y se anota.

4. **Sin control exclusivo de aplicaciones.** En la misma pestaña **Avanzadas**, desmarcar
   **Permitir que las aplicaciones tomen el control exclusivo de este dispositivo** y
   **Dar prioridad a las aplicaciones en modo exclusivo**. Con el control exclusivo activo, un
   programa que abra la tarjeta primero puede cambiarle el formato o dejar a medir.py sin entrada.

5. **Cerrar todo programa de videollamada.** Teams, Zoom, Meet, Discord, Skype, OBS y cualquier cosa
   que abra el micrófono: cerrados, no minimizados ni en la bandeja del sistema. Mientras uno de
   esos tiene la tarjeta abierta aplica su propio procesado y su propio nivel. En la ASUS también
   cuenta la utilidad del fabricante: la entrada que aparece como *AI Noise-cancelling Input (ASUS
   Utility)* es el micrófono interno con el procesado de ASUS encima, y no se usa para medir.

## Anotar el nivel de entrada y no moverlo nunca más

En Propiedades de la tarjeta, pestaña **Niveles**, está el nivel de entrada. Hay que **anotar el
número que tiene y no volver a moverlo**: los valores que mide medir.py son dBFS, relativos al fondo
de escala del conversor, no voltajes. El mismo sonido con otro nivel de entrada da otro número. Si
el nivel cambia, las mediciones anteriores dejan de ser comparables con las nuevas y hay que
repetirlas todas.

Windows no deja leer ese número desde Python sin instalar nada, así que se anota a mano y queda
guardado en cada medición. Una vez por terminal:

```
$env:FEUOIR_NIVEL_ENTRADA = "50"
```

o medición por medición:

```
.venv/Scripts/python medir.py piso-de-ruido --nivel-entrada 50
```

Sin una de las dos, medir.py avisa y guarda el nivel como `null`: la medición sirve para mirarla,
pero no para compararla contra otra.

## Comprobar que quedó bien

```
.venv/Scripts/python dispositivos.py
```

La tarjeta USB tiene que aparecer con el asterisco de **WASAPI**, con `48000 Hz` y con `sí` en la
columna de 48 kHz. El mismo aparato aparece además bajo MME y DirectSound: esas filas son otros
caminos hacia la misma tarjeta, con mezcla y remuestreo por el medio, y no se usan. MME recorta los
nombres a 31 caracteres, así que ahí la tarjeta puede verse con el nombre a medias.

Si la fila de WASAPI dice `NO` en 48 kHz, el formato del paso 3 no quedó aplicado.

## Lo que queda anotado en cada medición

`condiciones.json` guarda, además del pico y el RMS, el sistema operativo, el dispositivo con su
índice y su API de audio, y el nivel de entrada con el origen del dato. Esos tres son los que
permiten poner al lado una medición hecha en la Mac y otra hecha en la ASUS y saber si la diferencia
está en la guitarra, en la tarjeta o en la máquina.
