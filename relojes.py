"""Búsqueda exhaustiva de configuraciones del RP2040 para el reloj maestro del PCM1808.

    .venv/bin/python relojes.py

El PCM1808 a fS = 48 kHz necesita en SCKI 256 fS = 12.288 MHz y el Pico tiene un cristal de
12 MHz. El script prueba todas las combinaciones del PLL del sistema y, para cada una, el
divisor que haría falta en tres caminos: la salida de reloj GPOUT0 por GPIO21, y una máquina de
estados del PIO a 24.576 MHz o a 12.288 MHz. Todo en aritmética entera, sin coma flotante, y se
queda con las combinaciones que dan la frecuencia exacta.

Escribe docs/reloj-soluciones.csv con todas las soluciones exactas y cada restricción marcada, y
en docs/reloj.md reescribe solo el bloque entre las marcas de inicio y fin. El resto de reloj.md
(la solución elegida, el respaldo y cómo verificar) se escribe a mano.
"""
import csv, hashlib, platform
from collections import defaultdict
from datetime import datetime
from functools import lru_cache
from itertools import accumulate
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DOC = RAIZ / "docs" / "reloj.md"
CSV = RAIZ / "docs" / "reloj-soluciones.csv"
MARCA_INICIO = "<!-- inicio del bloque generado por relojes.py -->"
MARCA_FIN = "<!-- fin del bloque generado por relojes.py -->"

# PLL del sistema. Restricciones del enunciado, que coinciden con la sección 2.18 de la hoja del RP2040.
FREF_HZ = 12_000_000
REFDIV = range(1, 64)
FBDIV = range(16, 321)
VCO_MIN_HZ, VCO_MAX_HZ = 750_000_000, 1_600_000_000
POSTDIV = range(1, 8)

# Restricciones que agrega la hoja del RP2040 (secciones 2.15 y 2.18).
REF_MIN_HZ = 5_000_000                          # FREF/REFDIV mínima
SYSCLK_MAX_HZ = 133_000_000                     # máximo de clk_sys
GPOUT_MAX_HZ = 50_000_000                       # salidas de reloj por GPIO (2.15.1)

# PCM1808, tabla System clock timing.
DUTY_MIN, DUTY_MAX = 0.40, 0.60
PULSO_MIN_NS = 8.0

MCLK_HZ = 12_288_000
FILAS_POR_TABLA = 12


def divisor_pio_valido(div256):
    return 256 <= div256 <= 65536*256            # entero de 16 bits + fracción/256, de 1 a 65536 (3.5.5)


def divisor_gpout_valido(div256):
    return div256 == 256 or 512 <= div256 <= 2**32 - 1   # entero de 24 bits + fracción/256: 1, o desde 2.0 (2.15.3.3)


CASOS = [
    {"clave": "gpout0", "titulo": "GPOUT0 por GPIO21",
     "objetivo_hz": MCLK_HZ, "valido": divisor_gpout_valido},
    {"clave": "pio-24.576", "titulo": "PIO con la máquina a 24.576 MHz, dos instrucciones por periodo",
     "objetivo_hz": 24_576_000, "valido": divisor_pio_valido},
    {"clave": "pio-12.288", "titulo": "PIO con la máquina a 12.288 MHz, una instrucción por periodo",
     "objetivo_hz": MCLK_HZ, "valido": divisor_pio_valido},
]
assert MCLK_HZ <= GPOUT_MAX_HZ


def buscar(caso):
    objetivo_hz, valido = caso["objetivo_hz"], caso["valido"]
    soluciones = []
    for refdiv in REFDIV:
        for fbdiv in FBDIV:
            if not VCO_MIN_HZ*refdiv <= FREF_HZ*fbdiv <= VCO_MAX_HZ*refdiv:
                continue
            for pd1 in POSTDIV:
                for pd2 in POSTDIV:
                    # divisor = sysclk/objetivo; en 1/256 tiene que ser entero para que exista
                    num, den = 256*FREF_HZ*fbdiv, refdiv*pd1*pd2*objetivo_hz
                    if num % den:
                        continue
                    div256 = num // den
                    if not valido(div256):
                        continue
                    vco, r1 = divmod(FREF_HZ*fbdiv, refdiv)
                    sysclk, r2 = divmod(FREF_HZ*fbdiv, refdiv*pd1*pd2)
                    assert r1 == r2 == 0    # sysclk = objetivo*div256/256 siempre es un entero de Hz
                    soluciones.append({
                        "refdiv": refdiv, "fbdiv": fbdiv, "vco_hz": vco,
                        "postdiv1": pd1, "postdiv2": pd2, "sysclk_hz": sysclk,
                        "div256": div256, "div_int": div256 // 256, "div_frac": div256 % 256,
                        "cumple_ref_min_5mhz": FREF_HZ >= REF_MIN_HZ*refdiv,
                        "cumple_sysclk_max_133mhz": sysclk <= SYSCLK_MAX_HZ,
                        "postdiv1_mayor_o_igual": pd1 >= pd2,
                    })
    return soluciones


def ciclos_por_tick(div256, ticks):
    """Ciclos de sysclk entre habilitaciones sucesivas de la máquina de estados del PIO.

    Modelo de la hoja del RP2040 (3.5.5): el divisor lleva la suma de la parte fraccionaria
    y cada vez que pasa de 1 alarga el siguiente periodo de n a n+1 ciclos. Empieza en fase
    0, como después de CLKDIV_RESTART.
    """
    n, f = divmod(div256, 256)
    acumulado, alargar, d = 0, False, []
    for _ in range(ticks):
        d.append(n + alargar)
        acumulado += f
        alargar = acumulado >= 256
        acumulado %= 256
    return d


@lru_cache(maxsize=None)
def metricas(clave, sysclk_hz, div256):
    """Irregularidad determinista que mete el divisor en régimen estable; no incluye el jitter del PLL."""
    ts_ns = 1e9 / sysclk_hz
    n, f = divmod(div256, 256)
    if clave == "gpout0":
        # 2.15.3.3: con fracción, cada periodo de la salida dura n o n+1 ciclos de la fuente.
        # 2.15.3.4: con divisor impar el ciclo de trabajo es floor(n/2)/n, y 50 % con DC50.
        if f:
            return {"mclk_periodo_pp_ns": ts_ns}
        return {"mclk_periodo_pp_ns": 0.0, "mclk_tie_pp_ns": 0.0, "duty_min": 0.5, "duty_max": 0.5,
                "pulso_min_ns": n*ts_ns/2, "requiere_dc50": n % 2 == 1,
                "cumple_pcm1808": n*ts_ns/2 >= PULSO_MIN_NS}

    # El primer periodo después de arrancar no sigue el patrón estable, así que se descartan
    # los primeros 256 ticks. El patrón se repite cada 256 ticks o menos.
    d = ciclos_por_tick(div256, 256 + 1024)[256:]
    m = {"periodo_sm_pp_ns": (max(d) - min(d))*ts_ns}
    if clave != "pio-24.576":
        return m
    # Dos instrucciones por periodo: la primera pone el pin en alto y la segunda en bajo.
    # Se evalúan las dos alineaciones posibles del programa con el patrón y se toma la peor.
    ideal = 2*div256/256
    peor = {"mclk_periodo_pp_ns": 0.0, "mclk_tie_pp_ns": 0.0, "duty_min": 1.0, "duty_max": 0.0,
            "pulso_min_ns": float("inf")}
    for inicio in (0, 1):
        pares = list(zip(d[inicio::2], d[inicio+1::2]))
        periodos = [a + b for a, b in pares]
        tie = [t - (j + 1)*ideal for j, t in enumerate(accumulate(periodos))]
        peor["mclk_periodo_pp_ns"] = max(peor["mclk_periodo_pp_ns"], (max(periodos) - min(periodos))*ts_ns)
        peor["mclk_tie_pp_ns"] = max(peor["mclk_tie_pp_ns"], (max(tie) - min(tie))*ts_ns)
        peor["duty_min"] = min(peor["duty_min"], min(a/(a + b) for a, b in pares))
        peor["duty_max"] = max(peor["duty_max"], max(a/(a + b) for a, b in pares))
        peor["pulso_min_ns"] = min(peor["pulso_min_ns"], min(min(a, b) for a, b in pares)*ts_ns)
    m.update(peor)
    m["cumple_pcm1808"] = (peor["duty_min"] >= DUTY_MIN - 1e-9 and peor["duty_max"] <= DUTY_MAX + 1e-9
                           and peor["pulso_min_ns"] >= PULSO_MIN_NS)
    return m


def valida_hoja(s):
    return s["cumple_ref_min_5mhz"] and s["cumple_sysclk_max_133mhz"]


def filas_unicas(soluciones, clave):
    """Una fila por par (sysclk, divisor) que cumple la hoja, con una configuración de PLL representativa."""
    grupos = defaultdict(list)
    for s in soluciones:
        if valida_hoja(s):
            grupos[(s["sysclk_hz"], s["div256"])].append(s)
    filas = []
    for (sysclk, div256), configs in grupos.items():
        # REFDIV 1 como recomienda la hoja, VCO lo más alto posible (menos jitter) y POSTDIV1 >= POSTDIV2
        rep = min(configs, key=lambda s: (s["refdiv"] != 1, -s["vco_hz"], not s["postdiv1_mayor_o_igual"], s["postdiv1"]))
        filas.append({**rep, **metricas(clave, sysclk, div256), "configs_pll": len(configs)})
    filas.sort(key=lambda r: (r["div_frac"] != 0, r.get("mclk_periodo_pp_ns", r.get("periodo_sm_pp_ns", 0.0)),
                              r.get("mclk_tie_pp_ns", 0.0), -r["sysclk_hz"]))
    return filas


def mhz(hz):
    return f"{hz/1e6:.6f}".rstrip("0").rstrip(".")


def lista_mhz(valores):
    textos = [mhz(v) for v in valores]
    return textos[0] if len(textos) == 1 else ", ".join(textos[:-1]) + " y " + textos[-1]


def divisor(div256):
    return f"{div256/256:.8f}".rstrip("0").rstrip(".")


def pll(s):
    return f"{s['refdiv']}, {s['fbdiv']}, {mhz(s['vco_hz'])}, {s['postdiv1']}, {s['postdiv2']}"


def pll_texto(s):
    return (f"REFDIV {s['refdiv']}, FBDIV {s['fbdiv']}, VCO {mhz(s['vco_hz'])} MHz, "
            f"POSTDIV1 {s['postdiv1']}, POSTDIV2 {s['postdiv2']}")


def si_no(v):
    return "sí" if v else "no"


def tipo(s):
    return "entero" if s["div_frac"] == 0 else "fraccionario"


def duty_gpout(f):
    if f["div_frac"]:
        return "no se calcula"
    n = f["div_int"]
    return f"50 % con DC50 ({100*(n//2)/n:.1f} % sin DC50)" if n % 2 else "50 %"


def escribir_csv(resultados, ahora, sha):
    columnas = ["camino", "refdiv", "fbdiv", "vco_hz", "postdiv1", "postdiv2", "sysclk_hz", "divisor",
                "div_int", "div_frac", "divisor_entero", "cumple_ref_min_5mhz", "cumple_sysclk_max_133mhz",
                "postdiv1_mayor_o_igual", "periodo_sm_pp_ns", "mclk_periodo_pp_ns", "mclk_tie_pp_ns",
                "duty_min", "duty_max", "pulso_min_ns", "requiere_dc50", "cumple_pcm1808"]
    with CSV.open("w", newline="", encoding="utf-8") as fh:
        fh.write(f"# relojes.py {ahora.isoformat(timespec='seconds')} sha256 {sha}\n")
        fh.write("# FREF 12 MHz; REFDIV 1-63; FBDIV 16-320; VCO 750-1600 MHz; POSTDIV1 y POSTDIV2 1-7. "
                 "Divisor PIO entero 16 bits + fraccion/256; divisor GPOUT0 entero 24 bits + fraccion/256. "
                 "Tiempos en ns en regimen estable, sin el jitter del PLL.\n")
        w = csv.DictWriter(fh, fieldnames=columnas, extrasaction="ignore")
        w.writeheader()
        for clave, r in resultados.items():
            for s in r["soluciones"]:
                w.writerow({**s, **metricas(clave, s["sysclk_hz"], s["div256"]), "camino": clave,
                            "divisor": divisor(s["div256"]), "divisor_entero": s["div_frac"] == 0})


def bloque(resultados, ahora, sha):
    combinaciones = len(REFDIV)*len(FBDIV)*len(POSTDIV)**2
    g, p2, p1 = resultados["gpout0"], resultados["pio-24.576"], resultados["pio-12.288"]
    L = [f"Bloque generado por relojes.py el {ahora:%Y-%m-%d %H:%M %z} (sha256 del script {sha[:12]}, Python "
         f"{platform.python_version()}). Se reescribe en cada corrida; lo que está fuera de las marcas no lo toca. "
         "Todas las soluciones exactas, con cada restricción marcada, están en reloj-soluciones.csv.", ""]

    L += ["### Condiciones", "",
          f"Se probaron las {combinaciones:,} combinaciones de REFDIV, FBDIV, POSTDIV1 y POSTDIV2".replace(",", ".", 1)
          + " y, para cada una, el divisor que haría falta en cada camino. Una combinación es solución si ese "
          "divisor se puede escribir exacto en el registro del camino. Todo el cálculo es en enteros, sin redondeo.", "",
          "PLL del sistema, restricciones del enunciado:", "",
          "- FREF = 12 MHz, REFDIV de 1 a 63, FBDIV de 16 a 320",
          "- VCO = FREF/REFDIV x FBDIV entre 750 y 1600 MHz",
          "- POSTDIV1 y POSTDIV2 de 1 a 7, sysclk = VCO/(POSTDIV1 x POSTDIV2)", "",
          "Divisores:", "",
          "- PIO: entero de 16 bits más fracción/256, de 1 a 65536 (sección 3.5.5).",
          "- GPOUT0: entero de 24 bits más fracción/256, que divide por 1 o por 2.0 en adelante (sección 2.15.3.3). "
          "Salida de hasta 50 MHz (sección 2.15.1).", "",
          "Restricciones que agrega la hoja del RP2040 y que se marcan aparte:", "",
          "- FREF/REFDIV de al menos 5 MHz (sección 2.18). Con el cristal de 12 MHz deja REFDIV en 1 o 2.",
          "- FREF/REFDIV no mayor que VCO/16 (sección 2.18). Equivale a FBDIV >= 16, así que se cumple siempre.",
          "- clk_sys de 133 MHz como máximo (secciones 2.15 y 2.18).", "",
          "Irregularidad del divisor, sin el jitter propio del PLL:", "",
          "- PIO: delta-sigma de primer orden que alarga algunos periodos de n a n+1 ciclos de sysclk (sección 3.5.5), "
          "en régimen estable, sin los primeros 256 periodos después de arrancar.",
          "- GPOUT0: con fracción, cada periodo dura n o n+1 ciclos de la fuente (sección 2.15.3.3); con divisor entero "
          "no alterna. Con divisor impar el ciclo de trabajo es floor(n/2)/n, y 50 % con DC50 (sección 2.15.3.4).", ""]

    L += ["### Resultado", "",
          "| Camino | Soluciones exactas | Con divisor entero | Cumplen la hoja del RP2040 | "
          "Cumplen la hoja y tienen divisor entero |", "|---|---|---|---|---|"]
    for r in resultados.values():
        hoja = [s for s in r["soluciones"] if valida_hoja(s)]
        L.append(f"| {r['caso']['titulo']} | {len(r['soluciones'])} | {len(r['enteras'])} | {len(hoja)} | "
                 f"{len(r['enteras_hoja'])} |")
    L.append("")
    for r in resultados.values():
        if not r["enteras"]:
            L += [f"{r['caso']['titulo']}: ninguna combinación da divisor entero, ni con las restricciones del "
                  "enunciado ni con las de la hoja.", ""]
    if not p2["enteras"]:
        L += ["No es un límite de la búsqueda. Para que sysclk/24.576 MHz sea entero, FBDIV tendría que ser "
              "múltiplo de 256, o sea 256, y entonces REFDIV x POSTDIV1 x POSTDIV2 tendría que dividir a 125 con "
              "REFDIV entre 2 y 4 para que el VCO quede en rango, lo que no pasa.", ""]

    enteros = sorted({s["sysclk_hz"] for r in resultados.values() for s in r["enteras"]})
    enteros_hoja = sorted({s["sysclk_hz"] for r in resultados.values() for s in r["enteras_hoja"]})
    if enteros:
        L += [f"Con divisor entero, en cualquier camino, los únicos sysclk posibles son {lista_mhz(enteros)} MHz. "
              f"Cumple la hoja del RP2040: {lista_mhz(enteros_hoja) + ' MHz' if enteros_hoja else 'ninguno'}.", ""]

    L += ["Soluciones con divisor entero, sin filtrar:", "",
          "| Camino | sysclk (MHz) | Divisor | REFDIV, FBDIV, VCO (MHz), POSTDIV1, POSTDIV2 | REF >= 5 MHz | "
          "sysclk <= 133 MHz |", "|---|---|---|---|---|---|"]
    for r in resultados.values():
        for s in sorted(r["enteras"], key=lambda s: (s["sysclk_hz"], s["refdiv"], -s["postdiv1"])):
            L.append(f"| {r['caso']['titulo']} | {mhz(s['sysclk_hz'])} | {divisor(s['div256'])} | {pll(s)} | "
                     f"{si_no(s['cumple_ref_min_5mhz'])} | {si_no(s['cumple_sysclk_max_133mhz'])} |")
    L.append("")

    L += ["Las tablas que siguen tienen una fila por par de sysclk y divisor que cumple la hoja del RP2040, "
          "ordenadas por la irregularidad que mete el divisor. La configuración de PLL es la representativa: "
          "REFDIV 1, el VCO más alto (la hoja indica que minimiza el jitter) y POSTDIV1 >= POSTDIV2. Configuraciones "
          f"cuenta cuántas combinaciones de PLL dan el mismo sysclk. Cada tabla muestra las {FILAS_POR_TABLA} "
          "primeras; el resto está en reloj-soluciones.csv.", ""]

    L += [f"### {g['caso']['titulo']}", "", f"{len(g['filas'])} pares de sysclk y divisor.", "",
          "| sysclk (MHz) | Divisor | INT | FRAC | Tipo | REFDIV, FBDIV, VCO (MHz), POSTDIV1, POSTDIV2 | "
          "Configuraciones | Variación del periodo (ns p-p) | Ciclo de trabajo |", "|---|---|---|---|---|---|---|---|---|"]
    for f in g["filas"][:FILAS_POR_TABLA]:
        L.append(f"| {mhz(f['sysclk_hz'])} | {divisor(f['div256'])} | {f['div_int']} | {f['div_frac']} | {tipo(f)} | "
                 f"{pll(f)} | {f['configs_pll']} | {f['mclk_periodo_pp_ns']:.3f} | {duty_gpout(f)} |")

    L += ["", f"### {p2['caso']['titulo']}", "",
          f"{len(p2['filas'])} pares de sysclk y divisor. Reloj maestro de 12.288 MHz hecho con una instrucción que "
          "pone el pin en alto y otra que lo pone en bajo. TIE es el error de tiempo de los flancos de subida respecto "
          "de una rejilla ideal de 12.288 MHz. Las métricas son el peor caso entre las dos alineaciones posibles del "
          "programa con el patrón del divisor.", "",
          "| sysclk (MHz) | Divisor | INT | FRAC | Tipo | REFDIV, FBDIV, VCO (MHz), POSTDIV1, POSTDIV2 | "
          "Configuraciones | Periodo MCLK (ns p-p) | TIE (ns p-p) | Ciclo de trabajo (%) | Pulso mínimo (ns) | "
          "Cumple PCM1808 |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in p2["filas"][:FILAS_POR_TABLA]:
        L.append(f"| {mhz(f['sysclk_hz'])} | {divisor(f['div256'])} | {f['div_int']} | {f['div_frac']} | {tipo(f)} | "
                 f"{pll(f)} | {f['configs_pll']} | {f['mclk_periodo_pp_ns']:.3f} | {f['mclk_tie_pp_ns']:.3f} | "
                 f"{100*f['duty_min']:.1f} a {100*f['duty_max']:.1f} | {f['pulso_min_ns']:.2f} | "
                 f"{si_no(f['cumple_pcm1808'])} |")

    L += ["", f"### {p1['caso']['titulo']}", "", f"{len(p1['filas'])} pares de sysclk y divisor.", "",
          "| sysclk (MHz) | Divisor | INT | FRAC | Tipo | REFDIV, FBDIV, VCO (MHz), POSTDIV1, POSTDIV2 | "
          "Configuraciones | Variación del periodo del SM (ns p-p) |", "|---|---|---|---|---|---|---|---|"]
    for f in p1["filas"][:FILAS_POR_TABLA]:
        L.append(f"| {mhz(f['sysclk_hz'])} | {divisor(f['div256'])} | {f['div_int']} | {f['div_frac']} | {tipo(f)} | "
                 f"{pll(f)} | {f['configs_pll']} | {f['periodo_sm_pp_ns']:.3f} |")

    L += ["", "### Mejor opción de cada camino", ""]
    if g["filas"]:
        e = g["filas"][0]
        if e["div_frac"] == 0:
            detalle = (f"sin variación de periodo, ciclo de trabajo de {duty_gpout(e)} y pulsos de "
                       f"{e['pulso_min_ns']:.2f} ns")
        else:
            detalle = f"variación de periodo de {e['mclk_periodo_pp_ns']:.3f} ns pico a pico"
        L.append(f"- {g['caso']['titulo']}: sysclk {mhz(e['sysclk_hz'])} MHz ({pll_texto(e)}), divisor "
                 f"{divisor(e['div256'])} {tipo(e)}, {detalle}.")
    candidatas = [f for f in p2["filas"] if f["cumple_pcm1808"]]
    if p2["filas"]:
        e = min(candidatas or p2["filas"],
                key=lambda f: (f["mclk_periodo_pp_ns"], f["mclk_tie_pp_ns"],
                               max(0.5 - f["duty_min"], f["duty_max"] - 0.5), -f["vco_hz"]))
        limite = abs(e["duty_min"] - DUTY_MIN) < 1e-9 or abs(e["duty_max"] - DUTY_MAX) < 1e-9
        L.append(f"- {p2['caso']['titulo']}: sysclk {mhz(e['sysclk_hz'])} MHz ({pll_texto(e)}), divisor "
                 f"{divisor(e['div256'])} (INT {e['div_int']}, FRAC {e['div_frac']}), variación de periodo "
                 f"{e['mclk_periodo_pp_ns']:.3f} ns, TIE {e['mclk_tie_pp_ns']:.3f} ns, ciclo de trabajo de "
                 f"{100*e['duty_min']:.1f} % a {100*e['duty_max']:.1f} %"
                 f"{', en el límite del PCM1808' if limite else ''}.")
    L.append(f"- {p1['caso']['titulo']}: no genera el reloj maestro. Una salida del PIO cambia como mucho una vez "
             "por ciclo de la máquina, así que lo más rápido que sale es 6.144 MHz = 128 fS, y el PCM1808 pide 256, "
             "384 o 512 fS.")
    return "\n".join(L)


def escribir_bloque(texto):
    doc = DOC.read_text(encoding="utf-8")
    if doc.count(MARCA_INICIO) != 1 or doc.count(MARCA_FIN) != 1 or doc.index(MARCA_INICIO) > doc.index(MARCA_FIN):
        raise SystemExit(f"docs/reloj.md tiene que tener cada marca una sola vez y en este orden:\n"
                         f"{MARCA_INICIO}\n{MARCA_FIN}")
    antes, resto = doc.split(MARCA_INICIO)
    _, despues = resto.split(MARCA_FIN)
    DOC.write_text(f"{antes}{MARCA_INICIO}\n{texto}\n{MARCA_FIN}{despues}", encoding="utf-8")


def main():
    ahora = datetime.now().astimezone()
    sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    resultados = {}
    for caso in CASOS:
        sol = buscar(caso)
        resultados[caso["clave"]] = {
            "caso": caso, "soluciones": sol, "filas": filas_unicas(sol, caso["clave"]),
            "enteras": [s for s in sol if s["div_frac"] == 0],
            "enteras_hoja": [s for s in sol if s["div_frac"] == 0 and valida_hoja(s)],
        }
    escribir_csv(resultados, ahora, sha)
    escribir_bloque(bloque(resultados, ahora, sha))
    total = sum(len(r["soluciones"]) for r in resultados.values())
    print(f"Escrito docs/reloj-soluciones.csv y el bloque generado de docs/reloj.md ({total} soluciones exactas)")


if __name__ == "__main__":
    main()
