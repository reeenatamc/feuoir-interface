"""Simulación del efecto del jitter del reloj de muestreo, medido con analizador.py.

    .venv/bin/python jitter.py

No mide hardware. Arma capturas sintéticas de un tono muestreado en instantes corridos por un
jitter conocido y las pasa por las mismas funciones de analizador.py que se van a usar con el
circuito, para saber qué buscar cuando se compare GPOUT0 con el oscilador externo.

Modelo: cada muestra vale A*sin(2*pi*f*(n*T + tau_n)), donde tau_n es el error de tiempo del
reloj en esa muestra, más ruido blanco que representa el ruido propio del ADC. Cada jitter se
normaliza a su valor RMS exacto. El caso sobremuestreado muestrea a 64 fS con jitter y decima a
fS, como el modulador del PCM1808 (x64 según su hoja). Es un modelo idealizado del muestreo de la
entrada, no del circuito: vale para un modulador de tiempo discreto y no dice nada de uno de
tiempo continuo, que puede ser más sensible.

Guarda cada caso con sus condiciones, lo esperado según la teoría y lo medido en
simulaciones/<fecha>-jitter/resultados.json. Termina con código 1 si algún caso no coincide con lo
esperado dentro de su tolerancia.
"""
import hashlib, json, os, platform, sys
from datetime import datetime
from pathlib import Path

import numpy as np, scipy
from scipy import signal

import analizador as an

RAIZ = Path(__file__).resolve().parent
FS = 48000
DURACION_S = 5.0
AMPLITUD = 10**(-1/20)                      # tono de prueba a -1 dBFS
BANDA = (20.0, 20000.0)
FRACCION_BANDA = (BANDA[1] - BANDA[0]) / (FS/2)
SNR_PCM1808_DB = 99.0                       # S/N típico del PCM1808 a fS = 48 kHz, ponderado A (su hoja)
OSR = 64                                    # sobremuestreo del modulador del PCM1808 (su hoja)
SEMILLA = 20260913

# Ruido del ADC como ruido blanco que, en la banda de 20 Hz a 20 kHz, queda SNR_PCM1808_DB por debajo
# de una senoidal a fondo de escala. Es una aproximación: la hoja da el valor ponderado A.
RUIDO_BANDA_RMS = (1/np.sqrt(2)) * 10**(-SNR_PCM1808_DB/20)
RUIDO_SIGMA = RUIDO_BANDA_RMS / np.sqrt(FRACCION_BANDA)
PISO = RUIDO_BANDA_RMS / (AMPLITUD/np.sqrt(2))      # ruido del ADC en la banda, relativo al RMS del tono

CASOS = []
rng = np.random.default_rng(SEMILLA)


def db(razon):
    return float(20*np.log10(razon))


def normalizar(v, rms):
    v = v - np.mean(v)
    return v * (rms/np.sqrt(np.mean(v**2)))


def jitter_blanco(n, rms):
    return normalizar(rng.normal(size=n), rms) if rms else np.zeros(n)


def jitter_lento(n, rms, fs, corte_hz):
    """Jitter con su energía por debajo de corte_hz: ruido blanco por un Butterworth de orden 2."""
    if not rms:
        return np.zeros(n)
    sos = signal.butter(2, corte_hz, fs=fs, output="sos")
    extra = int(fs)                                  # un segundo para que se asiente el filtro
    return normalizar(signal.sosfilt(sos, rng.normal(size=n + extra))[extra:], rms)


def jitter_periodico(n, pico, fs, fm_hz):
    return pico*np.sin(2*np.pi*fm_hz*np.arange(n)/fs)


def tono(f, fs, tau):
    return AMPLITUD*np.sin(2*np.pi*f*(np.arange(len(tau))/fs + tau))


def ruido_adc(n):
    return rng.normal(0, RUIDO_SIGMA, n)


def razon_jitter_blanco(f, rms, osr=1):
    """Ruido de un jitter blanco dentro de la banda, relativo al RMS del tono."""
    return 2*np.pi*f*rms*np.sqrt(FRACCION_BANDA/osr)


def piso_en_banda(ancho_hz):
    """Ruido del ADC en una banda de ancho_hz, relativo al RMS del tono."""
    return RUIDO_SIGMA*np.sqrt(ancho_hz/(FS/2)) / (AMPLITUD/np.sqrt(2))


def nivel_relativo(f, espectro_db, centro, desde, hasta):
    """Potencia media del espectro entre desde y hasta Hz a cada lado del tono, en dB respecto del pico del tono."""
    pico = np.max(espectro_db[np.abs(f - centro) < 2])
    distancia = np.abs(f - centro)
    sel = (distancia >= desde) & (distancia < hasta)
    return float(10*np.log10(np.mean(10**(espectro_db[sel]/10))) - pico)


def registrar(caso, descripcion, condiciones, medido, esperado=None, tolerancia_db=None):
    medido = {k: float(v) for k, v in medido.items()}
    coincide = None
    if esperado is not None:
        esperado = {k: float(v) for k, v in esperado.items()}
        coincide = all(abs(medido[k] - v) <= tolerancia_db for k, v in esperado.items())
    CASOS.append({"caso": caso, "descripcion": descripcion, "condiciones": condiciones, "medido": medido,
                  "esperado": esperado, "tolerancia_db": tolerancia_db, "coincide": coincide})
    if coincide is False:
        print(f"NO COINCIDE  {caso}", file=sys.stderr)
    else:
        print(f"ok     {caso}")


def caso_blanco_sin_ruido():
    n = int(FS*DURACION_S)
    for f in (1000.0, 10000.0):
        for rms in (10e-12, 100e-12, 1e-9):
            x = tono(f, FS, jitter_blanco(n, rms))
            registrar(f"blanco_sin_ruido_{f:.0f}hz_{rms*1e12:.0f}ps",
                      "jitter blanco muestreado a fS, sin ruido del ADC: THD+N contra 2*pi*f*jitter",
                      dict(fs_hz=FS, duracion_s=DURACION_S, frecuencia_hz=f, amplitud_dbfs=-1.0,
                           jitter_rms_s=rms, banda_hz=list(BANDA)),
                      {"thd_n_db": an.thd_n(x, FS, f0=f)["db"]},
                      {"thd_n_db": db(razon_jitter_blanco(f, rms))}, 0.2)


def caso_blanco_con_ruido_adc():
    n = int(FS*DURACION_S)
    for f in (1000.0, 10000.0):
        for rms in (0.0, 100e-12, 1e-9):
            x = tono(f, FS, jitter_blanco(n, rms)) + ruido_adc(n)
            silencio = ruido_adc(n)                  # sin tono, el jitter no tiene nada que correr
            fr, e = an.espectro(x, FS)
            registrar(f"blanco_con_ruido_adc_{f:.0f}hz_{rms*1e12:.0f}ps",
                      "jitter blanco con el ruido del ADC: el THD+N lo ve, el SNR con captura sin señal no",
                      dict(fs_hz=FS, duracion_s=DURACION_S, frecuencia_hz=f, amplitud_dbfs=-1.0,
                           jitter_rms_s=rms, snr_adc_db=SNR_PCM1808_DB, banda_hz=list(BANDA),
                           ventana_espectro="hann"),
                      {"thd_n_db": an.thd_n(x, FS, f0=f)["db"], "snr_db": an.snr_db(x, silencio, FS, BANDA),
                       "espectro_2_a_20_hz_dbc": nivel_relativo(fr, e, f, 2, 20),
                       "espectro_20_a_200_hz_dbc": nivel_relativo(fr, e, f, 20, 200),
                       "espectro_200_a_2000_hz_dbc": nivel_relativo(fr, e, f, 200, 2000)},
                      {"thd_n_db": 10*np.log10(razon_jitter_blanco(f, rms)**2 + PISO**2), "snr_db": db(1/PISO)},
                      0.2)


def caso_blanco_sobremuestreado():
    fs_mod, duracion = OSR*FS, 1.0
    n = int(fs_mod*duracion)
    f = 10000.0
    for rms in (100e-12, 1e-9):
        y = tono(f, fs_mod, jitter_blanco(n, rms))
        x = signal.resample_poly(y, 1, OSR)[int(0.1*FS):int(0.9*FS)]    # sin los bordes del filtro
        registrar(f"blanco_sobremuestreado_{f:.0f}hz_{rms*1e12:.0f}ps",
                  "jitter blanco muestreado a 64 fS y decimado a fS: el ruido de jitter baja 10*log10(64)",
                  dict(fs_modulador_hz=fs_mod, osr=OSR, decimacion="scipy.signal.resample_poly",
                       duracion_analizada_s=0.8, frecuencia_hz=f, amplitud_dbfs=-1.0, jitter_rms_s=rms,
                       banda_hz=list(BANDA), thd_n_db_sin_sobremuestreo=db(razon_jitter_blanco(f, rms))),
                  {"thd_n_db": an.thd_n(x, FS, f0=f)["db"]},
                  {"thd_n_db": db(razon_jitter_blanco(f, rms, OSR))}, 0.5)


def caso_lento():
    n = int(FS*DURACION_S)
    for f in (10000.0, 10000.37):
        for rms in (0.0, 1e-9):
            x = tono(f, FS, jitter_lento(n, rms, FS, 20.0)) + ruido_adc(n)
            silencio = ruido_adc(n)
            fr, e = an.espectro(x, FS)
            jitter = 2*np.pi*f*rms
            registrar(f"lento_{f:.7g}hz_{rms*1e12:.0f}ps",
                      "jitter con la energía por debajo de 20 Hz: faldas alrededor del tono",
                      dict(fs_hz=FS, duracion_s=DURACION_S, frecuencia_hz=f, amplitud_dbfs=-1.0, jitter_rms_s=rms,
                           jitter_filtro="Butterworth pasabajos de orden 2 en 20 Hz", snr_adc_db=SNR_PCM1808_DB,
                           tono_en_un_bin=float(f*DURACION_S).is_integer(), ventana_espectro="hann",
                           banda_angosta_hz=[f - 200, f + 200]),
                      {"thd_n_db": an.thd_n(x, FS, f0=f)["db"],
                       "thd_n_db_banda_angosta": an.thd_n(x, FS, f0=f, banda=(f - 200, f + 200))["db"],
                       "snr_db": an.snr_db(x, silencio, FS, BANDA),
                       "espectro_2_a_20_hz_dbc": nivel_relativo(fr, e, f, 2, 20),
                       "espectro_20_a_200_hz_dbc": nivel_relativo(fr, e, f, 20, 200),
                       "espectro_200_a_2000_hz_dbc": nivel_relativo(fr, e, f, 200, 2000)},
                      {"thd_n_db": 10*np.log10(jitter**2 + PISO**2),
                       "thd_n_db_banda_angosta": 10*np.log10(jitter**2 + piso_en_banda(400)**2),
                       "snr_db": db(1/PISO)}, 0.6)


def caso_periodico():
    n = int(FS*DURACION_S)
    f, fm, pico = 10000.0, 1000.0, 1e-9
    x = tono(f, FS, jitter_periodico(n, pico, FS, fm))
    fr, e = an.espectro(x, FS)
    k = lambda hz: int(round(hz*DURACION_S))         # los tonos caen justo en un bin
    beta = 2*np.pi*f*pico                            # desviación de fase de pico
    registrar("periodico_10000hz_1000hz_1ns",
              "jitter senoidal de 1 kHz: bandas laterales a 1 kHz del tono",
              dict(fs_hz=FS, duracion_s=DURACION_S, frecuencia_hz=f, amplitud_dbfs=-1.0,
                   jitter_pico_s=pico, jitter_frecuencia_hz=fm, ventana_espectro="hann",
                   banda_angosta_hz=[f - 1500, f + 1500]),
              {"banda_lateral_inferior_dbc": e[k(f - fm)] - e[k(f)],
               "banda_lateral_superior_dbc": e[k(f + fm)] - e[k(f)],
               "thd_n_db_banda_angosta": an.thd_n(x, FS, f0=f, banda=(f - 1500, f + 1500))["db"]},
              {"banda_lateral_inferior_dbc": db(beta/2), "banda_lateral_superior_dbc": db(beta/2),
               "thd_n_db_banda_angosta": db(beta/np.sqrt(2))}, 0.05)


def umbrales():
    """Jitter blanco que haría subir el ruido del ADC, con un tono a -1 dBFS."""
    filas = []
    for f in (10000.0, 20000.0):
        for osr in (1, OSR):
            igual = PISO / (2*np.pi*f*np.sqrt(FRACCION_BANDA/osr))
            filas.append({"frecuencia_hz": f, "osr": osr,
                          "jitter_rms_para_igualar_el_ruido_del_adc_s": float(igual),
                          "jitter_rms_para_subir_el_ruido_0_5_db_s": float(igual*np.sqrt(10**(0.5/10) - 1))})
    return filas


def carpeta_nueva(ahora):
    base = RAIZ / "simulaciones" / f"{ahora:%Y-%m-%d}-jitter"
    carpeta, n = base, 2
    while carpeta.exists():
        carpeta, n = base.with_name(f"{base.name}-{n}"), n + 1
    carpeta.mkdir(parents=True)
    return carpeta


def main():
    ahora = datetime.now().astimezone()
    caso_blanco_sin_ruido()
    caso_blanco_con_ruido_adc()
    caso_blanco_sobremuestreado()
    caso_lento()
    caso_periodico()

    informe = {
        "fecha_hora": ahora.isoformat(timespec="seconds"),
        "jitter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "analizador_sha256": hashlib.sha256(Path(an.__file__).read_bytes()).hexdigest(),
        "versiones": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "plataforma": platform.platform(),
        "supuestos": {
            "fs_hz": FS, "duracion_s": DURACION_S, "amplitud_tono_dbfs": -1.0, "banda_hz": list(BANDA),
            "snr_adc_db": SNR_PCM1808_DB, "osr": OSR, "semilla": SEMILLA,
            "modelo": "muestra = A*sin(2*pi*f*(n*T + tau_n)) + ruido blanco del ADC; jitter normalizado a su RMS exacto",
            "nota": "el S/N del PCM1808 es ponderado A y aquí el ruido es blanco sin ponderar; el modelo "
                    "sobremuestreado idealiza un modulador de tiempo discreto",
        },
        "casos": CASOS,
        "umbrales": umbrales(),
    }
    carpeta = carpeta_nueva(ahora)
    ruta = carpeta / "resultados.json"
    ruta.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    no_coinciden = [c["caso"] for c in CASOS if c["coincide"] is False]
    if no_coinciden:
        print(f"\nSIMULACIÓN CON DIFERENCIAS: {len(no_coinciden)} casos no coinciden con la teoría. "
              f"Detalle en {os.path.relpath(ruta)}", file=sys.stderr)
        sys.exit(1)
    print(f"\nTodos los casos coinciden con lo esperado. Guardado en {os.path.relpath(ruta)}")


if __name__ == "__main__":
    main()
