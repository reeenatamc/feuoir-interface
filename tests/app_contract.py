#!/usr/bin/env python3
"""Tests the live measurement app without a window: a WebSocket client plays the interface.

    .venv/bin/python tests/app_contract.py

Starts the server from app/server.py on a free port, with the synthetic source and the measurements saved
to a temporary folder, and connects the way the interface does. Checks the contract: a 1 kHz sine at -6 dBFS
has to arrive as the spectrum peak at 1 kHz and -6 dBFS, clipping has to be reported and remembered, and each
measurement has to save its folder with its conditions. It also tests the processing with hand-built blocks:
a single clipped sample between two frames cannot be lost. It takes about a minute, because the synthetic
source delivers audio in real time. The checks are printed in Spanish.
"""
import asyncio
import base64
import ctypes
import json
import os
import socket
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from aiohttp import ClientSession, web

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import analizador as an  # noqa: E402
import device_volume  # noqa: E402
from app import sources  # noqa: E402
from app.processing import Processor  # noqa: E402
from app.server import Engine, create_app  # noqa: E402

FAILED = []
CHECKED = []


def check(name, condition, detail=""):
    print(f"{'ok    ' if condition else 'FALLA '} {name}" + (f"  ({detail})" if detail and not condition else ""))
    CHECKED.append(name)
    if not condition:
        FAILED.append(name)


def processing():
    fs = 48000
    p = Processor(fs)
    click = np.zeros(1024)
    click[701] = -1.0                 # an odd sample: a detector that skipped samples would miss it
    for block in (click, np.zeros(1024), np.zeros(1024)):
        p.block(block)
    q = p.frame()
    check("procesado: una sola muestra en fondo de escala entre dos cuadros enciende la saturación",
          q["clipping"]["now"] and q["clipping"]["blocks"] == 1, q["clipping"])
    check("procesado: el cuadro siguiente ya no dice saturando, pero la recuerda",
          (lambda c: not c["now"] and c["blocks"] == 1)(p.frame()["clipping"]))

    p = Processor(fs)
    p.block(an.tono(1000.0, fs, 1024/fs, -1.0))
    p.block(an.tono(1000.0, fs, 1024/fs, -20.0))
    q = p.frame()
    check("procesado: el pico se sostiene de un bloque al otro hasta el cuadro",
          abs(q["level"]["peak_dbfs"] + 1.0) < 0.05, q["level"])


def devices():
    """The real input's playback and the output check, with sounddevice replaced so nothing plays."""
    fs = 48000
    calls = []
    real_play, real_check = sources.sd.play, sources.sd.check_output_settings
    try:
        sources.sd.play = lambda x, samplerate, device=None: calls.append((samplerate, device))
        sources.DeviceSource.play(SimpleNamespace(fs=fs), np.zeros(8), 7)
        check("entrada real: el estímulo suena por la salida elegida", calls == [(fs, 7)], calls)

        def refuse(**settings):
            raise sources.sd.PortAudioError("no acepta")

        sources.sd.check_output_settings = refuse
        try:
            sources.check_output(7, fs)
            refused = ""
        except ValueError as e:
            refused = str(e)
        check("una salida que no acepta 48 kHz se rechaza con un aviso", "48000 Hz" in refused, refused)
    finally:
        sources.sd.play, sources.sd.check_output_settings = real_play, real_check


class FakeDevice:
    """Stands in for a real input: a synthetic source inside, and it records the output each stimulus asked for."""
    outputs_used = []

    def __init__(self, blocks, index):
        self.inner = sources.SyntheticSource(blocks, signal={"shape": "silence", "frequency_hz": 1000.0, "level_dbfs": -6.0})
        self.fs, self.index, self.name = self.inner.fs, int(index), "Entrada de prueba"

    def describe(self):
        return {"tipo": "dispositivo", "nombre": self.name, "indice": self.index, "bloques_perdidos": 0}

    def play(self, x, output=None):
        FakeDevice.outputs_used.append(output)
        self.inner.play(x)

    def close(self):
        self.inner.close()


class Client:
    def __init__(self, ws, fs):
        self.ws, self.fs = ws, fs

    async def send(self, **message):
        await self.ws.send_json(message)

    async def wait_for(self, condition, timeout_s=10.0):
        """The first message that meets the condition."""
        async with asyncio.timeout(timeout_s):
            async for incoming in self.ws:
                data = json.loads(incoming.data)
                if condition(data):
                    return data
        raise ConnectionError("el servidor cerró el WebSocket")

    async def signal(self, **signal):
        """Asks for a signal and returns a frame whose spectrum window is already full of it."""
        await self.send(type="signal", **signal)
        await self.wait_for(lambda d: d["type"] == "state" and d["signal"] == signal)
        first = await self.wait_for(lambda d: d["type"] == "frame")
        return await self.wait_for(lambda d: d["type"] == "frame" and d["samples"] >= first["samples"] + 0.4*self.fs)

    async def measure(self, measurement, timeout_s):
        await self.send(type="measure", measurement=measurement)
        return await self.wait_for(lambda d: d["type"] == "measurement" and d["status"] != "running", timeout_s)


def read_json(path, name):
    return json.loads((Path(path) / name).read_text(encoding="utf-8"))


def silent_client(port):
    """Opens /ws with a tiny receive buffer and never reads: the buffer fills right away."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    s.connect(("127.0.0.1", port))
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall((f"GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
    return s


async def contract(tmp):
    # Device lists and the real input are fakes, so the test does not depend on the Mac's devices and nothing
    # plays through the speakers.
    sources.list_inputs = lambda: [{"id": "synthetic", "name": sources.SyntheticSource.name},
                                   {"id": "99", "name": "Entrada de prueba"}]
    sources.list_outputs = lambda: [{"id": "default", "name": "Salida por defecto (prueba)"},
                                    {"id": "7", "name": "Salida de prueba"}]
    sources.check_output = lambda index, fs: None
    sources.DeviceSource = FakeDevice
    engine = Engine(destination=tmp / "mediciones")
    opened = []
    engine.open_path = opened.append      # records what was asked to open instead of opening Finder
    runner = web.AppRunner(create_app(engine))
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    port = runner.addresses[0][1]
    try:
        async with ClientSession() as session, session.ws_connect(f"http://127.0.0.1:{port}/ws") as ws:
            state = json.loads((await ws.receive()).data)
            check("al conectarse llega el estado con el contrato 3", state["type"] == "state" and state["contract"] == 3)
            check("estado: 512 puntos de espectro y 5 mediciones",
                  len(state["frequencies_hz"]) == 512 and len(state["measurements"]) == 5)
            check("estado: las salidas con la de por defecto primero, y elegida la de por defecto",
                  state["outputs"][0]["id"] == "default" and state["output"] == "default", state["outputs"])
            c = Client(ws, state["sample_rate"])
            frequencies = np.array(state["frequencies_hz"])
            half_step = np.sqrt(frequencies[1]/frequencies[0])

            q = await c.signal(shape="sine", frequency_hz=1000.0, level_dbfs=-6.0)
            spectrum = np.array(q["spectrum_dbfs"])
            k = int(np.argmax(spectrum))
            check("seno de 1 kHz a -6 dBFS: el máximo del espectro cae en el punto que contiene 1 kHz",
                  frequencies[k]/half_step <= 1000.0 < frequencies[k]*half_step, f"{frequencies[k]:.1f} Hz")
            check("seno de 1 kHz a -6 dBFS: el máximo del espectro vale -6 dBFS",
                  abs(spectrum[k] + 6.0) <= 0.1, f"{spectrum[k]} dBFS")
            peak = q["spectrum_peak"]
            check("seno de 1 kHz a -6 dBFS: el pico marcado dice 1 kHz y -6 dBFS",
                  peak is not None and abs(peak["frequency_hz"] - 1000.0) <= 0.5 and abs(peak["level_dbfs"] + 6.0) <= 0.1, peak)
            check("seno de 1 kHz a -6 dBFS: pico -6 y RMS -9.03 dBFS",
                  abs(q["level"]["peak_dbfs"] + 6.0) <= 0.1 and abs(q["level"]["rms_dbfs"] + 9.03) <= 0.1, q["level"])
            check("seno de 1 kHz a -6 dBFS: sin saturación", not q["clipping"]["now"] and q["clipping"]["blocks"] == 0)
            check("seno de 1 kHz a -6 dBFS: forma de onda de 10 ms", len(q["waveform"]) == round(0.010*c.fs))

            q = await c.signal(shape="sine", frequency_hz=1002.5, level_dbfs=-6.0)
            peak = q["spectrum_peak"]
            check("tono entre dos bins, 1002.5 Hz: el pico marcado sigue en -6 dBFS",
                  peak is not None and abs(peak["level_dbfs"] + 6.0) <= 0.1 and abs(peak["frequency_hz"] - 1002.5) <= 0.5, peak)

            q = await c.signal(shape="sine", frequency_hz=10000.0, level_dbfs=-6.0)
            spectrum = np.array(q["spectrum_dbfs"])
            check("seno de 10 kHz, donde cada punto junta decenas de bins: el máximo sigue en -6 dBFS",
                  abs(spectrum.max() + 6.0) <= 0.1, f"{spectrum.max()} dBFS")

            await c.send(type="signal", shape="sine", frequency_hz=1000.0, level_dbfs=2.0)
            q = await c.wait_for(lambda d: d["type"] == "frame" and d["clipping"]["now"])
            check("seno a +2 dBFS: avisa saturación con el pico en 0 dBFS", q["level"]["peak_dbfs"] >= -0.01, q["level"])

            q = await c.signal(shape="sine", frequency_hz=1000.0, level_dbfs=-6.0)
            clipping = q["clipping"]
            check("de vuelta a -6 dBFS: deja de saturar pero lo recuerda",
                  not clipping["now"] and clipping["blocks"] > 0 and clipping["seconds_ago"] is not None
                  and clipping["seconds_ago"] >= 0.3, clipping)
            await c.send(type="clear_clipping")
            q = await c.wait_for(lambda d: d["type"] == "frame" and d["clipping"]["blocks"] == 0, 2.0)
            check("borrar el aviso vuelve la saturación a cero", q["clipping"]["seconds_ago"] is None)

            slow = silent_client(port)
            try:
                clock = asyncio.get_running_loop().time
                arrivals, end = [], clock() + 6.0
                while clock() < end:
                    d = await c.wait_for(lambda d: d["type"] == "frame", 2.0)
                    arrivals.append((clock(), d["samples"]))
                last = [samples for t, samples in arrivals if t >= end - 2.0]
                progress = (last[-1] - last[0])/c.fs if len(last) > 1 else 0.0
                check("una conexión que no lee no frena los cuadros de las demás", progress >= 1.5,
                      f"{progress:.2f} s de audio en los últimos 2 s")
            finally:
                slow.close()

            await c.send(type="signal", shape="square", frequency_hz=1000.0, level_dbfs=-6.0)
            error = await c.wait_for(lambda d: d["type"] == "error")
            check("una forma desconocida responde con un error que la nombra", "square" in error["message"], error)

            await c.send(type="refresh_devices")
            state = await c.wait_for(lambda d: d["type"] == "state")
            q = await c.signal(shape="sine", frequency_hz=1000.0, level_dbfs=-6.0)
            check("buscar entradas con la fuente sintética reinicia PortAudio sin cortar los cuadros",
                  state["inputs"][0]["id"] == "synthetic" and abs(q["level"]["peak_dbfs"] + 6.0) <= 0.1)

            for shape, label, expected in (("sweep", "barrido", -23.0), ("noise", "ruido", -20.0), ("silence", "silencio", -100.0)):
                q = await c.signal(shape=shape, frequency_hz=1000.0, level_dbfs=-20.0)
                rms = q["level"]["rms_dbfs"]
                check(f"forma {label}: RMS cerca de {expected} dBFS", abs(rms - expected) <= 1.5, f"{rms} dBFS")

            await c.signal(shape="sine", frequency_hz=1000.0, level_dbfs=-6.0)
            r = await c.measure("capture", 20)
            check("captura: termina y guarda su carpeta", r["status"] == "done" and Path(r["path"]).is_dir(), r)
            if r["status"] == "done":
                conditions, result = read_json(r["path"], "condiciones.json"), read_json(r["path"], "resultado.json")
                check("captura: condiciones con entrada sintética, 48 kHz y sin estímulo",
                      conditions["entrada"]["tipo"] == "sintetica" and conditions["frecuencia_muestreo_hz"] == 48000
                      and conditions["estimulo"] is None and (Path(r["path"]) / "captura.wav").is_file(), conditions)
                check("captura: pico -6 dBFS", abs(result["pico_dbfs"] + 6.0) <= 0.1, result)

            await c.send(type="measure", measurement="thd_n")
            await c.send(type="measure", measurement="snr")
            error = await c.wait_for(lambda d: d["type"] == "error")
            check("una segunda medición mientras corre la primera responde con error", "en curso" in error["message"], error)
            r = await c.wait_for(lambda d: d["type"] == "measurement" and d["status"] != "running", 20)
            check("THD+N: termina y guarda su carpeta", r["status"] == "done", r)
            if r["status"] == "done":
                conditions, result = read_json(r["path"], "condiciones.json"), read_json(r["path"], "resultado.json")
                check("THD+N: condiciones con el tono de 1 kHz a -6 dBFS",
                      conditions["medicion"] == "THD+N" and conditions["estimulo"]["tono_hz"] == 1000.0
                      and conditions["estimulo"]["nivel_dbfs"] == -6.0, conditions)
                check("THD+N: con el ruido de -100 dBFS da menos de -85 dB", result["db"] < -85.0, result)

            r = await c.measure("snr", 20)
            check("SNR: termina y guarda su carpeta", r["status"] == "done", r)
            if r["status"] == "done":
                result = read_json(r["path"], "resultado.json")
                check("SNR: entre 85 y 98 dB con el tono a -6 dBFS y ruido a -100 dBFS", 85.0 < result["snr_db"] < 98.0, result)

            r = await c.measure("response", 60)
            check("respuesta en frecuencia: termina y guarda su carpeta", r["status"] == "done", r)
            if r["status"] == "done":
                conditions, rows = read_json(r["path"], "condiciones.json"), read_json(r["path"], "resultado.json")["filas"]
                tones = len(an.frecuencias_log(20.0, 20000.0, 3))
                deviation = max(abs(row["nivel_dbfs"] + 6.0) for row in rows)
                check(f"respuesta en frecuencia: {tones} tonos, planos en -6 dBFS a 0.2 dB",
                      len(rows) == tones == conditions["estimulo"]["tonos"] and deviation <= 0.2,
                      f"{len(rows)} tonos, desvío {deviation:.3f} dB")

            r = await c.measure("jitter", 60)
            check("prueba de jitter: termina y guarda su carpeta", r["status"] == "done", r)
            if r["status"] == "done":
                result = read_json(r["path"], "resultado.json")
                check("prueba de jitter: la fuente sintética no tiene jitter",
                      result["veredicto"] == "sin_efecto_detectable", result["veredicto"])

            folders = sorted(p.name for p in (tmp / "mediciones").iterdir())
            check("cinco carpetas en mediciones/, una por medición", len(folders) == 5, folders)

            await c.send(type="list_saved")
            saved = (await c.wait_for(lambda d: d["type"] == "saved"))["measurements"]
            check("guardadas: las cinco, de la más reciente a la más vieja y con su resumen",
                  len(saved) == 5 and saved[0]["measurement"] == "Prueba de jitter"
                  and saved[-1]["measurement"] == "Captura de 5 s" and all(s["summary"] for s in saved),
                  [s["measurement"] for s in saved])
            if saved:
                await c.send(type="open_saved", folder=saved[0]["folder"])
                await c.send(type="open_saved", folder="..")
                error = await c.wait_for(lambda d: d["type"] == "error")
                await c.send(type="open_saved", folder=None)
                await c.send(type="list_saved")
                await c.wait_for(lambda d: d["type"] == "saved")
                expected = [(tmp / "mediciones" / saved[0]["folder"]).resolve(), (tmp / "mediciones").resolve()]
                check("abrir una guardada abre la medición y la carpeta de mediciones, y rechaza una ruta que sale de ella",
                      [Path(p).resolve() for p in opened] == expected and "No existe" in error["message"], (opened, error))

            await c.send(type="output", id="12345")
            error = await c.wait_for(lambda d: d["type"] == "error")
            check("una salida que no existe responde con un error", "No existe la salida" in error["message"], error)

            await c.send(type="output", id="7")
            await c.wait_for(lambda d: d["type"] == "state" and d["output"] == "7")
            await c.send(type="input", id="99")
            await c.wait_for(lambda d: d["type"] == "state" and d["input"] == "99")
            r = await c.measure("thd_n", 20)
            check("con una entrada real, la medición termina", r["status"] == "done", r)
            if r["status"] == "done":
                used = read_json(r["path"], "condiciones.json")["salida_del_estimulo"]
                check("con una entrada real, el estímulo suena por la salida elegida y queda en las condiciones",
                      set(FakeDevice.outputs_used) == {7}
                      and used == {"tipo": "dispositivo", "nombre": "Salida de prueba", "indice": 7},
                      (FakeDevice.outputs_used, used))
    finally:
        await runner.cleanup()
        engine.close()


def volumes():
    """The volume saved in condiciones.json, read from Core Audio for any device, against two references on this
    Mac: osascript, which only knows the default input, and Core Audio's own conversion of that volume to dB."""
    import sounddevice as sd
    name = sd.query_devices(kind="input")["name"]
    r = subprocess.run(["osascript", "-e", "input volume of (get volume settings)"], capture_output=True, text=True)
    reference = int(r.stdout) if r.stdout.strip().isdigit() else None
    volume = device_volume.input_volume(name)
    check(f"volumen: el de la entrada por defecto ({name}) coincide con osascript", volume == reference,
          (volume, reference))

    gain_db = device_volume.input_gain_db(name)
    device_id = device_volume._find(name)
    converted = None
    for element in (0, 1):
        addr = device_volume._Address(device_volume._fourcc("v2db"), device_volume.SCOPE_INPUT, element)
        scalar = device_volume._input_value(device_id, device_volume.VOLUME_SCALAR)
        if scalar is None or not device_volume._ca.AudioObjectHasProperty(device_id, ctypes.byref(addr)):
            continue
        value, size = ctypes.c_float(scalar), ctypes.c_uint32(4)
        if not device_volume._ca.AudioObjectGetPropertyData(device_id, ctypes.byref(addr), 0, None,
                                                            ctypes.byref(size), ctypes.byref(value)):
            converted = round(value.value, 2)
            break
    check("volumen: la ganancia en dB coincide con la conversión de Core Audio",
          gain_db is not None and converted is not None and abs(gain_db - converted) <= 0.01, (gain_db, converted))
    check("volumen: una entrada que no existe da None, no un número",
          device_volume.input_volume("no existe") is None and device_volume.input_gain_db("no existe") is None)


def main():
    processing()
    devices()
    volumes()
    with tempfile.TemporaryDirectory(prefix="app-") as tmp:
        try:
            asyncio.run(contract(Path(tmp)))
        except TimeoutError:
            traceback.print_exc()
            check("el servidor responde a tiempo: la prueba se cortó esperando un mensaje", False)
    if FAILED:
        print(f"\nFALLA  {len(FAILED)} casos de la app sin ventana", file=sys.stderr)
        sys.exit(1)
    print(f"\nPasan los {len(CHECKED)} casos de la app. La ventana y la entrada real se prueban a mano.")


if __name__ == "__main__":
    main()
