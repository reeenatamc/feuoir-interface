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
import sys
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
SETTLE_S = 1.0            # la tarjeta USB da un golpe al abrir la grabación; este primer segundo se graba y se descarta
DEVICE = "USB PnP Sound Device"   # nombre como lo lista dispositivos.py, o su índice; --dispositivo manda sobre esto


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Graba una captura y la guarda en mediciones/<fecha>-<etiqueta>/")
    parser.add_argument("etiqueta", help="nombre de la medición, por ejemplo piso-de-ruido")
    parser.add_argument("--dispositivo", default=DEVICE,
                        help="nombre o índice de la entrada, el que lista dispositivos.py; "
                             f"por defecto «{DEVICE}»")
    parser.add_argument("--nivel-entrada", type=int, default=None,
                        help="nivel del control de entrada, para guardarlo en condiciones.json; "
                             f"también se puede dejar puesta la variable {devices.LEVEL_VARIABLE}")
    parser.add_argument("--segundos", type=float, default=SECONDS,
                        help=f"duración de la captura, por defecto {SECONDS}")
    parser.add_argument("--canal", type=int, default=1,
                        help="canal que se analiza y se guarda, desde 1; por defecto 1")
    parser.add_argument("--notas", default="", help="texto libre que se guarda en condiciones.json")
    args = parser.parse_args()
    if not re.fullmatch(r"[\w.-]+", args.etiqueta):
        parser.error("la etiqueta solo puede tener letras, números, puntos, guiones y guiones bajos")
    return args


def resolve_device(spec):
    """El índice de la entrada: tal cual si spec son solo dígitos, o buscándola por nombre."""
    if spec.isdigit():
        return int(spec)
    matches = [d for d in sd.query_devices() if d["name"] == spec and d["max_input_channels"] > 0]
    if not matches:
        raise SystemExit(f"No está conectada la entrada «{spec}». Revisa el cable y corre dispositivos.py")
    return matches[0]["index"]


def check_input(index, channel):
    """El dispositivo y su nivel, o termina explicando qué falta antes de grabar."""
    try:
        device = devices.describe(index)
        channels = sd.query_devices(index, "input")["max_input_channels"]
    except (sd.PortAudioError, ValueError) as error:
        raise SystemExit(f"No se puede usar esa entrada: {error}\n"
                         "Corre dispositivos.py para ver las que hay.")

    print(f"Entrada: {device['nombre']} "
          f"(índice {device['indice']}, {devices.short_api(device['api'])})")
    if not devices.accepts_48k(device["indice"]):
        raise SystemExit(f"Esa entrada no acepta 1 canal a {FS} Hz.\n"
                         "En Windows el formato se fija en el panel de sonido, en 24 bits y "
                         "48000 Hz (docs/configuracion-windows.md).")
    if not 1 <= channel <= channels:
        raise SystemExit(f"«{device['nombre']}» tiene {channels} canales de entrada; "
                         "--canal va de 1 a ese número")
    return device


def read_volume(device):
    """El volumen de entrada y la ganancia en dB, si el sistema los reporta.

    En macOS se leen con device_volume.py (Core Audio), que puede leer cualquier entrada, no solo la
    por defecto del sistema; ese módulo solo existe en macOS, así que se importa solo ahí. En los
    demás sistemas se guarda None: el nivel de entrada queda anotado en nivel_entrada, con el
    mecanismo del lado de Windows (--nivel-entrada o la variable de entorno).
    """
    if sys.platform != "darwin":
        return None, None
    import device_volume
    return device_volume.input_volume(device["nombre"]), device_volume.input_gain_db(device["nombre"])


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
    index = resolve_device(args.dispositivo)
    device = check_input(index, args.canal)
    level = devices.input_level(device["indice"], args.nivel_entrada)
    if level["valor"] is None:
        print(f"Aviso: no se guarda el nivel de entrada ({level['origen']})")
    volumen, ganancia_db = read_volume(device)
    if sys.platform == "darwin":
        if volumen is None:
            print("Aviso: el dispositivo no reporta volumen de entrada")
        else:
            print(f"Volumen de entrada del dispositivo: {volumen} ({ganancia_db} dB)")

    now = datetime.now().astimezone()
    print(f"Grabando {args.segundos:g} segundos...")
    x = sd.rec(int((SETTLE_S + args.segundos)*FS), samplerate=FS, channels=args.canal,
               device=device["indice"], blocking=True)[int(SETTLE_S*FS):, args.canal - 1]

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
        "canal": args.canal,
        "frecuencia_muestreo_hz": FS,
        "duracion_s": args.segundos,
        "descartado_al_inicio_s": SETTLE_S,
        "nivel_entrada": level,
        "volumen_entrada_sistema": volumen,
        "ganancia_entrada_db": ganancia_db,
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
