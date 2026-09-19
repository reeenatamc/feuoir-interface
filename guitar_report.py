"""Analyzes the guitar takes of 2026-09-19 and saves the result in mediciones/<date>-analisis-guitarra/.

    .venv/bin/python guitar_report.py

For each take: peak, RMS and crest factor; the mains hum (60 Hz and its harmonics) fitted and removed, with what is
left once it is gone; the averaged spectrum of that residual with its -20, -40 and -60 dB points, flagged when the
card's own floor hides them; and, for the takes with a single string, its fundamental and the nearest note. It also
compares the card alone (-73 dBFS RMS) with the guitar plugged in at volume 0 (-60 on battery, -42 on the charger).

Everything goes through analizador.py, whose functions are checked in calibrar.py. Output in Spanish.
"""
import json
import platform
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.ticker import FuncFormatter, NullFormatter  # noqa: E402
from scipy.io import wavfile  # noqa: E402

import analizador as an  # noqa: E402

ROOT = Path(__file__).resolve().parent
DAY = "2026-09-19"
INK, MUTED, ACCENT = "black", "0.35", "#c1121f"

GUITAR = {
    "modelo": "Yamaha ERG121C",
    "pastillas": "HSH, cerámicas, pasivas",
    "largo_del_cable": None,
    "posicion_del_selector": None,
}

# folder suffix, kind, what was played, as reported in the session. Kinds: floor (nothing played), strum, note.
TAKES = [
    ("piso-tarjeta-al-aire-2", "floor", "tarjeta sin nada en la entrada"),
    ("piso-tarjeta-al-aire-3", "floor", "tarjeta sin nada en la entrada, ruido en el cuarto"),
    ("piso-con-guitarra-2", "floor", "guitarra en volumen 0, Mac con cargador"),
    ("piso-con-guitarra-3", "floor", "guitarra en volumen 0, Mac con cargador, conexión revisada"),
    ("piso-con-guitarra-4", "floor", "guitarra en volumen 0, Mac a batería"),
    ("rasgueo-fuerte", "strum", "rasgueo fuerte, medir.py"),
    ("rasgueo-fuerte-2", "strum", "rasgueo fuerte continuo, medir.py"),
    ("rasgueo-suave", "strum", "rasgueo suave, medir.py"),
    ("captura", "strum", "rasgueo fuerte, app"),
    ("captura-2", "note", "cuerda grave al aire, app"),
    ("captura-3", "note", "nota sin identificar, app"),
    ("captura-4", "note", "cuerda aguda, app"),
    ("captura-5", "note", "cuerda aguda, app"),
]
CARD_FLOOR = ["piso-tarjeta-al-aire-2", "piso-tarjeta-al-aire-3"]
HARMONICS_SHOWN = 10


def load(name):
    fs, x = wavfile.read(ROOT / "mediciones" / f"{DAY}-{name}" / "captura.wav")
    x = np.asarray(x, dtype=np.float64)
    return (x if x.ndim == 1 else x[:, 0]), fs


def new_folder(name, now):
    base = ROOT / "mediciones" / f"{now:%Y-%m-%d}-{name}"
    folder, n = base, 2
    while folder.exists():
        folder, n = base.with_name(f"{base.name}-{n}"), n + 1
    folder.mkdir(parents=True)
    return folder


def card_floor():
    """Averaged spectrum of the card with nothing plugged in, the two takes averaged in power."""
    spectra = []
    for name in CARD_FLOOR:
        x, fs = load(name)
        f, db = an.averaged_spectrum(x - np.mean(x), fs)
        spectra.append(10**(db/10))
    return f, 10*np.log10(np.mean(spectra, axis=0))


def analyze(name, kind, played, floor_db):
    x, fs = load(name)
    mains = an.remove_mains(x, fs)
    f, db = an.averaged_spectrum(mains["residual"], fs)
    rolloff = an.rolloff_points(f, db, floor_db=floor_db)
    result = {
        "toma": f"mediciones/{DAY}-{name}",
        "tipo": {"floor": "piso", "strum": "rasgueo", "note": "nota"}[kind],
        "que_se_toco": played,
        "duracion_s": round(len(x)/fs, 3),
        "pico_dbfs": round(an.pico_dbfs(x), 2),
        "rms_dbfs": round(an.rms_dbfs(x), 2),
        "factor_de_cresta_db": round(an.crest_factor_db(x), 2),
        "red": {
            "frecuencia_hz": round(mains["mains_hz"], 3),
            "armonicos_dbfs_pico": [round(v, 1) for v in mains["harmonic_dbfs"][:HARMONICS_SHOWN]],
            "zumbido_rms_dbfs": round(mains["hum_rms_dbfs"], 2),
            "residuo_rms_dbfs": round(mains["residual_rms_dbfs"], 2),
        },
        "espectro_promediado": {
            "maximo_hz": round(rolloff["reference_hz"], 1),
            "maximo_dbfs": round(rolloff["reference_db"], 1),
            "puntos": [{"caida_db": p["drop_db"],
                        "frecuencia_hz": None if p["frequency_hz"] is None else round(p["frequency_hz"]),
                        "tapado_por_el_piso": bool(p["limited_by_floor"])} for p in rolloff["points"]],
        },
    }
    if kind == "note":
        f0 = an.fundamental(x - np.mean(x), fs)
        note = an.note_name(f0)
        result["fundamental"] = {"frecuencia_hz": round(f0, 2), "nota": note["name"], "cents": round(note["cents"], 1)}
    return result, (f, db)


def floor_comparison(results):
    """The card alone against the guitar at volume 0: how much of the difference is mains hum."""
    by_name = {Path(r["toma"]).name.removeprefix(f"{DAY}-"): r for r in results}
    card = np.mean([by_name[n]["rms_dbfs"] for n in CARD_FLOOR])
    rows = {}
    for name, label in [("piso-con-guitarra-4", "a_bateria"), ("piso-con-guitarra-2", "con_cargador"),
                        ("piso-con-guitarra-3", "con_cargador_2")]:
        r = by_name[name]
        rows[label] = {"toma": r["toma"], "rms_dbfs": r["rms_dbfs"],
                       "sobre_la_tarjeta_db": round(r["rms_dbfs"] - card, 2),
                       "zumbido_rms_dbfs": r["red"]["zumbido_rms_dbfs"],
                       "residuo_rms_dbfs": r["red"]["residuo_rms_dbfs"],
                       "residuo_sobre_la_tarjeta_db": round(r["red"]["residuo_rms_dbfs"] - card, 2)}
    return {"tarjeta_sola_rms_dbfs": round(card, 2), "guitarra_en_volumen_0": rows}


def frequency_axis(ax):
    ax.set_xscale("log")
    ax.set_xlim(20, 20000)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x/1e3:g} kHz" if x >= 1e3 else f"{x:g} Hz"))
    ax.xaxis.set_minor_formatter(NullFormatter())


def style(ax, xlabel=None, ylabel=None):
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.grid(True, which="major", alpha=0.3)
    ax.grid(True, which="minor", alpha=0.08)
    ax.spines[["top", "right"]].set_visible(False)


def plot(folder, results, spectra, floor):
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(10, 9.5))
    shown = ["captura", "rasgueo-suave", "captura-2", "captura-4"]
    colors = [INK, "0.55", ACCENT, "#1d4e89"]
    for name, color in zip(shown, colors):
        f, db = spectra[name]
        r = next(r for r in results if r["toma"].endswith(f"{DAY}-{name}"))
        top.plot(f[1:], db[1:], color=color, linewidth=1, label=f"{name}: {r['que_se_toco']}")
    top.plot(floor[0][1:], floor[1][1:], color=MUTED, linewidth=1, linestyle="--",
             label="tarjeta sin nada (piso, grabado con medir.py)")
    frequency_axis(top)
    top.set_ylim(-130, -30)
    style(top, "Frecuencia", "dBFS por bin (8192 muestras, Hann)")
    top.set_title("Espectro promediado, sin el zumbido de la red", loc="left")
    top.legend(fontsize=8, frameon=False)

    floors = [("piso-tarjeta-al-aire-2", "tarjeta sola", MUTED), ("piso-con-guitarra-4", "guitarra en 0, batería", INK),
              ("piso-con-guitarra-3", "guitarra en 0, cargador", ACCENT)]
    k = np.arange(1, HARMONICS_SHOWN + 1)
    width = 0.27
    for i, (name, label, color) in enumerate(floors):
        r = next(r for r in results if r["toma"].endswith(f"{DAY}-{name}"))
        bottom.bar(k + (i - 1)*width, np.array(r["red"]["armonicos_dbfs_pico"]) + 140, width, bottom=-140,
                   color=color, label=f"{label}: zumbido {r['red']['zumbido_rms_dbfs']:.1f}, "
                                      f"residuo {r['red']['residuo_rms_dbfs']:.1f} dBFS RMS")
    bottom.set_xticks(k, [f"{60*n}" for n in k])
    bottom.set_ylim(-130, -30)
    style(bottom, "Armónico de la red (Hz nominales)", "dBFS de pico")
    bottom.set_title("Zumbido de la red en las tomas sin tocar", loc="left")
    bottom.legend(fontsize=8, frameon=False, loc="upper right")
    fig.text(0.01, 0.005, f"{GUITAR['modelo']}, {GUITAR['pastillas']}; tarjeta USB PnP en 0 dB; {DAY}",
             fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(folder / "grafica.png", dpi=150)
    plt.close(fig)


def main():
    now = datetime.now().astimezone()
    floor = card_floor()
    results, spectra = [], {}
    for name, kind, played in TAKES:
        r, s = analyze(name, kind, played, floor[1])
        results.append(r)
        spectra[name] = s
        fund = f", fundamental {r['fundamental']['frecuencia_hz']} Hz ({r['fundamental']['nota']} " \
               f"{r['fundamental']['cents']:+.0f} cents)" if "fundamental" in r else ""
        print(f"{name:24s} pico {r['pico_dbfs']:6.1f}  RMS {r['rms_dbfs']:6.1f}  cresta {r['factor_de_cresta_db']:5.1f} dB  "
              f"zumbido {r['red']['zumbido_rms_dbfs']:6.1f}  residuo {r['red']['residuo_rms_dbfs']:6.1f}{fund}")

    comparison = floor_comparison(results)
    battery = comparison["guitarra_en_volumen_0"]["a_bateria"]
    summary = (f"Guitarra en volumen 0 a batería: {battery['sobre_la_tarjeta_db']:+.1f} dB sobre la tarjeta sola; "
               f"sin el zumbido de la red, {battery['residuo_sobre_la_tarjeta_db']:+.1f} dB")
    folder = new_folder("analisis-guitarra", now)
    conditions = {
        "fecha_hora": now.isoformat(timespec="seconds"),
        "etiqueta": "analisis-guitarra",
        "medicion": "Análisis de las tomas de guitarra",
        "guitarra": GUITAR,
        "tarjeta": "USB PnP Sound Device (08bb:2902), entrada de micrófono con adaptador de 6.35 a 3.5 mm, 0 dB",
        "metodo": {
            "red": "60 Hz nominales buscados en ±0.3 Hz, 40 armónicos ajustados por mínimos cuadrados y restados",
            "espectro": "Welch, 8192 muestras con Hann y 50 % de solape, del residuo sin la red",
            "puntos_de_caida": "la frecuencia más alta entre 20 Hz y 20 kHz que sigue a menos de N dB del máximo; "
                               "tapado_por_el_piso si ese nivel queda a menos de 6 dB del piso de la tarjeta",
            "fundamental": "espectro de productos armónicos con 4 factores, solo en las tomas de una cuerda",
        },
        "versiones": {"python": platform.python_version(), "numpy": np.__version__,
                      "matplotlib": matplotlib.__version__},
        "resumen": summary,
        "notas": ("Ninguna toma registra la posición del selector: la comparación entre pastillas simples y dobles "
                  "queda pendiente de tomas nuevas. En volumen 0 la pastilla queda a tierra, así que el zumbido de "
                  "esas tomas entra por el cable y la tarjeta, no por las pastillas. La entrada de micrófono carga "
                  "la guitarra: los puntos de caída describen la guitarra con esa carga, no la guitarra sola."),
    }
    result = {"tomas": results, "piso": comparison}
    (folder / "condiciones.json").write_text(json.dumps(conditions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (folder / "resultado.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plot(folder, results, spectra, floor)
    print(f"\n{summary}\nGuardado en {folder.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
