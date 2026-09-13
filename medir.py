import argparse, json, os, re, subprocess
from datetime import datetime
from pathlib import Path

import sounddevice as sd, numpy as np, matplotlib.pyplot as plt
from scipy.io import wavfile

import analizador as an

FS, SEG = 48000, 5
DISPOSITIVO = 0           # pon aquí el número del paso 2

p = argparse.ArgumentParser(description="Graba una captura y la guarda en mediciones/<fecha>-<etiqueta>/")
p.add_argument("etiqueta", help="nombre de la medición, por ejemplo piso-de-ruido")
p.add_argument("--notas", default="", help="texto libre que se guarda en condiciones.json")
args = p.parse_args()
if not re.fullmatch(r"[\w.-]+", args.etiqueta):
    p.error("la etiqueta solo puede tener letras, números, puntos, guiones y guiones bajos")


def volumen_entrada(indice):
    # osascript solo da el volumen de la entrada por defecto del sistema
    if indice != sd.query_devices(kind="input")["index"]:
        print("Aviso: el dispositivo no es la entrada por defecto, su volumen no se puede leer")
        return None
    try:
        r = subprocess.run(["osascript", "-e", "input volume of (get volume settings)"],
                           capture_output=True, text=True)
        return int(r.stdout)
    except (OSError, ValueError):   # "missing value" si no tiene control de volumen
        print("Aviso: el dispositivo no reporta volumen de entrada")
        return None


info = sd.query_devices(DISPOSITIVO, "input")
volumen = volumen_entrada(info["index"])

ahora = datetime.now().astimezone()
print("Grabando 5 segundos...")
x = sd.rec(int(SEG*FS), samplerate=FS, channels=1, device=DISPOSITIVO, blocking=True)[:,0]

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
    "frecuencia_muestreo_hz": FS,
    "duracion_s": SEG,
    "volumen_entrada_sistema": volumen,
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
