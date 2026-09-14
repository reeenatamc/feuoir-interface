"""From audio blocks to frames ready to draw.

Everything the interface shows is computed here, with analizador.py; the interface only draws.
Processing is driven by samples, not by a clock: every block that arrives is examined in full, and
a frame is built on request from what accumulated since the previous frame. That keeps the audio
rate (about 47 blocks per second) independent from the screen rate.
"""
import threading
from collections import deque

import numpy as np

import analizador as an

SPECTRUM_POINTS = 512
F_MIN_HZ, F_MAX_HZ = 20.0, 20000.0
SPECTRUM_SECONDS = 0.2        # 200 ms: 5 Hz bins at any sample rate
SPECTRUM_WINDOW = "flattop"   # with Hann, a tone that falls between two bins reads up to 1.42 dB low
WAVEFORM_MS = 10
READOUT_SECONDS = 0.5         # peak readouts show the maximum over this span, so they can be read
FULL_SCALE = 1 - 2**-15       # within one 16-bit code of the top: works for 16-bit and 24-bit converters
PEAK_THRESHOLD_DBFS = -90.0   # below this the spectrum peak is not marked: it would be a noise peak


def spectrum_points():
    """Edges and centers of the logarithmic spans between F_MIN_HZ and F_MAX_HZ."""
    edges = F_MIN_HZ * (F_MAX_HZ/F_MIN_HZ) ** (np.arange(SPECTRUM_POINTS + 1) / SPECTRUM_POINTS)
    return edges, np.sqrt(edges[:-1] * edges[1:])


def reduce_spectrum(f, db, edges):
    """One value per span: the maximum of the bins inside it, so no tone gets lost.

    Spans narrower than a bin, in the low end, take the value interpolated at their center.
    """
    out = np.interp(np.sqrt(edges[:-1] * edges[1:]), f, db)
    k = np.searchsorted(f, edges)
    filled = np.flatnonzero(k[1:] > k[:-1])
    if len(filled):
        out[filled] = np.maximum.reduceat(db[:k[-1]], k[filled])
    return out


class Recording:
    """Collects the next n samples that go through the processor."""

    def __init__(self, n):
        self._parts, self._missing = [], n
        self._done = threading.Event()

    def add(self, x):
        part = x[:self._missing]
        self._parts.append(part.copy())
        self._missing -= len(part)
        if self._missing == 0:
            self._done.set()
        return self._missing == 0

    def wait(self, timeout_s):
        if not self._done.wait(timeout_s):
            raise TimeoutError("La entrada dejó de mandar audio antes de completar la grabación")
        return np.concatenate(self._parts)


class Processor:
    def __init__(self, fs):
        self.fs = fs
        self.n_spectrum = int(round(SPECTRUM_SECONDS*fs))
        self.n_waveform = int(round(WAVEFORM_MS*fs/1000))
        self.edges, self.frequencies = spectrum_points()
        self._lock = threading.Lock()
        self._memory = np.zeros(self.n_spectrum)   # the latest samples, newest last
        self._samples = 0
        self._frame_peak = 0.0
        self._frame_clipped = False
        self._peaks = deque()                       # (samples up to the end of the block, block peak)
        self._last_clip = None
        self._clipped_blocks = 0
        self._recordings = []

    def block(self, x):
        x = np.asarray(x, dtype=np.float64)
        peak = float(np.max(np.abs(x)))   # every sample: a single clipped sample counts too
        n = len(x)
        with self._lock:
            if n >= self.n_spectrum:
                self._memory[:] = x[-self.n_spectrum:]
            else:
                self._memory[:-n] = self._memory[n:]
                self._memory[-n:] = x
            self._samples += n
            # The peak is held until the next frame, so a block that clips between two frames is not lost.
            self._frame_peak = max(self._frame_peak, peak)
            self._peaks.append((self._samples, peak))
            while self._peaks[0][0] <= self._samples - READOUT_SECONDS*self.fs:
                self._peaks.popleft()
            if peak >= FULL_SCALE:
                self._frame_clipped = True
                self._last_clip = self._samples
                self._clipped_blocks += 1
            self._recordings = [r for r in self._recordings if not r.add(x)]

    def record(self, n):
        recording = Recording(n)
        with self._lock:
            self._recordings.append(recording)
        return recording

    def clear_clipping(self):
        with self._lock:
            self._last_clip, self._clipped_blocks = None, 0

    def frame(self):
        with self._lock:
            x = self._memory.copy()
            frame_peak, clipped = self._frame_peak, self._frame_clipped
            self._frame_peak, self._frame_clipped = 0.0, False
            readout_peak = max(p for _, p in self._peaks) if self._peaks else 0.0
            last_clip, blocks, samples = self._last_clip, self._clipped_blocks, self._samples

        f, db = an.espectro(x, self.fs, ventana=SPECTRUM_WINDOW)
        in_band = np.flatnonzero((f >= F_MIN_HZ) & (f <= F_MAX_HZ))
        k = in_band[np.argmax(db[in_band])]
        spectrum_peak = None
        if db[k] >= PEAK_THRESHOLD_DBFS:
            frequency = an.frecuencia_dominante(x, self.fs)
            if abs(frequency - f[k]) > 2*self.fs/len(x):   # the dominant tone is outside the drawn band
                frequency = f[k]
            spectrum_peak = {"frequency_hz": round(float(frequency), 2), "level_dbfs": round(float(db[k]), 2)}

        # The waveform starts at a rising zero crossing, so it does not jump around from frame to frame.
        n = self.n_waveform
        tail = x[len(x) - 2*n:]
        crossings = np.flatnonzero((tail[:-1] < 0) & (tail[1:] >= 0)) + 1
        crossings = crossings[crossings <= n]
        start = len(x) - 2*n + (int(crossings[-1]) if len(crossings) else n)

        return {
            "type": "frame",
            "samples": samples,
            "waveform": np.round(x[start:start + n], 5).tolist(),
            "spectrum_dbfs": np.round(reduce_spectrum(f, db, self.edges), 1).tolist(),
            "spectrum_peak": spectrum_peak,
            "level": {
                "peak_dbfs": round(float(20*np.log10(frame_peak + an.EPS)), 2),
                "readout_peak_dbfs": round(float(20*np.log10(readout_peak + an.EPS)), 2),
                "rms_dbfs": round(an.rms_dbfs(x), 2),
            },
            "clipping": {
                "now": clipped,
                "seconds_ago": None if last_clip is None else round((samples - last_clip)/self.fs, 2),
                "blocks": blocks,
            },
        }
