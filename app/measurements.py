"""The measurement buttons.

Each measurement plays its stimulus, records the input, runs a function from analizador.py and saves its
folder with the medir.py convention: mediciones/<date>-<label>/, with -2, -3... when the label repeats on the
same day, and condiciones.json inside. It also writes resultado.json with what the analyzer returned, and the
captures as WAV, which the repo does not version. File names and JSON keys stay in Spanish: that format is
shared with medir.py and leer_verificacion.py.

With the synthetic source the stimulus goes straight into the simulated converter. With a real input it goes
out through the Mac's default output and has to come back through a cable to the input.
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.io import wavfile

import analizador as an

ROOT = Path(__file__).resolve().parent.parent
RAMP_S = 0.005
SETTLE_S = 0.25          # dropped at the start of each capture: round-trip latency and the ramp fall here
MARGIN_S = 0.25          # extra recording at the end, so latency does not cut the tone
SPAN_S = 1.0             # what gets analyzed from each tone
TONES_PER_OCTAVE = 3
RESPONSE_TONE_S = 0.5

MEASUREMENTS = [
    {"id": "capture", "name": "Captura de 5 s", "label": "captura"},
    {"id": "thd_n", "name": "THD+N", "label": "thd-n"},
    {"id": "snr", "name": "SNR", "label": "snr"},
    {"id": "response", "name": "Respuesta en frecuencia", "label": "respuesta-en-frecuencia"},
    {"id": "jitter", "name": "Prueba de jitter", "label": "prueba-de-jitter"},
]


def input_volume(index):
    """Same as medir.py: osascript only reports the volume of the default input, and it is only read."""
    if index != sd.query_devices(kind="input")["index"]:
        return None
    try:
        r = subprocess.run(["osascript", "-e", "input volume of (get volume settings)"],
                           capture_output=True, text=True)
        return int(r.stdout)
    except (OSError, ValueError):   # "missing value" when the device has no volume control
        return None


def new_folder(destination, label, now):
    base = Path(destination) / f"{now:%Y-%m-%d}-{label}"
    folder, n = base, 2
    while folder.exists():
        folder, n = base.with_name(f"{base.name}-{n}"), n + 1
    folder.mkdir(parents=True)
    return folder


def _write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_saved(destination, limit=100):
    """The measurements saved in destination, newest first.

    Reads each folder's condiciones.json, so the ones from medir.py and leer_verificacion.py show up too. Those
    have no resumen; for medir.py's one is built from the peak and the RMS.
    """
    destination = Path(destination)
    if not destination.is_dir():
        return []
    saved = []
    for folder in destination.iterdir():
        try:
            c = json.loads((folder / "condiciones.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):   # not a measurement folder, or its condiciones.json is broken
            continue
        summary = c.get("resumen") or ""
        if not summary and "pico_dbfs" in c and "rms_dbfs" in c:
            summary = f"Pico {c['pico_dbfs']:.1f} dBFS, RMS {c['rms_dbfs']:.1f} dBFS"
        source = c.get("entrada") or c.get("dispositivo") or {}
        saved.append({
            "folder": folder.name,
            "measurement": c.get("medicion") or c.get("etiqueta") or folder.name,
            "date_time": c.get("fecha_hora") or "",
            "input": source.get("nombre") if isinstance(source, dict) else None,
            "summary": summary,
        })
    saved.sort(key=lambda s: (s["date_time"], s["folder"]), reverse=True)
    return saved[:limit]


class Measurement:
    def __init__(self, source, processor, signal, notify, output_index=None):
        self.source, self.processor, self.fs = source, processor, processor.fs
        self.frequency, self.level = signal["frequency_hz"], signal["level_dbfs"]
        self.notify = notify
        self.output_index = output_index
        self.captures = {}

    def record(self, name, seconds, stimulus=None):
        recording = self.processor.record(int(round(seconds*self.fs)))
        if stimulus is not None:
            self.source.play(stimulus, self.output_index)
        x = recording.wait(seconds + 10.0)
        self.captures[name] = x
        return x

    def tone(self, frequency):
        """Records a tone and returns its middle span, without the latency and the ramp."""
        duration = SETTLE_S + SPAN_S + MARGIN_S
        x = self.record(f"tono-{frequency:.0f}-hz", duration,
                        an.tono(frequency, self.fs, duration, self.level, rampa_s=RAMP_S))
        start = int(round(SETTLE_S*self.fs))
        return x[start:start + int(round(SPAN_S*self.fs))]

    def silence(self):
        duration = SETTLE_S + SPAN_S + MARGIN_S
        x = self.record("silencio", duration, np.zeros(int(round(duration*self.fs))))
        start = int(round(SETTLE_S*self.fs))
        return x[start:start + int(round(SPAN_S*self.fs))]

    def capture(self):
        x = self.record("captura", 5.0)
        r = {"pico_dbfs": an.pico_dbfs(x), "rms_dbfs": an.rms_dbfs(x),
             "frecuencia_dominante_hz": an.frecuencia_dominante(x, self.fs)}
        return {}, r, f"Pico {r['pico_dbfs']:.1f} dBFS, RMS {r['rms_dbfs']:.1f} dBFS"

    def thd_n(self):
        r = an.thd_n(self.tone(self.frequency), self.fs, f0=self.frequency)
        stimulus = {"tono_hz": self.frequency, "nivel_dbfs": self.level, "tramo_analizado_s": SPAN_S}
        return stimulus, r, f"THD+N {r['porcentaje']:.4f} % ({r['db']:.1f} dB) a {self.frequency:g} Hz"

    def snr(self):
        signal = self.tone(self.frequency)
        self.notify("Midiendo el ruido, sin señal")
        band = (20.0, 20000.0)
        r = {"snr_db": an.snr_db(signal, self.silence(), self.fs, banda=band), "banda_hz": list(band)}
        stimulus = {"tono_hz": self.frequency, "nivel_dbfs": self.level, "tramo_analizado_s": SPAN_S}
        return stimulus, r, f"SNR {r['snr_db']:.1f} dB de 20 Hz a 20 kHz"

    def response(self):
        frequencies = an.frecuencias_log(20.0, 20000.0, TONES_PER_OCTAVE)
        x, segments = an.barrido_escalonado(frequencies, self.fs, RESPONSE_TONE_S, self.level)
        output = self.record("captura", len(x)/self.fs + MARGIN_S, x)
        rows = an.respuesta_en_frecuencia(output[:len(x)], self.fs, segments)
        levels = [row["nivel_dbfs"] for row in rows]
        stimulus = {"tonos": len(frequencies), "tonos_por_octava": TONES_PER_OCTAVE,
                    "duracion_tono_s": RESPONSE_TONE_S, "nivel_dbfs": self.level}
        return stimulus, {"filas": rows}, f"{len(rows)} tonos, de {min(levels):.1f} a {max(levels):.1f} dBFS"

    def jitter(self):
        tones = []
        for i, f in enumerate(an.FRECUENCIAS_PRUEBA_JITTER, 1):
            self.notify(f"Tono {i} de {len(an.FRECUENCIAS_PRUEBA_JITTER)}: {f:g} Hz")
            tones.append((f, self.tone(f)))
        r = an.prueba_jitter(tones, self.fs)
        stimulus = {"tonos_hz": list(an.FRECUENCIAS_PRUEBA_JITTER), "nivel_dbfs": self.level,
                    "tramo_analizado_s": SPAN_S}
        verdict = r["veredicto"].replace("_", " ")
        return stimulus, r, f"{verdict.capitalize()}, pendiente de {r['pendiente_db_por_decada']:.1f} dB por década"


def measure(measurement_id, source, processor, signal, destination=ROOT / "mediciones", notify=lambda text: None,
            output=None):
    """Runs a measurement and saves its folder. Returns the folder and a one-line summary.

    output is the output chosen for the stimulus, {"name", "index"}, with index None for the Mac's default one.
    """
    info = next((m for m in MEASUREMENTS if m["id"] == measurement_id), None)
    if info is None:
        raise ValueError(f"Medición desconocida: {measurement_id!r}")
    output = output or {"name": "Salida por defecto", "index": None}
    now = datetime.now().astimezone()
    m = Measurement(source, processor, signal, notify, output["index"])
    stimulus, result, summary = getattr(m, measurement_id)()

    described = source.describe()
    if described["tipo"] == "sintetica":
        output_used = {"tipo": "lazo de la fuente sintética"}
        volume = None
    else:
        kind = "salida por defecto de la Mac" if output["index"] is None else "dispositivo"
        output_used = {"tipo": kind, "nombre": output["name"], "indice": output["index"]}
        volume = input_volume(described["indice"])

    folder = new_folder(destination, info["label"], now)
    for name, x in m.captures.items():
        wavfile.write(folder / f"{name}.wav", processor.fs, np.asarray(x, dtype=np.float32))
    _write_json(folder / "condiciones.json", {
        "fecha_hora": now.isoformat(timespec="seconds"),
        "etiqueta": info["label"],
        "medicion": info["name"],
        "entrada": described,
        "salida_del_estimulo": output_used if stimulus else None,
        "frecuencia_muestreo_hz": processor.fs,
        "volumen_entrada_sistema": volume,
        "estimulo": stimulus or None,
        "resumen": summary,
        "notas": "",
    })
    _write_json(folder / "resultado.json", result)
    return folder, summary
