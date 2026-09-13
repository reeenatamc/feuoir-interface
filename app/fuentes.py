"""Fuentes de audio: una entrada real por sounddevice o una fuente sintética que hace de conversor.

Las dos dejan bloques float32 en la misma cola, y el resto de la app no sabe cuál está andando.
"""
import queue
import threading
import time

import numpy as np
import sounddevice as sd

import analizador as an

BLOQUE = 1024                   # a 48 kHz son unos 47 bloques por segundo
FS_PREFERIDA = 48000
RUIDO_SINTETICO_DBFS = -100.0   # RMS del ruido que suma la fuente sintética, del orden del piso del PCM1808
BITS_SINTETICOS = 24
DURACION_BARRIDO_S = 5.0
FORMAS = ("seno", "barrido", "ruido", "silencio")
SENAL_POR_DEFECTO = {"forma": "seno", "frecuencia_hz": 1000.0, "nivel_dbfs": -6.0}


def validar_senal(senal):
    """Devuelve la señal con sus tres campos, o ValueError con lo que está mal."""
    forma = senal.get("forma")
    if forma not in FORMAS:
        raise ValueError(f"forma desconocida: {forma!r}; las formas son {', '.join(FORMAS)}")
    frecuencia = float(senal.get("frecuencia_hz", SENAL_POR_DEFECTO["frecuencia_hz"]))
    nivel = float(senal.get("nivel_dbfs", SENAL_POR_DEFECTO["nivel_dbfs"]))
    if not 20.0 <= frecuencia <= 20000.0:
        raise ValueError(f"frecuencia fuera de 20 Hz a 20 kHz: {frecuencia}")
    if not -120.0 <= nivel <= 6.0:
        raise ValueError(f"nivel fuera de -120 a +6 dBFS: {nivel}")
    return {"forma": forma, "frecuencia_hz": frecuencia, "nivel_dbfs": nivel}


def listar_entradas(reiniciar=False):
    """Las entradas de la Mac.

    PortAudio arma la lista de dispositivos al iniciarse: una interfaz conectada después solo aparece
    si se lo reinicia, y eso corta cualquier stream abierto. Por eso reiniciar es opcional.
    """
    if reiniciar:
        sd._terminate()
        sd._initialize()
    entradas = [{"id": "sintetica", "nombre": FuenteSintetica.nombre}]
    for d in sd.query_devices():
        if d["max_input_channels"] > 0:
            entradas.append({"id": str(d["index"]), "nombre": d["name"]})
    return entradas


class FuenteSintetica:
    """Hace de conversor sin hardware.

    Genera la señal elegida, le suma ruido de fondo, la cuantiza a 24 bits y la recorta en fondo
    de escala, como el ADC. Entrega bloques a ritmo real. Para el seno y el barrido el nivel es de
    pico; para el ruido, RMS.
    """
    nombre = "Fuente sintética"

    def __init__(self, cola, fs=FS_PREFERIDA, senal=SENAL_POR_DEFECTO):
        self.cola, self.fs = cola, fs
        self._cerrojo = threading.Lock()
        self._rng = np.random.default_rng()
        self._fase = 0.0
        self._estimulo = np.zeros(0)
        self.configurar(senal)
        self._parar = threading.Event()
        self._hilo = threading.Thread(target=self._correr, name="fuente-sintetica", daemon=True)
        self._hilo.start()

    def descripcion(self):
        return {"tipo": "sintetica", "nombre": self.nombre, "senal": self.senal,
                "ruido_dbfs_rms": RUIDO_SINTETICO_DBFS, "bits": BITS_SINTETICOS}

    def configurar(self, senal):
        senal = validar_senal(senal)
        barrido = None
        if senal["forma"] == "barrido":
            barrido = an.barrido_log(20.0, 20000.0, self.fs, DURACION_BARRIDO_S, senal["nivel_dbfs"])
        with self._cerrojo:
            self.senal, self._barrido, self._posicion = senal, barrido, 0

    def reproducir(self, x):
        """Lo que suena por la salida entra por la entrada, como con un cable de lazo."""
        with self._cerrojo:
            self._estimulo = np.concatenate([self._estimulo, np.asarray(x, dtype=np.float64)])

    def _generar(self, n):
        s = self.senal
        a = 10**(s["nivel_dbfs"]/20)
        if len(self._estimulo):
            x = np.zeros(n)
            m = min(n, len(self._estimulo))
            x[:m], self._estimulo = self._estimulo[:m], self._estimulo[m:]
        elif s["forma"] == "seno":
            w = 2*np.pi*s["frecuencia_hz"]/self.fs
            x = a*np.sin(self._fase + w*np.arange(n))
            self._fase = (self._fase + w*n) % (2*np.pi)
        elif s["forma"] == "barrido":
            x = self._barrido[(self._posicion + np.arange(n)) % len(self._barrido)]
            self._posicion = (self._posicion + n) % len(self._barrido)
        elif s["forma"] == "ruido":
            x = self._rng.normal(0.0, a, n)
        else:
            x = np.zeros(n)
        x = x + self._rng.normal(0.0, 10**(RUIDO_SINTETICO_DBFS/20), n)
        paso = 2.0**-(BITS_SINTETICOS - 1)
        return np.clip(np.round(x/paso)*paso, -1.0, 1.0 - paso)

    def _correr(self):
        siguiente = time.perf_counter()
        while not self._parar.is_set():
            with self._cerrojo:
                x = self._generar(BLOQUE).astype(np.float32)
            try:
                self.cola.put_nowait(x)
            except queue.Full:
                pass                          # nadie está leyendo: el bloque se pierde, como en un conversor real
            siguiente += BLOQUE/self.fs
            espera = siguiente - time.perf_counter()
            if espera > 0:
                time.sleep(espera)
            else:
                siguiente = time.perf_counter()   # atrasada: sigue desde ahora en vez de mandar una ráfaga

    def cerrar(self):
        self._parar.set()
        self._hilo.join()


class FuenteDispositivo:
    """Una entrada de audio de la Mac: la interfaz feuoir, una tarjeta USB o el micrófono."""

    def __init__(self, cola, indice):
        info = sd.query_devices(int(indice), "input")
        self.cola, self.indice, self.nombre = cola, info["index"], info["name"]
        self.fs = FS_PREFERIDA
        try:
            sd.check_input_settings(device=self.indice, channels=1, samplerate=self.fs, dtype="float32")
        except sd.PortAudioError:
            self.fs = int(info["default_samplerate"])
        self.bloques_perdidos = 0
        self._stream = sd.InputStream(device=self.indice, channels=1, samplerate=self.fs, blocksize=BLOQUE,
                                      dtype="float32", callback=self._callback)
        self._stream.start()

    def _callback(self, indata, frames, tiempo, estado):
        # Corre en el hilo de tiempo real de CoreAudio: si se demora, el audio se corta. Por eso solo
        # copia el bloque a la cola y sale. Medir, reducir y mandar a la interfaz pasa en otro hilo.
        try:
            self.cola.put_nowait(indata[:, 0].copy())
        except queue.Full:
            self.bloques_perdidos += 1

    def descripcion(self):
        return {"tipo": "dispositivo", "nombre": self.nombre, "indice": self.indice,
                "bloques_perdidos": self.bloques_perdidos}

    def reproducir(self, x):
        """El estímulo sale por la salida por defecto de la Mac, sin tocar su configuración."""
        sd.play(np.asarray(x, dtype=np.float32), self.fs)

    def cerrar(self):
        self._stream.stop()
        self._stream.close()
