import argparse, json, os, re
from datetime import datetime
from pathlib import Path

import sounddevice as sd, numpy as np, matplotlib.pyplot as plt
from scipy.io import wavfile

import analizador as an
import device_volume

FS, SEG = 48000, 5
SETTLE_S = 1.0            # la tarjeta USB da un golpe al abrir la grabación; este primer segundo se graba y se descarta
DISPOSITIVO = "USB PnP Sound Device"   # nombre como lo lista dispositivos.py; el número cambia según lo conectado

p = argparse.ArgumentParser(description="Graba una captura y la guarda en mediciones/<fecha>-<etiqueta>/")
p.add_argument("etiqueta", help="nombre de la medición, por ejemplo piso-de-ruido")
p.add_argument("--notas", default="", help="texto libre que se guarda en condiciones.json")
p.add_argument("--segundos", type=float, default=SEG, help=f"duración de la captura, por defecto {SEG}")
p.add_argument("--dispositivo", default=DISPOSITIVO, help=f"entrada a grabar, por defecto «{DISPOSITIVO}»")
p.add_argument("--canal", type=int, default=1, help="canal que se analiza y se guarda, desde 1; por defecto 1")
args = p.parse_args()
if not re.fullmatch(r"[\w.-]+", args.etiqueta):
    p.error("la etiqueta solo puede tener letras, números, puntos, guiones y guiones bajos")


def find_input(name):
    matches = [d for d in sd.query_devices() if d["name"] == name and d["max_input_channels"] > 0]
    if not matches:
        raise SystemExit(f"No está conectada la entrada «{name}». Revisa el cable y corre dispositivos.py")
    return matches[0]


info = find_input(args.dispositivo)
if not 1 <= args.canal <= info["max_input_channels"]:
    p.error(f"«{info['name']}» tiene {info['max_input_channels']} canales de entrada; --canal va de 1 a ese número")
volumen = device_volume.input_volume(info["name"])
ganancia_db = device_volume.input_gain_db(info["name"])
if volumen is None:
    print("Aviso: el dispositivo no reporta volumen de entrada")
else:
    print(f"Volumen de entrada del dispositivo: {volumen} ({ganancia_db} dB)")

ahora = datetime.now().astimezone()
print(f"Grabando {args.segundos:g} segundos...")
x = sd.rec(int((SETTLE_S + args.segundos)*FS), samplerate=FS, channels=args.canal, device=info["index"],
           blocking=True)[int(SETTLE_S*FS):, args.canal - 1]

base = Path(__file__).resolve().parent / "mediciones" / f"{ahora:%Y-%m-%d}-{args.etiqueta}"
carpeta, n = base, 2
while carpeta.exists():           # misma etiqueta el mismo día: -2, -3...
    carpeta, n = base.with_name(f"{base.name}-{n}"), n + 1
carpeta.mkdir(parents=True)
wavfile.write(carpeta / "captura.wav", FS, x)

pico, rms = float(np.max(np.abs(x))), an.rms(x)
pico_db, rms_db = an.pico_dbfs(x), an.rms_dbfs(x)
print(f"Pico: {pico:.4f}  ({pico_db:.1f} dBFS)")
print(f"RMS:  {rms:.4f}  ({rms_db:.1f} dBFS)")

condiciones = {
    "fecha_hora": ahora.isoformat(timespec="seconds"),
    "etiqueta": args.etiqueta,
    "dispositivo": {"nombre": info["name"], "indice": info["index"]},
    "canal": args.canal,
    "frecuencia_muestreo_hz": FS,
    "duracion_s": args.segundos,
    "descartado_al_inicio_s": SETTLE_S,
    "volumen_entrada_sistema": volumen,
    "ganancia_entrada_db": ganancia_db,
    "pico_dbfs": round(pico_db, 2),
    "rms_dbfs": round(rms_db, 2),
    "notas": args.notas,
}
(carpeta / "condiciones.json").write_text(json.dumps(condiciones, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

f, espectro_db = an.espectro(x, FS)

fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 6))
a1.plot(np.arange(len(x))/FS, x); a1.set_xlabel("segundos")
a2.semilogx(f, espectro_db)
a2.set_xlim(20, 20000); a2.set_ylim(-160, 5); a2.set_xlabel("Hz"); a2.set_ylabel("dBFS")
a2.grid(True, which="both", alpha=.3)
plt.tight_layout(); plt.savefig(carpeta / "captura.png", dpi=120)

print(f"Guardado en {os.path.relpath(carpeta)}")
plt.show()
