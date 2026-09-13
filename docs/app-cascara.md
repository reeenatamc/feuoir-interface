# Cáscara de la app de medición en vivo

Decisión tomada el 2026-09-13, antes de escribir código.

## Qué es

Una app de escritorio: se abre en su propia ventana, como cualquier aplicación de la Mac, no en una pestaña del navegador. Dentro de esa ventana, la interfaz está hecha con HTML y TypeScript.

Así funcionan también Tauri y Electron: las tres opciones dibujan la interfaz con tecnología web dentro de una ventana nativa. Lo que cambia es qué corre detrás de la ventana.

| Opción | Qué corre detrás de la ventana |
|---|---|
| pywebview, la elegida | el mismo programa de Python que lee el audio, analiza y guarda |
| Tauri | una cáscara en Rust, que además tiene que lanzar el servidor de Python empaquetado con PyInstaller |
| Electron | Chromium y Node.js dentro de su binario, que además tiene que lanzar Python |

Que Python "sirva la página" es solo el mecanismo interno: levanta un servidor en la propia Mac, en un puerto local, y la ventana lo carga. No se ve ni se usa desde afuera.

## Qué hace falta

- Python es la única fuente de verdad: lee el audio con sounddevice, analiza con analizador.py y guarda las mediciones.
- TypeScript solo dibuja lo que recibe por WebSocket, sin estado propio duplicado.
- Criterios de la elección: no reimplementar nada del análisis, funcionar en macOS sobre Intel (MacBook Pro de 2019) y la menor fricción posible de instalación y arranque.
- Un dato de la máquina que pesa en los tres: la Mac ya anda justa de memoria con el uso diario.

## Decisión

Python abre la ventana con pywebview y le sirve la interfaz y el WebSocket desde el mismo proceso.

- Un solo proceso. El mismo programa en Python tiene el audio, el análisis, el WebSocket y los archivos de la interfaz. No hay un segundo proceso que lanzar, vigilar y cerrar.
- Servidor: aiohttp, que entrega la interfaz y el WebSocket en el mismo puerto local.
- Ventana: pywebview abre la interfaz en una ventana nativa. Si pywebview diera problemas, la misma interfaz se abre en el navegador sin cambiar nada más.
- Interfaz: TypeScript compilado con Vite a archivos estáticos que sirve Python. En desarrollo, el servidor de Vite con recarga en caliente, conectado al WebSocket del proceso de Python.
- Instalación: aiohttp y pywebview en el .venv que ya existe, y las dependencias de la interfaz con npm, que ya está en la Mac (Node 24).
- Arranque: un solo comando con el Python del .venv.

## Por qué, criterio por criterio

Reimplementar el análisis. Ninguna de las tres opciones obliga a reescribirlo, porque en las tres Python sigue analizando. La diferencia es cuántos programas hay que mantener juntos: con Tauri o con Electron, Python corre como un proceso aparte que la cáscara tiene que lanzar y cerrar; con pywebview, el que analiza es el mismo que abre la ventana, y el contrato del WebSocket es la única frontera.

macOS sobre Intel. Las tres funcionan, según lo revisado el 2026-09-13:

- aiohttp 3.14.3 tiene paquete para Python 3.12 en macOS x86_64.
- pywebview 6.2.1 usa en macOS pyobjc con WebKit, y pyobjc-core 12.2.2 tiene paquete universal2 para Python 3.12.
- Electron publica builds x64 para Mac Intel; la versión actual es la 44.3.0.
- Tauri 2 pide macOS 10.15 o posterior, y su CLI 2.11.4 tiene binario para darwin-x64.

Fricción de instalación y arranque. Con pywebview son dos paquetes más en el .venv y un comando. Con Tauri hay que agregar su CLI, compilar una cáscara en Rust y empaquetar el servidor de Python como ejecutable. Con Electron hay que bajar su runtime y escribir el código que lanza y cierra el proceso de Python.

Memoria. pywebview y Tauri usan la webview del sistema. Electron embebe Chromium y Node.js en su binario (documentación de Electron): un navegador y un runtime de JavaScript más, en una máquina que ya anda al límite, solo para dibujar.

## Qué se descartó

Tauri.

- A favor: usa la webview del sistema y no empaqueta un motor de navegador (documentación de Tauri). Rust ya está instalado en la Mac (rustc 1.97.1).
- En contra: Python no corre dentro de Tauri. La documentación de sidecars pide un ejecutable independiente con el sufijo de la plataforma, y da como caso común las aplicaciones de Python empaquetadas con PyInstaller. Eso suma PyInstaller, un segundo proceso con su ciclo de vida y una cáscara en Rust que compilar y mantener, a cambio de un .app distribuible que esta herramienta de laboratorio no necesita.

Electron.

- A favor: ecosistema conocido para quien trabaja con front-end, y builds para Mac Intel.
- En contra: embebe Chromium y Node.js, que en esta Mac es el costo más alto de los tres, y Python también sería un proceso aparte que Electron tiene que lanzar y cerrar.

La interfaz en una pestaña del navegador, sin ventana propia.

- Queda como alternativa inmediata, porque es la misma interfaz, pero no como principal: lo que se pidió es una app de escritorio, y en el navegador la herramienta queda mezclada con las pestañas de uso diario.

## Qué se pierde

- No hay un .app para abrir con doble clic ni instalador: se arranca desde la terminal. Para una herramienta propia de laboratorio alcanza. Queda anotado en docs/app-ideas.md.
- pywebview trae las dependencias de pyobjc en macOS. Si alguna vez fallan, la interfaz sigue funcionando en el navegador.

## Qué no depende de la cáscara

- Las restricciones de audio viven del lado de Python y valen con cualquier opción: el callback de sounddevice solo copia el bloque a una cola; el ritmo del audio va desacoplado del de la pantalla; por el socket viaja el resultado ya reducido; el pico se sostiene por bloque mirando todas las muestras.
- La prueba automática del contrato del WebSocket corre sin ventana: un cliente de aiohttp se conecta al servidor con la fuente sintética, pide un seno de 1 kHz a -6 dBFS y comprueba que el pico del espectro llegue en 1 kHz y a -6 dBFS.
- La estética sale del repo feuoir: las variables de apps/web/src/styles/theme.css, como --fire-orange, --fire-red y --fire-yellow, y la tipografía Inter que usa su interfaz.

## Decisiones de la primera versión

- Vive en app/, dentro de este repo. El servidor importa analizador.py directamente, sin copiarlo, y guarda en mediciones/ con la misma convención que medir.py.
- Cómo quedó construida, el contrato del WebSocket y sus pruebas están en docs/app.md.
- Se dibuja con TypeScript y canvas, sin framework. La forma de onda, el espectro y el medidor se redibujan con cada cuadro que llega, hasta 30 veces por segundo y al ritmo de la pantalla, y canvas los dibuja sin pasar por un árbol de componentes. Sin framework tampoco hay dónde guardar estado propio: cada cuadro se dibuja con lo último que llegó por el WebSocket. Los controles (el selector de entrada, los ajustes de la señal y los botones de medición) son elementos HTML comunes con el registro de feuoir: rótulos chicos en mayúsculas con tracking abierto, campos con una línea fina debajo y la línea de fuego en lo elegido.

## Fuentes

- Tauri, requisitos: https://v2.tauri.app/start/prerequisites/
- Tauri, qué es: https://v2.tauri.app/start/
- Tauri, sidecars: https://v2.tauri.app/develop/sidecar/
- Electron, introducción: https://www.electronjs.org/docs/latest/
- Electron, instalación y arquitecturas: https://www.electronjs.org/docs/latest/tutorial/installation
- PyPI: aiohttp, pywebview y pyobjc-core.
