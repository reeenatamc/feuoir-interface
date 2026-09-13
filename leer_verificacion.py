"""Lee por USB el informe del firmware de verificación del reloj y lo guarda con sus condiciones.

    .venv/bin/python leer_verificacion.py gpout0-puente --puentes "GPIO21 puenteado a GPIO20"

Espera un informe completo de firmware/verificar_reloj.c, de inicio_informe a fin_informe, y lo
guarda en mediciones/<fecha>-<etiqueta>/, igual que medir.py:

    informe.txt        las líneas tal como llegaron
    condiciones.json   fecha y hora, puerto, puentes, notas, modo del firmware y cada chequeo

Termina con código 1 si el informe trae fallas, si no es coherente o si no llega completo a tiempo.
Solo usa la biblioteca estándar: el USB del Pico es un puerto serie que macOS muestra como
/dev/cu.usbmodem*.
"""
import argparse, glob, json, os, re, select, sys, termios, time, tty
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent


def elegir_puerto(puerto):
    if puerto:
        return puerto
    candidatos = sorted(glob.glob("/dev/cu.usbmodem*"))
    if len(candidatos) != 1:
        sys.exit(f"No se puede elegir el puerto: hay {len(candidatos)} /dev/cu.usbmodem*. Indícalo con --puerto.")
    return candidatos[0]


def leer_informe(puerto, espera_s):
    """Líneas de un informe completo, desde inicio_informe hasta fin_informe, o None si no llega a tiempo."""
    fd = os.open(puerto, os.O_RDONLY | os.O_NOCTTY)
    try:
        tty.setraw(fd, termios.TCSANOW)            # sin eco ni procesamiento de líneas
        limite = time.monotonic() + espera_s
        pendiente, lineas = b"", None
        while (resto := limite - time.monotonic()) > 0:
            listos, _, _ = select.select([fd], [], [], resto)
            if not listos:
                break
            try:
                datos = os.read(fd, 4096)
            except OSError:                          # el otro extremo se cerró
                break
            if not datos:
                break
            pendiente += datos
            while b"\n" in pendiente:
                cruda, pendiente = pendiente.split(b"\n", 1)
                linea = cruda.decode("utf-8", errors="replace").rstrip("\r")
                if linea.startswith("inicio_informe="):   # si se abrió a mitad de un informe, se descarta
                    lineas = [linea]
                elif lineas is not None:
                    lineas.append(linea)
                    if linea.startswith("fin_informe="):
                        return lineas
        return None
    finally:
        os.close(fd)


def numero(texto):
    for tipo in (int, float):
        try:
            return tipo(texto)
        except ValueError:
            pass
    return texto


def campos(linea):
    """clave=valor separados por espacios; nota= se lleva el resto de la línea."""
    nota = None
    if " nota=" in linea:
        linea, nota = linea.split(" nota=", 1)
    pares = {}
    for token in linea.split():
        clave, _, valor = token.partition("=")
        pares[clave] = numero(valor)
    if nota is not None:
        pares["nota"] = nota
    return pares


def interpretar(lineas):
    inicio, fin = campos(lineas[0]), campos(lineas[-1])
    chequeos = []
    for linea in lineas[1:-1]:
        c = campos(linea)
        nombre = next(iter(c))
        chequeos.append({"chequeo": nombre, "valor": c.pop(nombre), **c})
    fallidos = [c["chequeo"] for c in chequeos if c.get("resultado") != "ok"]
    coherente = (inicio.get("inicio_informe") == fin.get("fin_informe") and fin.get("fallas") == len(fallidos)
                 and all("resultado" in c for c in chequeos))
    return {"informe_numero": inicio.get("inicio_informe"), "modo": inicio.get("modo"),
            "fallas": fin.get("fallas"), "resultado": fin.get("resultado"), "coherente": coherente,
            "chequeos_fallidos": fallidos, "chequeos": chequeos}


def carpeta_nueva(destino, ahora, etiqueta):
    base = destino / f"{ahora:%Y-%m-%d}-{etiqueta}"
    carpeta, n = base, 2
    while carpeta.exists():                          # misma etiqueta el mismo día: -2, -3...
        carpeta, n = base.with_name(f"{base.name}-{n}"), n + 1
    carpeta.mkdir(parents=True)
    return carpeta


def main():
    p = argparse.ArgumentParser(description="Guarda en mediciones/<fecha>-<etiqueta>/ un informe del firmware de verificación del reloj")
    p.add_argument("etiqueta", help="nombre de la medición, por ejemplo gpout0-puente")
    p.add_argument("--puentes", required=True,
                   help="cómo están los puentes y el jumper de SCKI, por ejemplo 'GPIO21 puenteado a GPIO20'")
    p.add_argument("--notas", default="", help="texto libre que se guarda en condiciones.json")
    p.add_argument("--puerto", help="puerto serie; si no se da, el único /dev/cu.usbmodem*")
    p.add_argument("--espera-s", type=float, default=10.0, help="tiempo máximo para recibir un informe completo")
    p.add_argument("--destino", type=Path, default=RAIZ / "mediciones", help=argparse.SUPPRESS)
    args = p.parse_args()
    if not re.fullmatch(r"[\w.-]+", args.etiqueta):
        p.error("la etiqueta solo puede tener letras, números, puntos, guiones y guiones bajos")

    puerto = elegir_puerto(args.puerto)
    ahora = datetime.now().astimezone()
    lineas = leer_informe(puerto, args.espera_s)
    if lineas is None:
        sys.exit(f"SIN INFORME: no llegó un informe completo por {puerto} en {args.espera_s:g} s. No se guardó nada.")

    informe = interpretar(lineas)
    carpeta = carpeta_nueva(args.destino, ahora, args.etiqueta)
    (carpeta / "informe.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    condiciones = {
        "fecha_hora": ahora.isoformat(timespec="seconds"),
        "etiqueta": args.etiqueta,
        "puerto": puerto,
        "puentes": args.puentes,
        "notas": args.notas,
        **informe,
    }
    (carpeta / "condiciones.json").write_text(json.dumps(condiciones, ensure_ascii=False, indent=2) + "\n",
                                              encoding="utf-8")

    ruta = os.path.relpath(carpeta)
    if not informe["coherente"]:
        sys.exit(f"INFORME INCOHERENTE: el total de fallas no coincide con los chequeos. Guardado en {ruta}")
    if informe["chequeos_fallidos"]:
        sys.exit(f"FALLA en {', '.join(informe['chequeos_fallidos'])}. Guardado en {ruta}")
    print(f"Informe sin fallas, modo {informe['modo']}. Guardado en {ruta}")


if __name__ == "__main__":
    main()
