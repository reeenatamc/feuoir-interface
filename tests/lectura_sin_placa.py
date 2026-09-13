#!/usr/bin/env python3
"""Prueba leer_verificacion.py sin placa: un pseudo terminal hace de puerto USB.

    .venv/bin/python tests/lectura_sin_placa.py

Compila firmware/informe.c para obtener informes con el formato real del firmware, los escribe en
un pseudo terminal empezando a mitad de un informe, como pasa al abrir el puerto con la placa ya
andando, y corre leer_verificacion.py sobre ese puerto. Comprueba que guarde un informe completo
con sus condiciones y que el código de salida refleje las fallas y la falta de informe.
"""
import json, os, subprocess, sys, tempfile, threading, time, tty
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verificacion_sin_placa import RAIZ, compilar_informe  # noqa: E402

CASOS_FALLIDOS = []


def comprobar(nombre, condicion):
    print(f"{'ok    ' if condicion else 'FALLA '} {nombre}")
    if not condicion:
        CASOS_FALLIDOS.append(nombre)


def correr_lector(texto, destino, espera_s=5.0):
    """Escribe texto en un pseudo terminal y corre leer_verificacion.py leyendo de él."""
    maestro, esclavo = os.openpty()
    tty.setraw(esclavo)
    lector = subprocess.Popen([sys.executable, str(RAIZ / "leer_verificacion.py"), "prueba",
                               "--puentes", "GPIO21 puenteado a GPIO20", "--notas", "sin placa",
                               "--puerto", os.ttyname(esclavo), "--espera-s", str(espera_s),
                               "--destino", str(destino)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def escribir():
        time.sleep(0.3)                              # que el lector alcance a abrir el puerto
        for linea in texto.splitlines(keepends=True):
            os.write(maestro, linea.encode("utf-8"))
            time.sleep(0.005)

    hilo = threading.Thread(target=escribir)
    hilo.start()
    salida, error = lector.communicate(timeout=espera_s + 10)
    hilo.join()
    os.close(maestro)
    os.close(esclavo)
    guardadas = sorted(Path(destino).glob("*-prueba*"))
    return lector.returncode, salida + error, guardadas


def main():
    with tempfile.TemporaryDirectory(prefix="lectura-") as tmp:
        tmp = Path(tmp)
        informe_prueba = compilar_informe(tmp)
        bueno = subprocess.run([str(informe_prueba), "--imprimir"], capture_output=True, text=True, check=True).stdout
        sin_dc50 = subprocess.run([str(informe_prueba), "--imprimir-sin-dc50"], capture_output=True, text=True,
                                  check=True).stdout
        lineas = bueno.splitlines()
        cola = "\n".join(lineas[6:]) + "\n"          # el final de un informe anterior, sin su inicio

        codigo, texto, guardadas = correr_lector(cola + bueno, tmp / "bueno")
        comprobar("informe sin fallas: código 0", codigo == 0)
        comprobar("informe sin fallas: una carpeta guardada", len(guardadas) == 1)
        if len(guardadas) == 1:
            c = json.loads((guardadas[0] / "condiciones.json").read_text(encoding="utf-8"))
            guardado = (guardadas[0] / "informe.txt").read_text(encoding="utf-8")
            comprobar("guarda el informe completo, no la cola del anterior", guardado == bueno)
            comprobar("condiciones: puentes y notas", c["puentes"] == "GPIO21 puenteado a GPIO20" and c["notas"] == "sin placa")
            comprobar("condiciones: modo, número de informe y resultado",
                      c["modo"] == "gpout0" and c["informe_numero"] == 7 and c["resultado"] == "ok" and c["fallas"] == 0)
            comprobar("condiciones: un chequeo por línea", len(c["chequeos"]) == len(lineas) - 2)
            dc50 = next(x for x in c["chequeos"] if x["chequeo"] == "gpout0_dc50")
            comprobar("condiciones: valor y esperado de un chequeo", dc50["valor"] == 1 and dc50["esperado"] == 1)
            gpio20 = next(x for x in c["chequeos"] if x["chequeo"] == "gpio20_hz")
            comprobar("condiciones: frecuencia y ppm como números",
                      gpio20["valor"] == 12288000.0 and gpio20["diferencia_ppm"] == 0.0)

        codigo, texto, guardadas = correr_lector(sin_dc50, tmp / "sin_dc50")
        comprobar("informe con DC50 sin activar: código 1", codigo == 1)
        comprobar("informe con DC50 sin activar: igual se guarda", len(guardadas) == 1)
        comprobar("informe con DC50 sin activar: nombra el chequeo", "gpout0_dc50" in texto)

        codigo, texto, guardadas = correr_lector(cola, tmp / "incompleto", espera_s=1.0)
        comprobar("sin informe completo: código distinto de 0", codigo != 0)
        comprobar("sin informe completo: no guarda nada", len(guardadas) == 0)

    if CASOS_FALLIDOS:
        print(f"\nFALLA  {len(CASOS_FALLIDOS)} casos de la lectura sin placa", file=sys.stderr)
        sys.exit(1)
    print("\nPasan todos los casos de la lectura. El puerto USB real solo se prueba con la placa.")


if __name__ == "__main__":
    main()
