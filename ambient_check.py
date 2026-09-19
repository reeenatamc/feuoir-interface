"""Records the USB sound card and the Mac microphone at the same time, to see whether the card hears the room.

    .venv/bin/python ambient_check.py mediciones/<fecha>-diagnostico-ruido-ambiente

Saves both captures, their RMS every half second and the correlation between the two envelopes.
"""
import json, sys, threading
from datetime import datetime
from pathlib import Path
import numpy as np, sounddevice as sd
from scipy.io import wavfile

FS, SECONDS = 48000, 60
out = Path(sys.argv[1]); out.mkdir(parents=True)
names = {"tarjeta": "USB PnP Sound Device", "mic_mac": "MacBook Pro (micrófono)"}
idx = {k: next(d["index"] for d in sd.query_devices() if d["name"] == n and d["max_input_channels"] > 0) for k, n in names.items()}
data = {}
def rec(k):
    data[k] = sd.rec(int(SECONDS*FS), samplerate=FS, channels=1, device=idx[k], blocking=True)[:, 0]
start = datetime.now().astimezone()
ts = [threading.Thread(target=rec, args=(k,)) for k in names]
[t.start() for t in ts]; [t.join() for t in ts]
rows = {}
for k, x in data.items():
    wavfile.write(out / f"{k}.wav", FS, x)
    env = [float(20*np.log10(np.sqrt(np.mean(x[i*FS//2:(i+1)*FS//2]**2)) + 1e-12)) for i in range(2*SECONDS)]
    rows[k] = [round(v, 1) for v in env]
corr = float(np.corrcoef(rows["tarjeta"][2:], rows["mic_mac"][2:])[0, 1])
json.dump({"fecha_hora": start.isoformat(timespec="seconds"), "motivo": "diagnóstico: Renata ve moverse el medidor de la app con ruido del cuarto aunque la tarjeta no tenga nada enchufado",
           "condiciones": "tarjeta sin nada en la entrada de micrófono, Renata aplaudiendo durante unos 30 s dentro de la ventana de 60 s; Mac a batería; la app abierta con la tarjeta como entrada",
           "dispositivos": names, "rms_dbfs_cada_medio_segundo": rows, "correlacion_envolventes": round(corr, 3)},
          open(out / "condiciones.json", "w"), ensure_ascii=False, indent=2)
print("corr", round(corr, 3))
for k in rows: print(k, "min", min(rows[k][2:]), "max", max(rows[k][2:]))
