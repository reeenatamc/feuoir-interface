"""Checks ngspice against circuits with a known result, before trusting it with the real circuit.

    .venv/bin/python -m spice.verify

Simulates a resistive divider and a first-order RC low-pass and compares each result with the theory within a
tolerance: the divider's operating point, and the filter's magnitude and phase from 10 Hz to 10 MHz, its step
response and its thermal noise. Saves every check with its conditions in calibraciones/<date>-spice/resultados.json,
in the same format as calibrar.py, and exits with code 1 if a check is out of tolerance or a simulation fails. If this
does not pass, no other simulation in the repo counts. The checks are printed in Spanish.
"""
import hashlib
import json
import os
import platform
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np

from spice import run

ROOT = Path(__file__).resolve().parent.parent
NETLISTS = Path(__file__).resolve().parent / "netlists"
BOLTZMANN = 1.380649e-23     # J/K
TEMPERATURE_K = 300.15       # ngspice simulates at 27 °C unless the netlist says otherwise

RESULTS = []
CURRENT_TEST = None


def check(name, obtained, expected, tolerance, unit, conditions=None):
    passed = bool(abs(obtained - expected) <= tolerance)
    RESULTS.append({"prueba": CURRENT_TEST, "chequeo": name, "condiciones": conditions or {},
                    "esperado": float(expected), "obtenido": float(obtained), "tolerancia": float(tolerance),
                    "unidad": unit, "paso": passed})
    line = f"{name}: {obtained:.6g} {unit} (esperado {expected:.6g} ± {tolerance:g})"
    if passed:
        print(f"ok     {line}")
    else:
        print(f"FALLA  {CURRENT_TEST} {line}", file=sys.stderr)


def test_raw_reader():
    """The reader against hand-written raw files, so a reader bug is not mistaken for a simulator error."""
    real_raw = ("Title: divider\nDate: today\nPlotname: Operating Point\nFlags: real\nNo. Variables: 2\n"
                "No. Points: 1\nVariables:\n\t0\tv(mid)\tvoltage\n\t1\tv(in)\tvoltage\nValues:\n 0\t1.5e+00\n\t9.0e+00\n")
    complex_raw = ("Title: rc\nDate: today\nPlotname: AC Analysis\nFlags: complex\nNo. Variables: 2\nNo. Points: 2\n"
                   "Variables:\n\t0\tfrequency\tfrequency grid=3\n\t1\tv(out)\tvoltage\nValues:\n"
                   " 0\t1.0e+01,0.0e+00\n\t9.0e-01,-3.0e-01\n\n 1\t1.0e+02,0.0e+00\n\t5.0e-01,-5.0e-01\n")
    with tempfile.TemporaryDirectory(prefix="raw-") as folder:
        (Path(folder) / "real.raw").write_text(real_raw)
        (Path(folder) / "complex.raw").write_text(complex_raw)
        real = run.read_ascii_raw(Path(folder) / "real.raw")
        cplx = run.read_ascii_raw(Path(folder) / "complex.raw")
    check("lector de .raw: nombres de las variables reales", float(sorted(real) == ["v(in)", "v(mid)"]), 1.0, 0.0, "")
    check("lector de .raw: valor real de la segunda variable", float(real["v(in)"][0]), 9.0, 0.0, "V")
    check("lector de .raw: parte imaginaria del segundo punto complejo", float(np.imag(cplx["v(out)"][1])), -0.5, 0.0, "V")
    check("lector de .raw: escala de frecuencia", float(np.real(cplx["frequency"][1])), 100.0, 0.0, "Hz")


def test_divider():
    raws, _ = run.simulate((NETLISTS / "verify_divider.cir").read_text(encoding="utf-8"))
    midpoint = float(np.real(run.vector(raws["divider_op.raw"], "mid")[0]))
    check("divisor: tensión en el punto medio", midpoint, 9.0 * 1e3 / (4.7e3 + 1e3), 1e-6, "V",
          {"fuente_v": 9.0, "r_arriba_ohm": 4.7e3, "r_abajo_ohm": 1e3})


def test_rc_lowpass():
    r, c = 4.7e3, 1e-9
    fc, tau = 1/(2*np.pi*r*c), r*c
    conditions = {"r_ohm": r, "c_f": c, "corte_hz": fc}
    raws, _ = run.simulate((NETLISTS / "verify_rc_lowpass.cir").read_text(encoding="utf-8"))

    ac = raws["rc_ac.raw"]
    f = np.real(run.vector(ac, "frequency"))
    h = run.vector(ac, "out")
    magnitude_db = 20*np.log10(np.abs(h))
    phase_deg = np.degrees(np.angle(h))
    check("filtro RC: error máximo de magnitud de 10 Hz a 10 MHz",
          np.max(np.abs(magnitude_db + 10*np.log10(1 + (f/fc)**2))), 0.0, 0.01, "dB", conditions)
    check("filtro RC: error máximo de fase de 10 Hz a 10 MHz",
          np.max(np.abs(phase_deg + np.degrees(np.arctan(f/fc)))), 0.0, 0.05, "°", conditions)
    check("filtro RC: magnitud en la frecuencia de corte",
          np.interp(np.log10(fc), np.log10(f), magnitude_db), -10*np.log10(2), 0.01, "dB", conditions)

    tran = raws["rc_tran.raw"]
    t, v = np.real(run.vector(tran, "time")), np.real(run.vector(tran, "out"))
    for k in (1, 3, 5):
        check(f"filtro RC: respuesta a un escalón de 1 V en t = {k} RC", np.interp(k*tau, t, v), 1 - np.exp(-k), 2e-3,
              "V", {**conditions, "tiempo_s": k*tau})

    noise = {**conditions, "temperatura_k": TEMPERATURE_K}
    spectrum = raws["rc_noise_spectrum.raw"]
    fn = np.real(run.vector(spectrum, "frequency"))
    density = np.abs(run.vector(spectrum, "onoise_spectrum"))
    expected_10hz = np.sqrt(4*BOLTZMANN*TEMPERATURE_K*r) / np.sqrt(1 + (10/fc)**2)
    check("filtro RC: ruido térmico a 10 Hz, raíz de 4kTR", np.interp(1.0, np.log10(fn), density)*1e9,
          expected_10hz*1e9, 0.01*expected_10hz*1e9, "nV/√Hz", noise)
    f1, f2 = 1.0, 1e9
    expected_total = np.sqrt(4*BOLTZMANN*TEMPERATURE_K*r*fc*(np.arctan(f2/fc) - np.arctan(f1/fc)))
    total = float(np.abs(run.vector(raws["rc_noise_total.raw"], "onoise_total")[0]))
    check("filtro RC: ruido total de 1 Hz a 1 GHz, casi raíz de kT/C", total*1e6, expected_total*1e6,
          0.01*expected_total*1e6, "µV", {**noise, "banda_hz": [f1, f2]})


TESTS = [test_raw_reader, test_divider, test_rc_lowpass]


def new_folder(now):
    base = ROOT / "calibraciones" / f"{now:%Y-%m-%d}-spice"
    folder, n = base, 2
    while folder.exists():                         # several runs on the same day: -2, -3...
        folder, n = base.with_name(f"{base.name}-{n}"), n + 1
    folder.mkdir(parents=True)
    return folder


def main():
    global CURRENT_TEST
    now = datetime.now().astimezone()
    errors = []
    for test in TESTS:
        CURRENT_TEST = test.__name__
        try:
            test()
        except Exception as e:
            print(f"ERROR  {test.__name__}: {e}", file=sys.stderr)
            errors.append({"prueba": test.__name__, "error": traceback.format_exc()})

    try:
        ngspice = {"ruta": run.ngspice_path(), "version": run.version()}
    except Exception as e:
        ngspice = {"error": str(e)}
    report = {
        "fecha_hora": now.isoformat(timespec="seconds"),
        "ngspice": ngspice,
        "netlists_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(NETLISTS.glob("verify_*.cir"))},
        "versiones": {"python": platform.python_version(), "numpy": np.__version__},
        "plataforma": platform.platform(),
        "resumen": {
            "pruebas": len(TESTS),
            "pruebas_fallidas": len(errors),
            "chequeos_ejecutados": len(RESULTS),
            "chequeos_fallidos": sum(not r["paso"] for r in RESULTS),
        },
        "errores": errors,
        "chequeos": RESULTS,
    }
    folder = new_folder(now)
    (folder / "resultados.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if errors or report["resumen"]["chequeos_fallidos"]:
        print(f"\nFALLA  la verificación del simulador. Detalle en {os.path.relpath(folder)}/resultados.json",
              file=sys.stderr)
        sys.exit(1)
    print(f"\nngspice coincide con la teoría en los {len(RESULTS)} chequeos. Guardado en {os.path.relpath(folder)}/resultados.json")


if __name__ == "__main__":
    main()
