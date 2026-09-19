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


# Guitar and mains

def test_crest_factor_db():
    fs = 48000
    t = np.arange(fs) / fs
    seno = np.sin(2*np.pi*1000*t)
    cuadrada = np.sign(np.sin(2*np.pi*1000*t))
    c = dict(fs_hz=fs, frecuencia_hz=1000, duracion_s=1.0)
    verificar("crest_factor_db_seno", an.crest_factor_db(seno), 3.01, 1e-2, "dB", **c)
    verificar("crest_factor_db_cuadrada", an.crest_factor_db(cuadrada), 0.0, 1e-2, "dB", **c)


def test_averaged_spectrum():
    fs, n_fft = 48000, 8192
    t = np.arange(int(fs*5.0)) / fs
    for A in (1.0, 0.3):
        k = 100
        f0 = k*fs/n_fft            # exact bin of an n_fft-point FFT
        x = A*np.sin(2*np.pi*f0*t)
        f, db = an.averaged_spectrum(x, fs, n_fft)
        i = int(np.argmin(np.abs(f - f0)))
        verificar("pico_averaged_spectrum_dbfs", db[i], 20*np.log10(A), 0.01, "dBFS",
                  fs_hz=fs, n_fft=n_fft, frecuencia_hz=f0, amplitud=A)

    # White noise: the expected power per bin follows from Welch's own normalization
    # (spectrum scaling, one-sided): 2*sigma^2*sum(w^2)/sum(w)^2, w the Hann window of
    # n_fft samples. The tolerance comes from the number of segments Welch averages
    # (50% overlap, so step = n_fft/2) times the bins compared, which sets how much the
    # averaged power estimate is expected to wander around that value.
    fs, n_fft, duracion, sigma, semilla = 48000, 8192, 5.0, 0.01, 999
    n = int(fs*duracion)
    x = np.random.default_rng(semilla).normal(0.0, sigma, n)
    f, db = an.averaged_spectrum(x, fs, n_fft)
    w = signal.get_window("hann", n_fft)
    ganancia = np.sum(w**2) / np.sum(w)**2
    esperado_db = 10*np.log10(4*sigma**2*ganancia)

    banda = (f > 100) & (f < 20000)
    potencia_media = np.mean(10**(db[banda]/10) / 2)
    obtenido_db = 10*np.log10(2*potencia_media)

    step = n_fft - n_fft//2
    segmentos = 1 + (n - n_fft)//step
    tol = 4*4.343/np.sqrt(segmentos*np.count_nonzero(banda)/1.5)   # /1.5: bins correlated by 50% Hann overlap
    verificar("ruido_promedio_por_bin_dbfs", obtenido_db, esperado_db, tol, "dBFS",
              fs_hz=fs, n_fft=n_fft, duracion_s=duracion, desviacion=sigma, semilla=semilla,
              segmentos=segmentos, ventana="hann")


def test_rolloff_points():
    # First-order lowpass, db = -10*log10(1+(f/fc)^2): the reference is at f=0 (0 dB),
    # so the point at drop N lands exactly at fc*sqrt(10**(N/10)-1).
    fc = 200.0
    f = np.arange(0.0, 20000.0 + 1.0, 1.0)
    db = -10*np.log10(1 + (f/fc)**2)
    r = an.rolloff_points(f, db, drops_db=(20, 40, 60), band=(0.0, 20000.0))
    c = dict(fc_hz=fc, banda_hz=[0.0, 20000.0])
    verificar("rolloff_referencia_hz", r["reference_hz"], 0.0, 1e-9, "Hz", **c)
    verificar("rolloff_referencia_db", r["reference_db"], 0.0, 1e-9, "dB", **c)
    for punto, N in zip(r["points"], (20, 40, 60)):
        esperado = fc*np.sqrt(10**(N/10) - 1)
        cc = dict(c, drop_db=N)
        if esperado <= 20000.0:
            verificar("rolloff_frecuencia_hz", punto["frequency_hz"], esperado, 1.0, "Hz", **cc)
            verificar("rolloff_no_limitado_por_piso", punto["limited_by_floor"], 0, 0, "", **cc)
        else:
            verificar("rolloff_fuera_de_banda_es_none", punto["frequency_hz"] is None, 1, 0, "", **cc)

    # A noise floor high enough to sit above the -60 dB point hides whether the signal
    # really dropped that far; a floor well below it does not.
    fc = 15.0
    db = -10*np.log10(1 + (f/fc)**2)
    esperado60 = fc*np.sqrt(10**(60/10) - 1)
    c = dict(fc_hz=fc, banda_hz=[0.0, 20000.0], drop_db=60, frecuencia_hz=esperado60)
    piso_bajo = an.rolloff_points(f, db, drops_db=(60,), band=(0.0, 20000.0),
                                   floor_db=np.full_like(f, -100.0))["points"][0]
    piso_alto = an.rolloff_points(f, db, drops_db=(60,), band=(0.0, 20000.0),
                                   floor_db=np.full_like(f, -30.0))["points"][0]
    verificar("rolloff_piso_bajo_no_limita", piso_bajo["limited_by_floor"], 0, 0, "", piso_dbfs=-100.0, **c)
    verificar("rolloff_piso_alto_limita", piso_alto["limited_by_floor"], 1, 0, "", piso_dbfs=-30.0, **c)


def test_remove_mains():
    fs, duracion, sigma, semilla = 48000, 4.0, 10**(-70/20), 20260913
    n = int(fs*duracion)
    t = np.arange(n) / fs
    rng = np.random.default_rng(semilla)
    ruido = rng.normal(0.0, sigma, n)

    f_red = 60.037
    amplitud_db = {1: -40.0, 2: -50.0, 4: -60.0}   # el 3 queda ausente a propósito
    fases = {k: rng.uniform(0, 2*np.pi) for k in amplitud_db}
    zumbido = sum(10**(amplitud_db[k]/20)*np.sin(2*np.pi*k*f_red*t + fases[k]) for k in amplitud_db)
    x = ruido + zumbido

    r = an.remove_mains(x, fs)
    c = dict(fs_hz=fs, duracion_s=duracion, frecuencia_red_hz=f_red, desviacion_ruido=sigma, semilla=semilla,
              armonicos_db=amplitud_db)
    verificar("remove_mains_frecuencia_hz", r["mains_hz"], f_red, 0.002, "Hz", **c)
    for k, adb in amplitud_db.items():
        verificar("remove_mains_armonico_dbfs", r["harmonic_dbfs"][k - 1], adb, 0.1, "dBFS", armonico=k, **c)
    verificar("remove_mains_armonico_ausente_bajo", r["harmonic_dbfs"][2] < -90.0, 1, 0, "", armonico=3, **c)

    ruido_rms_db = an.rms_dbfs(ruido)
    verificar("remove_mains_residual_rms_dbfs", r["residual_rms_dbfs"], ruido_rms_db, 0.1, "dBFS", **c)
    amplitudes = np.array([10**(adb/20) for adb in amplitud_db.values()])
    zumbido_rms_db = float(20*np.log10(np.sqrt(np.sum(amplitudes**2)/2)))
    verificar("remove_mains_hum_rms_dbfs", r["hum_rms_dbfs"], zumbido_rms_db, 0.1, "dBFS", **c)

    # Sin zumbido, el ajuste no tiene nada que quitar y el residuo queda igual al ruido.
    r2 = an.remove_mains(ruido, fs)
    verificar("remove_mains_sin_zumbido_residual_igual_al_ruido", r2["residual_rms_dbfs"], ruido_rms_db, 0.05, "dBFS", **c)


def test_fundamental():
    fs, duracion, B = 48000, 3.0, 1e-4
    n = int(fs*duracion)
    t = np.arange(n) / fs

    def cuerda(f0, amplitud_db_por_parcial, semilla):
        rng = np.random.default_rng(semilla)
        x = np.zeros(n)
        frecuencias = {}
        for k, adb in amplitud_db_por_parcial.items():
            fk = k*f0*np.sqrt(1 + B*k**2)
            frecuencias[k] = fk
            x += 10**(adb/20)*np.sin(2*np.pi*fk*t + rng.uniform(0, 2*np.pi))
        x *= np.exp(-t/1.0)
        x += rng.normal(0.0, 10**(-80/20), n)
        return x, frecuencias

    # Cuerda aguda: el 2do parcial es el más fuerte y la fundamental queda 12 dB abajo.
    amplitudes = {1: -32.0, 2: -20.0, 3: -26.0, 4: -32.0, 5: -38.0, 6: -44.0, 7: -50.0, 8: -56.0}
    x, frecuencias = cuerda(329.63, amplitudes, semilla=42)
    c = dict(fs_hz=fs, duracion_s=duracion, f0_hz=329.63, inarmonicidad_B=B, amplitudes_db=amplitudes)
    verificar("fundamental_cuerda_aguda_hz", an.fundamental(x, fs), frecuencias[1], 0.5, "Hz", **c)
    # frecuencia_dominante() se deja engañar por el 2do parcial, que es 12 dB más fuerte: por
    # eso hace falta fundamental().
    verificar("frecuencia_dominante_da_el_segundo_parcial", an.frecuencia_dominante(x, fs), frecuencias[2],
              0.5, "Hz", **c)

    # Cuerda grave: el 2do y el 3er parcial son más fuertes que la fundamental.
    amplitudes2 = {1: -40.0, 2: -20.0, 3: -20.0, 4: -30.0, 5: -36.0, 6: -42.0, 7: -48.0, 8: -54.0}
    x2, frecuencias2 = cuerda(82.41, amplitudes2, semilla=7)
    c2 = dict(c, f0_hz=82.41, amplitudes_db=amplitudes2)
    verificar("fundamental_cuerda_grave_hz", an.fundamental(x2, fs), frecuencias2[1], 0.5, "Hz", **c2)


def test_fundamental_correccion_octava():
    # Cuerda sintética como la toma real que motivó la corrección: parcial 2 de referencia, la
    # fundamental 16 dB abajo, los impares 3, 5 y 7 débiles y los pares bajando. Con la
    # inarmonicidad de una cuerda aguda (B = 1e-5) el HPS puro se engancha en la octava de
    # arriba; con B = 1e-4 los parciales altos se corren fuera de los bins que el HPS
    # multiplica y el error no aparece, así que la prueba no ejercitaría la corrección.
    fs, duracion, B = 48000, 2.0, 1e-5
    n = int(fs*duracion)
    t = np.arange(n) / fs
    f0 = 329.63
    amplitudes_db = {1: -16.0, 2: 0.0, 3: -35.0, 4: -10.0, 5: -35.0, 6: -20.0, 7: -35.0, 8: -30.0}
    frecuencias = {k: k*f0*np.sqrt(1 + B*k**2) for k in amplitudes_db}
    rng = np.random.default_rng(2026)
    x = np.zeros(n)
    for k, adb in amplitudes_db.items():
        x += 10**(adb/20)*np.sin(2*np.pi*frecuencias[k]*t + rng.uniform(0, 2*np.pi))
    x += rng.normal(0.0, 10**(-90/20), n)
    c = dict(fs_hz=fs, duracion_s=duracion, f0_hz=f0, inarmonicidad_B=B, amplitudes_db=amplitudes_db)
    verificar("fundamental_sin_correccion_da_la_octava_de_arriba",
              an.fundamental(x, fs, min_prominence_db=np.inf), frecuencias[2], 1.0, "Hz", **c)
    verificar("fundamental_con_correccion_da_la_fundamental",
              an.fundamental(x, fs), frecuencias[1], 0.5, "Hz", **c)

    # Un tono con armónicos propios (para que el HPS puro ya acierte) más ruido en f/2, sin
    # ninguna línea real ahí: la corrección no debe confundir el ruido con la fundamental.
    f0b = 800.0
    amplitudes_db_b = {1: 0.0, 2: -6.0, 3: -9.0, 4: -12.0}
    frecuencias_b = {k: k*f0b*np.sqrt(1 + B*k**2) for k in amplitudes_db_b}
    rng2 = np.random.default_rng(2027)
    x2 = np.zeros(n)
    for k, adb in amplitudes_db_b.items():
        x2 += 10**(adb/20)*np.sin(2*np.pi*frecuencias_b[k]*t + rng2.uniform(0, 2*np.pi))
    x2 += rng2.normal(0.0, 10**(-40/20), n)
    verificar("fundamental_ruido_en_f_medios_no_baja_de_octava", an.fundamental(x2, fs, fmin=60.0, fmax=1400.0),
              frecuencias_b[1], 1.0, "Hz", fs_hz=fs, duracion_s=duracion, f0_hz=f0b, ruido_dbfs=-40.0)


def test_note_name():
    for freq, esperado_midi, esperado_cents, nombre, nombre_en in (
        (440.0, 69, 0.0, "La4", "A4"),
        (329.63, 64, 0.0, "Mi4", "E4"),
        (82.41, 40, 0.0, "Mi2", "E2"),
        (333.0, 64, 17.6, "Mi4", "E4"),
        (261.63, 60, 0.0, "Do4", "C4"),
    ):
        r = an.note_name(freq)
        c = dict(frecuencia_hz=freq, a4_hz=440.0)
        verificar("note_name_midi", r["midi"], esperado_midi, 0, "", **c)
        verificar("note_name_cents", r["cents"], esperado_cents, 0.1, "cents", **c)
        verificar("note_name_nombre", r["name"] == nombre, 1, 0, "", nombre_obtenido=r["name"],
                  nombre_esperado=nombre, **c)
        verificar("note_name_nombre_en", r["name_en"] == nombre_en, 1, 0, "", nombre_obtenido=r["name_en"],
                  nombre_esperado=nombre_en, **c)


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


# Ruido cerca de un tono

def test_thd_n_banda_angosta():
    # Bandas laterales a 100 Hz del tono, como las que deja un jitter periódico, y dos componentes
    # fuera de la banda angosta, una por debajo y otra por encima. Con la banda de 800 a 1200 Hz el
    # THD+N tiene que ver solo las bandas laterales; con la banda por defecto, todo. Así se mide el
    # ruido cerca de un tono sin que entre lo que está lejos.
    fs = 48000
    t = np.arange(fs) / fs
    A, lateral, fuera = 0.5, 0.5e-3, 0.5e-2
    x = (A*np.sin(2*np.pi*1000*t) + lateral*np.sin(2*np.pi*900*t + 0.3) + lateral*np.sin(2*np.pi*1100*t + 1.2)
         + fuera*np.sin(2*np.pi*500*t + 0.7) + fuera*np.sin(2*np.pi*3000*t + 2.1))
    c = dict(fs_hz=fs, duracion_s=1.0, fundamental_hz=1000, amplitud_fundamental=A,
             bandas_laterales_hz=[900, 1100], amplitud_lateral=lateral,
             componentes_fuera_hz=[500, 3000], amplitud_fuera=fuera)
    verificar("thd_n_db_banda_angosta", an.thd_n(x, fs, banda=(800.0, 1200.0))["db"],
              20*np.log10(np.sqrt(2)*lateral/A), 1e-3, "dB", banda_hz=[800, 1200], **c)
    verificar("thd_n_db_banda_por_defecto", an.thd_n(x, fs)["db"],
              20*np.log10(np.sqrt(2*lateral**2 + 2*fuera**2)/A), 1e-3, "dB", banda_hz=[20, 20000], **c)


# Prueba de jitter

def tonos_con_jitter(fs, duracion_s, jitter_rms, ruido_rms, semilla):
    """Una captura por tono de FRECUENCIAS_PRUEBA_JITTER a -1 dBFS, con jitter blanco y ruido aditivo.

    ruido_rms puede ser un número o una función de la frecuencia del tono.
    """
    rng = np.random.default_rng(semilla)
    n = int(fs*duracion_s)
    t = np.arange(n) / fs
    tonos = []
    for f in an.FRECUENCIAS_PRUEBA_JITTER:
        tau = rng.normal(0.0, jitter_rms, n)
        ruido = ruido_rms(f) if callable(ruido_rms) else ruido_rms
        tonos.append((f, 10**(-1/20)*np.sin(2*np.pi*f*(t + tau)) + rng.normal(0.0, ruido, n)))
    return tonos


def test_prueba_jitter():
    fs, duracion = 48000, 2.0
    c0 = dict(fs_hz=fs, duracion_tono_s=duracion, amplitud_dbfs=-1.0, media_banda_hz=400,
              frecuencias_hz=list(an.FRECUENCIAS_PRUEBA_JITTER))

    # Solo jitter blanco de 1 ns: 20 dB por década y el jitter de vuelta.
    r = an.prueba_jitter(tonos_con_jitter(fs, duracion, 1e-9, 0.0, 101), fs)
    c = dict(c0, jitter_rms_s=1e-9, ruido_rms=0.0, semilla=101, veredicto=r["veredicto"])
    verificar("pendiente_solo_jitter", r["pendiente_db_por_decada"], 20.0, 0.3, "dB/década", **c)
    verificar("veredicto_solo_jitter_es_compatible", r["veredicto"] == "compatible_con_jitter", 1, 0, "", **c)
    verificar("jitter_equivalente_solo_jitter", r["jitter_rms_equivalente_s"]*1e9, 1.0, 0.05, "ns", **c)

    # Solo ruido blanco, sin jitter: la pendiente queda cerca de 0 y no hay efecto que atribuir.
    r = an.prueba_jitter(tonos_con_jitter(fs, duracion, 0.0, 1e-5, 102), fs)
    c = dict(c0, jitter_rms_s=0.0, ruido_rms=1e-5, semilla=102, veredicto=r["veredicto"])
    verificar("pendiente_solo_ruido", r["pendiente_db_por_decada"], 0.0, 1.0, "dB/década", **c)
    verificar("veredicto_solo_ruido_es_sin_efecto", r["veredicto"] == "sin_efecto_detectable", 1, 0, "", **c)

    # Ruido y 1 ns de jitter: el ruido domina en los tonos graves y el jitter en los agudos.
    r = an.prueba_jitter(tonos_con_jitter(fs, duracion, 1e-9, 1e-5, 103), fs)
    c = dict(c0, jitter_rms_s=1e-9, ruido_rms=1e-5, semilla=103, veredicto=r["veredicto"])
    verificar("veredicto_ruido_y_jitter_es_compatible", r["veredicto"] == "compatible_con_jitter", 1, 0, "", **c)
    verificar("jitter_equivalente_ruido_y_jitter", r["jitter_rms_equivalente_s"]*1e9, 1.0, 0.1, "ns", **c)

    # Ruido que crece 40 dB por década, sin jitter: crece con la frecuencia pero no como el jitter.
    r = an.prueba_jitter(tonos_con_jitter(fs, duracion, 0.0, lambda f: 2e-6*(f/1000)**2, 104), fs)
    c = dict(c0, jitter_rms_s=0.0, ruido_rms="2e-6*(f/1000)**2", semilla=104, veredicto=r["veredicto"])
    verificar("veredicto_ruido_40_db_por_decada_no_es_jitter", r["veredicto"] == "no_compatible", 1, 0, "", **c)


PRUEBAS = [
    test_seno_pico_rms,
    test_ruido_blanco_rms,
    test_espectro_amplitud,
    test_dos_tonos_resolucion,
    test_ajuste_seno,
    test_thd_n_armonico_1pc,
    test_thd_n_con_ruido,
    test_thd_n_banda_angosta,
    test_prueba_jitter,
    test_snr,
    test_generador_tono,
    test_generador_barrido_log,
    test_barrido_escalonado_y_respuesta,
    test_crest_factor_db,
    test_averaged_spectrum,
    test_rolloff_points,
    test_remove_mains,
    test_fundamental,
    test_fundamental_correccion_octava,
    test_note_name,
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
