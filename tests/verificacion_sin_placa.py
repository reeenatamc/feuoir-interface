#!/usr/bin/env python3
"""Prueba en la Mac la parte del firmware de verificación que no toca hardware.

    .venv/bin/python tests/verificacion_sin_placa.py

Compila firmware/informe.c con tests/informe_prueba.c usando el compilador de C de la Mac y corre
los casos: todo en orden, DC50 sin activar, PLL sin configurar, divisor con fracción, sin puente,
frecuencias en el borde de la tolerancia, contador que no termina y oscilador externo.

No prueba la lectura de los registros ni el contador de frecuencia del RP2040: eso solo se puede
probar en la placa.
"""
import shutil, subprocess, sys, tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def compilar_informe(carpeta):
    """Compila informe.c con los casos de prueba en carpeta y devuelve la ruta del ejecutable."""
    cc = shutil.which("cc")
    if not cc:
        sys.exit("FALLA  no hay compilador de C (cc) en el PATH")
    ejecutable = Path(carpeta) / "informe_prueba"
    r = subprocess.run([cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(RAIZ / "firmware"),
                        str(RAIZ / "tests" / "informe_prueba.c"), str(RAIZ / "firmware" / "informe.c"),
                        "-o", str(ejecutable)], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"FALLA  informe.c no compila en la Mac:\n{r.stderr}")
    return ejecutable


def main():
    with tempfile.TemporaryDirectory(prefix="informe-") as tmp:
        r = subprocess.run([str(compilar_informe(tmp))], capture_output=True, text=True)
        print(r.stdout, end="")
        if r.returncode:
            print("\nFALLA  la parte del firmware que no toca hardware no pasa sus casos", file=sys.stderr)
            sys.exit(1)
    print("\nPasan todos los casos del informe. La lectura de registros y el contador solo se prueban en la placa.")


if __name__ == "__main__":
    main()
