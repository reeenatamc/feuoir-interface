"""Verificación de analizador.py contra señales sintéticas de resultado conocido.

    .venv/bin/python calibrar.py

Cada chequeo se guarda con sus condiciones, lo esperado, lo obtenido y la tolerancia en
calibraciones/<fecha>-calibracion/resultados.json. Si alguno se sale de tolerancia el
script lo muestra y termina con código 1. Las funciones test_ también corren con pytest.

Las señales de las pruebas de análisis se construyen aquí con numpy, sin usar los
generadores de analizador.py, para que un error en un generador no tape un error en el
análisis. Los generadores se verifican al final, midiéndolos con funciones ya verificadas.

Las tolerancias de las pruebas con ruido son 4 errores estándar del estimador. Las
semillas son fijas, así que el resultado es el mismo en cada corrida.
"""
import hashlib, json, os, platform, sys, traceback
from datetime import datetime
from pathlib import Path

import numpy as np, scipy
from scipy import signal

import analizador as an

RESULTADOS = []
PRUEBA_ACTUAL = ""


def verificar(chequeo, obtenido, esperado, tolerancia, unidad, envolver_grados=False, **condiciones):
    obtenido, esperado = float(obtenido), float(esperado)
    diferencia = obtenido - esperado
    if envolver_grados:
        diferencia = (diferencia + 180) % 360 - 180
    paso = bool(abs(diferencia) <= tolerancia)
    RESULTADOS.append({
        "prueba": PRUEBA_ACTUAL, "chequeo": chequeo, "condiciones": condiciones,
        "esperado": esperado, "obtenido": obtenido, "tolerancia": tolerancia,
        "unidad": unidad, "paso": paso,
    })
    if not paso:
        raise AssertionError(f"{chequeo}: obtenido {obtenido:.9g} {unidad}, esperado {esperado:.9g} "
                             f"con tolerancia {tolerancia:g}, condiciones {condiciones}")


def error_estandar_rms_db(n):
    """Error estándar en dB del RMS de n grados de libertad de ruido gaussiano."""
    return 20*np.log10(1 + 1/np.sqrt(2*n))


# Niveles

def test_seno_pico_rms():
    for fs in (48000, 44100):
        t = np.arange(fs) / fs                     # 1 s, 1000 periodos completos
        for A in (1.0, 0.5, 0.1, 0.001):
            x = A*np.sin(2*np.pi*1000*t)
            c = dict(fs_hz=fs, frecuencia_hz=1000, amplitud=A, duracion_s=1.0)
            verificar("pico_dbfs", an.pico_dbfs(x), 20*np.log10(A), 1e-3, "dBFS", **c)
            verificar("rms_dbfs", an.rms_dbfs(x), 20*np.log10(A/np.sqrt(2)), 1e-3, "dBFS", **c)
    x = 0.2*np.sin(2*np.pi*1000*np.arange(48000)/48000) - 0.5   # el pico es la excursión negativa
    verificar("pico_dbfs_excursion_negativa", an.pico_dbfs(x), 20*np.log10(0.7), 1e-3, "dBFS",
              fs_hz=48000, frecuencia_hz=1000, amplitud=0.2, dc=-0.5, duracion_s=1.0)


def test_ruido_blanco_rms():
    fs, duracion = 48000, 5.0
    n = int(fs*duracion)
    tol = 4*error_estandar_rms_db(n)
    for sigma in (0.1, 0.01, 1e-4):
        x = np.random.default_rng(12345).normal(0.0, sigma, n)
        verificar("rms_dbfs_ruido_gaussiano", an.rms_dbfs(x), 20*np.log10(sigma), tol, "dBFS",
                  fs_hz=fs, duracion_s=duracion, desviacion=sigma, varianza=sigma**2, semilla=12345)
    a = 0.3                                        # uniforme en [-a, a]: varianza a²/3
    x = np.random.default_rng(54321).uniform(-a, a, n)
    verificar("rms_dbfs_ruido_uniforme", an.rms_dbfs(x), 20*np.log10(a/np.sqrt(3)), tol, "dBFS",
              fs_hz=fs, duracion_s=duracion, limite=a, varianza=a**2/3, semilla=54321)


# Espectro

def test_espectro_amplitud():
    fs = 48000
    t = np.arange(fs) / fs
    for A in (1.0, 0.01):
        f, e = an.espectro(A*np.sin(2*np.pi*1000*t), fs)
        c = dict(fs_hz=fs, n=fs, frecuencia_hz=1000, amplitud=A, ventana="hann")
        verificar("pico_espectro_dbfs", np.max(e), 20*np.log10(A), 1e-3, "dBFS", **c)
        verificar("frecuencia_del_pico", f[np.argmax(e)], 1000, 0, "Hz", **c)


def test_dos_tonos_resolucion():
    # Dos tonos iguales separados 2 Hz. Con 0.1 s la resolución es 10 Hz y la separación
    # es 0.2 bins: tienen que verse como un solo pico. Con 2 s la resolución es 0.5 Hz y
    # la separación es 4 bins, el ancho completo del lóbulo principal de la ventana Hann:
    # tienen que verse dos picos, cada uno a menos de medio bin de su frecuencia.
    fs, f1, f2, A = 48000, 1000.1, 1002.1, 0.5
    for duracion, picos_esperados in ((0.1, 1), (2.0, 2)):
        n = int(fs*duracion)
        t = np.arange(n) / fs
        f, _ = an.espectro(np.zeros(n), fs)
        res = an.resolucion_hz(fs, n)
        verificar("resolucion_hz", res, f[1] - f[0], 1e-9, "Hz", fs_hz=fs, n=n)
        for fase in (0.0, np.pi/2, np.pi, 3*np.pi/2):
            x = A*np.sin(2*np.pi*f1*t) + A*np.sin(2*np.pi*f2*t + fase)
            f, e = an.espectro(x, fs)
            picos = np.sort(an.picos_espectrales(f, e, umbral_db=-20.0))
            c = dict(fs_hz=fs, duracion_s=duracion, resolucion_hz=res, f1_hz=f1, f2_hz=f2,
                     separacion_bins=(f2 - f1)/res, amplitud=A, fase_f2_rad=fase,
                     ventana="hann", umbral_dbfs=-20.0)
            verificar("picos_detectados", len(picos), picos_esperados, 0, "picos", **c)
            if picos_esperados == 2:
                verificar("frecuencia_pico_1", picos[0], f1, res/2, "Hz", **c)
                verificar("frecuencia_pico_2", picos[1], f2, res/2, "Hz", **c)


# Ajuste de senoidal

def test_ajuste_seno():
    fs = 48000
    t = np.arange(fs) / fs
    A, f, fase, dc = 0.3, 997.3, 0.7, 0.01       # no cae en un bin
    x = A*np.cos(2*np.pi*f*t + fase) + dc
    for f0 in (None, f + 0.3):
        aj = an.ajuste_seno(x, fs, f0)
        c = dict(fs_hz=fs, duracion_s=1.0, amplitud=A, frecuencia_hz=f, fase_rad=fase, dc=dc,
                 f0_inicial_hz=f0)
        verificar("amplitud", aj["amplitud"], A, 1e-9, "", **c)
        verificar("frecuencia", aj["frecuencia_hz"], f, 1e-6, "Hz", **c)
        verificar("fase", aj["fase_rad"], fase, 1e-6, "rad", **c)
        verificar("dc", aj["dc"], dc, 1e-9, "", **c)


# Distorsión y ruido

def test_thd_n_armonico_1pc():
    fs = 48000
    t = np.arange(fs) / fs
    for f0, orden, fase in ((1000.0, 2, 0.0), (1000.0, 3, 1.1), (997.3, 2, 0.4)):
        x = 0.5*np.sin(2*np.pi*f0*t) + 0.005*np.sin(2*np.pi*orden*f0*t + fase)
        r = an.thd_n(x, fs)
        c = dict(fs_hz=fs, duracion_s=1.0, fundamental_hz=f0, amplitud_fundamental=0.5,
                 orden_armonico=orden, amplitud_armonico=0.005, fase_armonico_rad=fase,
                 banda_hz=[20, 20000], f0_dado=False)
        verificar("thd_n_porcentaje", r["porcentaje"], 1.000, 5e-4, "%", **c)
        verificar("thd_n_db", r["db"], -40.0, 5e-3, "dB", **c)


def test_thd_n_con_ruido():
    fs, duracion, sigma = 48000, 2.0, 1e-3
    n = int(fs*duracion)
    t = np.arange(n) / fs
    x = np.sin(2*np.pi*1000*t) + np.random.default_rng(20260913).normal(0.0, sigma, n)
    for banda in ((20.0, 20000.0), None):
        fraccion = 1.0 if banda is None else (banda[1] - banda[0])/(fs/2)
        esperado = 100*sigma*np.sqrt(fraccion) / (1/np.sqrt(2))
        tol = 4*esperado/np.sqrt(2*n*fraccion)
        verificar("thd_n_porcentaje", an.thd_n(x, fs, banda=banda)["porcentaje"], esperado, tol, "%",
                  fs_hz=fs, duracion_s=duracion, amplitud_fundamental=1.0, fundamental_hz=1000,
                  desviacion_ruido=sigma, semilla=20260913,
                  banda_hz=None if banda is None else list(banda))


def test_snr():
    fs, duracion, A, sigma = 48000, 5.0, 0.5, 1e-3
    n = int(fs*duracion)
    t = np.arange(n) / fs
    con_tono = A*np.sin(2*np.pi*1000*t)
    sin_senal = np.random.default_rng(777).normal(0.0, sigma, n)
    for banda in (None, (20.0, 20000.0)):
        fraccion = 1.0 if banda is None else (banda[1] - banda[0])/(fs/2)
        esperado = 20*np.log10((A/np.sqrt(2)) / (sigma*np.sqrt(fraccion)))
        verificar("snr_db", an.snr_db(con_tono, sin_senal, fs, banda), esperado,
                  4*error_estandar_rms_db(n*fraccion), "dB",
                  fs_hz=fs, duracion_s=duracion, amplitud_tono=A, frecuencia_hz=1000,
                  desviacion_ruido=sigma, semilla=777,
                  banda_hz=None if banda is None else list(banda))


# Generadores

def test_generador_tono():
    fs = 48000
    x = an.tono(1000, fs, 1.0, amplitud_dbfs=-6.0)
    c = dict(fs_hz=fs, frecuencia_hz=1000, duracion_s=1.0, amplitud_dbfs=-6.0)
    verificar("muestras", len(x), fs, 0, "muestras", **c)
    verificar("pico_dbfs", an.pico_dbfs(x), -6.0, 1e-3, "dBFS", **c)
    aj = an.ajuste_seno(x, fs)
    verificar("frecuencia", aj["frecuencia_hz"], 1000, 1e-6, "Hz", **c)
    verificar("amplitud_ajustada_dbfs", 20*np.log10(aj["amplitud"]), -6.0, 1e-6, "dBFS", **c)

    m = int(0.01*fs)
    y = an.tono(1000, fs, 1.0, amplitud_dbfs=-6.0, rampa_s=0.01)
    c["rampa_s"] = 0.01
    verificar("rampa_primera_muestra", abs(y[0]), 0, 1e-12, "", **c)
    verificar("rampa_ultima_muestra", abs(y[-1]), 0, 1e-12, "", **c)
    verificar("rampa_no_toca_el_centro", np.max(np.abs(y[m:-m] - x[m:-m])), 0, 1e-12, "", **c)


def test_generador_barrido_log():
    fs, duracion, f_ini, f_fin = 48000, 5.0, 20.0, 20000.0
    x = an.barrido_log(f_ini, f_fin, fs, duracion, amplitud_dbfs=-6.0)
    c = dict(fs_hz=fs, duracion_s=duracion, f_inicio_hz=f_ini, f_fin_hz=f_fin, amplitud_dbfs=-6.0)
    verificar("muestras", len(x), int(fs*duracion), 0, "muestras", **c)
    verificar("pico_dbfs", an.pico_dbfs(x), -6.0, 0.01, "dBFS", **c)

    # La frecuencia instantánea se mide ajustando una senoidal en una ventana centrada en
    # el instante esperado. La ventana es lo bastante corta para que el barrido no se
    # desfase más de 0.3 rad respecto de un tono fijo dentro de ella.
    L = duracion/np.log(f_fin/f_ini)
    for f_obj in (200.0, 1000.0, 5000.0, 15000.0):
        t_c = L*np.log(f_obj/f_ini)
        mitad = np.sqrt(0.3*L/(np.pi*f_obj))
        tramo = x[int(round((t_c - mitad)*fs)):int(round((t_c + mitad)*fs))]
        verificar("frecuencia_instantanea", an.ajuste_seno(tramo, fs, f_obj)["frecuencia_hz"],
                  f_obj, 1e-3*f_obj, "Hz", instante_s=t_c, ventana_s=2*mitad, **c)


def test_barrido_escalonado_y_respuesta():
    fs = 48000
    frecs = an.frecuencias_log(20.0, 20000.0, 3)
    c = dict(f_inicio_hz=20.0, f_fin_hz=20000.0, por_octava=3)
    verificar("cantidad_de_frecuencias", len(frecs), 30, 0, "", **c)
    verificar("primera_frecuencia", frecs[0], 20.0, 1e-9, "Hz", **c)
    verificar("ultima_frecuencia", frecs[-1], 20*2**(29/3), 1e-6, "Hz", **c)
    verificar("razon_entre_vecinas", np.max(np.abs(frecs[1:]/frecs[:-1] - 2**(1/3))), 0, 1e-12, "", **c)

    x, segs = an.barrido_escalonado(frecs, fs, duracion_tono_s=0.5, amplitud_dbfs=-6.0, rampa_s=0.005)
    c = dict(fs_hz=fs, tonos=len(frecs), duracion_tono_s=0.5, amplitud_dbfs=-6.0, rampa_s=0.005)
    verificar("muestras_barrido", len(x), len(frecs)*fs//2, 0, "muestras", **c)
    verificar("segmentos", len(segs), len(frecs), 0, "", **c)

    # Circuito conocido: pasabajos Butterworth digital de orden 2 en 1 kHz. Su respuesta
    # exacta sale de freqz y se compara con lo que mide respuesta_en_frecuencia.
    b, a = signal.butter(2, 1000, fs=fs)
    y = signal.lfilter(b, a, x)
    _, h = signal.freqz(b, a, worN=frecs, fs=fs)
    filas = an.respuesta_en_frecuencia(y, fs, segs, entrada=x, descarte=0.2)
    c.update(circuito="butter orden 2 pasabajos 1000 Hz", descarte=0.2)
    for fila, hk in zip(filas, h):
        cf = dict(c, frecuencia_hz=fila["frecuencia_hz"])
        verificar("ganancia_db", fila["ganancia_db"], 20*np.log10(abs(hk)), 0.01, "dB", **cf)
        verificar("fase_grados", fila["fase_grados"], np.degrees(np.angle(hk)), 0.1, "grados",
                  envolver_grados=True, **cf)
        verificar("nivel_dbfs", fila["nivel_dbfs"], -6.0 + 20*np.log10(abs(hk)), 0.01, "dBFS", **cf)


PRUEBAS = [
    test_seno_pico_rms,
    test_ruido_blanco_rms,
    test_espectro_amplitud,
    test_dos_tonos_resolucion,
    test_ajuste_seno,
    test_thd_n_armonico_1pc,
    test_thd_n_con_ruido,
    test_snr,
    test_generador_tono,
    test_generador_barrido_log,
    test_barrido_escalonado_y_respuesta,
]


def carpeta_nueva(ahora):
    base = Path(__file__).resolve().parent / "calibraciones" / f"{ahora:%Y-%m-%d}-calibracion"
    carpeta, n = base, 2
    while carpeta.exists():                        # varias corridas el mismo día: -2, -3...
        carpeta, n = base.with_name(f"{base.name}-{n}"), n + 1
    carpeta.mkdir(parents=True)
    return carpeta


def main():
    global PRUEBA_ACTUAL
    ahora = datetime.now().astimezone()
    errores = []
    for prueba in PRUEBAS:
        PRUEBA_ACTUAL = prueba.__name__
        try:
            prueba()
            print(f"ok     {prueba.__name__}")
        except AssertionError as e:
            errores.append({"prueba": prueba.__name__, "error": str(e)})
            print(f"FALLA  {prueba.__name__}\n       {e}", file=sys.stderr)
        except Exception:
            errores.append({"prueba": prueba.__name__, "error": traceback.format_exc()})
            print(f"ERROR  {prueba.__name__}\n{traceback.format_exc()}", file=sys.stderr)

    codigo = Path(an.__file__).read_bytes()
    informe = {
        "fecha_hora": ahora.isoformat(timespec="seconds"),
        "analizador_sha256": hashlib.sha256(codigo).hexdigest(),
        "versiones": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "plataforma": platform.platform(),
        "resumen": {
            "pruebas": len(PRUEBAS),
            "pruebas_fallidas": len(errores),
            "chequeos_ejecutados": len(RESULTADOS),
            "chequeos_fallidos": sum(not r["paso"] for r in RESULTADOS),
        },
        "errores": errores,
        "chequeos": RESULTADOS,
    }
    carpeta = carpeta_nueva(ahora)
    (carpeta / "resultados.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2, default=lambda o: o.item()) + "\n", encoding="utf-8")

    if errores:
        print(f"\nCALIBRACIÓN FALLIDA: {len(errores)} de {len(PRUEBAS)} pruebas no pasaron. "
              f"Detalle en {os.path.relpath(carpeta)}/resultados.json", file=sys.stderr)
        sys.exit(1)
    print(f"\nPasaron las {len(PRUEBAS)} pruebas, {len(RESULTADOS)} chequeos. "
          f"Guardado en {os.path.relpath(carpeta)}/resultados.json")


if __name__ == "__main__":
    main()
