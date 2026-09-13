"""Servidor de la app: entrega la interfaz y habla con ella por WebSocket en /ws.

Contrato, versión 1. Cada mensaje es un objeto JSON con un campo "tipo".

De Python a la interfaz:
  estado    al conectarse y cada vez que algo cambia: entradas, entrada elegida, señal, frecuencias
            de los puntos del espectro, mediciones disponibles y la que está en curso
  cuadro    hasta CUADROS_POR_SEGUNDO veces por segundo: forma de onda, espectro reducido en dBFS,
            pico del espectro, nivel y saturación (ver app/procesado.py)
  medicion  avance y final de una medición: estado en_curso, lista o error
  error     un pedido que no se pudo cumplir, con su mensaje

De la interfaz a Python:
  entrada              {"id": "sintetica" o el índice del dispositivo}
  senal                {"forma", "frecuencia_hz", "nivel_dbfs"}
  medir                {"medicion": "captura", "thd_n", "snr", "respuesta" o "jitter"}
  borrar_saturacion    vuelve a cero el aviso de saturación
  actualizar_entradas  vuelve a leer la lista de entradas de la Mac
"""
import asyncio
import json
import queue
import threading
from collections import deque
from pathlib import Path

import numpy as np
from aiohttp import WSMsgType, web

from app import fuentes, mediciones
from app.procesado import ONDA_MS, Procesador

CONTRATO = 1
CUADROS_POR_SEGUNDO = 30
INTERFAZ = Path(__file__).resolve().parent / "interfaz" / "dist"


class Motor:
    """Dueño de la fuente, la cola y el procesador. Un hilo saca bloques de la cola y los procesa."""

    def __init__(self, destino=mediciones.RAIZ / "mediciones"):
        self.destino = Path(destino)
        self.cola = queue.Queue(maxsize=64)
        self.senal = dict(fuentes.SENAL_POR_DEFECTO)
        self.entrada_id = "sintetica"
        self.fuente = fuentes.FuenteSintetica(self.cola, senal=self.senal)
        self.procesador = Procesador(self.fuente.fs)
        self.entradas = fuentes.listar_entradas()
        self.midiendo = None
        self._parar = threading.Event()
        self._hilo = threading.Thread(target=self._procesar, name="procesado", daemon=True)
        self._hilo.start()

    def _procesar(self):
        while not self._parar.is_set():
            try:
                x = self.cola.get(timeout=0.2)
            except queue.Empty:
                continue
            self.procesador.bloque(x)

    def estado(self):
        return {
            "tipo": "estado",
            "contrato": CONTRATO,
            "fs": self.procesador.fs,
            "entradas": self.entradas,
            "entrada": self.entrada_id,
            "senal": self.senal,
            "frecuencias_hz": np.round(self.procesador.frecuencias, 2).tolist(),
            "onda_ms": ONDA_MS,
            "mediciones": [{"id": m["id"], "nombre": m["nombre"]} for m in mediciones.MEDICIONES],
            "midiendo": self.midiendo,
        }

    def cambiar_entrada(self, entrada_id):
        if self.midiendo:
            raise ValueError("No se puede cambiar la entrada durante una medición")
        self.fuente.cerrar()
        while not self.cola.empty():
            self.cola.get_nowait()
        try:
            if entrada_id == "sintetica":
                fuente = fuentes.FuenteSintetica(self.cola, senal=self.senal)
            else:
                fuente = fuentes.FuenteDispositivo(self.cola, entrada_id)
        except Exception:
            fuente, entrada_id = fuentes.FuenteSintetica(self.cola, senal=self.senal), "sintetica"
            raise
        finally:
            self.procesador = Procesador(fuente.fs)
            self.fuente, self.entrada_id = fuente, entrada_id

    def configurar_senal(self, senal):
        self.senal = fuentes.validar_senal(senal)
        if isinstance(self.fuente, fuentes.FuenteSintetica):
            self.fuente.configurar(self.senal)

    def actualizar_entradas(self):
        # Con la fuente sintética no hay stream de PortAudio abierto, así que se puede reiniciar para ver
        # una interfaz recién conectada. Con una entrada real abierta solo se relee la lista.
        sintetica = isinstance(self.fuente, fuentes.FuenteSintetica)
        self.entradas = fuentes.listar_entradas(reiniciar=sintetica)

    def cerrar(self):
        self._parar.set()
        self._hilo.join()
        self.fuente.cerrar()


class Cliente:
    """Una conexión de la interfaz, con su propia tarea de escritura.

    Los mensajes de control (estado, medicion, error) salen todos y en orden. De los cuadros solo se
    guarda el último: si la conexión se atrasa, los cuadros viejos se descartan, y una conexión lenta
    no frena a las demás. Una saturación que caiga en un cuadro descartado sigue contada en los
    bloques y en hace_s de los cuadros siguientes.
    """

    def __init__(self, ws):
        self.ws = ws
        self._control = deque()
        self._cuadro = None
        self._hay = asyncio.Event()

    def mandar(self, texto):
        self._control.append(texto)
        self._hay.set()

    def mandar_cuadro(self, texto):
        self._cuadro = texto
        self._hay.set()

    async def escribir(self):
        try:
            while not self.ws.closed:
                await self._hay.wait()
                self._hay.clear()
                while self._control:
                    await self.ws.send_str(self._control.popleft())
                if self._cuadro is not None:
                    texto, self._cuadro = self._cuadro, None
                    await self.ws.send_str(texto)
        except (ConnectionError, RuntimeError):   # la conexión se cerró a mitad de un envío
            pass


def _difundir(app, mensaje):
    texto = json.dumps(mensaje, ensure_ascii=False)
    for cliente in list(app["clientes"]):
        cliente.mandar(texto)


async def _medir(app, medicion_id):
    motor, loop = app["motor"], asyncio.get_running_loop()

    def avisar(texto):
        loop.call_soon_threadsafe(_difundir, app, {
            "tipo": "medicion", "medicion": medicion_id, "estado": "en_curso", "mensaje": texto})

    _difundir(app, motor.estado())
    _difundir(app, {"tipo": "medicion", "medicion": medicion_id, "estado": "en_curso", "mensaje": "Midiendo"})
    try:
        carpeta, resumen = await asyncio.to_thread(mediciones.medir, medicion_id, motor.fuente, motor.procesador,
                                                   dict(motor.senal), motor.destino, avisar)
        mensaje = {"tipo": "medicion", "medicion": medicion_id, "estado": "lista",
                   "carpeta": f"{carpeta.parent.name}/{carpeta.name}/", "ruta": str(carpeta), "resumen": resumen}
    except Exception as e:
        mensaje = {"tipo": "medicion", "medicion": medicion_id, "estado": "error", "mensaje": str(e)}
    finally:
        motor.midiendo = None
    _difundir(app, mensaje)
    _difundir(app, motor.estado())


async def _atender(app, pedido):
    motor = app["motor"]
    tipo = pedido.get("tipo")
    if tipo == "entrada":
        try:
            await asyncio.to_thread(motor.cambiar_entrada, str(pedido["id"]))
        finally:
            _difundir(app, motor.estado())
    elif tipo == "senal":
        motor.configurar_senal(pedido)
        _difundir(app, motor.estado())
    elif tipo == "actualizar_entradas":
        await asyncio.to_thread(motor.actualizar_entradas)
        _difundir(app, motor.estado())
    elif tipo == "medir":
        if motor.midiendo:
            raise ValueError("Ya hay una medición en curso")
        if pedido.get("medicion") not in {m["id"] for m in mediciones.MEDICIONES}:
            raise ValueError(f"Medición desconocida: {pedido.get('medicion')!r}")
        # Se marca antes de crear la tarea: un segundo pedido puede llegar antes de que la tarea arranque.
        motor.midiendo = pedido["medicion"]
        tarea = asyncio.create_task(_medir(app, pedido["medicion"]))
        app["tareas"].add(tarea)
        tarea.add_done_callback(app["tareas"].discard)
    elif tipo == "borrar_saturacion":
        motor.procesador.borrar_saturacion()
    else:
        raise ValueError(f"Pedido desconocido: {tipo!r}")


async def _socket(request):
    ws = web.WebSocketResponse(heartbeat=10)
    await ws.prepare(request)
    app = request.app
    cliente = Cliente(ws)
    escritor = asyncio.create_task(cliente.escribir())
    app["clientes"].add(cliente)
    cliente.mandar(json.dumps(app["motor"].estado(), ensure_ascii=False))
    try:
        async for mensaje in ws:
            if mensaje.type != WSMsgType.TEXT:
                continue
            try:
                await _atender(app, json.loads(mensaje.data))
            except Exception as e:      # el pedido falla, la conexión sigue
                cliente.mandar(json.dumps({"tipo": "error", "mensaje": str(e)}, ensure_ascii=False))
    finally:
        app["clientes"].discard(cliente)
        escritor.cancel()
    return ws


async def _emitir(app):
    while True:
        await asyncio.sleep(1/CUADROS_POR_SEGUNDO)
        if app["clientes"]:
            texto = json.dumps(app["motor"].procesador.cuadro(), ensure_ascii=False)
            for cliente in list(app["clientes"]):
                cliente.mandar_cuadro(texto)


async def _indice(request):
    if (INTERFAZ / "index.html").exists():
        return web.FileResponse(INTERFAZ / "index.html")
    return web.Response(text="La interfaz no está compilada. En app/interfaz: npm install y npm run build.\n")


async def _archivo(request):
    ruta = INTERFAZ / request.match_info["archivo"]
    if ruta.parent != INTERFAZ or not ruta.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(ruta)


def crear_app(motor):
    app = web.Application()
    app["motor"], app["clientes"], app["tareas"] = motor, set(), set()
    app.router.add_get("/ws", _socket)
    app.router.add_get("/", _indice)
    if (INTERFAZ / "assets").is_dir():
        app.router.add_static("/assets", INTERFAZ / "assets")
    app.router.add_get("/{archivo}", _archivo)

    async def al_arrancar(app):
        app["emisor"] = asyncio.create_task(_emitir(app))

    async def al_cerrar(app):
        app["emisor"].cancel()

    app.on_startup.append(al_arrancar)
    app.on_cleanup.append(al_cerrar)
    return app


def arrancar_en_hilo(motor, puerto=0):
    """Levanta el servidor en 127.0.0.1 en un hilo propio y devuelve el puerto."""
    listo, datos = threading.Event(), {}

    def correr():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        runner = web.AppRunner(crear_app(motor))
        loop.run_until_complete(runner.setup())
        loop.run_until_complete(web.TCPSite(runner, "127.0.0.1", puerto).start())
        datos["puerto"] = runner.addresses[0][1]
        listo.set()
        loop.run_forever()

    threading.Thread(target=correr, name="servidor", daemon=True).start()
    if not listo.wait(10):
        raise RuntimeError("el servidor no arrancó en 10 segundos")
    return datos["puerto"]
