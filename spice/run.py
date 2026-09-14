"""Runs ngspice in batch mode and reads the ASCII raw files that the netlists' control blocks write.

Every netlist carries its own .control block: it runs the analyses, sets filetype=ascii and writes one .raw file
per analysis with write. simulate() runs the netlist in an empty folder and returns every .raw found there.
"""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

DEFAULT_NGSPICE = Path.home() / "spice" / "ngspice-47" / "bin" / "ngspice"


def ngspice_path():
    """The NGSPICE environment variable, then ~/spice/ngspice-47, then whatever is on the PATH."""
    path = os.environ.get("NGSPICE")
    if not path and DEFAULT_NGSPICE.exists():
        path = str(DEFAULT_NGSPICE)
    path = path or shutil.which("ngspice")
    if not path:
        raise FileNotFoundError("No se encontró ngspice. docs/simulador-spice.md explica cómo instalarlo.")
    return path


def version():
    r = subprocess.run([ngspice_path(), "--version"], capture_output=True, text=True, timeout=30)
    match = re.search(r"ngspice-\S+", r.stdout)
    return match.group(0) if match else r.stdout.strip()


def read_ascii_raw(path):
    """Reads a raw file written with filetype=ascii into {variable name: array}.

    Names are lower case. Complex analyses (AC, noise spectra in some versions) come back as complex arrays.
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    # Split at whole lines: "Variables:" also appears inside "No. Variables:".
    header, _, values = text.partition("\nValues:")
    fields = dict(re.findall(r"^([A-Za-z. ]+):[ \t]*(.*)$", header, flags=re.MULTILINE))
    n_vars, n_points = int(fields["No. Variables"]), int(fields["No. Points"])
    complex_data = "complex" in fields.get("Flags", "")
    variables = header.partition("\nVariables:")[2]
    names = re.findall(r"^[ \t]*\d+[ \t]+(\S+)[ \t]+\S+", variables, flags=re.MULTILINE)[:n_vars]
    tokens = values.split()
    data = np.zeros((n_points, n_vars), dtype=complex if complex_data else float)
    step = n_vars + 1                                  # each point: its index, then one value per variable
    for point in range(n_points):
        row = tokens[point*step + 1:(point + 1)*step]
        for var, token in enumerate(row):
            if complex_data:
                re_part, _, im_part = token.partition(",")
                data[point, var] = complex(float(re_part), float(im_part or 0.0))
            else:
                data[point, var] = float(token)
    return {name.lower(): data[:, i] for i, name in enumerate(names)}


def vector(raw, name):
    """A variable by name, accepting both "out" and "v(out)"."""
    name = name.lower()
    for candidate in (name, f"v({name})", name.removeprefix("v(").removesuffix(")")):
        if candidate in raw:
            return raw[candidate]
    raise KeyError(f"{name} no está entre {sorted(raw)}")


def with_params(netlist, **values):
    """The netlist with the given .param values replaced. Each name has to be on exactly one .param line."""
    for name, value in values.items():
        pattern = re.compile(rf"(^\.param\b[^\n]*?\b{re.escape(name)}\s*=\s*)(\S+)", flags=re.IGNORECASE | re.MULTILINE)
        netlist, count = pattern.subn(lambda m: m.group(1) + str(value), netlist)
        if count != 1:
            raise ValueError(f"El parámetro {name} tiene que estar en una sola línea .param y está en {count}")
    return netlist


def simulate(netlist, files=(), behavior=None, timeout_s=300):
    """Runs a netlist with ngspice -b and returns {raw file name: {variable: array}}, plus the log text.

    files are copied next to the netlist, so it can .include them by name. behavior sets ngbehavior in a
    .spiceinit before the netlist is read, for example "ps" to read PSpice model libraries.
    """
    with tempfile.TemporaryDirectory(prefix="spice-") as folder:
        folder = Path(folder)
        for file in files:
            shutil.copy(file, folder / Path(file).name)
        if behavior:
            (folder / ".spiceinit").write_text(f"set ngbehavior={behavior}\n", encoding="utf-8")
        (folder / "circuit.cir").write_text(netlist, encoding="utf-8")
        r = subprocess.run([ngspice_path(), "-b", "-o", "ngspice.log", "circuit.cir"], cwd=folder,
                           capture_output=True, text=True, timeout=timeout_s)
        log = (folder / "ngspice.log").read_text(encoding="utf-8", errors="replace") if (folder / "ngspice.log").exists() else ""
        raws = {p.name: read_ascii_raw(p) for p in sorted(folder.glob("*.raw"))}
        if r.returncode != 0 or not raws or re.search(r"^\s*error", log, flags=re.MULTILINE | re.IGNORECASE):
            tail = "\n".join((log or r.stdout + r.stderr).splitlines()[-25:])
            raise RuntimeError(f"ngspice no terminó bien (código {r.returncode}):\n{tail}")
        return raws, log
