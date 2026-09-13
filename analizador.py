"""Análisis de capturas de audio y generación de señales de prueba.

Todos los niveles están en dBFS: 0 dBFS es una muestra de valor 1.0, así que una
senoidal a fondo de escala tiene pico 0 dBFS y RMS -3.01 dBFS.

Cada función está verificada contra señales sintéticas en calibrar.py.
"""
import numpy as np
from scipy import signal

EPS = 1e-12   # evita log10(0) en capturas en silencio


# Niveles

def pico_dbfs(x):
    return float(20*np.log10(np.max(np.abs(x)) + EPS))


def rms(x):
    x = np.asarray(x, dtype=np.float64)
    return float(np.sqrt(np.mean(x**2)))


def rms_dbfs(x):
    return float(20*np.log10(rms(x) + EPS))


# Espectro

def resolucion_hz(fs, n):
    """Separación entre bins de una FFT de n muestras."""
    return fs / n


def espectro(x, fs, ventana="hann"):
    """Espectro de amplitud en dBFS.

    Una senoidal de amplitud A que cae justo en un bin da 20*log10(A). Fuera de un
    bin la ventana Hann baja el pico hasta 1.42 dB.
    """
    x = np.asarray(x, dtype=np.float64)
    w = signal.get_window(ventana, len(x))
    amplitud = 2*np.abs(np.fft.rfft(x*w)) / np.sum(w)
    amplitud[0] /= 2   # la continua no se reparte entre frecuencias positivas y negativas
    return np.fft.rfftfreq(len(x), 1/fs), 20*np.log10(amplitud + EPS)


def picos_espectrales(f, espectro_db, umbral_db):
    """Frecuencias de los máximos locales del espectro que superan umbral_db."""
    i, _ = signal.find_peaks(espectro_db, height=umbral_db)
    return f[i]


def frecuencia_dominante(x, fs):
    """Frecuencia del máximo del espectro, interpolada entre bins con una parábola."""
    x = np.asarray(x, dtype=np.float64)
    X = np.abs(np.fft.rfft((x - np.mean(x))*signal.get_window("hann", len(x))))
    k = int(np.argmax(X[1:-1])) + 1
    a, b, c = np.log(X[k-1:k+2] + EPS)
    return (k + 0.5*(a - c)/(a - 2*b + c)) * fs / len(x)


def filtrar_banda(x, fs, banda):
    """Deja solo lo que está entre banda[0] y banda[1] Hz. Con banda=None no filtra."""
    x = np.asarray(x, dtype=np.float64)
    if banda is None:
        return x
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1/fs)
    X[(f < banda[0]) | (f > banda[1])] = 0
    return np.fft.irfft(X, n=len(x))


# Ajuste de senoidal

def ajuste_seno(x, fs, f0=None, iteraciones=10):
    """Ajusta A*cos(2*pi*f*t + fase) + dc por mínimos cuadrados (IEEE 1057, 4 parámetros).

    La frecuencia se refina a partir de f0; si no se da, se parte del máximo del
    espectro. Devuelve amplitud, fase_rad, dc, frecuencia_hz y el modelo evaluado.
    """
    x = np.asarray(x, dtype=np.float64)
    t = np.arange(len(x)) / fs
    w = 2*np.pi*(frecuencia_dominante(x, fs) if f0 is None else f0)
    uno = np.ones_like(t)

    c, s = np.cos(w*t), np.sin(w*t)
    a, b, dc = np.linalg.lstsq(np.column_stack([c, s, uno]), x, rcond=None)[0]
    for _ in range(iteraciones):
        M = np.column_stack([c, s, uno, t*(b*c - a*s)])   # última columna: derivada respecto de w
        a, b, dc, dw = np.linalg.lstsq(M, x, rcond=None)[0]
        w += dw
        c, s = np.cos(w*t), np.sin(w*t)
        if abs(dw) < 1e-13*w:
            break
    a, b, dc = np.linalg.lstsq(np.column_stack([c, s, uno]), x, rcond=None)[0]

    return {
        "amplitud": float(np.hypot(a, b)),
        "fase_rad": float(np.arctan2(-b, a)),
        "dc": float(dc),
        "frecuencia_hz": float(w/(2*np.pi)),
        "modelo": a*c + b*s + dc,
    }


# Distorsión y ruido

def thd_n(x, fs, f0=None, banda=(20.0, 20000.0)):
    """THD+N relativo a la fundamental.

    Resta la fundamental ajustada y la continua, limita lo que queda a la banda y
    compara su RMS con el RMS de la fundamental. Un armónico con el 1 % de la
    amplitud de la fundamental da 1.000 %.
    """
    aj = ajuste_seno(x, fs, f0)
    residuo = filtrar_banda(np.asarray(x, dtype=np.float64) - aj["modelo"], fs, banda)
    razon = rms(residuo) / (aj["amplitud"]/np.sqrt(2))
    return {
        "porcentaje": float(100*razon),
        "db": float(20*np.log10(razon + EPS)),
        "frecuencia_hz": aj["frecuencia_hz"],
        "amplitud": aj["amplitud"],
    }


def snr_db(captura_senal, captura_ruido, fs=None, banda=None):
    """Relación señal a ruido a partir de dos capturas.

    captura_senal se toma con el tono de prueba en la entrada y captura_ruido con la
    entrada sin señal. SNR = 20*log10(RMS con tono / RMS sin señal). Con banda, las
    dos capturas se limitan a esa banda antes de medir y hace falta fs.
    """
    if banda is not None and fs is None:
        raise ValueError("para limitar la banda hace falta fs")
    senal = filtrar_banda(captura_senal, fs, banda)
    ruido = filtrar_banda(captura_ruido, fs, banda)
    return float(20*np.log10(rms(senal) / (rms(ruido) + EPS)))


# Señales de prueba

def _rampa(n, m):
    """Envolvente con subida y bajada de medio coseno de m muestras."""
    env = np.ones(n)
    if m > 0:
        sube = 0.5 - 0.5*np.cos(np.pi*np.arange(m)/m)
        env[:m] = sube
        env[n-m:] = sube[::-1]
    return env


def tono(frecuencia_hz, fs, duracion_s, amplitud_dbfs=-6.0, fase_rad=0.0, rampa_s=0.0):
    """Senoidal de pico amplitud_dbfs. rampa_s suaviza los bordes para no meter clics al circuito."""
    n = int(round(duracion_s*fs))
    t = np.arange(n) / fs
    x = 10**(amplitud_dbfs/20) * np.sin(2*np.pi*frecuencia_hz*t + fase_rad)
    return x * _rampa(n, int(round(rampa_s*fs)))


def barrido_log(f_inicio, f_fin, fs, duracion_s, amplitud_dbfs=-6.0, rampa_s=0.0):
    """Barrido senoidal exponencial: la frecuencia en el instante t es f_inicio*(f_fin/f_inicio)**(t/duracion_s)."""
    n = int(round(duracion_s*fs))
    t = np.arange(n) / fs
    L = duracion_s / np.log(f_fin/f_inicio)
    fase = 2*np.pi*f_inicio*L*(np.exp(t/L) - 1)
    return 10**(amplitud_dbfs/20) * np.sin(fase) * _rampa(n, int(round(rampa_s*fs)))


def frecuencias_log(f_inicio, f_fin, por_octava):
    """Frecuencias espaciadas por_octava veces por octava, desde f_inicio sin pasar de f_fin."""
    n = int(np.floor(np.log2(f_fin/f_inicio)*por_octava + 1e-9)) + 1
    return f_inicio * 2**(np.arange(n)/por_octava)


def barrido_escalonado(frecuencias_hz, fs, duracion_tono_s=0.5, amplitud_dbfs=-6.0, rampa_s=0.005):
    """Tonos seguidos, uno por frecuencia.

    Devuelve la señal y los segmentos: una lista de dicts con inicio y fin en muestras
    y la frecuencia de cada tono, que es lo que necesita respuesta_en_frecuencia.
    """
    partes, segmentos, inicio = [], [], 0
    for f in frecuencias_hz:
        x = tono(f, fs, duracion_tono_s, amplitud_dbfs, rampa_s=rampa_s)
        partes.append(x)
        segmentos.append({"inicio": inicio, "fin": inicio + len(x), "frecuencia_hz": float(f)})
        inicio += len(x)
    return np.concatenate(partes), segmentos


# Respuesta en frecuencia

def respuesta_en_frecuencia(salida, fs, segmentos, entrada=None, descarte=0.2):
    """Nivel, ganancia y fase de cada tono de un barrido escalonado.

    salida es la captura a la salida del circuito. Sin entrada, cada fila trae el nivel
    de pico del tono en dBFS. Con entrada (la captura antes del circuito, alineada
    muestra a muestra con salida), trae también ganancia en dB y fase en grados
    relativas a ella. descarte es la fracción de cada segmento que se ignora al
    principio y al final, para saltar la rampa y el transitorio del circuito.
    """
    filas = []
    for seg in segmentos:
        m = int(descarte*(seg["fin"] - seg["inicio"]))
        tramo = slice(seg["inicio"] + m, seg["fin"] - m)
        sal = ajuste_seno(salida[tramo], fs, seg["frecuencia_hz"])
        fila = {
            "frecuencia_hz": seg["frecuencia_hz"],
            "frecuencia_medida_hz": sal["frecuencia_hz"],
            "nivel_dbfs": float(20*np.log10(sal["amplitud"] + EPS)),
        }
        if entrada is not None:
            ent = ajuste_seno(entrada[tramo], fs, seg["frecuencia_hz"])
            fila["ganancia_db"] = float(20*np.log10(sal["amplitud"] / ent["amplitud"]))
            fase = np.degrees(sal["fase_rad"] - ent["fase_rad"])
            fila["fase_grados"] = float((fase + 180) % 360 - 180)
        filas.append(fila)
    return filas
