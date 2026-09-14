# Ideas para la app de medición en vivo

Lo que falta o se podría sumar, anotado en vez de construido. La primera versión es a propósito pequeña.

- Empaquetar la app como .app para abrirla con doble clic. Hoy se arranca desde la terminal (docs/app-cascara.md, qué se pierde).
- Hacer sonar la señal de prueba en vivo por la salida de la Mac, no solo durante las mediciones, para ajustar el nivel de la entrada mirando el medidor.
- Guardar junto a cada medición un PNG con la forma de onda y el espectro, como hace medir.py.
- Escribir notas para cada medición, como --notas en medir.py. Hoy condiciones.json las guarda vacías.
- Elegir el canal de la entrada. Hoy se toma el primero.
- Cambiar la duración de la forma de onda, hoy de 10 ms, sin tocar el código.
- Ver una interfaz recién conectada sin pasar antes por la fuente sintética.
- Una prueba automática de la interfaz en el navegador. Hoy lo que dibuja se revisa con capturas.
- Grabar tomas largas, con empezar y parar, además de la captura de 5 s. Para grabar música no hace falta la app: cuando la interfaz aparezca como entrada de audio de la Mac, cualquier programa de grabación la puede usar.
- Ver dentro de la app el resultado de una medición guardada, con su gráfico. Hoy se abre su carpeta en Finder.
