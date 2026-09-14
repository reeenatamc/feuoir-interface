#!/usr/bin/env python3
"""Comprueba que las pruebas siguen atrapando errores inyectados en analizador.py y en la app.

    .venv/bin/python tests/mutaciones.py

Copia analizador.py y calibrar.py a una carpeta temporal, inyecta un error a la vez y corre
calibrar.py sobre esa copia. Cada error tiene que hacer fallar la calibración. Con la app de
medición hace lo mismo: copia analizador.py, app/ y tests/app_contract.py, inyecta un error en
app/ y corre esa prueba. Con la verificación del simulador, lo mismo sobre spice/: le cambia un valor
a un netlist o rompe el lector, y spice/verify.py tiene que fallar. Antes de cada tanda corre una
copia sin cambios como control, que tiene que pasar: si el control falla, que fallen las copias con
errores no demuestra nada.

Cada mutación reemplaza un texto que tiene que aparecer exactamente una vez en su archivo.
Si alguien cambia el archivo y un texto deja de aparecer, el script falla. Hay que actualizar
esa mutación para que siga inyectando el mismo error, no borrarla.

Guarda el resultado con sus condiciones en calibraciones/<fecha>-mutaciones/resultados.json y
termina con código 1 si algún error pasa sin detectarse, si falta un texto o si un control no pasa.
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
    ("banda_inferior_ignorada", "filtro de banda que no corta en la frecuencia inferior",
     "(f < banda[0])", "(f < banda[0]/2)"),
    ("prueba_jitter_pendiente_con_log_natural", "pendiente de la prueba de jitter por década natural en vez de decimal",
     "np.polyfit(np.log10(f), thd_db, 1)", "np.polyfit(np.log(f), thd_db, 1)"),
    ("prueba_jitter_sin_piso", "modelo de la prueba de jitter sin el término del ruido de fondo",
     "np.column_stack([fe**2, np.ones_like(fe)])", "np.column_stack([fe**2, np.zeros_like(fe)])"),
    ("prueba_jitter_sin_fraccion_de_banda", "jitter equivalente sin corregir por el ancho de la banda medida",
     "np.sqrt(a/fraccion)", "np.sqrt(a)"),
    ("prueba_jitter_banda_proporcional", "banda que crece con la frecuencia del tono, con más ruido de fondo en los agudos",
     "(fr - media_banda_hz, fr + media_banda_hz)", "(fr/2, 3*fr/2)"),
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

# Los archivos que necesita tests/app_contract.py para correr en una carpeta aparte
ARCHIVOS_APP = ["analizador.py", "app/__init__.py", "app/processing.py", "app/sources.py", "app/measurements.py",
                "app/server.py", "tests/app_contract.py"]

# nombre, error que simula, archivo, texto original, texto que lo reemplaza
MUTACIONES_APP = [
    ("saturacion_con_muestras_salteadas", "detector de saturación que mira una muestra de cada dos",
     "app/processing.py", "peak = float(np.max(np.abs(x)))", "peak = float(np.max(np.abs(x[::2])))"),
    ("pico_sin_sostener_entre_bloques", "pico del cuadro que se queda con el último bloque en vez del máximo",
     "app/processing.py", "self._frame_peak = max(self._frame_peak, peak)", "self._frame_peak = peak"),
    ("espectro_reducido_con_minimo", "reducción del espectro que se queda con el mínimo de cada tramo",
     "app/processing.py", "np.maximum.reduceat(", "np.minimum.reduceat("),
    ("espectro_en_vivo_con_hann", "espectro en vivo con Hann, que baja el pico de un tono que cae entre bins",
     "app/processing.py", 'SPECTRUM_WINDOW = "flattop"', 'SPECTRUM_WINDOW = "hann"'),
    ("fuente_sintetica_nivel_en_potencia", "nivel de la fuente sintética con 10**(dB/10) en vez de 10**(dB/20)",
     "app/sources.py", 'amplitude = 10**(s["level_dbfs"]/20)', 'amplitude = 10**(s["level_dbfs"]/10)'),
    ("medicion_marcada_tarde", "medición en curso marcada recién cuando arranca su tarea",
     "app/server.py", '        engine.measuring = message["measurement"]\n', ""),
    ("guardadas_de_la_mas_vieja", "lista de mediciones guardadas de la más vieja a la más reciente",
     "app/measurements.py", "reverse=True)", "reverse=False)"),
    ("abrir_guardada_sin_validar", "abre cualquier carpeta que exista, aunque salga de mediciones/",
     "app/server.py", "if path.parent != self.destination.resolve() or not path.is_dir():", "if not path.is_dir():"),
    ("estimulo_sin_la_salida_elegida", "estímulo que suena por la salida por defecto aunque se haya elegido otra",
     "app/measurements.py", "self.source.play(stimulus, self.output_index)", "self.source.play(stimulus, None)"),
    ("reproducir_sin_pasar_la_salida", "entrada real que reproduce sin decirle a sounddevice por qué salida",
     "app/sources.py", "self.fs, device=output)", "self.fs)"),
    ("cuadros_esperando_a_cada_conexion", "emisor que espera a que cada conexión reciba el cuadro: una lenta frena a todas",
     "app/server.py", '            for client in list(app[CLIENTS]):\n                client.send_frame(text)\n',
     '            await asyncio.gather(*(client.ws.send_str(text) for client in list(app[CLIENTS])))\n'),
]

# Los archivos que necesita spice/verify.py para correr en una carpeta aparte
ARCHIVOS_SPICE = ["spice/__init__.py", "spice/run.py", "spice/verify.py",
                  "spice/netlists/verify_divider.cir", "spice/netlists/verify_rc_lowpass.cir"]

# nombre, error que simula, archivo, texto original, texto que lo reemplaza
MUTACIONES_SPICE = [
    ("spice_divisor_con_otra_resistencia", "divisor con la resistencia de abajo cambiada: otro punto de operación",
     "spice/netlists/verify_divider.cir", "Rbottom mid 0 1k", "Rbottom mid 0 1.1k"),
    ("spice_filtro_con_otro_capacitor", "filtro RC con el doble de capacidad: el corte en la mitad de la frecuencia",
     "spice/netlists/verify_rc_lowpass.cir", "C1 out 0 1n", "C1 out 0 2n"),
    ("spice_lector_sin_parte_imaginaria", "lector de .raw que descarta la parte imaginaria y pierde la fase",
     "spice/run.py", "complex(float(re_part), float(im_part or 0.0))", "complex(float(re_part), 0.0)"),
    ("spice_ruido_con_otra_temperatura", "teoría del ruido calculada a 17 °C en vez de los 27 °C de ngspice",
     "spice/verify.py", "TEMPERATURE_K = 300.15", "TEMPERATURE_K = 290.15"),
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


def correr_app(carpeta, archivos, python, limite_s):
    carpeta.mkdir()
    for relativa, texto in archivos.items():
        (carpeta / relativa).parent.mkdir(parents=True, exist_ok=True)
        (carpeta / relativa).write_text(texto, encoding="utf-8")
    try:
        r = subprocess.run([python, "tests/app_contract.py"], cwd=carpeta, capture_output=True, text=True,
                           timeout=limite_s)
    except subprocess.TimeoutExpired:
        return {"codigo_salida": None, "tiempo_agotado": True, "pruebas_que_fallan": []}
    fallan = [linea[len("FALLA "):].split("  (")[0].strip() for linea in r.stdout.splitlines()
              if linea.startswith("FALLA ")]
    return {"codigo_salida": r.returncode, "tiempo_agotado": False, "pruebas_que_fallan": fallan}


def correr_spice(carpeta, archivos, python, limite_s):
    carpeta.mkdir()
    for relativa, texto in archivos.items():
        (carpeta / relativa).parent.mkdir(parents=True, exist_ok=True)
        (carpeta / relativa).write_text(texto, encoding="utf-8")
    try:
        r = subprocess.run([python, "-m", "spice.verify"], cwd=carpeta, capture_output=True, text=True,
                           timeout=limite_s)
    except subprocess.TimeoutExpired:
        return {"codigo_salida": None, "tiempo_agotado": True, "pruebas_que_fallan": []}
    fallan = sorted({linea.split()[1].rstrip(":") for linea in r.stderr.splitlines()
                     if linea.startswith(("FALLA ", "ERROR ")) and len(linea.split()) > 1
                     and linea.split()[1].startswith("test_")})
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


def registrar(resultados, nombre, descripcion, archivo, prueba, original, reemplazo, r):
    detectada = r["codigo_salida"] != 0
    resultados.append({"mutacion": nombre, "error_simulado": descripcion, "archivo": archivo, "prueba": prueba,
                       "texto_original": original, "reemplazo": reemplazo, **r, "detectada": detectada})
    if detectada:
        motivo = "; ".join(r["pruebas_que_fallan"]) or "tiempo agotado"
        print(f"ok     {nombre}: la atrapa {motivo}")
    else:
        print(f"SOBREVIVE  {nombre}: {prueba} pasó con el error inyectado ({descripcion})", file=sys.stderr)


def main():
    p = argparse.ArgumentParser(description="Comprueba que las pruebas atrapan errores inyectados en analizador.py y en la app")
    p.add_argument("--trabajos", type=int, default=3,
                   help="pruebas corriendo a la vez; por defecto 3 para no llenar la memoria")
    p.add_argument("--limite-s", type=float, default=900, help="tiempo máximo de cada prueba, en segundos")
    args = p.parse_args()

    ahora = datetime.now().astimezone()
    python = str(PYTHON_VENV) if PYTHON_VENV.exists() else sys.executable
    analizador = (RAIZ / "analizador.py").read_text(encoding="utf-8")
    calibrar = (RAIZ / "calibrar.py").read_text(encoding="utf-8")
    app = {relativa: (RAIZ / relativa).read_text(encoding="utf-8") for relativa in ARCHIVOS_APP}
    spice = {relativa: (RAIZ / relativa).read_text(encoding="utf-8") for relativa in ARCHIVOS_SPICE}
    total = len(MUTACIONES) + len(MUTACIONES_APP) + len(MUTACIONES_SPICE)

    archivo_de = {nombre: "analizador.py" for nombre, *_ in MUTACIONES}
    archivo_de.update({nombre: archivo for nombre, _, archivo, _, _ in MUTACIONES_APP})
    archivo_de.update({nombre: archivo for nombre, _, archivo, _, _ in MUTACIONES_SPICE})
    apariciones = {nombre: analizador.count(original) for nombre, _, original, _ in MUTACIONES}
    apariciones.update({nombre: app[archivo].count(original) for nombre, _, archivo, original, _ in MUTACIONES_APP})
    apariciones.update({nombre: spice[archivo].count(original) for nombre, _, archivo, original, _ in MUTACIONES_SPICE})
    faltan = [nombre for nombre, veces in apariciones.items() if veces != 1]
    for nombre in faltan:
        print(f"FALTA  {nombre}: el texto a reemplazar aparece {apariciones[nombre]} veces en {archivo_de[nombre]} "
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
                    registrar(resultados, nombre, descripcion, "analizador.py", "calibrar.py", original, reemplazo,
                              futuro.result())
        else:
            print(f"FALLA  control: calibrar.py no pasa con analizador.py sin cambios "
                  f"(código {control['codigo_salida']}); no se corren sus mutaciones", file=sys.stderr)

        control_app = correr_app(tmp / "control-app", app, python, args.limite_s)
        control_app_pasa = control_app["codigo_salida"] == 0
        if control_app_pasa:
            print("ok     control: tests/app_contract.py pasa con app/ sin cambios")
            aplicables = [m for m in MUTACIONES_APP if apariciones[m[0]] == 1]
            with ThreadPoolExecutor(max_workers=args.trabajos) as ex:
                futuros = [ex.submit(correr_app, tmp / nombre, {**app, archivo: app[archivo].replace(original, reemplazo)},
                                     python, args.limite_s)
                           for nombre, _, archivo, original, reemplazo in aplicables]
                for (nombre, descripcion, archivo, original, reemplazo), futuro in zip(aplicables, futuros):
                    registrar(resultados, nombre, descripcion, archivo, "tests/app_contract.py", original, reemplazo,
                              futuro.result())
        else:
            print(f"FALLA  control: tests/app_contract.py no pasa con app/ sin cambios "
                  f"(código {control_app['codigo_salida']}); no se corren sus mutaciones", file=sys.stderr)

        control_spice = correr_spice(tmp / "control-spice", spice, python, args.limite_s)
        control_spice_pasa = control_spice["codigo_salida"] == 0
        if control_spice_pasa:
            print("ok     control: spice/verify.py pasa con spice/ sin cambios")
            aplicables = [m for m in MUTACIONES_SPICE if apariciones[m[0]] == 1]
            with ThreadPoolExecutor(max_workers=args.trabajos) as ex:
                futuros = [ex.submit(correr_spice, tmp / nombre,
                                     {**spice, archivo: spice[archivo].replace(original, reemplazo)}, python, args.limite_s)
                           for nombre, _, archivo, original, reemplazo in aplicables]
                for (nombre, descripcion, archivo, original, reemplazo), futuro in zip(aplicables, futuros):
                    registrar(resultados, nombre, descripcion, archivo, "spice/verify.py", original, reemplazo,
                              futuro.result())
        else:
            print(f"FALLA  control: spice/verify.py no pasa con spice/ sin cambios "
                  f"(código {control_spice['codigo_salida']}); no se corren sus mutaciones", file=sys.stderr)

    sobreviven = [r["mutacion"] for r in resultados if not r["detectada"]]
    informe = {
        "fecha_hora": ahora.isoformat(timespec="seconds"),
        "analizador_sha256": sha256(analizador),
        "calibrar_sha256": sha256(calibrar),
        "app_sha256": {relativa: sha256(texto) for relativa, texto in app.items()},
        "spice_sha256": {relativa: sha256(texto) for relativa, texto in spice.items()},
        "python_de_las_pruebas": python,
        "versiones": versiones(python),
        "plataforma": platform.platform(),
        "condiciones": {"trabajos": args.trabajos, "limite_s": args.limite_s},
        "control": {**control, "pasa": control_pasa},
        "control_app": {**control_app, "pasa": control_app_pasa},
        "control_spice": {**control_spice, "pasa": control_spice_pasa},
        "textos_no_encontrados": {nombre: apariciones[nombre] for nombre in faltan},
        "resumen": {
            "mutaciones": total,
            "corridas": len(resultados),
            "detectadas": sum(r["detectada"] for r in resultados),
            "sobreviven": sobreviven,
        },
        "mutaciones": resultados,
    }
    carpeta = carpeta_nueva(ahora)
    ruta = carpeta / "resultados.json"
    ruta.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if faltan or sobreviven or not control_pasa or not control_app_pasa or not control_spice_pasa or len(resultados) != total:
        print(f"\nMUTACIONES FALLIDAS. Detalle en {os.path.relpath(ruta)}", file=sys.stderr)
        sys.exit(1)
    print(f"\nLas {total} mutaciones hicieron fallar sus pruebas. Guardado en {os.path.relpath(ruta)}")


if __name__ == "__main__":
    main()
