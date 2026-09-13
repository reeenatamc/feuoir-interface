"""De bloques de audio a cuadros listos para dibujar.

Todo lo que la interfaz muestra se calcula acá, con analizador.py; la interfaz solo dibuja.
El procesado va por muestras y no por reloj: cada bloque que llega se mira entero, y un
cuadro se arma cuando se pide, con lo acumulado desde el cuadro anterior. Así el ritmo del
audio (unos 47 bloques por segundo) no depende del de la pantalla.
"""
import threading
from collections import deque

import numpy as np

import analizador as an

PUNTOS_ESPECTRO = 512
F_MIN_HZ, F_MAX_HZ = 20.0, 20000.0
SEGUNDOS_ESPECTRO = 0.2        # 200 ms: bins de 5 Hz a cualquier frecuencia de muestreo
VENTANA_ESPECTRO = "flattop"   # con Hann un tono que cae entre dos bins marca hasta 1.42 dB menos
ONDA_MS = 10
SEGUNDOS_LECTURA = 0.5         # las cifras de pico muestran el máximo de este tramo, para que se alcancen a leer
FONDO_DE_ESCALA = 1 - 2**-15   # a menos de un código de 16 bits del tope: vale para conversores de 16 y de 24 bits
UMBRAL_PICO_DBFS = -90.0       # por debajo no se marca el pico del espectro: sería un pico del ruido


def puntos_espectro():
    """Bordes y centros de los tramos logarítmicos entre F_MIN_HZ y F_MAX_HZ."""
    bordes = F_MIN_HZ * (F_MAX_HZ/F_MIN_HZ) ** (np.arange(PUNTOS_ESPECTRO + 1) / PUNTOS_ESPECTRO)
    return bordes, np.sqrt(bordes[:-1] * bordes[1:])


def reducir_espectro(f, db, bordes):
    """Un valor por tramo: el máximo de los bins que caen adentro, para que ningún tono se pierda.

    Los tramos más angostos que un bin, en los graves, toman el valor interpolado en su centro.
    """
    salida = np.interp(np.sqrt(bordes[:-1] * bordes[1:]), f, db)
    k = np.searchsorted(f, bordes)
    llenos = np.flatnonzero(k[1:] > k[:-1])
    if len(llenos):
        salida[llenos] = np.maximum.reduceat(db[:k[-1]], k[llenos])
    return salida


class Grabacion:
    """Junta las próximas n muestras que pasen por el procesador."""

    def __init__(self, n):
        self._partes, self._faltan = [], n
        self._lista = threading.Event()

    def agregar(self, x):
        parte = x[:self._faltan]
        self._partes.append(parte.copy())
        self._faltan -= len(parte)
        if self._faltan == 0:
            self._lista.set()
        return self._faltan == 0

    def esperar(self, limite_s):
        if not self._lista.wait(limite_s):
            raise TimeoutError("la entrada dejó de mandar bloques antes de completar la grabación")
        return np.concatenate(self._partes)


class Procesador:
    def __init__(self, fs):
        self.fs = fs
        self.n_espectro = int(round(SEGUNDOS_ESPECTRO*fs))
        self.n_onda = int(round(ONDA_MS*fs/1000))
        self.bordes, self.frecuencias = puntos_espectro()
        self._cerrojo = threading.Lock()
        self._memoria = np.zeros(self.n_espectro)   # las últimas muestras, la más nueva al final
        self._muestras = 0
        self._pico_cuadro = 0.0
        self._saturo_cuadro = False
        self._picos = deque()                        # (muestras hasta el final del bloque, pico del bloque)
        self._ultima_saturacion = None
        self._bloques_saturados = 0
        self._grabaciones = []

    def bloque(self, x):
        x = np.asarray(x, dtype=np.float64)
        pico = float(np.max(np.abs(x)))   # todas las muestras: un recorte de una sola muestra también cuenta
        n = len(x)
        with self._cerrojo:
            if n >= self.n_espectro:
                self._memoria[:] = x[-self.n_espectro:]
            else:
                self._memoria[:-n] = self._memoria[n:]
                self._memoria[-n:] = x
            self._muestras += n
            # El pico se sostiene hasta el próximo cuadro: un bloque que satura entre dos cuadros no se pierde.
            self._pico_cuadro = max(self._pico_cuadro, pico)
            self._picos.append((self._muestras, pico))
            while self._picos[0][0] <= self._muestras - SEGUNDOS_LECTURA*self.fs:
                self._picos.popleft()
            if pico >= FONDO_DE_ESCALA:
                self._saturo_cuadro = True
                self._ultima_saturacion = self._muestras
                self._bloques_saturados += 1
            self._grabaciones = [g for g in self._grabaciones if not g.agregar(x)]

    def grabar(self, n):
        g = Grabacion(n)
        with self._cerrojo:
            self._grabaciones.append(g)
        return g

    def borrar_saturacion(self):
        with self._cerrojo:
            self._ultima_saturacion, self._bloques_saturados = None, 0

    def cuadro(self):
        with self._cerrojo:
            x = self._memoria.copy()
            pico_cuadro, saturo = self._pico_cuadro, self._saturo_cuadro
            self._pico_cuadro, self._saturo_cuadro = 0.0, False
            pico_lectura = max(p for _, p in self._picos) if self._picos else 0.0
            ultima, bloques, muestras = self._ultima_saturacion, self._bloques_saturados, self._muestras

        f, db = an.espectro(x, self.fs, ventana=VENTANA_ESPECTRO)
        en_banda = np.flatnonzero((f >= F_MIN_HZ) & (f <= F_MAX_HZ))
        k = en_banda[np.argmax(db[en_banda])]
        pico_espectral = None
        if db[k] >= UMBRAL_PICO_DBFS:
            frecuencia = an.frecuencia_dominante(x, self.fs)
            if abs(frecuencia - f[k]) > 2*self.fs/len(x):   # la dominante quedó fuera de la banda dibujada
                frecuencia = f[k]
            pico_espectral = {"frecuencia_hz": round(float(frecuencia), 2), "nivel_dbfs": round(float(db[k]), 2)}

        # La forma de onda arranca en un cruce por cero subiendo, para que no baile de un cuadro al otro.
        n = self.n_onda
        tramo = x[len(x) - 2*n:]
        cruces = np.flatnonzero((tramo[:-1] < 0) & (tramo[1:] >= 0)) + 1
        cruces = cruces[cruces <= n]
        inicio = len(x) - 2*n + (int(cruces[-1]) if len(cruces) else n)

        return {
            "tipo": "cuadro",
            "muestras": muestras,
            "onda": np.round(x[inicio:inicio + n], 5).tolist(),
            "espectro_dbfs": np.round(reducir_espectro(f, db, self.bordes), 1).tolist(),
            "pico_espectral": pico_espectral,
            "nivel": {
                "pico_dbfs": round(float(20*np.log10(pico_cuadro + an.EPS)), 2),
                "pico_lectura_dbfs": round(float(20*np.log10(pico_lectura + an.EPS)), 2),
                "rms_dbfs": round(an.rms_dbfs(x), 2),
            },
            "saturacion": {
                "ahora": saturo,
                "hace_s": None if ultima is None else round((muestras - ultima)/self.fs, 2),
                "bloques": bloques,
            },
        }
