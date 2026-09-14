# Simulador del circuito analógico

Decisión tomada el 2026-09-14, antes de construir. El diseño del circuito lo decide Renata (docs/entrada-analogica.md). Esto es la herramienta para simularlo dentro del repo, en modo batch y desde Python, sin interfaz gráfica.

## Qué hace falta

- Correr sin interfaz gráfica en macOS sobre Intel (MacBook Pro 2019, macOS 26.5.2).
- Automatizarse desde Python: los netlists son texto plano, y cada simulación guarda sus datos con sus condiciones, como el resto del repo.
- Aceptar los modelos SPICE del TL072 que publica TI.
- Hacer análisis AC, transitorio y de ruido.

## Decisión

ngspice 47, en modo batch, compilado desde el código fuente oficial sin interfaz gráfica.

- Instalación: el paquete fuente de ngspice-47, publicado el 11 de agosto de 2026, compilado sin X11 en ~/spice/ngspice-47, igual que el toolchain del Pico vive en ~/pico. La versión queda fija y se anota en cada resultado.
- Automatización: Python arma cada netlist, corre ngspice con -b en un subproceso y lee las tablas de texto que escribe wrdata desde un bloque .control. No hacen falta librerías de Python nuevas.
- Modelos de TI: con set ngbehavior=ps, ngspice traduce a su sintaxis las bibliotecas PSpice que se incluyen con .include.
- Ruido: el análisis .noise da el espectro de ruido a la salida y referido a la entrada.

## Por qué, criterio por criterio

Sin interfaz en macOS Intel. ngspice está hecho para correr en batch: -b simula y termina, -r guarda el archivo de datos y -o el registro (manual de ngspice 47, sección 12.3, con un ejemplo en la 12.4.1). No publica binarios para macOS; su página de descarga remite a Homebrew. Compilado sin X11 no depende de ninguna librería gráfica. La Mac ya tiene lo necesario para compilarlo: Apple clang 21, make, bison y flex.

Automatización desde Python. Un bloque .control corre los análisis y escribe tablas ASCII con wrdata (sección 13.5.107), que Python lee con numpy. La versión de ngspice sale del propio programa y va a las condiciones de cada resultado. PySpice, la opción conocida para usarlo desde Python, tuvo su última versión en mayo de 2021 y soporta ngspice hasta la 34. spicelib, que sí está mantenida, también maneja ngspice como programa de línea de comandos, que es lo mismo que se hace acá sin sumar la dependencia.

Modelos de TI. Los dos modelos de TI están en texto plano y sin cifrar. El del TL072 (SLOJ067) es un macromodelo de 1989 en sintaxis SPICE clásica. El del TL072H (SLOM513) usa sintaxis PSpice, que ngspice traduce con ngbehavior=ps (secciones 12.11.1 y 12.11.5). Los modelos cifrados no se pueden usar en ngspice, pero estos no lo están.

Ruido. .noise guarda el espectro de ruido a la salida y referido a la entrada, y sus totales integrados (sección 11.3.4). Usa el resolvedor por defecto; con KLU no hay análisis de ruido (sección 11.1.1).

## Qué se descartó

LTspice.

- A favor: es el simulador más usado y lee modelos PSpice.
- En contra: la versión nativa para Mac tiene la línea de comandos muy recortada. La documentación de spicelib lo dice así: "the command line interface of the native LTspice is severely limited", y en macOS recomienda correr LTspice bajo Wine. El instalador de LTspice 26 para Mac, de julio de 2026, trae adentro archivos de Wine y CrossOver, y no está comprobado que -b funcione en una Mac Intel. Sus datos salen por defecto en un .raw binario.

ngspice por Homebrew.

- A favor: se instala con un comando.
- En contra: desde septiembre de 2026 Homebrew no da soporte a las Mac Intel (nivel 3) y ya no compila paquetes para esta configuración. ngspice 47 solo tiene paquete para Sonoma en Intel, y libomp, una de sus dependencias, no tiene paquete para Intel, así que igual se compilaría. Además arrastra las librerías de X11, que en batch no se usan.

## Instalación

Una sola vez. En esta Mac compila en unos 4 minutos.

```
mkdir -p ~/spice/src && cd ~/spice/src
curl -fL -o ngspice-47.tar.gz https://sourceforge.net/projects/ngspice/files/ng-spice-rework/47/ngspice-47.tar.gz/download
shasum -a 256 ngspice-47.tar.gz
tar xzf ngspice-47.tar.gz && cd ngspice-47
./configure --prefix="$HOME/spice/ngspice-47" --with-x=no --disable-debug --disable-openmp --with-readline=no --with-editline=no
make -j4 && make install
```

El paquete descargado el 2026-09-14 tiene sha256 894e649651f1838a14095e5a5439e7d3aa63e87ede14d283173fda4fcdef675f.

Por qué cada opción:

- --with-x=no: sin ventanas de gráficos, que en batch no se usan.
- --disable-openmp: el configurador activa OpenMP por defecto, y la compilación falla porque el clang de Apple no trae omp.h. La simulación no lo necesita.
- --with-readline=no y --with-editline=no: el configurador toma el readline.h del SDK de Apple, que en realidad es libedit, y la compilación falla en rl_reset_after_signal. La línea de comandos interactiva tampoco se usa.
- make -j4 y no con todos los núcleos, porque la Mac anda justa de memoria.

spice/run.py busca ngspice en la variable NGSPICE, después en ~/spice/ngspice-47/bin/ngspice y después en el PATH.

## Verificación

```
.venv/bin/python -m spice.verify
```

Antes de creerle al simulador en el circuito real, spice/verify.py lo compara con la teoría en circuitos de resultado conocido y guarda cada chequeo con sus condiciones en calibraciones/<fecha>-spice/resultados.json, con el formato de calibrar.py:

- El lector de los archivos .raw, contra archivos armados a mano con valores reales y complejos.
- Un divisor resistivo de 9 V con 4.7 kΩ arriba y 1 kΩ abajo: la tensión del punto medio, a 1 µV.
- Un filtro RC de 4.7 kΩ y 1 nF: magnitud y fase de 10 Hz a 10 MHz, a 0.01 dB y 0.05°; la respuesta a un escalón en 1, 3 y 5 constantes de tiempo, a 2 mV; el ruido térmico a 10 Hz contra la raíz de 4kTR y el ruido total de 1 Hz a 1 GHz contra la raíz de kT/C corregida por la banda, los dos al 1 %.

Si algo no pasa, termina con código 1, y ninguna otra simulación del repo vale. tests/mutaciones.py le inyecta 4 errores (ver Errores inyectados en el README).

## Qué dio la instalación

- ngspice 47 compiló al tercer intento, con las opciones de arriba, en 248 s y sin errores.
- La verificación pasa sus 13 chequeos (docs/bitacora.md, entrada 26).
- Lee los dos modelos de TI: el del TL072 tal como viene, con el fin de línea de Windows y el byte 0x1A después de .ENDS, y el del TL072H con ngbehavior=ps.

## Lo que hay que saber de los modelos antes de usarlos

- El modelo del TL072 (SLOJ067, archivo TL072.301) es un macromodelo de Boyle de 1989, con un par JFET de entrada, fuentes polinómicas y diodos de recorte. No tiene fuentes de ruido ajustadas a la hoja, y su JFET no tiene parámetros de ruido 1/f. El ruido que dé .noise va a salir solo de los componentes del macromodelo, así que no se puede esperar que coincida con los 18 ni con los 37 nV/√Hz: hay que medirlo en simulación antes de usarlo. En continua se porta bien: como seguidor con ±9 V, la salida sigue a la entrada a menos de 0.05 mV entre -1 V y 1 V.
- El modelo del TL072H (SLOM513, revisión B de 2021) sí modela el ruido de tensión y de corriente de entrada. Es el del dado nuevo, que según la tabla 5.9 de la hoja tiene los mismos 37 nV/√Hz que el DIP-8 de TI. En continua, como seguidor con ±9 V, sigue a la entrada con la ganancia correcta pero con un offset fijo de -6.47 mV, más que el máximo de ±4 mV de la tabla 5.7. Viene de la biblioteca: su subcircuito VOS_DRIFT_0 fija .PARAM DC = -0.0126, o sea -12.6 mV. Da -6.47 mV igual con ±9 V que con 0 y 18 V, y -2.38 mV con ±15 V: cambia con la tensión total y no con cómo se alimenta, así que no es un error de configuración. No se sigue: en el circuito C3 bloquea la continua.
- La inversión de fase no es simulable con los modelos disponibles. El del TL072 clásico no la muestra: como seguidor con 9 V simples y la entrada barrida de 0 a 9 V, la salida nunca baja mientras la entrada sube (la mayor caída es de 0.014 V), y con la entrada en 0 V se queda en 1.55 V. Tampoco representa el límite de modo común: sigue a la entrada, a menos de 0.1 V, hasta 1.47 V, cuando la hoja pide quedarse 4 V por encima del riel negativo. El TL07xH está hecho para no invertir la fase. Una simulación limpia de 9 V simples no prueba que el problema no exista.
- El modelo del TL072 clásico consume 8.4 mA por amplificador con ±9 V: su resistencia RP, de 2.143 kΩ, va de riel a riel. La tabla 5.8 de la hoja da 1.4 mA típicos y 2.5 mA como máximo. En el transitorio de la etapa de entrada las pilas entregan 17.1 mA por riel con ±9 V y 13.2 mA con ±7 V, y con 10 Ω de resistencia interna los rieles bajan 0.13 V, cuando con el consumo de la hoja bajarían unos 0.03 V. El margen de entrada simulado queda un poco por debajo del real. La respuesta en frecuencia no cambia.
- El modelo del TL072H tiene 79.2 fA/√Hz de ruido de corriente a 1 kHz, lo que da la tabla 5.7 para el TL07xH. La tabla 5.9 da 10 fA/√Hz para los TL07xC, TL07xAC, TL07xBC, TL07xI y TL07xM, y el DIP-8 que se va a comprar es uno de ellos: la tensión de ruido coincide con la del DIP-8 y la corriente no. Pesa donde la impedancia en la entrada no inversora es alta. Con la entrada al aire, sobre 1 MΩ, 79.2 fA/√Hz son 79 nV/√Hz y 10 fA/√Hz serían 10 nV/√Hz, así que la simulación da entre 1.2 y 1.3 dB más de ruido a 1 kHz que el que tendría el DIP-8, según el cálculo a mano. Con la guitarra conectada pesa sobre todo cerca de la resonancia, donde sube la impedancia de la pastilla.

## Qué modelo se usa para qué

Decisión de Renata, del 2026-09-14: no se elige uno, se usan los dos, cada uno para lo que sabe hacer. Ningún macromodelo es correcto para todo, y eso es normal.

- El del TL072 clásico (SLOJ067) para todo lo lineal: respuesta en frecuencia, ganancia, transitorio y margen con pila fresca y con pila gastada.
- El del TL072H (SLOM513) solo para el análisis de ruido.

Advertencia: el ruido sale de un modelo distinto al del resto de las simulaciones. Es aceptable porque el DIP-8 de TI que se va a comprar figura en la tabla 5.9 de la hoja con 37 nV/√Hz a 1 kHz, la misma cifra que el TL07xH: el modelo del H reproduce el ruido que va a tener el circuito, aunque por dentro sea otro chip. Lo que el H no reproduce bien, como su offset en continua, no cambia el ruido, y en el circuito C3 bloquea la continua igual. Antes de usarlo se compara su ruido a 1 kHz con la hoja; si no coincide dentro de una tolerancia razonable, no se usa.

Comprobado el 2026-09-14 con spice/characterize.py, que caracteriza los dos modelos y guarda sus resultados y gráficas en calibraciones/<fecha>-modelos-tl072/:

```
.venv/bin/python -m spice.characterize
```

- Ruido del modelo del TL072H como seguidor: 37.6 nV/√Hz a 1 kHz, 0.13 dB por encima de los 37 de la hoja, dentro de la tolerancia de ±1 dB. A 10 kHz, 22.1 nV/√Hz contra 21. De corriente a 1 kHz, 79.2 fA/√Hz contra 80. Se usa para el ruido.
- Si el ruido a 1 kHz se sale de ±1 dB, el script termina con código 1 y dice que no se use.

## Simulaciones de la etapa de entrada

spice/simulate_input.py corre las simulaciones que pidió Renata sobre el netlist del circuito, spice/netlists/input_stage.cir, que tiene las dos versiones, y el de la guitarra, spice/netlists/guitar.cir. Los opamps entran por spice/netlists/opamp_tl072.cir y opamp_tl072h.cir.

```
.venv/bin/python -m spice.simulate_input
.venv/bin/python -m spice.simulate_input carga ruido
```

- respuesta: de 1 Hz a 1 MHz con la ganancia en 1, 3, 5, 8 y 11, en las dos versiones, con pilas frescas y la carga de 60 kΩ del PCM1808.
- transitorio: 1.5 V de pico a 1 kHz con ganancia 11, con 9 V simples, con ±9 V y pilas frescas y con ±7 V y pilas gastadas. Mide el margen de la entrada no inversora contra la tabla 5.3 de la hoja del TL072 y la tensión en la entrada del PCM1808 contra su fondo de escala y su máximo absoluto.
- ruido: con ±9 V, en la entrada del PCM1808, con la entrada al aire y con la guitarra con cable de 300 y 600 pF, con ganancia 1 y 11. Lo integra de 20 Hz a 20 kHz y lo da en µV y en dBFS, con 0 dBFS en 1.5 V de pico.
- carga: la guitarra sola, cargada con 1 MΩ y con 10 kΩ, con cable de 300 y 600 pF.

Cada una guarda su carpeta en mediciones/<fecha>-sim-<nombre>/ con condiciones.json, resultado.json, los datos en CSV, los netlists que corrió y las gráficas. condiciones.json lleva medicion, resumen y fecha_hora, así las simulaciones aparecen en Guardadas de la app.

Los netlists tienen que ser el circuito del papel, y cada corrida lo comprueba contra cálculos a mano:

- la ganancia a 1 kHz en cada punto, a 0.1 dB;
- la curva de 1 Hz a 5 kHz contra el circuito resuelto con opamps ideales, en las dos versiones, a 0.01 dB;
- el corte del filtro R5 con C5, al 2 %;
- la amplitud y el centro de la entrada no inversora en el transitorio;
- el ruido a 1 kHz con la entrada al aire contra la suma de sus fuentes, a 1 dB;
- la guitarra cargada contra su fórmula, a 0.01 dB.

Si alguno falla, el script termina con código 1. tests/mutaciones.py le inyecta 5 errores: R4, C4 y R3 cambiados en el circuito, otra bobina en la guitarra y la entrada al aire cargada con 1 MΩ.

## Fuentes

- ngspice, noticias y versión 47: https://ngspice.sourceforge.io/news.html
- ngspice, descargas: https://ngspice.sourceforge.io/download.html
- Manual de ngspice 47: https://ngspice.sourceforge.io/docs/ngspice-47-manual.pdf
- ngspice, modelos de fabricantes y modelos cifrados: https://ngspice.sourceforge.io/modelparams.html
- Homebrew, niveles de soporte: https://docs.brew.sh/Support-Tiers
- Homebrew, paquetes de ngspice y libomp: https://formulae.brew.sh/api/formula/ngspice.json y https://formulae.brew.sh/api/formula/libomp.json
- spicelib: https://github.com/nunobrum/spicelib
- PySpice: https://pypi.org/project/PySpice/
- LTspice, versión actual: https://ltspice.analog.com/download/updates.txt
- TI, modelo del TL072: https://www.ti.com/lit/zip/SLOJ067 (página del producto: https://www.ti.com/product/TL072)
- TI, modelo del TL072H: https://www.ti.com/lit/zip/SLOM513 (página del producto: https://www.ti.com/product/TL072H)
