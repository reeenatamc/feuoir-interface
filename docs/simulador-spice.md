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

## Qué falta comprobar al instalar

- Que ngspice 47 compile en esta Mac.
- Que lea los dos modelos de TI. El del TL072 trae fin de línea de Windows y un byte de fin de archivo (0x1A) después de .ENDS.
- Que sus resultados coincidan con la teoría en circuitos de resultado conocido, un divisor resistivo y un filtro RC de primer orden, antes de creerle en el circuito real.

## Lo que hay que saber de los modelos antes de usarlos

- El modelo del TL072 (SLOJ067, archivo TL072.301) es un macromodelo de Boyle de 1989, con un par JFET de entrada, fuentes polinómicas y diodos de recorte. No tiene fuentes de ruido, y su JFET no tiene parámetros de ruido 1/f: .noise no va a reproducir el ruido de la hoja, solo el de las resistencias.
- El modelo del TL072H (SLOM513, revisión B de 2021) sí modela el ruido de tensión y de corriente de entrada. Es el del dado nuevo, que según la tabla 5.9 de la hoja tiene los mismos 37 nV/√Hz que el DIP-8 de TI.
- Ninguno de los dos está comprobado todavía para la inversión de fase.
- Cuál se usa lo decide Renata, antes de simular el circuito.

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
