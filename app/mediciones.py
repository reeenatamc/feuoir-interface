"""Las mediciones de los botones.

Cada una hace sonar su estímulo, graba la entrada, corre una función de analizador.py y guarda
su carpeta con la convención de medir.py: mediciones/<fecha>-<etiqueta>/, con -2, -3... si la
etiqueta se repite el mismo día, y condiciones.json adentro. Además deja resultado.json con lo
que devolvió el analizador y las capturas en WAV, que el repo no versiona.

Con la fuente sintética el estímulo entra directo al conversor simulado. Con una entrada real
sale por la salida por defecto de la Mac y tiene que volver por un cable hasta la entrada.
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.io import wavfile

import analizador as an

RAIZ = Path(__file__).resolve().parent.parent
RAMPA_S = 0.005
ASENTAMIENTO_S = 0.25   # se descarta al principio de cada captura: la latencia de ida y vuelta y la rampa
MARGEN_S = 0.25         # grabación de más al final, para que la latencia no corte el tono
TRAMO_S = 1.0           # lo que se analiza de cada tono
TONOS_POR_OCTAVA = 3
DURACION_TONO_RESPUESTA_S = 0.5

MEDICIONES = [
    {"id": "captura", "nombre": "Captura de 5 s", "etiqueta": "captura"},
    {"id": "thd_n", "nombre": "THD+N", "etiqueta": "thd-n"},
    {"id": "snr", "nombre": "SNR", "etiqueta": "snr"},
    {"id": "respuesta", "nombre": "Respuesta en frecuencia", "etiqueta": "respuesta-en-frecuencia"},
    {"id": "jitter", "nombre": "Prueba de jitter", "etiqueta": "prueba-de-jitter"},
]


def volumen_entrada(indice):
    """Igual que en medir.py: osascript solo da el volumen de la entrada por defecto, y solo se lee."""
    if indice != sd.query_devices(kind="input")["index"]:
        return None
    try:
        r = subprocess.run(["osascript", "-e", "input volume of (get volume settings)"],
                           capture_output=True, text=True)
        return int(r.stdout)
    except (OSError, ValueError):   # "missing value" si no tiene control de volumen
        return None


def carpeta_nueva(destino, etiqueta, ahora):
    base = Path(destino) / f"{ahora:%Y-%m-%d}-{etiqueta}"
    carpeta, n = base, 2
    while carpeta.exists():
        carpeta, n = base.with_name(f"{base.name}-{n}"), n + 1
    carpeta.mkdir(parents=True)
    return carpeta


def _escribir_json(ruta, datos):
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class Medicion:
    def __init__(self, fuente, procesador, senal, avisar):
        self.fuente, self.procesador, self.fs = fuente, procesador, procesador.fs
        self.frecuencia, self.nivel = senal["frecuencia_hz"], senal["nivel_dbfs"]
        self.avisar = avisar
        self.capturas = {}

    def grabar(self, nombre, segundos, estimulo=None):
        g = self.procesador.grabar(int(round(segundos*self.fs)))
        if estimulo is not None:
            self.fuente.reproducir(estimulo)
        x = g.esperar(segundos + 10.0)
        self.capturas[nombre] = x
        return x

    def tono(self, frecuencia):
        """Graba un tono y devuelve el tramo del medio, sin la latencia ni la rampa."""
        duracion = ASENTAMIENTO_S + TRAMO_S + MARGEN_S
        x = self.grabar(f"tono-{frecuencia:.0f}-hz", duracion,
                        an.tono(frecuencia, self.fs, duracion, self.nivel, rampa_s=RAMPA_S))
        inicio = int(round(ASENTAMIENTO_S*self.fs))
        return x[inicio:inicio + int(round(TRAMO_S*self.fs))]

    def silencio(self):
        duracion = ASENTAMIENTO_S + TRAMO_S + MARGEN_S
        x = self.grabar("silencio", duracion, np.zeros(int(round(duracion*self.fs))))
        inicio = int(round(ASENTAMIENTO_S*self.fs))
        return x[inicio:inicio + int(round(TRAMO_S*self.fs))]

    def captura(self):
        x = self.grabar("captura", 5.0)
        r = {"pico_dbfs": an.pico_dbfs(x), "rms_dbfs": an.rms_dbfs(x),
             "frecuencia_dominante_hz": an.frecuencia_dominante(x, self.fs)}
        return {}, r, f"Pico {r['pico_dbfs']:.1f} dBFS, RMS {r['rms_dbfs']:.1f} dBFS"

    def thd_n(self):
        r = an.thd_n(self.tono(self.frecuencia), self.fs, f0=self.frecuencia)
        estimulo = {"tono_hz": self.frecuencia, "nivel_dbfs": self.nivel, "tramo_analizado_s": TRAMO_S}
        return estimulo, r, f"THD+N {r['porcentaje']:.4f} % ({r['db']:.1f} dB) a {self.frecuencia:g} Hz"

    def snr(self):
        senal = self.tono(self.frecuencia)
        self.avisar("Midiendo el ruido, sin señal")
        banda = (20.0, 20000.0)
        r = {"snr_db": an.snr_db(senal, self.silencio(), self.fs, banda=banda), "banda_hz": list(banda)}
        estimulo = {"tono_hz": self.frecuencia, "nivel_dbfs": self.nivel, "tramo_analizado_s": TRAMO_S}
        return estimulo, r, f"SNR {r['snr_db']:.1f} dB de 20 Hz a 20 kHz"

    def respuesta(self):
        frecuencias = an.frecuencias_log(20.0, 20000.0, TONOS_POR_OCTAVA)
        x, segmentos = an.barrido_escalonado(frecuencias, self.fs, DURACION_TONO_RESPUESTA_S, self.nivel)
        salida = self.grabar("captura", len(x)/self.fs + MARGEN_S, x)
        filas = an.respuesta_en_frecuencia(salida[:len(x)], self.fs, segmentos)
        niveles = [f["nivel_dbfs"] for f in filas]
        estimulo = {"tonos": len(frecuencias), "tonos_por_octava": TONOS_POR_OCTAVA,
                    "duracion_tono_s": DURACION_TONO_RESPUESTA_S, "nivel_dbfs": self.nivel}
        return estimulo, {"filas": filas}, f"{len(filas)} tonos, de {min(niveles):.1f} a {max(niveles):.1f} dBFS"

    def jitter(self):
        tonos = []
        for i, f in enumerate(an.FRECUENCIAS_PRUEBA_JITTER, 1):
            self.avisar(f"Tono {i} de {len(an.FRECUENCIAS_PRUEBA_JITTER)}: {f:g} Hz")
            tonos.append((f, self.tono(f)))
        r = an.prueba_jitter(tonos, self.fs)
        estimulo = {"tonos_hz": list(an.FRECUENCIAS_PRUEBA_JITTER), "nivel_dbfs": self.nivel,
                    "tramo_analizado_s": TRAMO_S}
        veredicto = r["veredicto"].replace("_", " ")
        return estimulo, r, f"{veredicto.capitalize()}, pendiente de {r['pendiente_db_por_decada']:.1f} dB por década"


def medir(medicion_id, fuente, procesador, senal, destino=RAIZ / "mediciones", avisar=lambda texto: None):
    """Corre una medición y guarda su carpeta. Devuelve la carpeta y un resumen de una línea."""
    datos = next((m for m in MEDICIONES if m["id"] == medicion_id), None)
    if datos is None:
        raise ValueError(f"medición desconocida: {medicion_id!r}")
    ahora = datetime.now().astimezone()
    m = Medicion(fuente, procesador, senal, avisar)
    estimulo, resultado, resumen = getattr(m, medicion_id)()

    entrada = fuente.descripcion()
    if entrada["tipo"] == "sintetica":
        salida = {"tipo": "lazo de la fuente sintética"}
        volumen = None
    else:
        salida = {"tipo": "salida por defecto de la Mac", "nombre": sd.query_devices(kind="output")["name"]}
        volumen = volumen_entrada(entrada["indice"])

    carpeta = carpeta_nueva(destino, datos["etiqueta"], ahora)
    for nombre, x in m.capturas.items():
        wavfile.write(carpeta / f"{nombre}.wav", procesador.fs, np.asarray(x, dtype=np.float32))
    _escribir_json(carpeta / "condiciones.json", {
        "fecha_hora": ahora.isoformat(timespec="seconds"),
        "etiqueta": datos["etiqueta"],
        "medicion": datos["nombre"],
        "entrada": entrada,
        "salida_del_estimulo": salida if estimulo else None,
        "frecuencia_muestreo_hz": procesador.fs,
        "volumen_entrada_sistema": volumen,
        "estimulo": estimulo or None,
        "resumen": resumen,
        "notas": "",
    })
    _escribir_json(carpeta / "resultado.json", resultado)
    return carpeta, resumen
