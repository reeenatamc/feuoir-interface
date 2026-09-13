// Los dos menús de la barra: la entrada y los ajustes de la señal de prueba.
// No guardan la señal: muestran la del último estado y mandan cada cambio a Python.

import type { Estado, Forma, Pedido, Senal } from "./contrato";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

const F_MIN = 20;
const F_MAX = 20000;
const PASOS_DESLIZADOR = 1000;
const ENVIOS_POR_SEGUNDO = 20;

export function frecuenciaCorta(f: number): string {
  return f >= 1000 ? `${Number((f / 1000).toFixed(3))} kHz` : `${Number(f.toFixed(1))} Hz`;
}

export function describirSenal(senal: Senal, sintetica: boolean): string {
  const nivel = `${senal.nivel_dbfs > 0 ? "+" : ""}${senal.nivel_dbfs} dBFS`;
  if (!sintetica) return `Tono de ${frecuenciaCorta(senal.frecuencia_hz)} a ${nivel}`;
  switch (senal.forma) {
    case "seno": return `Seno de ${frecuenciaCorta(senal.frecuencia_hz)} a ${nivel}`;
    case "barrido": return `Barrido de 20 Hz a 20 kHz a ${nivel}`;
    case "ruido": return `Ruido a ${nivel} RMS`;
    case "silencio": return "Silencio";
  }
}

const aDeslizador = (f: number) => Math.round((PASOS_DESLIZADOR * Math.log(f / F_MIN)) / Math.log(F_MAX / F_MIN));
const deDeslizador = (p: number) => Math.round(F_MIN * (F_MAX / F_MIN) ** (p / PASOS_DESLIZADOR));
const acotar = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v));

export function crearMenus(enviar: (p: Pedido) => void) {
  const campoEntrada = $<HTMLButtonElement>("campo-entrada");
  const campoSenal = $<HTMLButtonElement>("campo-senal");
  const menuEntrada = $("menu-entrada");
  const menuSenal = $("menu-senal");
  const opciones = $("opciones-entrada");
  const formas = Array.from(menuSenal.querySelectorAll<HTMLButtonElement>(".formas button"));
  const frecuencia = $<HTMLInputElement>("frecuencia");
  const frecuenciaDeslizador = $<HTMLInputElement>("frecuencia-deslizador");
  const nivel = $<HTMLInputElement>("nivel");
  const nivelDeslizador = $<HTMLInputElement>("nivel-deslizador");

  let senal: Senal | null = null;
  let editando = false;
  let pendiente: number | null = null;
  const pares: [HTMLButtonElement, HTMLElement][] = [[campoEntrada, menuEntrada], [campoSenal, menuSenal]];

  function cerrar(devolverFoco = false) {
    for (const [campo, menu] of pares) {
      if (!menu.hidden && devolverFoco) campo.focus();
      menu.hidden = true;
      campo.setAttribute("aria-expanded", "false");
    }
  }

  function abrir(campo: HTMLButtonElement, menu: HTMLElement) {
    const yaAbierto = !menu.hidden;
    cerrar();
    if (yaAbierto) return;
    menu.hidden = false;
    campo.setAttribute("aria-expanded", "true");
    const r = campo.getBoundingClientRect();
    menu.style.top = `${r.bottom + 12}px`;
    menu.style.left = `${Math.max(16, Math.min(r.right - menu.offsetWidth, window.innerWidth - menu.offsetWidth - 16))}px`;
    menu.querySelector<HTMLElement>("[aria-pressed='true'], [aria-checked='true'], button, input")?.focus();
  }

  campoEntrada.addEventListener("click", () => abrir(campoEntrada, menuEntrada));
  campoSenal.addEventListener("click", () => abrir(campoSenal, menuSenal));
  document.addEventListener("pointerdown", (e) => {
    const dentro = pares.some(([campo, menu]) => campo.contains(e.target as Node) || menu.contains(e.target as Node));
    if (!dentro) cerrar();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") cerrar(true);
  });
  window.addEventListener("resize", () => cerrar());
  $("actualizar-entradas").addEventListener("click", () => enviar({ tipo: "actualizar_entradas" }));

  // Los deslizadores mandan a lo sumo ENVIOS_POR_SEGUNDO cambios; el último siempre sale.
  function mandar(cambio: Partial<Senal>) {
    if (!senal) return;
    senal = { ...senal, ...cambio };
    if (pendiente !== null) return;
    pendiente = window.setTimeout(() => {
      pendiente = null;
      if (senal) enviar({ tipo: "senal", ...senal });
    }, 1000 / ENVIOS_POR_SEGUNDO);
  }

  for (const boton of formas) {
    boton.addEventListener("click", () => {
      formas.forEach((b) => b.setAttribute("aria-checked", String(b === boton)));
      mandar({ forma: boton.dataset.forma as Forma });
    });
  }

  frecuenciaDeslizador.addEventListener("input", () => {
    const f = deDeslizador(Number(frecuenciaDeslizador.value));
    frecuencia.value = String(f);
    mandar({ frecuencia_hz: f });
  });
  frecuencia.addEventListener("change", () => {
    const f = acotar(Number(frecuencia.value) || 1000, F_MIN, F_MAX);
    frecuencia.value = String(f);
    frecuenciaDeslizador.value = String(aDeslizador(f));
    mandar({ frecuencia_hz: f });
  });
  nivelDeslizador.addEventListener("input", () => {
    nivel.value = nivelDeslizador.value;
    mandar({ nivel_dbfs: Number(nivelDeslizador.value) });
  });
  nivel.addEventListener("change", () => {
    const n = acotar(Number(nivel.value) || 0, -120, 6);
    nivel.value = String(n);
    nivelDeslizador.value = String(n);
    mandar({ nivel_dbfs: n });
  });

  // Mientras se arrastra o se escribe, el estado que llega no pisa lo que se está tocando.
  for (const control of [frecuencia, frecuenciaDeslizador, nivel, nivelDeslizador]) {
    control.addEventListener("pointerdown", () => (editando = true));
    control.addEventListener("focus", () => (editando = true));
    control.addEventListener("blur", () => (editando = false));
  }
  document.addEventListener("pointerup", () => {
    if (document.activeElement !== frecuencia && document.activeElement !== nivel) editando = false;
  });

  function actualizar(estado: Estado) {
    const sintetica = estado.entrada === "sintetica";
    const actual = estado.entradas.find((e) => e.id === estado.entrada);
    $("valor-entrada").textContent = actual?.nombre ?? estado.entrada;
    $("valor-senal").textContent = describirSenal(estado.senal, sintetica);
    campoEntrada.disabled = estado.midiendo !== null;

    opciones.replaceChildren(
      ...estado.entradas.map((e) => {
        const li = document.createElement("li");
        const boton = document.createElement("button");
        boton.className = "opcion";
        boton.textContent = e.nombre;
        boton.setAttribute("aria-pressed", String(e.id === estado.entrada));
        boton.addEventListener("click", () => {
          cerrar(true);
          if (e.id !== estado.entrada) enviar({ tipo: "entrada", id: e.id });
        });
        li.append(boton);
        return li;
      }),
    );

    ($("rotulo-forma").parentElement as HTMLElement).hidden = !sintetica;
    $("pista-senal").textContent = sintetica
      ? "Por encima de 0 dBFS la fuente satura, como el conversor. THD+N y SNR miden un tono con esta frecuencia y este nivel."
      : "Suena por la salida de la Mac solo durante las mediciones, con esta frecuencia y este nivel.";

    if (editando || pendiente !== null) return;
    senal = { ...estado.senal };
    formas.forEach((b) => b.setAttribute("aria-checked", String(b.dataset.forma === senal!.forma)));
    frecuencia.value = String(senal.frecuencia_hz);
    frecuenciaDeslizador.value = String(aDeslizador(senal.frecuencia_hz));
    nivel.value = String(senal.nivel_dbfs);
    nivelDeslizador.value = String(senal.nivel_dbfs);
  }

  return { actualizar, cerrar };
}
