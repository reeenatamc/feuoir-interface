#!/usr/bin/env python3
"""Graba una captura de una entrada de audio y la guarda con sus condiciones.

    .venv/bin/python medir.py piso-de-ruido --notas "entrada al aire"          en la Mac
    .venv/Scripts/python medir.py piso-de-ruido --dispositivo 12               en Windows

Cada corrida deja una carpeta en mediciones/<fecha>-<etiqueta>/ con el audio, una gráfica de la
forma de onda y el espectro, y condiciones.json: con qué se midió, en qué sistema, por qué API de
audio y con qué nivel de entrada. El pico, el RMS y el espectro salen de analizador.py.
"""
import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import sounddevice as sd
from scipy.io import wavfile

import analizador as an
import dispositivos as devices

ROOT = Path(__file__).resolve().parent
FS = 48000
SECONDS = 5
DEVICE = None        # None: la entrada por defecto del sistema. --dispositivo manda sobre esto


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Graba una captura y la guarda en mediciones/<fecha>-<etiqueta>/")
    parser.add_argument("etiqueta", help="nombre de la medición, por ejemplo piso-de-ruido")
    parser.add_argument("--dispositivo", type=int, default=DEVICE,
                        help="índice de la entrada, el que lista dispositivos.py; "
                             "sin esto, la entrada por defecto del sistema")
    parser.add_argument("--nivel-entrada", type=int, default=None,
                        help="nivel del control de entrada, para guardarlo en condiciones.json; "
                             f"también se puede dejar puesta la variable {devices.LEVEL_VARIABLE}")
    parser.add_argument("--notas", default="", help="texto libre que se guarda en condiciones.json")
    args = parser.parse_args()
    if not re.fullmatch(r"[\w.-]+", args.etiqueta):
        parser.error("la etiqueta solo puede tener letras, números, puntos, guiones y guiones bajos")
    return args


def check_input(index):
    """El dispositivo y su nivel, o termina explicando qué falta antes de grabar."""
    try:
        device = devices.describe(index)
    except (sd.PortAudioError, ValueError) as error:
        raise SystemExit(f"No se puede usar esa entrada: {error}\n"
                         "Corre dispositivos.py para ver las que hay.")

    print(f"Entrada: {device['nombre']} "
          f"(índice {device['indice']}, {devices.short_api(device['api'])})")
    if not devices.accepts_48k(device["indice"]):
        raise SystemExit(f"Esa entrada no acepta 1 canal a {FS} Hz.\n"
                         "En Windows el formato se fija en el panel de sonido, en 24 bits y "
                         "48000 Hz (docs/configuracion-windows.md).")
    return device


def new_folder(label, now):
    """La carpeta de la medición. Misma etiqueta el mismo día: -2, -3..."""
    base = ROOT / "mediciones" / f"{now:%Y-%m-%d}-{label}"
    folder, n = base, 2
    while folder.exists():
        folder, n = base.with_name(f"{base.name}-{n}"), n + 1
    folder.mkdir(parents=True)
    return folder


def save_plot(path, x, fs):
    """La forma de onda arriba y el espectro en dBFS abajo, en escala logarítmica."""
    figure, (wave, spectrum) = plt.subplots(2, 1, figsize=(9, 6))
    wave.plot(np.arange(len(x))/fs, x)
    wave.set_xlabel("segundos")

    f, level_db = an.espectro(x, fs)
    spectrum.semilogx(f, level_db)
    spectrum.set_xlim(20, 20000)
    spectrum.set_ylim(-160, 5)
    spectrum.set_xlabel("Hz")
    spectrum.set_ylabel("dBFS")
    spectrum.grid(True, which="both", alpha=.3)

    plt.tight_layout()
    plt.savefig(path, dpi=120)


def main():
    args = parse_arguments()
    device = check_input(args.dispositivo)
    level = devices.input_level(device["indice"], args.nivel_entrada)
    if level["valor"] is None:
        print(f"Aviso: no se guarda el nivel de entrada ({level['origen']})")

    now = datetime.now().astimezone()
    print(f"Grabando {SECONDS} segundos...")
    x = sd.rec(SECONDS*FS, samplerate=FS, channels=1, device=device["indice"], blocking=True)[:, 0]

    peak_db, rms_db = an.pico_dbfs(x), an.rms_dbfs(x)
    print(f"Pico: {float(np.max(np.abs(x))):.4f}  ({peak_db:.1f} dBFS)")
    print(f"RMS:  {an.rms(x):.4f}  ({rms_db:.1f} dBFS)")

    folder = new_folder(args.etiqueta, now)
    wavfile.write(folder / "captura.wav", FS, x)
    save_plot(folder / "captura.png", x, FS)

    # Claves en español: este formato lo comparten la app y leer_verificacion.py
    conditions = {
        "fecha_hora": now.isoformat(timespec="seconds"),
        "etiqueta": args.etiqueta,
        "sistema_operativo": devices.operating_system(),
        "dispositivo": device,
        "frecuencia_muestreo_hz": FS,
        "duracion_s": SECONDS,
        "nivel_entrada": level,
        "pico_dbfs": round(peak_db, 2),
        "rms_dbfs": round(rms_db, 2),
        "notas": args.notas,
    }
    (folder / "condiciones.json").write_text(
        json.dumps(conditions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Guardado en {os.path.relpath(folder)}")
    plt.show()


if __name__ == "__main__":
    main()
