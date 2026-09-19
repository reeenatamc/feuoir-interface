#!/usr/bin/env python3
"""Lista las entradas de audio y describe el entorno en que se mide.

    .venv/bin/python dispositivos.py           en la Mac
    .venv/Scripts/python dispositivos.py       en Windows

En Windows el mismo aparato aparece una vez por cada API de audio: MME, DirectSound y WASAPI son
tres caminos distintos hacia el mismo conversor. Hay que elegir WASAPI, que habla con el driver sin
remuestrear ni mezclar por el medio; la tabla la marca con un asterisco. MME además recorta los
nombres a 31 caracteres, así que la misma tarjeta puede aparecer con dos nombres.

medir.py y la app toman de aquí lo que guardan en condiciones.json: el sistema operativo, la API de
audio y el nivel de entrada. Sin esos tres datos una medición hecha en la Mac y otra hecha en la
ASUS no se pueden comparar.
"""
import os
import platform
import subprocess

import sounddevice as sd

TARGET_FS = 48000
LEVEL_VARIABLE = "FEUOIR_NIVEL_ENTRADA"

# Como PortAudio nombra a la API recomendada en cada sistema
RECOMMENDED_API = {"Windows": "Windows WASAPI", "Darwin": "Core Audio", "Linux": "ALSA"}

# En la tabla las APIs de Windows se muestran como las nombra el sistema, sin el prefijo
SHORT_API_NAMES = {"Windows WASAPI": "WASAPI", "Windows DirectSound": "DirectSound",
                   "Windows WDM-KS": "WDM-KS"}

# Los nombres de WDM-KS traen saltos de línea y rutas de drivers: en la tabla se recortan
NAME_WIDTH = 45


# El entorno de la medición

def operating_system():
    """El sistema donde corre la medición.

    platform.release() dice 10 en un Windows 11, así que en Windows se guarda el número de build,
    que sí distingue una versión de otra.
    """
    system = platform.system()
    if system == "Windows":
        return f"Windows {platform.win32_ver()[1]}"
    if system == "Darwin":
        return f"macOS {platform.mac_ver()[0]}"
    return platform.platform()


def recommended_api():
    """La API de audio que hay que usar en este sistema, o None si no hay una elegida."""
    return RECOMMENDED_API.get(platform.system())


def host_api_name(api_index):
    try:
        return sd.query_hostapis(api_index)["name"]
    except (sd.PortAudioError, IndexError, KeyError):   # el índice quedó fuera de rango
        return None


def short_api(name):
    return SHORT_API_NAMES.get(name, name)


def one_line(name, width=NAME_WIDTH):
    """El nombre en una sola línea y recortado, para que la tabla quede alineada."""
    name = " ".join(name.split())
    return name if len(name) <= width else name[:width - 3] + "..."


# Las entradas de audio

def default_input():
    try:
        return sd.query_devices(kind="input")["index"]
    except (sd.PortAudioError, ValueError):   # no hay ninguna entrada
        return None


def accepts_48k(index):
    """Si la entrada acepta un canal a 48 kHz, que es como graba medir.py."""
    try:
        sd.check_input_settings(device=index, channels=1, samplerate=TARGET_FS, dtype="float32")
        return True
    except (sd.PortAudioError, ValueError):
        return False


def inputs():
    """Una fila por entrada de audio, en el orden en que las numera sounddevice."""
    recommended, default = recommended_api(), default_input()
    rows = []
    for device in sd.query_devices():
        if device["max_input_channels"] < 1:
            continue
        api = host_api_name(device["hostapi"])
        rows.append({
            "index": device["index"],
            "name": device["name"],
            "api": api,
            "channels": device["max_input_channels"],
            "sample_rate": int(device["default_samplerate"]),
            "accepts_48k": accepts_48k(device["index"]),
            "is_default": device["index"] == default,
            "is_recommended": api is not None and api == recommended,
        })
    return rows


COLUMNS = [
    ("", lambda r: "*" if r["is_recommended"] else ""),
    ("Índice", lambda r: str(r["index"])),
    ("Nombre", lambda r: one_line(r["name"])),
    ("API", lambda r: short_api(r["api"]) or "?"),
    ("Canales", lambda r: str(r["channels"])),
    ("Frecuencia", lambda r: f"{r['sample_rate']} Hz"),
    ("48 kHz", lambda r: "sí" if r["accepts_48k"] else "NO"),
    ("", lambda r: "entrada por defecto del sistema" if r["is_default"] else ""),
]


def table(rows=None):
    """La tabla de entradas tal como la imprime el script."""
    rows = inputs() if rows is None else rows
    if not rows:
        return "No hay ninguna entrada de audio."

    cells = [[title for title, _ in COLUMNS]] + [[read(r) for _, read in COLUMNS] for r in rows]
    widths = [max(len(cell[i]) for cell in cells) for i in range(len(COLUMNS))]
    lines = ["  ".join(text.ljust(width) for text, width in zip(cell, widths)).rstrip() for cell in cells]
    lines.insert(1, "  ".join("-"*width for width in widths).rstrip())

    recommended = recommended_api()
    if recommended is None:
        lines.append("\nNo hay una API recomendada para este sistema.")
    elif any(r["is_recommended"] for r in rows):
        lines.append(f"\n*  {short_api(recommended)}: la API recomendada. El mismo aparato aparece una vez por API;"
                     "\n   elige la fila marcada de tu tarjeta de sonido USB, no la del micrófono interno.")
    else:
        lines.append(f"\nNinguna entrada aparece bajo {short_api(recommended)}, la API recomendada.")
    lines.append("   Se elige con: python medir.py <etiqueta> --dispositivo <índice>")
    return "\n".join(lines)


# Lo que se guarda en condiciones.json. Las claves van en español: ese formato lo comparten
# medir.py, la app y leer_verificacion.py.

def describe(index):
    """El dispositivo con su índice y su API."""
    info = sd.query_devices(index, "input")
    return {"nombre": info["name"], "indice": info["index"], "api": host_api_name(info["hostapi"])}


def input_level(index, given=None):
    """El nivel del control de entrada, con el origen del dato.

    Windows no expone el nivel de entrada sin instalar nada, así que ahí se anota a mano: con
    --nivel-entrada, o dejando puesta la variable de entorno FEUOIR_NIVEL_ENTRADA. En la Mac se lee
    solo, y solo el de la entrada por defecto del sistema. Desde aquí nunca se cambia: el nivel se
    anota una vez y no se vuelve a mover (docs/configuracion-windows.md).
    """
    if given is not None:
        return {"valor": int(given), "origen": "indicado con --nivel-entrada"}

    from_environment = os.environ.get(LEVEL_VARIABLE, "").strip()
    if from_environment:
        try:
            return {"valor": int(from_environment), "origen": f"variable de entorno {LEVEL_VARIABLE}"}
        except ValueError:
            return {"valor": None, "origen": f"{LEVEL_VARIABLE} no es un número: {from_environment!r}"}

    if platform.system() == "Darwin":
        if index is not None and index != default_input():
            return {"valor": None, "origen": "el dispositivo no es la entrada por defecto del sistema"}
        try:
            r = subprocess.run(["osascript", "-e", "input volume of (get volume settings)"],
                               capture_output=True, text=True)
            return {"valor": int(r.stdout), "origen": "volumen de entrada del sistema (macOS)"}
        except (OSError, ValueError):   # "missing value" si el dispositivo no tiene control de volumen
            return {"valor": None, "origen": "el dispositivo no reporta volumen de entrada"}

    return {"valor": None, "origen": f"sin anotar: usa --nivel-entrada o pon {LEVEL_VARIABLE}"}


if __name__ == "__main__":
    print(table())
