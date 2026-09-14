"""Audio sources: a real input through sounddevice, or a synthetic source that acts as a converter.

Both put float32 blocks into the same queue, and the rest of the app does not know which one is running.
"""
import queue
import threading
import time

import numpy as np
import sounddevice as sd

import analizador as an

BLOCK_SIZE = 1024                # at 48 kHz, about 47 blocks per second
PREFERRED_FS = 48000
SYNTHETIC_NOISE_DBFS = -100.0    # RMS of the noise the synthetic source adds, on the order of the PCM1808 floor
SYNTHETIC_BITS = 24
SWEEP_SECONDS = 5.0
SHAPES = ("sine", "sweep", "noise", "silence")
SHAPE_LABELS = {"sine": "seno", "sweep": "barrido", "noise": "ruido", "silence": "silencio"}
DEFAULT_SIGNAL = {"shape": "sine", "frequency_hz": 1000.0, "level_dbfs": -6.0}


def validate_signal(signal):
    """Returns the signal with its three fields, or raises ValueError saying what is wrong."""
    shape = signal.get("shape")
    if shape not in SHAPES:
        raise ValueError(f"Forma desconocida: {shape!r}")
    frequency = float(signal.get("frequency_hz", DEFAULT_SIGNAL["frequency_hz"]))
    level = float(signal.get("level_dbfs", DEFAULT_SIGNAL["level_dbfs"]))
    if not 20.0 <= frequency <= 20000.0:
        raise ValueError(f"Frecuencia fuera de 20 Hz a 20 kHz: {frequency}")
    if not -120.0 <= level <= 6.0:
        raise ValueError(f"Nivel fuera de -120 a +6 dBFS: {level}")
    return {"shape": shape, "frequency_hz": frequency, "level_dbfs": level}


def list_inputs(restart=False):
    """The Mac's audio inputs.

    PortAudio builds its device list when it starts: an interface plugged in afterwards only shows up after a
    restart, and a restart stops any open stream. That is why restarting is optional.
    """
    if restart:
        sd._terminate()
        sd._initialize()
    inputs = [{"id": "synthetic", "name": SyntheticSource.name}]
    for d in sd.query_devices():
        if d["max_input_channels"] > 0:
            inputs.append({"id": str(d["index"]), "name": d["name"]})
    return inputs


class SyntheticSource:
    """Acts as a converter without hardware.

    Generates the chosen signal, adds background noise, quantizes it to 24 bits and clips it at full scale,
    like the ADC. Delivers blocks in real time. For the sine and the sweep the level is peak; for noise, RMS.
    """
    name = "Fuente sintética"

    def __init__(self, blocks, fs=PREFERRED_FS, signal=DEFAULT_SIGNAL):
        self.blocks, self.fs = blocks, fs
        self._lock = threading.Lock()
        self._rng = np.random.default_rng()
        self._phase = 0.0
        self._stimulus = np.zeros(0)
        self.configure(signal)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="synthetic-source", daemon=True)
        self._thread.start()

    def describe(self):
        # Spanish keys: this goes into condiciones.json, whose format is shared with medir.py.
        return {"tipo": "sintetica", "nombre": self.name,
                "senal": {"forma": SHAPE_LABELS[self.signal["shape"]], "frecuencia_hz": self.signal["frequency_hz"],
                          "nivel_dbfs": self.signal["level_dbfs"]},
                "ruido_dbfs_rms": SYNTHETIC_NOISE_DBFS, "bits": SYNTHETIC_BITS}

    def configure(self, signal):
        signal = validate_signal(signal)
        sweep = None
        if signal["shape"] == "sweep":
            sweep = an.barrido_log(20.0, 20000.0, self.fs, SWEEP_SECONDS, signal["level_dbfs"])
        with self._lock:
            self.signal, self._sweep, self._position = signal, sweep, 0

    def play(self, x):
        """What plays through the output comes back through the input, as with a loopback cable."""
        with self._lock:
            self._stimulus = np.concatenate([self._stimulus, np.asarray(x, dtype=np.float64)])

    def _generate(self, n):
        s = self.signal
        amplitude = 10**(s["level_dbfs"]/20)
        if len(self._stimulus):
            x = np.zeros(n)
            m = min(n, len(self._stimulus))
            x[:m], self._stimulus = self._stimulus[:m], self._stimulus[m:]
        elif s["shape"] == "sine":
            w = 2*np.pi*s["frequency_hz"]/self.fs
            x = amplitude*np.sin(self._phase + w*np.arange(n))
            self._phase = (self._phase + w*n) % (2*np.pi)
        elif s["shape"] == "sweep":
            x = self._sweep[(self._position + np.arange(n)) % len(self._sweep)]
            self._position = (self._position + n) % len(self._sweep)
        elif s["shape"] == "noise":
            x = self._rng.normal(0.0, amplitude, n)
        else:
            x = np.zeros(n)
        x = x + self._rng.normal(0.0, 10**(SYNTHETIC_NOISE_DBFS/20), n)
        step = 2.0**-(SYNTHETIC_BITS - 1)
        return np.clip(np.round(x/step)*step, -1.0, 1.0 - step)

    def _run(self):
        deadline = time.perf_counter()
        while not self._stop.is_set():
            with self._lock:
                x = self._generate(BLOCK_SIZE).astype(np.float32)
            try:
                self.blocks.put_nowait(x)
            except queue.Full:
                pass                              # nobody is reading: the block is lost, as with a real converter
            deadline += BLOCK_SIZE/self.fs
            wait = deadline - time.perf_counter()
            if wait > 0:
                time.sleep(wait)
            else:
                deadline = time.perf_counter()    # running late: continue from now instead of sending a burst

    def close(self):
        self._stop.set()
        self._thread.join()


class DeviceSource:
    """One of the Mac's audio inputs: the feuoir interface, a USB sound card or the microphone."""

    def __init__(self, blocks, index):
        info = sd.query_devices(int(index), "input")
        self.blocks, self.index, self.name = blocks, info["index"], info["name"]
        self.fs = PREFERRED_FS
        try:
            sd.check_input_settings(device=self.index, channels=1, samplerate=self.fs, dtype="float32")
        except sd.PortAudioError:
            self.fs = int(info["default_samplerate"])
        self.lost_blocks = 0
        self._stream = sd.InputStream(device=self.index, channels=1, samplerate=self.fs, blocksize=BLOCK_SIZE,
                                      dtype="float32", callback=self._callback)
        self._stream.start()

    def _callback(self, indata, frames, time_info, status):
        # Runs on CoreAudio's real-time thread: if it takes too long, the audio drops out. So it only copies
        # the block into the queue and returns. Measuring, reducing and sending to the interface happen on
        # another thread.
        try:
            self.blocks.put_nowait(indata[:, 0].copy())
        except queue.Full:
            self.lost_blocks += 1

    def describe(self):
        # Spanish keys: this goes into condiciones.json, whose format is shared with medir.py.
        return {"tipo": "dispositivo", "nombre": self.name, "indice": self.index,
                "bloques_perdidos": self.lost_blocks}

    def play(self, x):
        """The stimulus goes out through the Mac's default output, without touching its settings."""
        sd.play(np.asarray(x, dtype=np.float32), self.fs)

    def close(self):
        self._stream.stop()
        self._stream.close()
