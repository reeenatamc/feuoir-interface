#!/usr/bin/env python3
"""Comprueba que calibrar.py sigue atrapando errores inyectados en analizador.py.

    .venv/bin/python tests/mutaciones.py

Copia analizador.py y calibrar.py a una carpeta temporal, inyecta un error a la vez y corre
calibrar.py sobre esa copia. Cada error tiene que hacer fallar la calibración. Antes corre una
copia sin cambios como control, que tiene que pasar: si el control falla, que fallen las copias
con errores no demuestra nada.

Cada mutación reemplaza un texto que tiene que aparecer exactamente una vez en analizador.py.
Si alguien cambia analizador.py y un texto deja de aparecer, el script falla. Hay que actualizar
esa mutación para que siga inyectando el mismo error, no borrarla.

Guarda el resultado con sus condiciones en calibraciones/<fecha>-mutaciones/resultados.json y
termina con código 1 si algún error pasa sin detectarse, si falta un texto o si el control no pasa.
"""
import argparse, hashlib, json, os, platform, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PYTHON_VENV = RAIZ / ".venv" / "bin" / "python"

# nombre, error que simula, texto original en analizador.py, texto que lo reemplaza
MUTACIONES = [
    ("rms_sin_raiz", "RMS calculado como potencia media, sin la raíz",
     "np.sqrt(np.mean(x**2))", "np.mean(x**2)"),
    ("pico_sin_valor_absoluto", "pico calculado como max(x) en vez de max(|x|)",
     "np.max(np.abs(x))", "np.max(x)"),
    ("espectro_sin_factor_2", "espectro de un solo lado sin el factor 2",
     "amplitud = 2*np.abs(", "amplitud = np.abs("),
    ("resolucion_a_la_mitad", "resolución de la FFT calculada con el doble de muestras",
     "return fs / n", "return fs / (2*n)"),
    ("picos_sin_umbral", "búsqueda de picos que ignora el umbral",
     "height=umbral_db", "height=None"),
    ("ajuste_sin_refinar_frecuencia", "ajuste de senoidal que no refina la frecuencia",
     "for _ in range(iteraciones):", "for _ in range(0):"),
    ("fase_con_signo_invertido", "fase del ajuste con el signo cambiado",
     "np.arctan2(-b, a)", "np.arctan2(b, a)"),
    ("thd_n_sin_raiz_de_2", "RMS de la fundamental tomado igual a su amplitud de pico",
     '(aj["amplitud"]/np.sqrt(2))', 'aj["amplitud"]'),
    ("banda_superior_ignorada", "filtro de banda que no corta en la frecuencia superior",
     "(f > banda[1])", "(f > 2*banda[1])"),
    ("snr_en_potencia", "SNR con razón de potencias pasada por 20*log10",
     "rms(senal) / (rms(ruido) + EPS)", "rms(senal)**2 / (rms(ruido)**2 + EPS)"),
    ("tono_con_amplitud_mal_escalada", "amplitud del tono con 10**(dB/10) en vez de 10**(dB/20)",
     "x = 10**(amplitud_dbfs/20) * np.sin", "x = 10**(amplitud_dbfs/10) * np.sin"),
    ("rampa_final_sin_invertir", "rampa del final que sube en vez de bajar",
     "env[n-m:] = sube[::-1]", "env[n-m:] = sube"),
    ("barrido_log_con_log10", "barrido exponencial con log10 en vez de logaritmo natural",
     "L = duracion_s / np.log(f_fin/f_inicio)", "L = duracion_s / np.log10(f_fin/f_inicio)"),
    ("frecuencias_log_una_de_mas", "frecuencias_log con una frecuencia de más",
     "+ 1e-9)) + 1", "+ 1e-9)) + 2"),
    ("respuesta_con_fase_invertida", "fase de la respuesta en frecuencia restada al revés",
     'sal["fase_rad"] - ent["fase_rad"]', 'ent["fase_rad"] - sal["fase_rad"]'),
]


def sha256(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def correr_calibracion(carpeta, analizador, calibrar, python, limite_s):
    carpeta.mkdir()
    (carpeta / "analizador.py").write_text(analizador, encoding="utf-8")
    (carpeta / "calibrar.py").write_text(calibrar, encoding="utf-8")
    try:
        r = subprocess.run([python, "calibrar.py"], cwd=carpeta, capture_output=True, text=True, timeout=limite_s)
    except subprocess.TimeoutExpired:
        return {"codigo_salida": None, "tiempo_agotado": True, "pruebas_que_fallan": []}
    fallan = [linea.split()[1] for linea in r.stderr.splitlines()
              if linea.startswith(("FALLA ", "ERROR ")) and len(linea.split()) > 1]
    return {"codigo_salida": r.returncode, "tiempo_agotado": False, "pruebas_que_fallan": fallan}


def versiones(python):
    r = subprocess.run([python, "-c", "import platform, numpy, scipy; "
                        "print(platform.python_version(), numpy.__version__, scipy.__version__)"],
                       capture_output=True, text=True)
    partes = r.stdout.split()
    return dict(zip(("python", "numpy", "scipy"), partes)) if len(partes) == 3 else {"error": r.stderr.strip()}


def carpeta_nueva(ahora):
    base = RAIZ / "calibraciones" / f"{ahora:%Y-%m-%d}-mutaciones"
    carpeta, n = base, 2
    while carpeta.exists():                        # varias corridas el mismo día: -2, -3...
        carpeta, n = base.with_name(f"{base.name}-{n}"), n + 1
    carpeta.mkdir(parents=True)
    return carpeta


def main():
    p = argparse.ArgumentParser(description="Comprueba que calibrar.py atrapa errores inyectados en analizador.py")
    p.add_argument("--trabajos", type=int, default=3,
                   help="calibraciones corriendo a la vez; por defecto 3 para no llenar la memoria")
    p.add_argument("--limite-s", type=float, default=900, help="tiempo máximo de cada calibración, en segundos")
    args = p.parse_args()

    ahora = datetime.now().astimezone()
    python = str(PYTHON_VENV) if PYTHON_VENV.exists() else sys.executable
    analizador = (RAIZ / "analizador.py").read_text(encoding="utf-8")
    calibrar = (RAIZ / "calibrar.py").read_text(encoding="utf-8")

    apariciones = {nombre: analizador.count(original) for nombre, _, original, _ in MUTACIONES}
    faltan = [nombre for nombre, veces in apariciones.items() if veces != 1]
    for nombre in faltan:
        print(f"FALTA  {nombre}: el texto a reemplazar aparece {apariciones[nombre]} veces en analizador.py "
              "y tiene que aparecer una sola", file=sys.stderr)

    resultados = []
    with tempfile.TemporaryDirectory(prefix="mutaciones-") as tmp:
        tmp = Path(tmp)
        control = correr_calibracion(tmp / "control", analizador, calibrar, python, args.limite_s)
        control_pasa = control["codigo_salida"] == 0
        if control_pasa:
            print("ok     control: calibrar.py pasa con analizador.py sin cambios")
            aplicables = [m for m in MUTACIONES if apariciones[m[0]] == 1]
            with ThreadPoolExecutor(max_workers=args.trabajos) as ex:
                futuros = [ex.submit(correr_calibracion, tmp / nombre, analizador.replace(original, reemplazo),
                                     calibrar, python, args.limite_s)
                           for nombre, _, original, reemplazo in aplicables]
                for (nombre, descripcion, original, reemplazo), futuro in zip(aplicables, futuros):
                    r = futuro.result()
                    detectada = r["codigo_salida"] != 0
                    resultados.append({"mutacion": nombre, "error_simulado": descripcion,
                                       "texto_original": original, "reemplazo": reemplazo,
                                       **r, "detectada": detectada})
                    if detectada:
                        motivo = ", ".join(r["pruebas_que_fallan"]) or "tiempo agotado"
                        print(f"ok     {nombre}: la atrapa {motivo}")
                    else:
                        print(f"SOBREVIVE  {nombre}: calibrar.py pasó con el error inyectado ({descripcion})",
                              file=sys.stderr)
        else:
            print(f"FALLA  control: calibrar.py no pasa con analizador.py sin cambios "
                  f"(código {control['codigo_salida']}); no se corren las mutaciones", file=sys.stderr)

    sobreviven = [r["mutacion"] for r in resultados if not r["detectada"]]
    informe = {
        "fecha_hora": ahora.isoformat(timespec="seconds"),
        "analizador_sha256": sha256(analizador),
        "calibrar_sha256": sha256(calibrar),
        "python_de_las_calibraciones": python,
        "versiones": versiones(python),
        "plataforma": platform.platform(),
        "condiciones": {"trabajos": args.trabajos, "limite_s": args.limite_s},
        "control": {**control, "pasa": control_pasa},
        "textos_no_encontrados": {nombre: apariciones[nombre] for nombre in faltan},
        "resumen": {
            "mutaciones": len(MUTACIONES),
            "corridas": len(resultados),
            "detectadas": sum(r["detectada"] for r in resultados),
            "sobreviven": sobreviven,
        },
        "mutaciones": resultados,
    }
    carpeta = carpeta_nueva(ahora)
    ruta = carpeta / "resultados.json"
    ruta.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if faltan or sobreviven or not control_pasa or len(resultados) != len(MUTACIONES):
        print(f"\nMUTACIONES FALLIDAS. Detalle en {os.path.relpath(ruta)}", file=sys.stderr)
        sys.exit(1)
    print(f"\nLas {len(MUTACIONES)} mutaciones hicieron fallar la calibración. Guardado en {os.path.relpath(ruta)}")


if __name__ == "__main__":
    main()
