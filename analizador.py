"""Análisis de capturas de audio y generación de señales de prueba.

Todos los niveles están en dBFS: 0 dBFS es una muestra de valor 1.0, así que una
senoidal a fondo de escala tiene pico 0 dBFS y RMS -3.01 dBFS.

Cada función está verificada contra señales sintéticas en calibrar.py.
"""
import numpy as np
from scipy import optimize, signal

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


# Prueba de jitter

FRECUENCIAS_PRUEBA_JITTER = (1000.0, 1468.0, 2154.0, 3162.0, 4642.0, 6813.0, 10000.0)   # 7 tonos de 1 a 10 kHz


def prueba_jitter(tonos, fs, media_banda_hz=400.0, umbral_db=1.0, tolerancia_db=1.0):
    """Prueba de pendiente: decide si el ruido cerca de un tono crece con su frecuencia como el del jitter.

    tonos es una lista de pares (frecuencia_hz, captura), una captura por tono y todos al mismo nivel;
    FRECUENCIAS_PRUEBA_JITTER son los tonos de 1 a 10 kHz. Para cada tono mide thd_n en una banda de
    ancho fijo centrada en él, de f - media_banda_hz a f + media_banda_hz, que deja afuera los
    armónicos y mantiene constante el ruido de fondo que entra. El jitter mete un ruido que crece con
    f² en potencia, 20 dB por década; el ruido propio del ADC no depende del tono. Por eso ajusta
    razón² = a*f² + b con a y b no negativos.

    veredicto:
      compatible_con_jitter   el ajuste queda dentro de tolerancia_db y a*f² suma al menos
                              umbral_db en el tono más agudo
      sin_efecto_detectable   el ajuste queda dentro de tolerancia_db y a*f² suma menos que eso
      no_compatible           los puntos no siguen a*f² + b

    Devuelve también la pendiente de la recta de thd_n en dB contra log10(f), en dB por década, y el
    jitter RMS equivalente suponiendo jitter blanco, repartido de 0 a fs/2.
    """
    f = np.array([float(fr) for fr, _ in tonos])
    thd_db = np.array([thd_n(x, fs, f0=fr, banda=(fr - media_banda_hz, fr + media_banda_hz))["db"]
                       for fr, x in tonos])
    pendiente = float(np.polyfit(np.log10(f), thd_db, 1)[0])

    r2 = 10**(thd_db/10)
    fe = f / np.max(f)                                   # escala para que el ajuste esté bien condicionado
    A = np.column_stack([fe**2, np.ones_like(fe)]) / r2[:, None]   # error relativo en cada punto
    (a_escalado, b), _ = optimize.nnls(A, np.ones_like(fe))
    a = a_escalado / np.max(f)**2
    residuo_max_db = float(np.max(np.abs(thd_db - 10*np.log10(a*f**2 + b + EPS**2))))
    aporte_db = float(10*np.log10((a*np.max(f)**2 + b + EPS**2) / (b + EPS**2)))
    fraccion = 2*media_banda_hz / (fs/2)

    if residuo_max_db > tolerancia_db:
        veredicto = "no_compatible"
    elif aporte_db >= umbral_db:
        veredicto = "compatible_con_jitter"
    else:
        veredicto = "sin_efecto_detectable"
    return {
        "frecuencias_hz": f.tolist(),
        "thd_n_db": thd_db.tolist(),
        "pendiente_db_por_decada": pendiente,
        "coeficiente_f2": float(a),
        "piso": float(b),
        "residuo_max_db": residuo_max_db,
        "aporte_jitter_db": aporte_db,
        "jitter_rms_equivalente_s": float(np.sqrt(a/fraccion) / (2*np.pi)),
        "veredicto": veredicto,
    }


# Guitar and mains

def crest_factor_db(x):
    """Peak minus RMS, in dB. A sine wave gives 3.01 dB, a square wave gives 0 dB."""
    return pico_dbfs(x) - rms_dbfs(x)


def averaged_spectrum(x, fs, n_fft=8192):
    """Welch-averaged amplitude spectrum in dBFS, on the same scale as espectro().

    Uses a Hann window with 50% overlap. A sine wave of amplitude A centered on a bin
    gives 20*log10(A), same as espectro() but with less variance on noisy captures
    because it averages several segments instead of a single FFT.
    """
    x = np.asarray(x, dtype=np.float64)
    nperseg = min(n_fft, len(x))
    noverlap = nperseg // 2
    f, power = signal.welch(x, fs, window="hann", nperseg=nperseg, noverlap=noverlap, scaling="spectrum")
    return f, 20*np.log10(np.sqrt(2*power) + EPS)


def rolloff_points(f, db, drops_db=(20, 40, 60), band=(20.0, 20000.0), floor_db=None, margin_db=6.0):
    """Where an averaged spectrum falls drops_db below its peak within band.

    reference_db is the maximum of db inside band. For each drop, frequency_hz is the
    highest frequency in band where db is still within reference_db - drop; if that
    frequency is the last bin of band, the drop was never reached and frequency_hz is
    None. With floor_db (an array the same length as f, e.g. the averaged spectrum of
    the card with nothing connected) limited_by_floor marks a point where
    reference_db - drop falls at or below the noise floor plus margin_db between the
    found frequency and the top of band: at that level the drop could be the signal
    rolling off or just the floor covering it, and there is no way to tell which.
    """
    f = np.asarray(f, dtype=np.float64)
    db = np.asarray(db, dtype=np.float64)
    mask = (f >= band[0]) & (f <= band[1])
    idx = np.nonzero(mask)[0]
    f_band, db_band = f[idx], db[idx]
    peak = int(np.argmax(db_band))
    reference_db = float(db_band[peak])
    reference_hz = float(f_band[peak])

    floor = np.asarray(floor_db, dtype=np.float64) if floor_db is not None else None
    points = []
    for drop in drops_db:
        threshold = reference_db - drop
        above = np.nonzero(db_band >= threshold)[0]
        last = int(above[-1])
        frequency_hz = None if last == len(f_band) - 1 else float(f_band[last])

        limited_by_floor = False
        if floor is not None and frequency_hz is not None:
            floor_mask = (f > frequency_hz) & (f <= band[1])
            if np.any(floor_mask):
                floor_median = float(np.median(floor[floor_mask]))
                limited_by_floor = bool(threshold <= floor_median + margin_db)

        points.append({"drop_db": float(drop), "frequency_hz": frequency_hz, "limited_by_floor": limited_by_floor})
    return {"reference_hz": reference_hz, "reference_db": reference_db, "points": points}


def remove_mains(x, fs, nominal_hz=60.0, harmonics=40, search_hz=0.3):
    """Removes mains hum by least squares in the time domain, so a picket-fence FFT leak never bleeds into it.

    Subtracts the mean first, then fits cos and sin of k*f for k = 1..harmonics (only
    the ones that land under fs/2) by least squares. f starts from a 13-point grid
    around nominal_hz +/- search_hz, scored with just the first 4 harmonics because
    that grid search is the slow part; the best grid point is then refined with
    scipy.optimize.minimize_scalar within +/-0.05 Hz. The final fit uses all the
    harmonics at that refined frequency.
    """
    x = np.asarray(x, dtype=np.float64)
    x = x - np.mean(x)
    t = np.arange(len(x)) / fs

    def harmonics_under_nyquist(f, n):
        return max(1, int(np.sum(np.arange(1, n + 1) * f < fs/2)))

    def fit(f, n):
        k = np.arange(1, n + 1)
        w = 2*np.pi*k[:, None]*f*t[None, :]
        basis = np.empty((len(t), 2*n))
        basis[:, 0::2] = np.cos(w).T
        basis[:, 1::2] = np.sin(w).T
        coeffs, *_ = np.linalg.lstsq(basis, x, rcond=None)
        return basis, coeffs

    def residual_power(f, n):
        basis, coeffs = fit(f, n)
        return float(np.mean((x - basis @ coeffs)**2))

    n_coarse = min(4, harmonics)
    grid = np.linspace(nominal_hz - search_hz, nominal_hz + search_hz, 13)
    powers = [residual_power(f, n_coarse) for f in grid]
    best = float(grid[int(np.argmin(powers))])

    result = optimize.minimize_scalar(lambda f: residual_power(f, n_coarse),
                                       bounds=(best - 0.05, best + 0.05), method="bounded",
                                       options={"xatol": 1e-4})
    mains_hz = float(result.x)

    n_final = harmonics_under_nyquist(mains_hz, harmonics)
    basis, coeffs = fit(mains_hz, n_final)
    hum = basis @ coeffs
    residual = x - hum

    harmonic_dbfs = [float(20*np.log10(np.hypot(coeffs[2*i], coeffs[2*i + 1]) + EPS)) for i in range(n_final)]

    return {
        "mains_hz": mains_hz,
        "harmonic_dbfs": harmonic_dbfs,
        "hum": hum,
        "residual": residual,
        "hum_rms_dbfs": rms_dbfs(hum),
        "residual_rms_dbfs": rms_dbfs(residual),
    }


def fundamental(x, fs, fmin=60.0, fmax=1400.0, factors=4, min_prominence_db=20.0, max_below_peak_db=30.0):
    """Fundamental frequency by the harmonic product spectrum (HPS), with an octave check.

    frecuencia_dominante() picks the tallest bin, which is wrong whenever a harmonic
    outweighs the fundamental: on a real high string the second harmonic came out 12 dB
    stronger than the fundamental, and frecuencia_dominante() locked onto the octave
    above. HPS instead multiplies the spectrum by itself decimated by 2, 3, ... factors,
    so only a peak with energy at f, 2f, 3f, ... lines up in every decimated copy; a lone
    strong harmonic without the fundamental underneath does not.

    HPS alone can still lock onto the wrong octave: on a real take of an open high E
    string, with the fundamental 16 dB under the second harmonic and weak odd harmonics,
    HPS gave 657.8 Hz, an octave above the 329.63 Hz fundamental. So after HPS, as long as
    half the current frequency is still above fmin, this looks for the tallest bin of the
    magnitude spectrum within +/-3% of half that frequency. It only drops the octave if
    that bin looks like an actual line, not the noise floor: min_prominence_db above the
    median of the spectrum within +/-20% of half the frequency, and no more than
    max_below_peak_db under the tallest bin between fmin and 5 kHz. On that real take the
    candidate at half the frequency stood 32.9 dB over its local median and 15.9 dB under
    the overall peak, comfortably past both defaults; on takes where half the frequency was
    not the fundamental, the same prominence only reached 8.9 to 11.4 dB, well short of
    min_prominence_db. Each accepted drop is refined with the same parabolic interpolation
    in log magnitude that frecuencia_dominante() uses, applied to the original spectrum, and
    the check repeats in case the true fundamental is another octave down.
    """
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    w = signal.get_window("hann", n)
    X = np.abs(np.fft.rfft((x - np.mean(x))*w))
    f = np.fft.rfftfreq(n, 1/fs)
    db = 20*np.log10(X + EPS)

    def refine(k):
        k = min(max(int(k), 1), len(X) - 2)   # keep room for the neighbours the parabola needs
        a, b, c = np.log(X[k-1:k+2] + EPS)
        return float((k + 0.5*(a - c)/(a - 2*b + c)) * fs / n)

    hps = X.copy()
    for factor in range(2, factors + 1):
        decimated = X[::factor]
        hps[:len(decimated)] *= decimated

    mask = (f >= fmin) & (f <= fmax)
    idx = np.nonzero(mask)[0]
    k = int(idx[np.argmax(hps[idx])])
    freq = refine(k)

    ceiling_mask = (f >= fmin) & (f <= 5000.0)
    ceiling_db = float(np.max(db[ceiling_mask])) if np.any(ceiling_mask) else -np.inf

    while freq/2 >= fmin:
        half = freq/2
        candidate_mask = (f >= half*0.97) & (f <= half*1.03)
        candidate_idx = np.nonzero(candidate_mask)[0]
        if len(candidate_idx) == 0:
            break
        peak_idx = candidate_idx[np.argmax(db[candidate_idx])]
        peak_db = float(db[peak_idx])

        median_mask = (f >= half*0.8) & (f <= half*1.2)
        median_db = float(np.median(db[median_mask])) if np.any(median_mask) else -np.inf

        if peak_db >= median_db + min_prominence_db and peak_db >= ceiling_db - max_below_peak_db:
            freq = refine(peak_idx)
        else:
            break

    return freq


NOTE_NAMES_ES = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]
NOTE_NAMES_EN = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_name(frequency_hz, a4_hz=440.0):
    """Nearest note to frequency_hz, with the deviation in cents.

    midi is the closest MIDI note number, 69 = A4 at a4_hz. cents is the signed offset
    from that note, between -50 and +50. name and name_en are that note with scientific
    pitch octave numbering, e.g. "Mi4" and "E4"; the octave rolls over at C, not at A.
    """
    midi_float = 69 + 12*np.log2(frequency_hz/a4_hz)
    midi = int(round(midi_float))
    cents = float(100*(midi_float - midi))
    pitch_class = midi % 12
    octave = midi//12 - 1
    return {
        "midi": midi,
        "cents": cents,
        "name": f"{NOTE_NAMES_ES[pitch_class]}{octave}",
        "name_en": f"{NOTE_NAMES_EN[pitch_class]}{octave}",
    }
