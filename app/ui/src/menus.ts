// The menus: the input, the test signal settings and the saved measurements.
// They do not keep the signal: they show the one in the latest state and send every change to Python.

import type { Request, SavedMeasurement, Shape, Signal, State } from "./contract";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

const F_MIN = 20;
const F_MAX = 20000;
const SLIDER_STEPS = 1000;
const SENDS_PER_SECOND = 20;

export function shortFrequency(f: number): string {
  return f >= 1000 ? `${Number((f / 1000).toFixed(3))} kHz` : `${Number(f.toFixed(1))} Hz`;
}

export function describeSignal(signal: Signal, synthetic: boolean): string {
  const level = `${signal.level_dbfs > 0 ? "+" : ""}${signal.level_dbfs} dBFS`;
  if (!synthetic) return `Tono de ${shortFrequency(signal.frequency_hz)} a ${level}`;
  switch (signal.shape) {
    case "sine": return `Seno de ${shortFrequency(signal.frequency_hz)} a ${level}`;
    case "sweep": return `Barrido de 20 Hz a 20 kHz a ${level}`;
    case "noise": return `Ruido a ${level} RMS`;
    case "silence": return "Silencio";
  }
}

function shortDate(iso: string): string {
  const d = new Date(iso);
  if (!iso || Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("es", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

const toSlider = (f: number) => Math.round((SLIDER_STEPS * Math.log(f / F_MIN)) / Math.log(F_MAX / F_MIN));
const fromSlider = (p: number) => Math.round(F_MIN * (F_MAX / F_MIN) ** (p / SLIDER_STEPS));
const clamp = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v));

export function createMenus(send: (request: Request) => void) {
  const inputField = $<HTMLButtonElement>("input-field");
  const signalField = $<HTMLButtonElement>("signal-field");
  const savedButton = $<HTMLButtonElement>("show-saved");
  const inputMenu = $("input-menu");
  const signalMenu = $("signal-menu");
  const savedMenu = $("saved-menu");
  const shapes = Array.from(signalMenu.querySelectorAll<HTMLButtonElement>(".shapes button"));
  const frequency = $<HTMLInputElement>("frequency");
  const frequencySlider = $<HTMLInputElement>("frequency-slider");
  const level = $<HTMLInputElement>("level");
  const levelSlider = $<HTMLInputElement>("level-slider");

  let signal: Signal | null = null;
  let editing = false;
  let pending: number | null = null;
  const pairs: [HTMLButtonElement, HTMLElement][] = [
    [inputField, inputMenu],
    [signalField, signalMenu],
    [savedButton, savedMenu],
  ];

  function close(returnFocus = false) {
    for (const [trigger, menu] of pairs) {
      if (!menu.hidden && returnFocus) trigger.focus();
      menu.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
    }
  }

  function open(trigger: HTMLButtonElement, menu: HTMLElement) {
    const wasOpen = !menu.hidden;
    close();
    if (wasOpen) return;
    menu.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    // Menus in the top bar open downwards; the one in the footer opens upwards and grows upwards.
    const r = trigger.getBoundingClientRect();
    const upwards = r.top > window.innerHeight / 2;
    menu.style.top = upwards ? "auto" : `${r.bottom + 12}px`;
    menu.style.bottom = upwards ? `${window.innerHeight - r.top + 12}px` : "auto";
    menu.style.left = `${Math.max(16, Math.min(r.right - menu.offsetWidth, window.innerWidth - menu.offsetWidth - 16))}px`;
    menu.querySelector<HTMLElement>("[aria-pressed='true'], [aria-checked='true'], button, input")?.focus();
  }

  inputField.addEventListener("click", () => open(inputField, inputMenu));
  signalField.addEventListener("click", () => open(signalField, signalMenu));
  savedButton.addEventListener("click", () => {
    open(savedButton, savedMenu);
    if (!savedMenu.hidden) send({ type: "list_saved" });
  });
  document.addEventListener("pointerdown", (e) => {
    const inside = pairs.some(([trigger, menu]) => trigger.contains(e.target as Node) || menu.contains(e.target as Node));
    if (!inside) close();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close(true);
  });
  window.addEventListener("resize", () => close());
  $("refresh-devices").addEventListener("click", () => send({ type: "refresh_devices" }));
  $("open-measurements-folder").addEventListener("click", () => send({ type: "open_saved", folder: null }));

  // The sliders send at most SENDS_PER_SECOND changes; the last one always goes out.
  function queueChange(change: Partial<Signal>) {
    if (!signal) return;
    signal = { ...signal, ...change };
    if (pending !== null) return;
    pending = window.setTimeout(() => {
      pending = null;
      if (signal) send({ type: "signal", ...signal });
    }, 1000 / SENDS_PER_SECOND);
  }

  for (const button of shapes) {
    button.addEventListener("click", () => {
      shapes.forEach((b) => b.setAttribute("aria-checked", String(b === button)));
      queueChange({ shape: button.dataset.shape as Shape });
    });
  }

  frequencySlider.addEventListener("input", () => {
    const f = fromSlider(Number(frequencySlider.value));
    frequency.value = String(f);
    queueChange({ frequency_hz: f });
  });
  frequency.addEventListener("change", () => {
    const f = clamp(Number(frequency.value) || 1000, F_MIN, F_MAX);
    frequency.value = String(f);
    frequencySlider.value = String(toSlider(f));
    queueChange({ frequency_hz: f });
  });
  levelSlider.addEventListener("input", () => {
    level.value = levelSlider.value;
    queueChange({ level_dbfs: Number(levelSlider.value) });
  });
  level.addEventListener("change", () => {
    const n = clamp(Number(level.value) || 0, -120, 6);
    level.value = String(n);
    levelSlider.value = String(n);
    queueChange({ level_dbfs: n });
  });

  // While dragging or typing, an incoming state does not overwrite what is being edited.
  for (const control of [frequency, frequencySlider, level, levelSlider]) {
    control.addEventListener("pointerdown", () => (editing = true));
    control.addEventListener("focus", () => (editing = true));
    control.addEventListener("blur", () => (editing = false));
  }
  document.addEventListener("pointerup", () => {
    if (document.activeElement !== frequency && document.activeElement !== level) editing = false;
  });

  function renderOptions(listId: string, items: { id: string; name: string }[], selected: string, pick: (id: string) => void) {
    $(listId).replaceChildren(
      ...items.map((item) => {
        const element = document.createElement("li");
        const button = document.createElement("button");
        button.className = "option";
        button.textContent = item.name;
        button.setAttribute("aria-pressed", String(item.id === selected));
        button.addEventListener("click", () => pick(item.id));
        element.append(button);
        return element;
      }),
    );
  }

  function update(state: State) {
    const synthetic = state.input === "synthetic";
    const current = state.inputs.find((i) => i.id === state.input);
    $("input-value").textContent = current?.name ?? state.input;
    $("signal-value").textContent = describeSignal(state.signal, synthetic);
    inputField.disabled = state.measuring !== null;

    renderOptions("input-options", state.inputs, state.input, (id) => {
      close(true);
      if (id !== state.input) send({ type: "input", id });
    });
    // The output only matters with a real input: with the synthetic source the stimulus goes into the loopback.
    renderOptions("output-options", state.outputs, state.output, (id) => {
      if (id !== state.output) send({ type: "output", id });
    });

    $("output-setting").hidden = synthetic;
    $("shape-setting").hidden = !synthetic;
    $("signal-hint").textContent = synthetic
      ? "Por encima de 0 dBFS la fuente satura, como el conversor. THD+N y SNR miden un tono con esta frecuencia y este nivel."
      : "Suena por la salida elegida solo durante las mediciones, con esta frecuencia y este nivel.";

    if (editing || pending !== null) return;
    signal = { ...state.signal };
    shapes.forEach((b) => b.setAttribute("aria-checked", String(b.dataset.shape === signal!.shape)));
    frequency.value = String(signal.frequency_hz);
    frequencySlider.value = String(toSlider(signal.frequency_hz));
    level.value = String(signal.level_dbfs);
    levelSlider.value = String(signal.level_dbfs);
  }

  // Each row opens its folder in Finder. Python sends the list every time the menu opens.
  function showSaved(list: SavedMeasurement[]) {
    $("saved-empty").hidden = list.length > 0;
    $("saved-list").replaceChildren(
      ...list.map((saved) => {
        const item = document.createElement("li");
        const button = document.createElement("button");
        button.className = "option saved-option";
        button.title = `Abrir ${saved.folder} en Finder`;
        const parts: [string, string][] = [
          ["saved-name", saved.measurement],
          ["saved-date", shortDate(saved.date_time)],
          ["saved-summary", [saved.summary, saved.input ? `con ${saved.input}` : ""].filter(Boolean).join(", ")],
        ];
        for (const [className, text] of parts) {
          const span = document.createElement("span");
          span.className = className;
          span.textContent = text;
          button.append(span);
        }
        button.addEventListener("click", () => send({ type: "open_saved", folder: saved.folder }));
        item.append(button);
        return item;
      }),
    );
  }

  return { update, close, showSaved };
}
