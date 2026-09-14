"""Runs the input stage simulations Renata asked for and saves each one in mediciones/<date>-sim-<name>/.

    .venv/bin/python -m spice.simulate_input                   the four
    .venv/bin/python -m spice.simulate_input carga ruido       only some of: respuesta, transitorio, ruido, carga

Each folder gets condiciones.json (with the keys the app's saved list reads), resultado.json, the curves as CSV, the
netlists that were run (netlists/) and the plots. The linear simulations use TI's classic TL072 model and the noise one
the TL07XH_TL08XH model, as decided in docs/simulador-spice.md.

resultado.json also carries checks against hand calculations of the circuit on paper (docs/entrada-analogica.md). If
one fails, the netlists are not that circuit: the script says so and exits with code 1. Output in Spanish.
"""
import hashlib
import json
import os
import platform
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.ticker import FuncFormatter, NullFormatter  # noqa: E402

from spice import run  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NETLISTS = Path(__file__).resolve().parent / "netlists"
MODELS = Path(__file__).resolve().parent / "models"
STAGE = NETLISTS / "input_stage.cir"
GUITAR = NETLISTS / "guitar.cir"
LINEAR = {"wrapper": NETLISTS / "opamp_tl072.cir", "library": MODELS / "TL072.301", "behavior": None,
          "use": "lineal: respuesta en frecuencia, ganancia, transitorio y margen"}
NOISE = {"wrapper": NETLISTS / "opamp_tl072h.cir", "library": MODELS / "tl07xh_tl08xh.lib", "behavior": "ps",
         "use": "solo el ruido"}

# The circuit on paper, for the hand calculations the checks compare against.
R1_OHM, C1_F, R4_OHM = 1e6, 100e-9, 1e3
R2_OHM, R3_OHM, C2_F, C4_F = 100e3, 100e3, 47e-6, 47e-6      # only in the single supply version
R5_OHM, C5_F, C3_F = 4.7e3, 1e-9, 2.2e-6
GUITAR_L_H, GUITAR_R_OHM, GUITAR_C_F = 5.0, 8e3, 100e-12
GAINS = (1, 3, 5, 8, 11)
FRESH = {"vbat": 9.0, "rbat": 2.0}
DEPLETED = {"vbat": 7.0, "rbat": 10.0}

PCM1808_LOAD_OHM = 60e3              # PCM1808 datasheet (SLES177B), 6.5: input impedance
PCM1808_FULL_SCALE_PEAK_V = 1.5      # 6.3: 3 Vpp full scale with VCC = 5 V
PCM1808_CENTER_V = 2.5               # 6.5: input center voltage, 0.5 VCC
PCM1808_PIN_V = (-0.3, 5.3)          # 6.1: absolute maximum on VINL and VINR, -0.3 V to VCC + 0.3 V
TL072_INPUT_OVER_VNEG_V = 4.0        # TL072 datasheet (SLOS080W), 5.3: input from (VCC-) + 4 V
TL072_INPUT_OVER_VPOS_V = 0.1        # to (VCC+) + 0.1 V, for every device other than the NS, PS and TL07xM
MODEL_EN_1K = 37.6e-9                # TL07XH_TL08XH model at 1 kHz, calibraciones/2026-09-14-modelos-tl072
MODEL_IN_1K = 79.2e-15
DATASHEET_DIP8_IN_1K = 10e-15        # TL072 datasheet, 5.9: TL07xC, the DIP-8
BOLTZMANN = 1.380649e-23
TEMPERATURE_K = 300.15               # ngspice simulates at 27 °C
AUDIO_BAND_HZ = (20.0, 20e3)

INK, MUTED, ACCENT = "black", "0.35", "#c1121f"
PHASE_REVERSAL_NOTE = ("El modelo del TL072 no reproduce la inversión de fase (calibraciones/2026-09-14-modelos-tl072): "
                       "que la versión de 9 V simples salga limpia no prueba que no ocurra.")
CURRENT_NOISE_NOTE = ("El modelo del TL072H tiene 79 fA/√Hz de ruido de corriente, como su hoja (tabla 5.7), pero la "
                      "tabla 5.9 da 10 fA/√Hz para el TL07xC, el DIP-8. Pesa donde la impedancia en la entrada es "
                      "alta: con la entrada al aire, sobre 1 MΩ, esta simulación exagera el ruido.")
QUIESCENT_NOTE = ("El modelo del TL072 clásico consume 8.4 mA por amplificador con ±9 V (RP = 2.143 kΩ entre sus "
                  "rieles), contra 1.4 mA típicos en la tabla 5.8 de la hoja: los rieles bajan más que en el circuito "
                  "real y el margen simulado queda un poco por debajo del real.")


def pot_ohm(gain):
    return (gain - 1) * R4_OHM


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def batteries(version, vbat, rbat):
    """Ideal sources with their internal resistance. Split: two in series, and the midpoint is ground."""
    if version == "split":
        return (f"Vbat_pos bpos 0 DC {vbat}\nRbat_pos bpos vpos {rbat}\n"
                f"Vbat_neg 0 bneg DC {vbat}\nRbat_neg bneg vneg {rbat}\n")
    return f"Vbat bpos 0 DC {vbat}\nRbat bpos vpos {rbat}\n"


def stage(version, gain):
    rails = "vpos vneg input_stage_split" if version == "split" else "vpos input_stage_single"
    return f"Xstage in adc {rails} params: rpot={pot_ohm(gain):g}\n"


def pcm1808_load():
    return f"Rload adc 0 {PCM1808_LOAD_OHM:g}\n"


def simulate(title, body, analysis, includes, model=None):
    """Runs a top-level netlist that includes the given netlists by name. Returns the raws and the netlist text."""
    head = "".join(f".include {p.name}\n" for p in includes)
    text = (f"* {title}\n{head}\n{body}\n.control\nset noaskquit\nset filetype=ascii\n{analysis}\nquit\n.endc\n\n"
            ".end\n")
    files = list(includes) + ([model["library"]] if model else [])
    raws, _ = run.simulate(text, files=files, behavior=model["behavior"] if model else None)
    return raws, text


def new_folder(name, now):
    base = ROOT / "mediciones" / f"{now:%Y-%m-%d}-{name}"
    folder, n = base, 2
    while folder.exists():
        folder, n = base.with_name(f"{base.name}-{n}"), n + 1
    (folder / "netlists").mkdir(parents=True)
    return folder


def conditions(now, name, title, summary, notes, model, netlists, extra):
    data = {
        "fecha_hora": now.isoformat(timespec="seconds"),
        "etiqueta": name,
        "medicion": title,
        "simulador": {"version": run.version(), "ruta": run.ngspice_path(), "temperatura_c": 27},
        "netlists_sha256": {p.name: sha256(p) for p in netlists},
    }
    if model:
        data["modelo_del_opamp"] = {"archivo": model["library"].name, "sha256": sha256(model["library"]),
                                    "uso": model["use"]}
    data.update(extra)
    data["versiones"] = {"python": platform.python_version(), "numpy": np.__version__, "matplotlib": matplotlib.__version__}
    data["resumen"] = summary
    data["notas"] = notes
    return data


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path, columns):
    names = list(columns)
    table = np.column_stack([np.asarray(columns[n], dtype=float) for n in names])
    np.savetxt(path, table, delimiter=",", header=",".join(names), comments="", fmt="%.9g")


def same_sweep(columns, f):
    """The first sweep becomes the frequency column. Every later one has to match it to share the CSV."""
    if "frecuencia_hz" not in columns:
        columns["frecuencia_hz"] = f
    elif len(f) != len(columns["frecuencia_hz"]) or not np.allclose(f, columns["frecuencia_hz"], rtol=1e-9):
        raise RuntimeError("Los barridos de frecuencia no coinciden entre simulaciones")


def check(test, what, conditions_text, expected, obtained, tolerance, unit):
    """One check in the format of calibrar.py."""
    passed = obtained is not None and abs(obtained - expected) <= tolerance
    return {"prueba": test, "chequeo": what, "condiciones": conditions_text, "esperado": expected, "obtenido": obtained,
            "tolerancia": tolerance, "unidad": unit, "paso": bool(passed)}


def db(values):
    return 20*np.log10(np.maximum(np.abs(values), 1e-30))


def rounded(value, digits):
    """value rounded for display, without a -0.0 for a value just under zero."""
    return round(value, digits) + 0.0


def at(f, values, frequency):
    """values at frequency, interpolated over log f."""
    return float(np.interp(np.log10(frequency), np.log10(f), values))


def at_log(f, values, frequency):
    """A positive quantity at frequency, interpolated over log f and log values."""
    return float(10**np.interp(np.log10(frequency), np.log10(f), np.log10(values)))


def band_rms(f, density):
    """RMS over the audio band of a density in units/√Hz, on a fine grid that starts and ends exactly at the edges."""
    grid = np.geomspace(*AUDIO_BAND_HZ, 4000)
    return float(np.sqrt(np.trapezoid(10**np.interp(np.log10(grid), np.log10(f), np.log10(density**2)), grid)))


def crossing(f, values, level, start, upwards):
    """Where values first cross level walking the sweep up (or down) from index start, interpolated over log f."""
    step = 1 if upwards else -1
    i = start
    while 0 <= i + step < len(f):
        j = i + step
        if (values[i] - level)*(values[j] - level) <= 0 and values[i] != values[j]:
            t = (level - values[i])/(values[j] - values[i])
            return float(10**(np.log10(f[i]) + t*(np.log10(f[j]) - np.log10(f[i]))))
        i = j
    return None


def ideal_response(f, version, gain):
    """Hand calculation of input_stage.cir with ideal op-amps: from the source to the PCM1808 input, with its load."""
    s = 2j*np.pi*np.asarray(f)
    after_stage_a = 1/(1 + s*R5_OHM*C5_F) * PCM1808_LOAD_OHM/(PCM1808_LOAD_OHM + 1/(s*C3_F))
    if version == "split":
        return R1_OHM/(R1_OHM + 1/(s*C1_F)) * gain * after_stage_a
    rpot = max(pot_ohm(gain), 1e-3)
    out = np.empty(len(s), dtype=complex)
    for k, sk in enumerate(s):
        y1, y2, y4 = sk*C1_F, sk*C2_F, sk*C4_F
        # Node equations for v(inp), v(bias), v(r4c2) and v(outa), with v(inn) = v(inp) and 1 V at the source.
        a = np.array([[-(y1 + 1/R1_OHM), 1/R1_OHM, 0, 0],
                      [-(1/rpot + 1/R4_OHM), 0, 1/R4_OHM, 1/rpot],
                      [1/R4_OHM, y2, -(1/R4_OHM + y2), 0],
                      [1/R1_OHM, -(1/R1_OHM + y2 + 1/R2_OHM + 1/R3_OHM + y4), y2, 0]])
        out[k] = np.linalg.solve(a, np.array([-y1, 0, 0, 0]))[3]
    return out * after_stage_a


def frequency_axis(ax):
    def label(x, _):
        if x >= 1e6:
            return f"{x/1e6:g} MHz"
        return f"{x/1e3:g} kHz" if x >= 1e3 else f"{x:g} Hz"
    ax.xaxis.set_major_formatter(FuncFormatter(label))
    ax.xaxis.set_minor_formatter(NullFormatter())


def style(ax, xlabel=None, ylabel=None):
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.grid(True, which="major", alpha=0.3)
    ax.grid(True, which="minor", alpha=0.08)
    ax.spines[["top", "right"]].set_visible(False)


def footer(fig, lines):
    fig.text(0.01, 0.01, "\n".join(lines), ha="left", va="bottom", fontsize=8, color=MUTED)


def frequency_response(now):
    name = "sim-respuesta-en-frecuencia"
    folder = new_folder(name, now)
    includes = [LINEAR["wrapper"], STAGE]
    results, columns, curves, checks = {}, {}, {}, []
    fc_c1 = 1/(2*np.pi*R1_OHM*C1_F)
    fc_c3 = 1/(2*np.pi*PCM1808_LOAD_OHM*C3_F)
    fc_rc = 1/(2*np.pi*R5_OHM*C5_F)

    for version, label in (("split", "partida"), ("single", "simple")):
        for gain in GAINS:
            key = f"{label}-ganancia-{gain}"
            body = batteries(version, **FRESH) + "Vin in 0 DC 0 AC 1\n" + stage(version, gain) + pcm1808_load()
            raws, text = simulate(f"Input stage, {version} supply, gain {gain}: frequency response at the PCM1808 input",
                                  body, "ac dec 50 1 1meg\nwrite ac.raw v(adc)", includes, LINEAR)
            (folder / "netlists" / f"{key}.cir").write_text(text, encoding="utf-8")
            f = np.real(run.vector(raws["ac.raw"], "frequency"))
            h = run.vector(raws["ac.raw"], "adc")
            same_sweep(columns, f)
            mag = db(h)
            level = at(f, mag, 1e3)
            start = int(np.argmin(np.abs(f - 1e3)))
            results[key] = {
                "alimentacion": label, "ganancia_nominal": gain, "potenciometro_ohm": pot_ohm(gain),
                "nivel_a_1khz_db": level, "error_contra_la_ganancia_nominal_db": level - 20*np.log10(gain),
                "corte_inferior_menos_3db_hz": crossing(f, mag, level - 3, start, upwards=False),
                "corte_superior_menos_3db_hz": crossing(f, mag, level - 3, start, upwards=True),
                "relativo_a_1khz_en_20hz_db": at(f, mag, 20) - level,
                "relativo_a_1khz_en_20khz_db": at(f, mag, 20e3) - level,
                "maximo_sobre_1khz_db": float(mag.max() - level),
            }
            curves[(label, gain)] = mag
            columns[f"{label}_g{gain}_db"] = mag
            columns[f"{label}_g{gain}_fase_grados"] = np.degrees(np.angle(h))
            below = f <= 5e3
            ideal_error = float(np.max(np.abs(mag[below] - db(ideal_response(f[below], version, gain)))))
            results[key]["diferencia_con_opamps_ideales_hasta_5khz_db"] = ideal_error
            checks.append(check("respuesta", f"ganancia a 1 kHz, {label}, ganancia {gain}",
                                f"potenciómetro en {pot_ohm(gain):g} Ω, pilas frescas, 60 kΩ de carga",
                                20*np.log10(gain), level, 0.1, "dB"))
            checks.append(check("respuesta", f"curva hasta 5 kHz, {label}, ganancia {gain}",
                                "contra el cálculo del circuito con opamps ideales, el peor punto desde 1 Hz",
                                0.0, ideal_error, 0.01, "dB"))
    checks.append(check("respuesta", "corte superior, partida, ganancia 1", "R5 con C5, relativo a 1 kHz",
                        fc_rc, results["partida-ganancia-1"]["corte_superior_menos_3db_hz"], 0.02*fc_rc, "Hz"))

    f = columns["frecuencia_hz"]
    band = (f >= AUDIO_BAND_HZ[0]) & (f <= AUDIO_BAND_HZ[1])
    for label in ("partida", "simple"):
        reference = curves[(label, 1)] - results[f"{label}-ganancia-1"]["nivel_a_1khz_db"]
        for gain in GAINS:
            entry = results[f"{label}-ganancia-{gain}"]
            relative = curves[(label, gain)] - entry["nivel_a_1khz_db"]
            entry["forma_contra_ganancia_1_de_20hz_a_20khz_db"] = float(np.max(np.abs(relative[band] - reference[band])))
    write_csv(folder / "datos.csv", columns)

    ramp = plt.cm.Blues(np.linspace(0.6, 1.0, len(GAINS)))
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(9, 8.5), sharex=True)
    for color, gain in zip(ramp, GAINS):
        mag = curves[("partida", gain)]
        top.semilogx(f, mag, color=color, linewidth=1.8, label=f"ganancia {gain}")
        bottom.semilogx(f, mag - results[f"partida-ganancia-{gain}"]["nivel_a_1khz_db"], color=color, linewidth=1.8)
    for ax in (top, bottom):
        ax.axvspan(*AUDIO_BAND_HZ, color="0.5", alpha=0.07, linewidth=0)
        for corner in (fc_c3, fc_c1, fc_rc):
            ax.axvline(corner, color="0.55", linestyle=":", linewidth=1)
        frequency_axis(ax)
    fig.suptitle("Etapa de entrada con ±9 V: respuesta hasta la entrada del PCM1808")
    top.set_title("Nivel absoluto", fontsize=10, loc="left")
    bottom.set_title("Relativa a 1 kHz, para comparar la forma", fontsize=10, loc="left")
    style(top, ylabel="Magnitud (dB)")
    style(bottom, "Frecuencia", "Relativa a 1 kHz (dB)")
    bottom.set_ylim(-20, 2)
    top.legend(loc="lower center", ncol=5, fontsize=9, frameon=False)
    footer(fig, [f"Punteadas: C3 con los 60 kΩ del PCM1808 ({fc_c3:.2f} Hz), C1 con R1 ({fc_c1:.2f} Hz) y R5 con C5 "
                 f"({fc_rc/1e3:.1f} kHz). Sombreado: de 20 Hz a 20 kHz.",
                 "Fuente ideal, pilas frescas de 9 V con 2 Ω, modelo del TL072 clásico."])
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(folder / "grafica-partida.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.axvspan(*AUDIO_BAND_HZ, color="0.5", alpha=0.07, linewidth=0)
    for gain, color in ((1, ramp[0]), (11, ramp[-1])):
        ax.semilogx(f, curves[("partida", gain)], color=color, linewidth=1.8, label=f"±9 V, ganancia {gain}")
        ax.semilogx(f, curves[("simple", gain)], color=color, linewidth=1.8, linestyle="--",
                    label=f"9 V simples, ganancia {gain}")
    ax.set_title("9 V simples contra ±9 V, con la ganancia en 1 y en 11")
    style(ax, "Frecuencia", "Magnitud (dB)")
    frequency_axis(ax)
    ax.legend(fontsize=9, frameon=False)
    single11 = results["simple-ganancia-11"]
    footer(fig, ["En la versión simple, R4 vuelve a través de C2 = 47 µF al nodo de polarización, desacoplado con C4 = 47 µF:",
                 "en graves la ganancia cae antes cuanto más alta es. Con ganancia 11, "
                 f"{single11['relativo_a_1khz_en_20hz_db']:.2f} dB en 20 Hz y -3 dB en {single11['corte_inferior_menos_3db_hz']:.1f} Hz.",
                 "Sombreado: de 20 Hz a 20 kHz."])
    fig.tight_layout(rect=(0, 0.09, 1, 1))
    fig.savefig(folder / "grafica-simple-contra-partida.png", dpi=150)
    plt.close(fig)

    split1, split11 = results["partida-ganancia-1"], results["partida-ganancia-11"]
    summary = (f"Simulación: de {rounded(split1['nivel_a_1khz_db'], 1):.1f} a {split11['nivel_a_1khz_db']:.1f} dB a 1 kHz con ±9 V, "
               f"-3 dB en {split11['corte_inferior_menos_3db_hz']:.2f} Hz y {split11['corte_superior_menos_3db_hz']/1e3:.1f} kHz")
    write_json(folder / "condiciones.json", conditions(
        now, name, "Simulación: respuesta en frecuencia", summary, "", LINEAR, includes,
        {"barrido_hz": [1, 1e6], "puntos_por_decada": 50, "fuente": "ideal a la entrada, AC 1 V",
         "ganancias": list(GAINS), "potenciometro_ohm": [pot_ohm(g) for g in GAINS],
         "potenciometro_en_0_ohm": "modelado como 1 mΩ", "pilas": FRESH, "carga_pcm1808_ohm": PCM1808_LOAD_OHM,
         "versiones": ["partida", "simple"]}))
    write_json(folder / "resultado.json", {"curvas": results, "chequeos": checks})

    lines = []
    for label in ("partida", "simple"):
        for gain in GAINS:
            r = results[f"{label}-ganancia-{gain}"]
            lines.append(f"{label}, ganancia {gain:>2}: {rounded(r['nivel_a_1khz_db'], 2):5.2f} dB a 1 kHz, -3 dB en "
                         f"{r['corte_inferior_menos_3db_hz']:.2f} Hz y {r['corte_superior_menos_3db_hz']/1e3:.1f} kHz, "
                         f"forma contra ganancia 1 en audio: {r['forma_contra_ganancia_1_de_20hz_a_20khz_db']:.3f} dB")
    return folder, lines, checks


def transient(now):
    name = "sim-transitorio-1v5"
    folder = new_folder(name, now)
    includes = [LINEAR["wrapper"], STAGE]
    gain, peak, tone = 11, 1.5, 1e3
    cases = (("simple-9v", "9 V simples, pila fresca", "single", FRESH),
             ("partida-9v", "±9 V, pilas frescas", "split", FRESH),
             ("partida-7v", "±7 V, pilas gastadas", "split", DEPLETED))
    columns_by_node = {"in": "entrada_v", "adc": "entrada_pcm1808_v", "vpos": "riel_positivo_v",
                       "vneg": "riel_negativo_v", "xstage.inp": "entrada_no_inversora_v",
                       "xstage.outa": "salida_etapa_a_v", "xstage.outb": "salida_etapa_b_v"}
    results, traces, checks = {}, {}, []

    for key, title, version, battery in cases:
        nodes = ["in", "adc", "vpos"] + (["vneg"] if version == "split" else []) + ["xstage.inp", "xstage.outa", "xstage.outb"]
        body = (batteries(version, **battery) + f"Vin in 0 DC 0 SIN(0 {peak} {tone:g})\n" + stage(version, gain)
                + pcm1808_load())
        raws, text = simulate(f"Input stage, {version} supply, {battery['vbat']} V batteries: {peak} V peak at "
                              f"{tone:g} Hz with gain {gain}", body,
                              "tran 5u 10m 0 5u\nwrite tran.raw " + " ".join(f"v({n})" for n in nodes), includes, LINEAR)
        (folder / "netlists" / f"{key}.cir").write_text(text, encoding="utf-8")
        raw = raws["tran.raw"]
        t = np.real(run.vector(raw, "time"))
        v = {n: np.real(run.vector(raw, n)) for n in nodes}
        if version == "single":
            v["vneg"] = np.zeros_like(t)          # the negative rail is ground
        steady = t >= 5e-3
        vpos, vneg = float(np.mean(v["vpos"][steady])), float(np.mean(v["vneg"][steady]))
        rail_current = np.trapezoid((battery["vbat"] - v["vpos"][steady])/battery["rbat"], t[steady])/np.ptp(t[steady])
        inp, outa, adc = v["xstage.inp"][steady], v["xstage.outa"][steady], v["adc"][steady]
        low_limit, high_limit = vneg + TL072_INPUT_OVER_VNEG_V, vpos + TL072_INPUT_OVER_VPOS_V
        results[key] = {
            "caso": title, "alimentacion": "partida" if version == "split" else "simple", "pilas": battery,
            "riel_positivo_v": vpos, "riel_negativo_v": vneg, "corriente_media_del_riel_positivo_ma": float(rail_current*1e3),
            "entrada_no_inversora_min_v": float(inp.min()), "entrada_no_inversora_max_v": float(inp.max()),
            "limite_inferior_de_entrada_v": low_limit, "limite_superior_de_entrada_v": high_limit,
            "margen_inferior_de_entrada_v": float(inp.min() - low_limit),
            "margen_superior_de_entrada_v": float(high_limit - inp.max()),
            "entrada_dentro_de_la_tabla_5_3": bool(inp.min() >= low_limit and inp.max() <= high_limit),
            "salida_etapa_a_min_v": float(outa.min()), "salida_etapa_a_max_v": float(outa.max()),
            "etapa_a_recorta": bool(np.ptp(outa) < 0.95*2*peak*gain),
            "entrada_pcm1808_min_v": float(adc.min()), "entrada_pcm1808_max_v": float(adc.max()),
            "supera_el_fondo_de_escala_del_pcm1808": bool(np.max(np.abs(adc)) > PCM1808_FULL_SCALE_PEAK_V),
            "pin_del_pcm1808_min_v": PCM1808_CENTER_V + float(adc.min()),
            "pin_del_pcm1808_max_v": PCM1808_CENTER_V + float(adc.max()),
            "supera_el_maximo_absoluto_del_pcm1808": bool(PCM1808_CENTER_V + adc.min() < PCM1808_PIN_V[0]
                                                          or PCM1808_CENTER_V + adc.max() > PCM1808_PIN_V[1]),
        }
        traces[key] = (t, v)
        write_csv(folder / f"datos-{key}.csv", {"tiempo_s": t, **{columns_by_node[n]: v[n] for n in columns_by_node}})
        center = vpos/2 if version == "single" else 0.0
        checks.append(check("transitorio", f"amplitud en la entrada no inversora, {title}", "1.5 V de pico a 1 kHz",
                            peak, float((inp.max() - inp.min())/2), 0.03, "V"))
        checks.append(check("transitorio", f"centro de la entrada no inversora, {title}",
                            "0 V con alimentación partida, la mitad del riel con R2 = R3", center,
                            float((inp.max() + inp.min())/2), 0.02, "V"))

    fig, axes = plt.subplots(len(cases), 2, figsize=(12.5, 10.5), sharex=True)
    for row, (key, title, version, _) in enumerate(cases):
        t, v = traces[key]
        r = results[key]
        window = (t >= 5e-3) & (t <= 8e-3)
        ms = (t[window] - 5e-3)*1e3
        left, right = axes[row]
        bottom_edge = r["riel_negativo_v"] - 1
        left.axhspan(bottom_edge, r["limite_inferior_de_entrada_v"], color=ACCENT, alpha=0.10, linewidth=0,
                     label="menos de 4 V sobre el riel negativo")
        for rail in (r["riel_positivo_v"], r["riel_negativo_v"]):
            left.axhline(rail, color="0.6", linewidth=0.8)
        left.plot(ms, v["xstage.outa"][window], color=INK, linewidth=1.6, label="salida de la etapa A")
        left.plot(ms, v["xstage.inp"][window], color="0.55", linewidth=1.6, label="entrada no inversora")
        left.set_ylim(bottom_edge, r["riel_positivo_v"] + 1)
        left.set_title(f"{title}: margen de entrada {r['margen_inferior_de_entrada_v']:+.2f} V", fontsize=10, loc="left")
        style(left, ylabel="V")
        if version == "single":
            left.text(0.99, 0.04, "El modelo no reproduce la inversión de fase:\nesta salida limpia no prueba que no ocurra.",
                      transform=left.transAxes, ha="right", va="bottom", fontsize=8.5, color=INK,
                      bbox={"facecolor": "white", "edgecolor": ACCENT, "linewidth": 0.8, "pad": 4})

        right.axhspan(-PCM1808_FULL_SCALE_PEAK_V, PCM1808_FULL_SCALE_PEAK_V, color="0.5", alpha=0.12, linewidth=0,
                      label="fondo de escala, ±1.5 V")
        for n, limit in enumerate(PCM1808_PIN_V):
            right.axhline(limit - PCM1808_CENTER_V, color=ACCENT, linewidth=1, linestyle="--",
                          label="máximo absoluto del pin, ±2.8 V" if n == 0 else None)
        right.plot(ms, v["adc"][window], color=INK, linewidth=1.6, label="entrada del PCM1808")
        right.set_ylim(-9, 9)
        beyond = ", pasa el máximo absoluto" if r["supera_el_maximo_absoluto_del_pcm1808"] else ""
        right.set_title(f"entrada del PCM1808: de {r['entrada_pcm1808_min_v']:+.1f} a {r['entrada_pcm1808_max_v']:+.1f} V"
                        f"{beyond}", fontsize=10, loc="left")
        style(right, ylabel="V desde el centro del pin")
    for ax in axes[-1]:
        ax.set_xlabel("Tiempo desde los 5 ms simulados (ms)")
    # The curves first, so the long label of the limit goes alone in the second column.
    for ax, x, order in ((axes[0][0], 0.06, (1, 2, 0)), (axes[0][1], 0.54, (2, 0, 1))):
        handles, labels = ax.get_legend_handles_labels()
        fig.legend([handles[i] for i in order], [labels[i] for i in order], loc="lower left", bbox_to_anchor=(x, 0.095),
                   ncol=2, frameon=False, fontsize=8.5)
    fig.suptitle("1.5 V de pico a 1 kHz con ganancia 11: rango de entrada del TL072 y entrada del PCM1808")
    footer(fig, [PHASE_REVERSAL_NOTE,
                 "La simulación no tiene los diodos de protección del PCM1808: en el chip, pasado el máximo absoluto, "
                 "conducen y la tensión no llega a esos valores.",
                 *textwrap.wrap(QUIESCENT_NOTE, 150),
                 "Modelo del TL072 clásico. Carga de 60 kΩ detrás de C3. Pilas: 9 V con 2 Ω, gastadas 7 V con 10 Ω."])
    fig.tight_layout(rect=(0, 0.15, 1, 1))
    fig.savefig(folder / "grafica.png", dpi=150)
    plt.close(fig)

    summary = ("Simulación: margen de entrada del TL072 con 1.5 V de pico, "
               + ", ".join(f"{results[k]['margen_inferior_de_entrada_v']:+.2f} V con {label}"
                           for k, label in (("partida-9v", "±9 V"), ("partida-7v", "±7 V"), ("simple-9v", "9 V simples"))))
    write_json(folder / "condiciones.json", conditions(
        now, name, "Simulación: transitorio con 1.5 V de pico", summary, f"{PHASE_REVERSAL_NOTE} {QUIESCENT_NOTE}",
        LINEAR, includes,
        {"fuente": f"senoidal ideal de {peak} V de pico y {tone:g} Hz a la entrada", "ganancia": gain,
         "potenciometro_ohm": pot_ohm(gain), "tramo_analizado_ms": [5, 10],
         "pilas": {"fresca": FRESH, "gastada": DEPLETED}, "carga_pcm1808_ohm": PCM1808_LOAD_OHM,
         "rango_de_entrada_del_tl072": "de (VCC-) + 4 V a (VCC+) + 0.1 V, tabla 5.3 de su hoja",
         "entrada_del_pcm1808": "fondo de escala 3 Vpp con VCC = 5 V, centro en 2.5 V y máximo absoluto de -0.3 V a "
                                "5.3 V en el pin, tablas 6.1, 6.3 y 6.5 de su hoja"}))
    write_json(folder / "resultado.json", {"casos": results, "chequeos": checks,
                                           "advertencias": [PHASE_REVERSAL_NOTE, QUIESCENT_NOTE]})

    lines = [f"{r['caso']}: entrada no inversora de {r['entrada_no_inversora_min_v']:+.2f} a "
             f"{r['entrada_no_inversora_max_v']:+.2f} V, límite {r['limite_inferior_de_entrada_v']:+.2f} V, margen "
             f"{r['margen_inferior_de_entrada_v']:+.2f} V; etapa A de {r['salida_etapa_a_min_v']:+.2f} a "
             f"{r['salida_etapa_a_max_v']:+.2f} V; PCM1808 de {r['entrada_pcm1808_min_v']:+.2f} a "
             f"{r['entrada_pcm1808_max_v']:+.2f} V" for r in results.values()]
    return folder, lines, checks


def noise(now):
    name = "sim-ruido"
    folder = new_folder(name, now)
    includes = [NOISE["wrapper"], STAGE, GUITAR]
    sources = (("al-aire", "entrada al aire", "open input", None),
               ("guitarra-300pf", "guitarra con cable de 300 pF", "guitar with a 300 pF cable", "300p"),
               ("guitarra-600pf", "guitarra con cable de 600 pF", "guitar with a 600 pF cable", "600p"))
    gains = (1, 11)
    results, columns, checks = {}, {}, []

    for gain in gains:
        for key, title, english, cable in sources:
            if cable is None:
                source = ("* Nothing connected to C1. Rleak only gives that node a DC path, and Vref is the source\n"
                          "* the noise analysis needs as its input.\nVref ref 0 DC 0 AC 1\nRleak ref in 1G\n")
                reference = "vref"
            else:
                source = f"Vemf emf 0 DC 0 AC 1\nXguitar emf in guitar params: ccable={cable}\n"
                reference = "vemf"
            body = batteries("split", **FRESH) + source + stage("split", gain) + pcm1808_load()
            analysis = (f"noise v(adc) {reference} dec 50 1 1meg\nsetplot noise1\n"
                        "write noise.raw onoise_spectrum inoise_spectrum")
            raws, text = simulate(f"Input stage, split supply, gain {gain}: noise at the PCM1808 input, {english}",
                                  body, analysis, includes, NOISE)
            (folder / "netlists" / f"{key}-ganancia-{gain}.cir").write_text(text, encoding="utf-8")
            raw = raws["noise.raw"]
            f = np.real(run.vector(raw, "frequency"))
            onoise = np.abs(run.vector(raw, "onoise_spectrum"))
            same_sweep(columns, f)
            total = band_rms(f, onoise)
            entry = {"fuente": title, "ganancia": gain, "ruido_a_1khz_nv_raiz_hz": at_log(f, onoise, 1e3)*1e9,
                     "ruido_de_20hz_a_20khz_uv": total*1e6,
                     "ruido_de_20hz_a_20khz_dbfs": float(20*np.log10(total/PCM1808_FULL_SCALE_PEAK_V))}
            columns[f"{key.replace('-', '_')}_g{gain}_nv_raiz_hz"] = onoise*1e9
            if cable is not None:
                inoise = np.abs(run.vector(raw, "inoise_spectrum"))
                entry["referido_a_la_pastilla_a_1khz_nv_raiz_hz"] = at_log(f, inoise, 1e3)*1e9
                entry["referido_a_la_pastilla_de_20hz_a_20khz_uv"] = band_rms(f, inoise)*1e6
            results[f"{key}-ganancia-{gain}"] = entry
        open_total = results[f"al-aire-ganancia-{gain}"]["ruido_de_20hz_a_20khz_uv"]
        for key, *_ in sources[1:]:
            entry = results[f"{key}-ganancia-{gain}"]
            entry["contra_la_entrada_al_aire_db"] = float(20*np.log10(entry["ruido_de_20hz_a_20khz_uv"]/open_total))

    # Open input with gain 1: R1's thermal noise, the model's current noise on R1, the voltage noise of both halves
    # of the TL072 and R5's thermal noise, which the filter still passes at 1 kHz.
    kt4 = 4*BOLTZMANN*TEMPERATURE_K
    expected = np.sqrt(kt4*R1_OHM + (MODEL_IN_1K*R1_OHM)**2 + 2*MODEL_EN_1K**2 + kt4*R5_OHM)
    obtained = results["al-aire-ganancia-1"]["ruido_a_1khz_nv_raiz_hz"]*1e-9
    checks.append(check("ruido", "densidad a 1 kHz con la entrada al aire y ganancia 1",
                        "raíz de 4kT·R1 + (in·R1)² + 2·en² + 4kT·R5, con en e in del modelo a 1 kHz",
                        0.0, float(20*np.log10(obtained/expected)), 1.0, "dB"))
    write_csv(folder / "datos.csv", columns)

    f = columns["frecuencia_hz"]
    looks = {"al-aire": (INK, "-"), "guitarra-300pf": (ACCENT, "-"), "guitarra-600pf": (ACCENT, "--")}
    fig, axes = plt.subplots(1, 2, figsize=(12, 6), sharey=True)
    for ax, gain in zip(axes, gains):
        ax.axvspan(*AUDIO_BAND_HZ, color="0.5", alpha=0.07, linewidth=0)
        for key, title, _, _ in sources:
            r = results[f"{key}-ganancia-{gain}"]
            color, line = looks[key]
            ax.loglog(f, columns[f"{key.replace('-', '_')}_g{gain}_nv_raiz_hz"], color=color, linestyle=line,
                      linewidth=1.8, label=f"{title}: {r['ruido_de_20hz_a_20khz_uv']:.1f} µV, "
                                           f"{r['ruido_de_20hz_a_20khz_dbfs']:.1f} dBFS")
        ax.set_title(f"Ganancia {gain}", fontsize=10, loc="left")
        style(ax, "Frecuencia", "Ruido en la entrada del PCM1808 (nV/√Hz)" if gain == gains[0] else None)
        frequency_axis(ax)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}"))
        ax.set_xlim(1, 1e6)
        ax.legend(fontsize=8, loc="lower left", frameon=False)
    fig.suptitle("Ruido con ±9 V: entrada al aire contra la guitarra conectada")
    footer(fig, ["En la leyenda, el ruido de 20 Hz a 20 kHz. 0 dBFS es el pico del fondo de escala del PCM1808, 1.5 V. "
                 "Sombreado: de 20 Hz a 20 kHz.",
                 "El ruido sale del modelo del TL072H; el resto de las simulaciones usa el del TL072 clásico "
                 "(docs/simulador-spice.md).",
                 *textwrap.wrap(CURRENT_NOISE_NOTE, 150)])
    fig.tight_layout(rect=(0, 0.11, 1, 1))
    fig.savefig(folder / "grafica.png", dpi=150)
    plt.close(fig)

    g11 = {k: results[f"{k}-ganancia-11"]["ruido_de_20hz_a_20khz_uv"] for k in ("al-aire", "guitarra-300pf")}
    summary = (f"Simulación: ruido de 20 Hz a 20 kHz con ganancia 11, {g11['al-aire']:.0f} µV al aire y "
               f"{g11['guitarra-300pf']:.0f} µV con la guitarra y 300 pF")
    write_json(folder / "condiciones.json", conditions(
        now, name, "Simulación: ruido", summary, CURRENT_NOISE_NOTE, NOISE, includes,
        {"alimentacion": "partida", "pilas": FRESH, "ganancias": list(gains), "carga_pcm1808_ohm": PCM1808_LOAD_OHM,
         "barrido_hz": [1, 1e6], "puntos_por_decada": 50, "punto_de_salida": "entrada del PCM1808, detrás de C3",
         "entrada_al_aire": "nada conectado a C1, con 1 GΩ a tierra para que ese nodo tenga camino de continua",
         "guitarra": "spice/netlists/guitar.cir con cable de 300 y 600 pF",
         "banda_integrada_hz": list(AUDIO_BAND_HZ), "fondo_de_escala_pcm1808_v_pico": PCM1808_FULL_SCALE_PEAK_V,
         "dbfs": "20·log10(ruido RMS / 1.5 V): 0 dBFS es la muestra de valor 1.0, como en analizador.py",
         "ruido_de_corriente_del_modelo_fa": MODEL_IN_1K*1e15,
         "ruido_de_corriente_del_dip8_en_la_hoja_fa": DATASHEET_DIP8_IN_1K*1e15}))
    write_json(folder / "resultado.json", {"casos": results, "chequeos": checks, "advertencias": [CURRENT_NOISE_NOTE]})

    lines = []
    for r in results.values():
        line = (f"{r['fuente']}, ganancia {r['ganancia']:>2}: {r['ruido_a_1khz_nv_raiz_hz']:.0f} nV/√Hz a 1 kHz, "
                f"{r['ruido_de_20hz_a_20khz_uv']:.1f} µV de 20 Hz a 20 kHz ({r['ruido_de_20hz_a_20khz_dbfs']:.1f} dBFS)")
        if "contra_la_entrada_al_aire_db" in r:
            line += f", {r['contra_la_entrada_al_aire_db']:+.1f} dB contra al aire"
        lines.append(line)
    return folder, lines, checks


def guitar_transfer(f, load_ohm, cable_f):
    """Hand calculation of guitar.cir: the pickup's voltage divided between the coil and the capacitances with the load."""
    w = 2*np.pi*f
    series = GUITAR_R_OHM + 1j*w*GUITAR_L_H
    shunt = 1/(1/load_ohm + 1j*w*(GUITAR_C_F + cable_f))
    return shunt/(series + shunt)


def loading(now):
    name = "sim-carga-guitarra"
    folder = new_folder(name, now)
    loads = (("1meg", 1e6, "1 MΩ"), ("10k", 10e3, "10 kΩ"))
    cables = (("300p", 300e-12), ("600p", 600e-12))
    results, columns, curves, checks = {}, {}, {}, []

    for load_spice, load_ohm, load_label in loads:
        for cable_spice, cable_f in cables:
            key = f"{load_spice}-{cable_spice}f"
            body = f"Vemf emf 0 DC 0 AC 1\nXguitar emf out guitar params: ccable={cable_spice}\nRload out 0 {load_spice}\n"
            raws, text = simulate(f"Guitar alone, loaded with {load_spice} Ohm, {cable_spice}F cable", body,
                                  "ac dec 100 1 1meg\nwrite ac.raw v(out)", [GUITAR])
            (folder / "netlists" / f"{key}.cir").write_text(text, encoding="utf-8")
            f = np.real(run.vector(raws["ac.raw"], "frequency"))
            mag = db(run.vector(raws["ac.raw"], "out"))
            same_sweep(columns, f)
            level_100 = at(f, mag, 100)
            first = int(np.argmax(f >= 100))
            peak = first + int(np.argmax(mag[first:]))
            resonant = peak > first             # with 10 kOhm the curve only falls from 100 Hz on
            results[key] = {
                "carga_ohm": load_ohm, "cable_pf": cable_f*1e12, "nivel_a_100hz_db": level_100,
                "pico_db": float(mag[peak]) if resonant else None,
                "frecuencia_del_pico_hz": float(f[peak]) if resonant else None,
                "pico_sobre_100hz_db": float(mag[peak] - level_100) if resonant else None,
                "nivel_a_5khz_db": at(f, mag, 5e3),
                "cae_3db_bajo_100hz_en_hz": crossing(f, mag, level_100 - 3, int(np.argmin(np.abs(f - 100))), upwards=True),
            }
            curves[(load_spice, cable_spice)] = (mag, load_label)
            columns[f"carga_{load_spice}_cable_{cable_spice}f_db"] = mag
            error = float(np.max(np.abs(mag - db(guitar_transfer(f, load_ohm, cable_f)))))
            checks.append(check("carga", f"magnitud contra el cálculo a mano, {load_label}, cable de {cable_f*1e12:.0f} pF",
                                "el peor punto de 1 Hz a 1 MHz", 0.0, error, 0.01, "dB"))
    write_csv(folder / "datos.csv", columns)

    f = columns["frecuencia_hz"]
    fig, ax = plt.subplots(figsize=(10, 6.2))
    ax.axvspan(*AUDIO_BAND_HZ, color="0.5", alpha=0.07, linewidth=0)
    for (load_spice, cable_spice), (mag, load_label) in curves.items():
        ax.semilogx(f, mag, color=INK if load_spice == "1meg" else ACCENT, linestyle="-" if cable_spice == "300p" else "--",
                    linewidth=2, label=f"carga de {load_label}, cable de {cable_spice[:-1]} pF")
    for key, dx, align in (("1meg-300pf", 10, "left"), ("1meg-600pf", -10, "right")):
        r = results[key]
        ax.plot(r["frecuencia_del_pico_hz"], r["pico_db"], "o", color=INK, markersize=5)
        ax.annotate(f"{r['frecuencia_del_pico_hz']/1e3:.2f} kHz, {r['pico_sobre_100hz_db']:+.1f} dB",
                    (r["frecuencia_del_pico_hz"], r["pico_db"]), textcoords="offset points", xytext=(dx, 6),
                    ha=align, fontsize=9, color=INK)
    low = results["10k-300pf"]
    if low["cae_3db_bajo_100hz_en_hz"]:
        ax.plot(low["cae_3db_bajo_100hz_en_hz"], low["nivel_a_100hz_db"] - 3, "o", color=ACCENT, markersize=5)
        ax.annotate(f"-3 dB en {low['cae_3db_bajo_100hz_en_hz']:.0f} Hz",
                    (low["cae_3db_bajo_100hz_en_hz"], low["nivel_a_100hz_db"] - 3), textcoords="offset points",
                    xytext=(-8, -16), ha="right", fontsize=9, color=INK)
    resonance = results["1meg-300pf"]["frecuencia_del_pico_hz"]
    high_curve, low_curve = at(f, curves[("1meg", "300p")][0], resonance), at(f, curves[("10k", "300p")][0], resonance)
    gap = high_curve - low_curve
    ax.annotate("", xy=(resonance, low_curve), xytext=(resonance, high_curve),
                arrowprops={"arrowstyle": "<->", "color": MUTED, "linewidth": 1})
    ax.text(resonance/1.1, low_curve + 0.3*gap, f"{gap:.0f} dB", fontsize=9, color=INK, ha="right", va="center")
    ax.set_xlim(10, 100e3)
    ax.set_ylim(-45, max(r["pico_db"] for r in results.values() if r["pico_db"] is not None) + 8)
    fig.suptitle("La misma pastilla, cargada con 1 MΩ y con 10 kΩ")
    ax.set_title(f"Con 10 kΩ cae 3 dB en {low['cae_3db_bajo_100hz_en_hz']:.0f} Hz, y a {resonance/1e3:.2f} kHz queda "
                 f"{gap:.0f} dB por debajo de la carga de 1 MΩ", fontsize=10, color=MUTED)
    style(ax, "Frecuencia", "Tensión a la salida del cable, relativa a la de la pastilla (dB)")
    frequency_axis(ax)
    ax.legend(fontsize=9, loc="lower left", frameon=False)
    footer(fig, ["Pastilla: bobina de 5 H en serie con 8 kΩ y 100 pF en paralelo, más la capacitancia del cable "
                 "(spice/netlists/guitar.cir). Sombreado: de 20 Hz a 20 kHz."])
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(folder / "grafica.png", dpi=150)
    plt.close(fig)

    summary = (f"Simulación: con 10 kΩ la pastilla cae 3 dB en {low['cae_3db_bajo_100hz_en_hz']:.0f} Hz; con 1 MΩ "
               f"resuena en {resonance/1e3:.2f} kHz")
    write_json(folder / "condiciones.json", conditions(
        now, name, "Simulación: carga de la guitarra", summary, "", None, [GUITAR],
        {"guitarra": "bobina de 5 H en serie con 8 kΩ, 100 pF en paralelo", "cables_pf": [300, 600],
         "cargas_ohm": [1e6, 10e3], "fuente": "AC 1 V como tensión de la pastilla", "barrido_hz": [1, 1e6],
         "puntos_por_decada": 100}))
    write_json(folder / "resultado.json", {"curvas": results, "chequeos": checks})

    lines = [f"{key}: {r['nivel_a_100hz_db']:+.2f} dB a 100 Hz, "
             + (f"pico de {r['pico_sobre_100hz_db']:+.1f} dB en {r['frecuencia_del_pico_hz']/1e3:.2f} kHz"
                if r["pico_db"] is not None else "sin pico de resonancia")
             + f", {r['nivel_a_5khz_db']:+.1f} dB a 5 kHz, -3 dB en {r['cae_3db_bajo_100hz_en_hz']:.0f} Hz"
             for key, r in results.items()]
    return folder, lines, checks


SIMULATIONS = {"respuesta": frequency_response, "transitorio": transient, "ruido": noise, "carga": loading}


def main():
    chosen = sys.argv[1:] or list(SIMULATIONS)
    unknown = [name for name in chosen if name not in SIMULATIONS]
    if unknown:
        sys.exit(f"No hay simulación {', '.join(unknown)}. Las que hay: {', '.join(SIMULATIONS)}")
    now = datetime.now().astimezone()
    failed = []
    for name in chosen:
        folder, lines, checks = SIMULATIONS[name](now)
        print(f"{name.capitalize()}: guardado en {os.path.relpath(folder)}/")
        for line in lines:
            print(f"  {line}")
        passed = sum(c["paso"] for c in checks)
        print(f"  chequeos contra el cálculo a mano: {passed} de {len(checks)} pasan")
        failed += [c for c in checks if not c["paso"]]
    for c in failed:
        print(f"FALLA  {c['prueba']}, {c['chequeo']}: esperado {c['esperado']:.6g}, obtenido {c['obtenido']}, "
              f"tolerancia {c['tolerancia']:.3g} {c['unidad']}", file=sys.stderr)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
