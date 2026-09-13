"""Búsqueda exhaustiva de configuraciones del RP2040 para el reloj maestro del PCM1808.

    .venv/bin/python relojes.py

El PCM1808 a fS = 48 kHz necesita en SCKI 256 fS = 12.288 MHz y el Pico tiene un cristal de
12 MHz. La cadena es cristal, PLL del sistema, sysclk, divisor del PIO y máquina de estados.
El script prueba todas las combinaciones de esa cadena en aritmética entera, sin coma
flotante, y se queda con las que dan la frecuencia objetivo exacta.

Escribe docs/reloj.md (tablas, solución elegida y por qué) y docs/reloj-soluciones.csv
(todas las soluciones exactas con cada restricción marcada). Las dos salidas llevan las
condiciones de la búsqueda y se reescriben completas en cada corrida.
"""
import csv, hashlib, platform
from collections import defaultdict
from datetime import datetime
from functools import lru_cache
from itertools import accumulate
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

# Restricciones del enunciado. Coinciden con la sección 2.18 de la hoja del RP2040.
FREF_HZ = 12_000_000
REFDIV = range(1, 64)
FBDIV = range(16, 321)
VCO_MIN_HZ, VCO_MAX_HZ = 750_000_000, 1_600_000_000
POSTDIV = range(1, 8)
DIV_MIN_256, DIV_MAX_256 = 256, 65536*256      # divisor del PIO en 1/256: de 1 a 65536

# Restricciones que agrega la hoja del RP2040 (secciones 2.15 y 2.18).
REF_MIN_HZ = 5_000_000                          # FREF/REFDIV mínima
SYSCLK_MAX_HZ = 133_000_000                     # máximo de clk_sys

# PCM1808, tabla System clock timing.
DUTY_MIN, DUTY_MAX = 0.40, 0.60
PULSO_MIN_NS = 8.0

MCLK_HZ = 12_288_000
FILAS_POR_TABLA = 12

CASOS = [
    {"clave": "12.288", "objetivo_hz": 12_288_000, "instrucciones": 1},
    {"clave": "24.576", "objetivo_hz": 24_576_000, "instrucciones": 2},
]


def buscar(objetivo_hz):
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
                    if not DIV_MIN_256 <= div256 <= DIV_MAX_256:
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
    """Ciclos de sysclk entre habilitaciones sucesivas de la máquina de estados.

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
def metricas(sysclk_hz, div256, instrucciones):
    """Irregularidad determinista que mete el divisor en régimen estable; no incluye el jitter del PLL."""
    ts_ns = 1e9 / sysclk_hz
    # El primer periodo después de arrancar no sigue el patrón estable, así que se descartan
    # los primeros 256 ticks. El patrón se repite cada 256 ticks o menos.
    d = ciclos_por_tick(div256, 256 + 1024)[256:]
    m = {"periodo_sm_pp_ns": (max(d) - min(d))*ts_ns}
    if instrucciones != 2:
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


def filas_unicas(soluciones, instrucciones):
    """Una fila por par (sysclk, divisor) que cumple la hoja, con una configuración de PLL representativa."""
    grupos = defaultdict(list)
    for s in soluciones:
        if valida_hoja(s):
            grupos[(s["sysclk_hz"], s["div256"])].append(s)
    filas = []
    for (sysclk, div256), configs in grupos.items():
        # REFDIV 1 como recomienda la hoja, VCO lo más alto posible (menos jitter) y POSTDIV1 >= POSTDIV2
        rep = min(configs, key=lambda s: (s["refdiv"] != 1, -s["vco_hz"], not s["postdiv1_mayor_o_igual"], s["postdiv1"]))
        filas.append({**rep, **metricas(sysclk, div256, instrucciones), "configs_pll": len(configs)})
    filas.sort(key=lambda r: (r["div_frac"] != 0, r.get("mclk_periodo_pp_ns", r["periodo_sm_pp_ns"]),
                              r.get("mclk_tie_pp_ns", 0.0), -r["sysclk_hz"]))
    return filas


def mhz(hz):
    return f"{hz/1e6:.6f}".rstrip("0").rstrip(".")


def divisor(div256):
    return f"{div256/256:.8f}".rstrip("0").rstrip(".")


def pll(s):
    return f"{s['refdiv']}, {s['fbdiv']}, {mhz(s['vco_hz'])}, {s['postdiv1']}, {s['postdiv2']}"


def si_no(v):
    return "sí" if v else "no"


def tipo(s):
    return "entero" if s["div_frac"] == 0 else "fraccionario"


def main():
    ahora = datetime.now().astimezone()
    sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    combinaciones = len(REFDIV)*len(FBDIV)*len(POSTDIV)**2

    resultados = {}
    for caso in CASOS:
        sol = buscar(caso["objetivo_hz"])
        resultados[caso["clave"]] = {
            "caso": caso, "soluciones": sol, "filas": filas_unicas(sol, caso["instrucciones"]),
            "enteras": [s for s in sol if s["div_frac"] == 0],
            "enteras_hoja": [s for s in sol if s["div_frac"] == 0 and valida_hoja(s)],
        }
    r1, r2 = resultados["12.288"], resultados["24.576"]

    # CSV con todas las soluciones exactas
    columnas = ["caso_mhz", "instrucciones_por_periodo", "refdiv", "fbdiv", "vco_hz", "postdiv1", "postdiv2",
                "sysclk_hz", "divisor", "div_int", "div_frac", "divisor_entero", "cumple_ref_min_5mhz",
                "cumple_sysclk_max_133mhz", "postdiv1_mayor_o_igual", "periodo_sm_pp_ns",
                "mclk_periodo_pp_ns", "mclk_tie_pp_ns", "duty_min", "duty_max", "pulso_min_ns", "cumple_pcm1808"]
    csv_path = RAIZ / "docs" / "reloj-soluciones.csv"
    csv_path.parent.mkdir(exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        fh.write(f"# relojes.py {ahora.isoformat(timespec='seconds')} sha256 {sha}\n")
        fh.write("# FREF 12 MHz; REFDIV 1-63; FBDIV 16-320; VCO 750-1600 MHz; POSTDIV1 y POSTDIV2 1-7; "
                 "divisor PIO entero 16 bits + fraccion/256. Tiempos en ns en regimen estable, sin el jitter del PLL.\n")
        w = csv.DictWriter(fh, fieldnames=columnas, extrasaction="ignore")
        w.writeheader()
        for r in (r1, r2):
            caso = r["caso"]
            for s in r["soluciones"]:
                m = metricas(s["sysclk_hz"], s["div256"], caso["instrucciones"])
                w.writerow({**s, **m, "caso_mhz": caso["clave"], "instrucciones_por_periodo": caso["instrucciones"],
                            "divisor": divisor(s["div256"]), "divisor_entero": s["div_frac"] == 0})

    candidatas = [f for f in r2["filas"] if f["cumple_pcm1808"]]
    enteras2 = [f for f in r2["filas"] if f["div_frac"] == 0]
    if enteras2:
        elegida = min(enteras2, key=lambda f: -f["vco_hz"])
    else:
        elegida = min(candidatas or r2["filas"],
                      key=lambda f: (f["mclk_periodo_pp_ns"], f["mclk_tie_pp_ns"],
                                     max(0.5 - f["duty_min"], f["duty_max"] - 0.5), -f["vco_hz"]))

    L = []
    L += ["# Reloj maestro del PCM1808", "",
          f"Generado por relojes.py el {ahora:%Y-%m-%d %H:%M %z} (sha256 del script {sha[:12]}, Python "
          f"{platform.python_version()}). Se reescribe completo en cada corrida, no editar a mano. "
          "Todas las soluciones exactas, con cada restricción marcada, están en reloj-soluciones.csv.", ""]

    L += ["## Qué hace falta", "",
          "A fS = 48 kHz el PCM1808 acepta en SCKI 256 fS = 12.288 MHz, 384 fS = 18.432 MHz o 512 fS = 24.576 MHz, "
          "con ciclo de trabajo entre 40 % y 60 % y pulsos alto y bajo de al menos 8 ns (hoja del PCM1808, tabla "
          "System clock timing). El Pico tiene un cristal de 12 MHz, así que la frecuencia sale de multiplicar con el "
          "PLL del sistema y dividir con el divisor del PIO.", ""]

    L += ["## Condiciones de la búsqueda", "",
          f"Se probaron las {combinaciones:,} combinaciones de REFDIV, FBDIV, POSTDIV1 y POSTDIV2".replace(",", ".", 1)
          + ", y para cada una se calculó el divisor del PIO que haría falta. Una combinación es solución si ese "
          "divisor es exactamente representable como entero de 16 bits más fracción/256 y está entre 1 y 65536. "
          "Todo el cálculo es en enteros, sin redondeo.", "",
          "Restricciones del enunciado:", "",
          "- FREF = 12 MHz, REFDIV de 1 a 63, FBDIV de 16 a 320",
          "- VCO = FREF/REFDIV x FBDIV entre 750 y 1600 MHz",
          "- POSTDIV1 y POSTDIV2 de 1 a 7, sysclk = VCO/(POSTDIV1 x POSTDIV2)",
          "- divisor del PIO = entero + fracción/256", "",
          "Restricciones que agrega la hoja del RP2040 y que se marcan aparte:", "",
          "- FREF/REFDIV de al menos 5 MHz (sección 2.18). Con el cristal de 12 MHz eso deja REFDIV en 1 o 2.",
          "- FREF/REFDIV no mayor que VCO/16 (sección 2.18). Equivale a FBDIV >= 16, así que ya se cumple siempre.",
          "- clk_sys de 133 MHz como máximo (secciones 2.15 y 2.18).", "",
          "El jitter se calcula con el modelo del divisor fraccionario de la hoja del RP2040 (sección 3.5.5): "
          "delta-sigma de primer orden que alarga algunos periodos de n a n+1 ciclos de sysclk. Es la parte "
          "determinista que agrega el divisor en régimen estable, sin los primeros 256 periodos después de "
          "arrancar. El jitter propio del PLL no está incluido.", ""]

    L += ["## Resultado", "",
          "| Máquina de estados | Soluciones exactas | Con divisor entero | Cumplen la hoja del RP2040 | "
          "Cumplen la hoja y tienen divisor entero |", "|---|---|---|---|---|"]
    for r in (r1, r2):
        hoja = [s for s in r["soluciones"] if valida_hoja(s)]
        L.append(f"| {r['caso']['clave']} MHz | {len(r['soluciones'])} | {len(r['enteras'])} | {len(hoja)} | "
                 f"{len(r['enteras_hoja'])} |")
    L.append("")
    for r in (r1, r2):
        if not r["enteras"]:
            L += [f"Para {r['caso']['clave']} MHz ninguna combinación da divisor entero, ni con las restricciones "
                  "del enunciado ni con las de la hoja.", ""]
    if not r2["enteras"]:
        L += ["No es un límite de la búsqueda. Para que sysclk/24.576 MHz sea entero, FBDIV tendría que ser "
              "múltiplo de 256, o sea 256, y entonces REFDIV x POSTDIV1 x POSTDIV2 tendría que dividir a 125 con "
              "REFDIV entre 2 y 4 para que el VCO quede en rango, lo que no pasa.", ""]

    L += ["Las soluciones con divisor entero, sin filtrar:", "",
          "| Máquina de estados | sysclk (MHz) | Divisor | REFDIV, FBDIV, VCO (MHz), POSTDIV1, POSTDIV2 | "
          "REF >= 5 MHz | sysclk <= 133 MHz |", "|---|---|---|---|---|---|"]
    for r in (r1, r2):
        for s in sorted(r["enteras"], key=lambda s: (s["sysclk_hz"], s["refdiv"], -s["postdiv1"])):
            L.append(f"| {r['caso']['clave']} MHz | {mhz(s['sysclk_hz'])} | {divisor(s['div256'])} | {pll(s)} | "
                     f"{si_no(s['cumple_ref_min_5mhz'])} | {si_no(s['cumple_sysclk_max_133mhz'])} |")
    if not r1["enteras"] and not r2["enteras"]:
        L.append("| ninguna | | | | | |")
    L.append("")

    L += ["## Soluciones que cumplen la hoja del RP2040", "",
          "Una fila por par de sysclk y divisor, ordenadas por la irregularidad que mete el divisor. La "
          "configuración de PLL mostrada es la representativa: REFDIV 1, el VCO más alto (la hoja indica que "
          "minimiza el jitter) y POSTDIV1 >= POSTDIV2. La columna de configuraciones cuenta cuántas combinaciones de "
          f"PLL dan el mismo sysclk. Cada tabla muestra las {FILAS_POR_TABLA} primeras; el resto está en "
          "reloj-soluciones.csv.", "",
          "### Máquina de estados a 12.288 MHz, una instrucción por periodo", "",
          f"{len(r1['filas'])} pares de sysclk y divisor.", "",
          "| sysclk (MHz) | Divisor | INT | FRAC | Tipo | REFDIV, FBDIV, VCO (MHz), POSTDIV1, POSTDIV2 | "
          "Configuraciones | Variación del periodo del SM (ns p-p) |", "|---|---|---|---|---|---|---|---|"]
    for f in r1["filas"][:FILAS_POR_TABLA]:
        L.append(f"| {mhz(f['sysclk_hz'])} | {divisor(f['div256'])} | {f['div_int']} | {f['div_frac']} | "
                 f"{tipo(f)} | {pll(f)} | {f['configs_pll']} | {f['periodo_sm_pp_ns']:.3f} |")
    L += ["", "### Máquina de estados a 24.576 MHz, dos instrucciones por periodo", "",
          f"{len(r2['filas'])} pares de sysclk y divisor. Reloj maestro de 12.288 MHz hecho con una instrucción que "
          "pone el pin en alto y otra que lo pone en bajo. TIE es el error de tiempo de los flancos de subida "
          "respecto de una rejilla ideal de 12.288 MHz. Las métricas son el peor caso entre las dos alineaciones "
          "posibles del programa con el patrón del divisor.", "",
          "| sysclk (MHz) | Divisor | INT | FRAC | Tipo | REFDIV, FBDIV, VCO (MHz), POSTDIV1, POSTDIV2 | "
          "Configuraciones | Periodo MCLK (ns p-p) | TIE (ns p-p) | Ciclo de trabajo (%) | Pulso mínimo (ns) | "
          "Cumple PCM1808 |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in r2["filas"][:FILAS_POR_TABLA]:
        L.append(f"| {mhz(f['sysclk_hz'])} | {divisor(f['div256'])} | {f['div_int']} | {f['div_frac']} | "
                 f"{tipo(f)} | {pll(f)} | {f['configs_pll']} | "
                 f"{f['mclk_periodo_pp_ns']:.3f} | {f['mclk_tie_pp_ns']:.3f} | "
                 f"{100*f['duty_min']:.1f} a {100*f['duty_max']:.1f} | {f['pulso_min_ns']:.2f} | "
                 f"{si_no(f['cumple_pcm1808'])} |")
    L.append("")

    e = elegida
    periodo_mclk_ns = 1e9/MCLK_HZ
    periodo_fijo = e["mclk_periodo_pp_ns"] < 1e-9
    en_limite = abs(e["duty_min"] - DUTY_MIN) < 1e-9 or abs(e["duty_max"] - DUTY_MAX) < 1e-9
    L += ["## Solución elegida", "",
          "- Máquina de estados a 24.576 MHz con dos instrucciones por periodo, reloj maestro de 12.288 MHz",
          f"- PLL del sistema: REFDIV {e['refdiv']}, FBDIV {e['fbdiv']}, VCO {mhz(e['vco_hz'])} MHz, "
          f"POSTDIV1 {e['postdiv1']}, POSTDIV2 {e['postdiv2']}",
          f"- sysclk {mhz(e['sysclk_hz'])} MHz",
          f"- Divisor del PIO {divisor(e['div256'])} (INT {e['div_int']}, FRAC {e['div_frac']}), {tipo(e)}",
          f"- Con el SDK 2.3.1: set_sys_clock_pll({e['vco_hz']}, {e['postdiv1']}, {e['postdiv2']}) y "
          f"pio_sm_set_clkdiv_int_frac8(pio, sm, {e['div_int']}, {e['div_frac']})", "",
          "## Por qué", ""]

    if not r2["enteras_hoja"]:
        L += ["Una salida del PIO cambia como mucho una vez por ciclo de la máquina de estados, así que una onda "
              "cuadrada necesita al menos dos ciclos por periodo. Con la máquina a 12.288 MHz lo más rápido que "
              "sale es 6.144 MHz = 128 fS, que el PCM1808 no acepta. El caso que sirve es el de 24.576 MHz, y ahí "
              "no hay divisor entero posible.", ""]
        if r1["enteras_hoja"]:
            s = r1["enteras_hoja"][0]
            L += [f"La única forma entera que cumple la hoja es a 12.288 MHz: sysclk {mhz(s['sysclk_hz'])} MHz y "
                  f"divisor {divisor(s['div256'])}. Sirve si una máquina de estados tiene que correr a 12.288 MHz "
                  "por otro motivo, pero no para generar el reloj maestro con el PIO.", ""]

    if e["div_frac"] == 0:
        L += ["Tiene divisor entero, así que la máquina de estados avanza a intervalos iguales y el divisor no "
              "agrega jitter. Entre las enteras es la de VCO más alto.", ""]
    else:
        n = e["div_int"]
        texto = ("Entre las fraccionarias que cumplen la hoja del RP2040 y la del PCM1808, es la de menor variación "
                 "del periodo del reloj maestro. ")
        if periodo_fijo and e["div_frac"] == 128:
            texto += (f"Con divisor {divisor(e['div256'])} el delta-sigma alterna periodos de {n} y {n + 1} ciclos de "
                      f"sysclk, y como el programa tiene dos instrucciones, cada periodo del reloj maestro suma uno de "
                      f"cada tipo: siempre {2*n + 1} ciclos, {periodo_mclk_ns:.2f} ns. El periodo no varía.")
        else:
            texto += (f"Varía {e['mclk_periodo_pp_ns']:.3f} ns pico a pico, con TIE de {e['mclk_tie_pp_ns']:.3f} ns, "
                      f"sobre un periodo de {periodo_mclk_ns:.2f} ns.")
        L += [texto, ""]
        if en_limite:
            L += [f"El precio es el ciclo de trabajo, que queda en {100*e['duty_min']:.1f} % o "
                  f"{100*e['duty_max']:.1f} % según qué instrucción caiga en el periodo corto. La hoja del PCM1808 "
                  "pide de 40 % a 60 %, así que queda justo en el límite, sin margen para la diferencia entre subida "
                  "y bajada del pin. Hay que medirlo con osciloscopio cuando exista la placa.", ""]
        else:
            L += [f"El ciclo de trabajo queda entre {100*e['duty_min']:.1f} % y {100*e['duty_max']:.1f} %, dentro "
                  "de lo que pide la hoja del PCM1808 (40 % a 60 %).", ""]
        otras = [f for f in candidatas if f is not e]
        if otras:
            o = min(otras, key=lambda f: f["mclk_periodo_pp_ns"])
            L += [f"La siguiente opción que cumple las dos hojas (sysclk {mhz(o['sysclk_hz'])} MHz, divisor "
                  f"{divisor(o['div256'])}) ya varía {o['mclk_periodo_pp_ns']:.3f} ns pico a pico, un "
                  f"{100*o['mclk_periodo_pp_ns']/periodo_mclk_ns:.0f} % del periodo del reloj maestro, con ciclo de "
                  f"trabajo de {100*o['duty_min']:.1f} % a {100*o['duty_max']:.1f} %.", ""]
        L += [f"REFDIV {e['refdiv']} porque la hoja del RP2040 lo recomienda con cristales de 5 a 15 MHz, y VCO de "
              f"{mhz(e['vco_hz'])} MHz porque indica que el jitter del PLL baja con el VCO más alto.", ""]

    gp = [s for s in r1["enteras_hoja"] if s["sysclk_hz"] == e["sysclk_hz"]]
    if gp and e["div_frac"] != 0:
        L += ["## Alternativa fuera del PIO", "",
              "Conviene evaluarla antes de escribir el firmware. El RP2040 puede sacar un reloj generado por GPIO21 "
              "(CLOCK GPOUT0 en la tabla de funciones de la hoja), hasta 50 MHz. Ese divisor, con valor entero, no "
              "alterna entre dos divisores (la alternancia es como la hoja describe la división fraccionaria), y el "
              "bit DC50 de CLK_GPOUT0_CTRL corrige el ciclo de trabajo con divisores impares. Con el mismo sysclk de "
              f"{mhz(e['sysclk_hz'])} MHz y divisor entero {divisor(gp[0]['div256'])} saldrían 12.288 MHz exactos, "
              "sin divisor fraccionario y con el ciclo de trabajo corregido.", "",
              "En el SDK 2.3.1, clock_gpio_init_int_frac8 configura la fuente y el divisor pero no activa DC50: habría "
              "que poner CLOCKS_CLK_GPOUT0_CTRL_DC50_BITS a mano. Nada de esto está medido todavía.", ""]

    L += ["## Conclusión de diseño", ""]
    if not r2["enteras"]:
        conclusion = ("Con el PIO no hay forma de sacar el reloj maestro de 12.288 MHz del cristal de 12 MHz con "
                      "divisor entero. ")
        if periodo_fijo and en_limite:
            conclusion += ("La mejor opción fraccionaria mantiene el periodo exacto pero deja el ciclo de trabajo en "
                           "el borde de la especificación del PCM1808.")
        elif periodo_fijo:
            conclusion += "La mejor opción fraccionaria mantiene el periodo exacto y cumple el ciclo de trabajo."
        else:
            conclusion += (f"La mejor opción fraccionaria varía {e['mclk_periodo_pp_ns']:.3f} ns pico a pico en "
                           "cada periodo.")
        if gp and e["div_frac"] != 0:
            conclusion += " La salida de reloj por GPIO21 con divisor entero es la alternativa a medir."
        L += [conclusion, ""]
    else:
        L += ["Existe una configuración con divisor entero y es la elegida.", ""]

    (RAIZ / "docs" / "reloj.md").write_text("\n".join(L), encoding="utf-8")
    print(f"Escrito docs/reloj.md y docs/reloj-soluciones.csv "
          f"({len(r1['soluciones']) + len(r2['soluciones'])} soluciones exactas)")


if __name__ == "__main__":
    main()
