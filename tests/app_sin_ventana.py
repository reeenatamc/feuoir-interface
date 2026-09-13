#!/usr/bin/env python3
"""Prueba la app de medición sin ventana: un cliente WebSocket hace de interfaz.

    .venv/bin/python tests/app_sin_ventana.py

Levanta el servidor de app/servidor.py en un puerto libre, con la fuente sintética y las
mediciones guardándose en una carpeta temporal, y se conecta como lo haría la interfaz. Comprueba
el contrato: un seno de 1 kHz a -6 dBFS tiene que llegar como pico del espectro en 1 kHz y a
-6 dBFS, la saturación tiene que avisarse y quedar marcada, y cada medición tiene que guardar su
carpeta con sus condiciones. Aparte prueba el procesado con bloques armados a mano: un recorte de
una sola muestra entre dos cuadros no se puede perder. Tarda cerca de un minuto, porque la fuente
sintética entrega el audio a ritmo real.
"""
import asyncio
import base64
import json
import os
import socket
import sys
import tempfile
import traceback
from pathlib import Path

import numpy as np
from aiohttp import ClientSession, web

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import analizador as an  # noqa: E402
from app.procesado import Procesador  # noqa: E402
from app.servidor import Motor, crear_app  # noqa: E402

CASOS_FALLIDOS = []


def comprobar(nombre, condicion, detalle=""):
    print(f"{'ok    ' if condicion else 'FALLA '} {nombre}" + (f"  ({detalle})" if detalle and not condicion else ""))
    if not condicion:
        CASOS_FALLIDOS.append(nombre)


def procesado():
    fs = 48000
    p = Procesador(fs)
    clic = np.zeros(1024)
    clic[701] = -1.0                 # una muestra impar: un detector que salteara muestras no la vería
    for bloque in (clic, np.zeros(1024), np.zeros(1024)):
        p.bloque(bloque)
    q = p.cuadro()
    comprobar("procesado: una sola muestra en fondo de escala entre dos cuadros enciende la saturación",
              q["saturacion"]["ahora"] and q["saturacion"]["bloques"] == 1, q["saturacion"])
    comprobar("procesado: el cuadro siguiente ya no dice saturando, pero la recuerda",
              (lambda s: not s["ahora"] and s["bloques"] == 1)(p.cuadro()["saturacion"]))

    p = Procesador(fs)
    p.bloque(an.tono(1000.0, fs, 1024/fs, -1.0))
    p.bloque(an.tono(1000.0, fs, 1024/fs, -20.0))
    q = p.cuadro()
    comprobar("procesado: el pico se sostiene de un bloque al otro hasta el cuadro",
              abs(q["nivel"]["pico_dbfs"] + 1.0) < 0.05, q["nivel"])


class Cliente:
    def __init__(self, ws, fs):
        self.ws, self.fs = ws, fs

    async def enviar(self, **pedido):
        await self.ws.send_json(pedido)

    async def esperar(self, condicion, limite_s=10.0):
        """El primer mensaje que cumple la condición."""
        async with asyncio.timeout(limite_s):
            async for mensaje in self.ws:
                datos = json.loads(mensaje.data)
                if condicion(datos):
                    return datos
        raise ConnectionError("el servidor cerró el WebSocket")

    async def senal(self, **senal):
        """Pide una señal y devuelve un cuadro cuya ventana de espectro ya se llenó con ella."""
        await self.enviar(tipo="senal", **senal)
        await self.esperar(lambda d: d["tipo"] == "estado" and d["senal"] == senal)
        primero = await self.esperar(lambda d: d["tipo"] == "cuadro")
        return await self.esperar(lambda d: d["tipo"] == "cuadro" and d["muestras"] >= primero["muestras"] + 0.4*self.fs)

    async def medir(self, medicion, limite_s):
        await self.enviar(tipo="medir", medicion=medicion)
        return await self.esperar(lambda d: d["tipo"] == "medicion" and d["estado"] != "en_curso", limite_s)


def leer(ruta, nombre):
    return json.loads((Path(ruta) / nombre).read_text(encoding="utf-8"))


def cliente_que_no_lee(puerto):
    """Abre /ws con un buffer de recepción mínimo y nunca lee: se llena enseguida."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    s.connect(("127.0.0.1", puerto))
    clave = base64.b64encode(os.urandom(16)).decode()
    s.sendall((f"GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{puerto}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {clave}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
    return s


async def contrato(tmp):
    motor = Motor(destino=tmp / "mediciones")
    runner = web.AppRunner(crear_app(motor))
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 0).start()
    try:
        async with ClientSession() as sesion, sesion.ws_connect(f"http://127.0.0.1:{runner.addresses[0][1]}/ws") as ws:
            estado = json.loads((await ws.receive()).data)
            comprobar("al conectarse llega el estado con el contrato 1", estado["tipo"] == "estado" and estado["contrato"] == 1)
            comprobar("estado: 512 puntos de espectro y 5 mediciones",
                      len(estado["frecuencias_hz"]) == 512 and len(estado["mediciones"]) == 5)
            c = Cliente(ws, estado["fs"])
            frecuencias = np.array(estado["frecuencias_hz"])
            medio_paso = np.sqrt(frecuencias[1]/frecuencias[0])

            q = await c.senal(forma="seno", frecuencia_hz=1000.0, nivel_dbfs=-6.0)
            e = np.array(q["espectro_dbfs"])
            k = int(np.argmax(e))
            comprobar("seno de 1 kHz a -6 dBFS: el máximo del espectro cae en el punto que contiene 1 kHz",
                      frecuencias[k]/medio_paso <= 1000.0 < frecuencias[k]*medio_paso, f"{frecuencias[k]:.1f} Hz")
            comprobar("seno de 1 kHz a -6 dBFS: el máximo del espectro vale -6 dBFS", abs(e[k] + 6.0) <= 0.1, f"{e[k]} dBFS")
            pe = q["pico_espectral"]
            comprobar("seno de 1 kHz a -6 dBFS: el pico marcado dice 1 kHz y -6 dBFS",
                      pe is not None and abs(pe["frecuencia_hz"] - 1000.0) <= 0.5 and abs(pe["nivel_dbfs"] + 6.0) <= 0.1, pe)
            comprobar("seno de 1 kHz a -6 dBFS: pico -6 y RMS -9.03 dBFS",
                      abs(q["nivel"]["pico_dbfs"] + 6.0) <= 0.1 and abs(q["nivel"]["rms_dbfs"] + 9.03) <= 0.1, q["nivel"])
            comprobar("seno de 1 kHz a -6 dBFS: sin saturación", not q["saturacion"]["ahora"] and q["saturacion"]["bloques"] == 0)
            comprobar("seno de 1 kHz a -6 dBFS: forma de onda de 10 ms", len(q["onda"]) == round(0.010*c.fs))

            q = await c.senal(forma="seno", frecuencia_hz=1002.5, nivel_dbfs=-6.0)
            pe = q["pico_espectral"]
            comprobar("tono entre dos bins, 1002.5 Hz: el pico marcado sigue en -6 dBFS",
                      pe is not None and abs(pe["nivel_dbfs"] + 6.0) <= 0.1 and abs(pe["frecuencia_hz"] - 1002.5) <= 0.5, pe)

            q = await c.senal(forma="seno", frecuencia_hz=10000.0, nivel_dbfs=-6.0)
            e = np.array(q["espectro_dbfs"])
            comprobar("seno de 10 kHz, donde cada punto junta decenas de bins: el máximo sigue en -6 dBFS",
                      abs(e.max() + 6.0) <= 0.1, f"{e.max()} dBFS")

            await c.enviar(tipo="senal", forma="seno", frecuencia_hz=1000.0, nivel_dbfs=2.0)
            q = await c.esperar(lambda d: d["tipo"] == "cuadro" and d["saturacion"]["ahora"])
            comprobar("seno a +2 dBFS: avisa saturación con el pico en 0 dBFS", q["nivel"]["pico_dbfs"] >= -0.01, q["nivel"])

            q = await c.senal(forma="seno", frecuencia_hz=1000.0, nivel_dbfs=-6.0)
            s = q["saturacion"]
            comprobar("de vuelta a -6 dBFS: deja de saturar pero lo recuerda",
                      not s["ahora"] and s["bloques"] > 0 and s["hace_s"] is not None and s["hace_s"] >= 0.3, s)
            await c.enviar(tipo="borrar_saturacion")
            q = await c.esperar(lambda d: d["tipo"] == "cuadro" and d["saturacion"]["bloques"] == 0, 2.0)
            comprobar("borrar_saturacion vuelve el aviso a cero", q["saturacion"]["hace_s"] is None)

            lento = cliente_que_no_lee(runner.addresses[0][1])
            try:
                reloj = asyncio.get_running_loop().time
                llegadas, fin = [], reloj() + 6.0
                while reloj() < fin:
                    d = await c.esperar(lambda d: d["tipo"] == "cuadro", 2.0)
                    llegadas.append((reloj(), d["muestras"]))
                ultimos = [m for t, m in llegadas if t >= fin - 2.0]
                avance = (ultimos[-1] - ultimos[0])/c.fs if len(ultimos) > 1 else 0.0
                comprobar("una conexión que no lee no frena los cuadros de las demás", avance >= 1.5,
                          f"{avance:.2f} s de audio en los últimos 2 s")
            finally:
                lento.close()

            await c.enviar(tipo="senal", forma="cuadrada", frecuencia_hz=1000.0, nivel_dbfs=-6.0)
            error = await c.esperar(lambda d: d["tipo"] == "error")
            comprobar("una forma desconocida responde con un error que la nombra", "cuadrada" in error["mensaje"], error)

            await c.enviar(tipo="actualizar_entradas")
            estado = await c.esperar(lambda d: d["tipo"] == "estado")
            q = await c.senal(forma="seno", frecuencia_hz=1000.0, nivel_dbfs=-6.0)
            comprobar("buscar entradas con la fuente sintética reinicia PortAudio sin cortar los cuadros",
                      estado["entradas"][0]["id"] == "sintetica" and abs(q["nivel"]["pico_dbfs"] + 6.0) <= 0.1)

            for forma in ("barrido", "ruido", "silencio"):
                q = await c.senal(forma=forma, frecuencia_hz=1000.0, nivel_dbfs=-20.0)
                rms = q["nivel"]["rms_dbfs"]
                esperado = {"barrido": -23.0, "ruido": -20.0, "silencio": -100.0}[forma]
                comprobar(f"forma {forma}: RMS cerca de {esperado} dBFS", abs(rms - esperado) <= 1.5, f"{rms} dBFS")

            await c.senal(forma="seno", frecuencia_hz=1000.0, nivel_dbfs=-6.0)
            r = await c.medir("captura", 20)
            comprobar("captura: termina y guarda su carpeta", r["estado"] == "lista" and Path(r["ruta"]).is_dir(), r)
            if r["estado"] == "lista":
                cond, res = leer(r["ruta"], "condiciones.json"), leer(r["ruta"], "resultado.json")
                comprobar("captura: condiciones con entrada sintética, 48 kHz y sin estímulo",
                          cond["entrada"]["tipo"] == "sintetica" and cond["frecuencia_muestreo_hz"] == 48000
                          and cond["estimulo"] is None and (Path(r["ruta"]) / "captura.wav").is_file(), cond)
                comprobar("captura: pico -6 dBFS", abs(res["pico_dbfs"] + 6.0) <= 0.1, res)

            await c.enviar(tipo="medir", medicion="thd_n")
            await c.enviar(tipo="medir", medicion="snr")
            error = await c.esperar(lambda d: d["tipo"] == "error")
            comprobar("una segunda medición mientras corre la primera responde con error", "en curso" in error["mensaje"], error)
            r = await c.esperar(lambda d: d["tipo"] == "medicion" and d["estado"] != "en_curso", 20)
            comprobar("THD+N: termina y guarda su carpeta", r["estado"] == "lista", r)
            if r["estado"] == "lista":
                cond, res = leer(r["ruta"], "condiciones.json"), leer(r["ruta"], "resultado.json")
                comprobar("THD+N: condiciones con el tono de 1 kHz a -6 dBFS",
                          cond["medicion"] == "THD+N" and cond["estimulo"]["tono_hz"] == 1000.0
                          and cond["estimulo"]["nivel_dbfs"] == -6.0, cond)
                comprobar("THD+N: con el ruido de -100 dBFS da menos de -85 dB", res["db"] < -85.0, res)

            r = await c.medir("snr", 20)
            comprobar("SNR: termina y guarda su carpeta", r["estado"] == "lista", r)
            if r["estado"] == "lista":
                res = leer(r["ruta"], "resultado.json")
                comprobar("SNR: entre 85 y 98 dB con el tono a -6 dBFS y ruido a -100 dBFS", 85.0 < res["snr_db"] < 98.0, res)

            r = await c.medir("respuesta", 60)
            comprobar("respuesta en frecuencia: termina y guarda su carpeta", r["estado"] == "lista", r)
            if r["estado"] == "lista":
                cond, filas = leer(r["ruta"], "condiciones.json"), leer(r["ruta"], "resultado.json")["filas"]
                tonos = len(an.frecuencias_log(20.0, 20000.0, 3))
                desvio = max(abs(f["nivel_dbfs"] + 6.0) for f in filas)
                comprobar(f"respuesta en frecuencia: {tonos} tonos, planos en -6 dBFS a 0.2 dB",
                          len(filas) == tonos == cond["estimulo"]["tonos"] and desvio <= 0.2,
                          f"{len(filas)} tonos, desvío {desvio:.3f} dB")

            r = await c.medir("jitter", 60)
            comprobar("prueba de jitter: termina y guarda su carpeta", r["estado"] == "lista", r)
            if r["estado"] == "lista":
                res = leer(r["ruta"], "resultado.json")
                comprobar("prueba de jitter: la fuente sintética no tiene jitter", res["veredicto"] == "sin_efecto_detectable", res["veredicto"])

            carpetas = sorted(p.name for p in (tmp / "mediciones").iterdir())
            comprobar("cinco carpetas en mediciones/, una por medición", len(carpetas) == 5, carpetas)
    finally:
        await runner.cleanup()
        motor.cerrar()


def main():
    procesado()
    with tempfile.TemporaryDirectory(prefix="app-") as tmp:
        try:
            asyncio.run(contrato(Path(tmp)))
        except TimeoutError:
            traceback.print_exc()
            comprobar("el servidor responde a tiempo: la prueba se cortó esperando un mensaje", False)
    if CASOS_FALLIDOS:
        print(f"\nFALLA  {len(CASOS_FALLIDOS)} casos de la app sin ventana", file=sys.stderr)
        sys.exit(1)
    print("\nPasan todos los casos de la app. La ventana y la entrada real se prueban a mano.")


if __name__ == "__main__":
    main()
