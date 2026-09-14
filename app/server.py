"""App server: serves the interface and talks to it over a WebSocket at /ws.

Contract, version 2. Every message is a JSON object with a "type" field. Keys and values the code reads are
in English; text meant for the user (names, summaries, error messages) comes in Spanish.

From Python to the interface:
  state        on connect and whenever something changes: inputs, chosen input, signal, frequencies of the
               spectrum points, available measurements and the one running
  frame        up to FRAMES_PER_SECOND times per second: waveform, reduced spectrum in dBFS, spectrum peak,
               level and clipping (see app/processing.py)
  measurement  progress and end of a measurement: status running, done or error
  saved        the list of saved measurements, when asked for
  error        a request that could not be fulfilled, with its message

From the interface to Python:
  input           {"id": "synthetic" or the device index}
  signal          {"shape", "frequency_hz", "level_dbfs"}
  measure         {"measurement": "capture", "thd_n", "snr", "response" or "jitter"}
  clear_clipping  resets the clipping warning
  refresh_inputs  reads the Mac's input list again
  list_saved      asks for the list of saved measurements
  open_saved      {"folder": name or null}: opens that measurement, or the measurements folder, in Finder
"""
import asyncio
import json
import queue
import subprocess
import threading
from collections import deque
from pathlib import Path

import numpy as np
from aiohttp import WSMsgType, web

from app import measurements, sources
from app.processing import WAVEFORM_MS, Processor

CONTRACT = 2
FRAMES_PER_SECOND = 30
UI_DIST = Path(__file__).resolve().parent / "ui" / "dist"


class Engine:
    """Owns the source, the block queue and the processor. A thread takes blocks off the queue and processes them."""

    def __init__(self, destination=measurements.ROOT / "mediciones"):
        self.destination = Path(destination)
        self.blocks = queue.Queue(maxsize=64)
        self.signal = dict(sources.DEFAULT_SIGNAL)
        self.input_id = "synthetic"
        self.source = sources.SyntheticSource(self.blocks, signal=self.signal)
        self.processor = Processor(self.source.fs)
        self.inputs = sources.list_inputs()
        self.measuring = None
        self.open_path = lambda path: subprocess.run(["open", str(path)], check=False)   # the test replaces it
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._process, name="processing", daemon=True)
        self._thread.start()

    def _process(self):
        while not self._stop.is_set():
            try:
                x = self.blocks.get(timeout=0.2)
            except queue.Empty:
                continue
            self.processor.block(x)

    def state(self):
        return {
            "type": "state",
            "contract": CONTRACT,
            "sample_rate": self.processor.fs,
            "inputs": self.inputs,
            "input": self.input_id,
            "signal": self.signal,
            "frequencies_hz": np.round(self.processor.frequencies, 2).tolist(),
            "waveform_ms": WAVEFORM_MS,
            "measurements": [{"id": m["id"], "name": m["name"]} for m in measurements.MEASUREMENTS],
            "measuring": self.measuring,
        }

    def change_input(self, input_id):
        if self.measuring:
            raise ValueError("No se puede cambiar la entrada durante una medición")
        self.source.close()
        while not self.blocks.empty():
            self.blocks.get_nowait()
        try:
            if input_id == "synthetic":
                source = sources.SyntheticSource(self.blocks, signal=self.signal)
            else:
                source = sources.DeviceSource(self.blocks, input_id)
        except Exception:
            source, input_id = sources.SyntheticSource(self.blocks, signal=self.signal), "synthetic"
            raise
        finally:
            self.processor = Processor(source.fs)
            self.source, self.input_id = source, input_id

    def configure_signal(self, signal):
        self.signal = sources.validate_signal(signal)
        if isinstance(self.source, sources.SyntheticSource):
            self.source.configure(self.signal)

    def refresh_inputs(self):
        # With the synthetic source no PortAudio stream is open, so PortAudio can be restarted to find an
        # interface plugged in after startup. With a real input open, the list is only read again.
        self.inputs = sources.list_inputs(restart=isinstance(self.source, sources.SyntheticSource))

    def saved_path(self, folder):
        """The folder of a saved measurement, or the measurements folder when folder is None.

        Only a folder directly inside destination is accepted: the interface cannot ask to open any path on
        the Mac.
        """
        if folder is None:
            self.destination.mkdir(parents=True, exist_ok=True)
            return self.destination
        path = (self.destination / str(folder)).resolve()
        if path.parent != self.destination.resolve() or not path.is_dir():
            raise ValueError(f"No existe la medición guardada {folder!r}")
        return path

    def close(self):
        self._stop.set()
        self._thread.join()
        self.source.close()


class Client:
    """One interface connection, with its own writer task.

    Control messages (state, measurement, saved, error) all go out, in order. Of the frames only the latest
    is kept: if the connection falls behind, old frames are dropped, and a slow connection does not hold
    back the others. A clip that lands in a dropped frame is still counted in the blocks and seconds_ago of
    the following frames.
    """

    def __init__(self, ws):
        self.ws = ws
        self._control = deque()
        self._frame = None
        self._pending = asyncio.Event()

    def send(self, text):
        self._control.append(text)
        self._pending.set()

    def send_frame(self, text):
        self._frame = text
        self._pending.set()

    async def write(self):
        try:
            while not self.ws.closed:
                await self._pending.wait()
                self._pending.clear()
                while self._control:
                    await self.ws.send_str(self._control.popleft())
                if self._frame is not None:
                    text, self._frame = self._frame, None
                    await self.ws.send_str(text)
        except (ConnectionError, RuntimeError):   # the connection closed in the middle of a send
            pass


ENGINE = web.AppKey("engine", Engine)
CLIENTS = web.AppKey("clients", set)
TASKS = web.AppKey("tasks", set)
EMITTER = web.AppKey("emitter", asyncio.Task)


def _broadcast(app, message):
    text = json.dumps(message, ensure_ascii=False)
    for client in list(app[CLIENTS]):
        client.send(text)


async def _measure(app, measurement_id):
    engine, loop = app[ENGINE], asyncio.get_running_loop()

    def notify(text):
        loop.call_soon_threadsafe(_broadcast, app, {
            "type": "measurement", "measurement": measurement_id, "status": "running", "message": text})

    _broadcast(app, engine.state())
    _broadcast(app, {"type": "measurement", "measurement": measurement_id, "status": "running", "message": "Midiendo"})
    try:
        folder, summary = await asyncio.to_thread(measurements.measure, measurement_id, engine.source, engine.processor,
                                                  dict(engine.signal), engine.destination, notify)
        message = {"type": "measurement", "measurement": measurement_id, "status": "done", "folder_name": folder.name,
                   "folder": f"{folder.parent.name}/{folder.name}/", "path": str(folder), "summary": summary}
    except Exception as e:
        message = {"type": "measurement", "measurement": measurement_id, "status": "error", "message": str(e)}
    finally:
        engine.measuring = None
    _broadcast(app, message)
    _broadcast(app, engine.state())


async def _handle(app, message):
    engine = app[ENGINE]
    kind = message.get("type")
    if kind == "input":
        try:
            await asyncio.to_thread(engine.change_input, str(message["id"]))
        finally:
            _broadcast(app, engine.state())
    elif kind == "signal":
        engine.configure_signal(message)
        _broadcast(app, engine.state())
    elif kind == "refresh_inputs":
        await asyncio.to_thread(engine.refresh_inputs)
        _broadcast(app, engine.state())
    elif kind == "measure":
        if engine.measuring:
            raise ValueError("Ya hay una medición en curso")
        if message.get("measurement") not in {m["id"] for m in measurements.MEASUREMENTS}:
            raise ValueError(f"Medición desconocida: {message.get('measurement')!r}")
        # Marked before creating the task: a second request can arrive before the task starts.
        engine.measuring = message["measurement"]
        task = asyncio.create_task(_measure(app, message["measurement"]))
        app[TASKS].add(task)
        task.add_done_callback(app[TASKS].discard)
    elif kind == "clear_clipping":
        engine.processor.clear_clipping()
    elif kind == "list_saved":
        saved = await asyncio.to_thread(measurements.list_saved, engine.destination)
        _broadcast(app, {"type": "saved", "measurements": saved})
    elif kind == "open_saved":
        await asyncio.to_thread(engine.open_path, engine.saved_path(message.get("folder")))
    else:
        raise ValueError(f"Pedido desconocido: {kind!r}")


async def _socket(request):
    ws = web.WebSocketResponse(heartbeat=10)
    await ws.prepare(request)
    app = request.app
    client = Client(ws)
    writer = asyncio.create_task(client.write())
    app[CLIENTS].add(client)
    client.send(json.dumps(app[ENGINE].state(), ensure_ascii=False))
    try:
        async for incoming in ws:
            if incoming.type != WSMsgType.TEXT:
                continue
            try:
                await _handle(app, json.loads(incoming.data))
            except Exception as e:      # the request fails, the connection stays
                client.send(json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False))
    finally:
        app[CLIENTS].discard(client)
        writer.cancel()
    return ws


async def _emit(app):
    while True:
        await asyncio.sleep(1/FRAMES_PER_SECOND)
        if app[CLIENTS]:
            text = json.dumps(app[ENGINE].processor.frame(), ensure_ascii=False)
            for client in list(app[CLIENTS]):
                client.send_frame(text)


async def _index(request):
    if (UI_DIST / "index.html").exists():
        return web.FileResponse(UI_DIST / "index.html")
    return web.Response(text="La interfaz no está compilada. En app/ui: npm install y npm run build.\n")


async def _file(request):
    path = UI_DIST / request.match_info["name"]
    if path.parent != UI_DIST or not path.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(path)


def create_app(engine):
    app = web.Application()
    app[ENGINE], app[CLIENTS], app[TASKS] = engine, set(), set()
    app.router.add_get("/ws", _socket)
    app.router.add_get("/", _index)
    if (UI_DIST / "assets").is_dir():
        app.router.add_static("/assets", UI_DIST / "assets")
    app.router.add_get("/{name}", _file)

    async def on_startup(app):
        app[EMITTER] = asyncio.create_task(_emit(app))

    async def on_cleanup(app):
        app[EMITTER].cancel()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


def start_in_thread(engine, port=0):
    """Starts the server on 127.0.0.1 in its own thread and returns the port."""
    ready, info = threading.Event(), {}

    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        runner = web.AppRunner(create_app(engine))
        loop.run_until_complete(runner.setup())
        loop.run_until_complete(web.TCPSite(runner, "127.0.0.1", port).start())
        info["port"] = runner.addresses[0][1]
        ready.set()
        loop.run_forever()

    threading.Thread(target=run, name="server", daemon=True).start()
    if not ready.wait(10):
        raise RuntimeError("El servidor no arrancó en 10 segundos")
    return info["port"]
