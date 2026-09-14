"""Checks what TI's TL072 models do before using them in the input stage.

    .venv/bin/python -m spice.characterize

- Noise of the TL07XH_TL08XH model, the one used for noise: its input voltage noise at 1 kHz against the 37 nV/√Hz of
  the datasheet (tables 5.7 and 5.9), within ±1 dB. This check decides whether its noise analysis can be trusted; if
  it fails, the script exits with code 1. The 10 kHz value and the input current noise are recorded too.
- Phase reversal with the classic TL072 model: a follower on a single 9 V supply with the input swept down to 0 V.
- Offset of the TL07XH_TL08XH model with several supplies, to rule out a configuration error on our side.

Saves the results with their conditions, and the plots, in calibraciones/<date>-modelos-tl072/. Output in Spanish.
"""
import hashlib
import json
import os
import platform
import re
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from spice import run  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NETLISTS = Path(__file__).resolve().parent / "netlists"
MODELS = Path(__file__).resolve().parent / "models"
TL072 = MODELS / "TL072.301"
TL072H = MODELS / "tl07xh_tl08xh.lib"
BOLTZMANN = 1.380649e-23
TEMPERATURE_K = 300.15
DATASHEET_EN_1K = 37e-9      # V/√Hz at 1 kHz, tables 5.7 (TL07xH) and 5.9 (all other devices, DIP-8 included)
DATASHEET_EN_10K = 21e-9     # V/√Hz at 10 kHz, same tables
DATASHEET_IN_1K = 80e-15     # A/√Hz at 1 kHz, table 5.7 (TL07xH)
EN_TOLERANCE_DB = 1.0
SOURCE_FOR_CURRENT_NOISE = 1e6
FOLLOW_ERROR_V = 0.1         # beyond this the classic model stops following its input


def log_interp(f, values, frequency):
    return float(10**np.interp(np.log10(frequency), np.log10(f), np.log10(values)))


def noise_spectrum(rsource):
    netlist = run.with_params((NETLISTS / "model_noise_tl072h.cir").read_text(encoding="utf-8"), rsource=rsource)
    raws, _ = run.simulate(netlist, files=[TL072H], behavior="ps")
    raw = raws["noise_spectrum.raw"]
    return np.real(run.vector(raw, "frequency")), np.abs(run.vector(raw, "onoise_spectrum"))


def characterize_noise(folder):
    f, en = noise_spectrum("1m")
    en_1k, en_10k = log_interp(f, en, 1e3), log_interp(f, en, 1e4)
    error_db = 20*np.log10(en_1k/DATASHEET_EN_1K)

    f_rs, total = noise_spectrum("1meg")
    thermal = np.sqrt(4*BOLTZMANN*TEMPERATURE_K*SOURCE_FOR_CURRENT_NOISE)
    # total² = en² + (in·Rs)² + 4kTRs, with the op-amp's voltage noise the same as with a 1 mOhm source
    current = np.sqrt(max(log_interp(f_rs, total, 1e3)**2 - en_1k**2 - thermal**2, 0.0)) / SOURCE_FOR_CURRENT_NOISE

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.loglog(f, en*1e9, color="black", label="modelo TL07XH_TL08XH, seguidor")
    ax.loglog([1e3, 1e4], [DATASHEET_EN_1K*1e9, DATASHEET_EN_10K*1e9], "o", color="#c1121f", label="hoja de TI, típico")
    ax.set_xlabel("Frecuencia (Hz)")
    ax.set_ylabel("Ruido de tensión de entrada (nV/√Hz)")
    ax.set_title("Ruido de entrada del modelo del TL072H contra la hoja")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(folder / "ruido-tl072h.png", dpi=130)
    plt.close(fig)

    return {
        "en_1khz_nv": en_1k*1e9, "en_hoja_1khz_nv": DATASHEET_EN_1K*1e9, "error_1khz_db": error_db,
        "tolerancia_db": EN_TOLERANCE_DB, "pasa": bool(abs(error_db) <= EN_TOLERANCE_DB),
        "en_10khz_nv": en_10k*1e9, "en_hoja_10khz_nv": DATASHEET_EN_10K*1e9,
        "in_1khz_fa": current*1e15, "in_hoja_1khz_fa": DATASHEET_IN_1K*1e15,
        "condiciones": {"alimentacion_v": [9, -9], "resistencia_de_fuente_ohm": [1e-3, SOURCE_FOR_CURRENT_NOISE],
                        "temperatura_k": TEMPERATURE_K, "ngbehavior": "ps"},
    }


def characterize_phase_reversal(folder):
    raws, _ = run.simulate((NETLISTS / "model_phase_reversal_tl072.cir").read_text(encoding="utf-8"), files=[TL072])
    sweep = raws["dc_sweep.raw"]
    vin, vout = np.real(run.vector(sweep, "in")), np.real(run.vector(sweep, "out"))
    order = np.argsort(vin)
    vin, vout = vin[order], vout[order]
    # A follower's output never goes down while its input goes up. The largest such drop measures phase reversal.
    drop = float(np.max(np.maximum.accumulate(vout) - vout))
    following = np.abs(vout - vin) <= FOLLOW_ERROR_V
    lowest_followed = float(vin[following].min()) if following.any() else None

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.axvspan(0, 4, color="#ff5a1f", alpha=0.12, label="entrada a menos de 4 V del riel negativo")
    ax.plot(vin, vin, color="0.6", linestyle="--", label="seguidor ideal")
    ax.plot(vin, vout, color="black", label="modelo TL072 clásico")
    ax.set_xlabel("Entrada (V)")
    ax.set_ylabel("Salida (V)")
    ax.set_title("Seguidor con 9 V simples: el modelo no muestra inversión de fase" if drop < 0.5
                 else "Seguidor con 9 V simples: el modelo muestra inversión de fase")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(folder / "inversion-de-fase-tl072.png", dpi=130)
    plt.close(fig)

    return {
        "caida_maxima_de_la_salida_v": drop, "muestra_inversion": bool(drop >= 0.5),
        "salida_con_entrada_en_0_v": float(vout[0]), "salida_minima_v": float(vout.min()),
        "entrada_minima_que_sigue_a_0_1_v": lowest_followed,
        "condiciones": {"alimentacion_v": [9, 0], "barrido_entrada_v": [0, 9, 0.01], "modelo": "TL072.301"},
    }


def characterize_offset():
    text = (NETLISTS / "model_offset_tl072h.cir").read_text(encoding="utf-8")
    cases = []
    for label, vpos, vneg, vin in (("±9 V", 9, -9, 0), ("±15 V", 15, -15, 0), ("0 y 18 V", 18, 0, 9)):
        raws, _ = run.simulate(run.with_params(text, vpos=vpos, vneg=vneg, vin=vin), files=[TL072H], behavior="ps")
        out = float(np.real(run.vector(raws["offset_op.raw"], "out")[0]))
        cases.append({"alimentacion": label, "entrada_v": vin, "offset_mv": (out - vin)*1e3})
    library = TL072H.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"\.SUBCKT VOS_DRIFT_0.*?\.PARAM DC\s*=\s*(\S+)", library, flags=re.IGNORECASE | re.DOTALL)
    return {"casos": cases, "parametro_dc_de_vos_drift_v": float(match.group(1)) if match else None}


def new_folder(now):
    base = ROOT / "calibraciones" / f"{now:%Y-%m-%d}-modelos-tl072"
    folder, n = base, 2
    while folder.exists():
        folder, n = base.with_name(f"{base.name}-{n}"), n + 1
    folder.mkdir(parents=True)
    return folder


def main():
    now = datetime.now().astimezone()
    folder = new_folder(now)
    noise = characterize_noise(folder)
    reversal = characterize_phase_reversal(folder)
    offset = characterize_offset()

    report = {
        "fecha_hora": now.isoformat(timespec="seconds"),
        "ngspice": {"ruta": run.ngspice_path(), "version": run.version()},
        "modelos_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (TL072, TL072H)},
        "netlists_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(NETLISTS.glob("model_*.cir"))},
        "versiones": {"python": platform.python_version(), "numpy": np.__version__, "matplotlib": matplotlib.__version__},
        "plataforma": platform.platform(),
        "ruido_tl072h": noise,
        "inversion_de_fase_tl072": reversal,
        "offset_tl072h": offset,
    }
    (folder / "resultados.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Ruido del TL072H a 1 kHz: {noise['en_1khz_nv']:.1f} nV/√Hz, la hoja dice 37 ({noise['error_1khz_db']:+.2f} dB)")
    print(f"  a 10 kHz: {noise['en_10khz_nv']:.1f} nV/√Hz, la hoja dice 21")
    print(f"  corriente a 1 kHz: {noise['in_1khz_fa']:.1f} fA/√Hz, la hoja del TL07xH dice 80")
    print(f"Inversión de fase con el TL072 clásico: {'sí' if reversal['muestra_inversion'] else 'no'} "
          f"(la salida baja como mucho {reversal['caida_maxima_de_la_salida_v']:.3f} V mientras la entrada sube; "
          f"con la entrada en 0 V la salida queda en {reversal['salida_con_entrada_en_0_v']:.2f} V)")
    for case in offset["casos"]:
        print(f"Offset del TL072H con {case['alimentacion']}: {case['offset_mv']:+.2f} mV")
    print(f"  parámetro DC del subcircuito VOS_DRIFT_0 de la biblioteca: {offset['parametro_dc_de_vos_drift_v']} V")
    print(f"Guardado en {os.path.relpath(folder)}/")

    if not noise["pasa"]:
        print("\nFALLA  el ruido del modelo del TL072H no coincide con la hoja: no se usa para el análisis de ruido",
              file=sys.stderr)
        sys.exit(1)
    print("\nEl ruido del modelo del TL072H coincide con la hoja dentro de ±1 dB: se puede usar para el análisis de ruido.")


if __name__ == "__main__":
    main()
