// Connects to Python, keeps the latest state and frame, and draws at the screen's pace.
// Frames arrive up to 30 times per second; drawing happens only when a new one has arrived.

import "./styles.css";
import { CONTRACT, type Frame, type MeasurementUpdate, type Request, type ServerMessage, type State } from "./contract";
import { drawMeter, drawSpectrum, drawWaveform, formatDb, readInk } from "./draw";
import { createMenus } from "./menus";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const READOUT_EVERY_MS = 200; // the figures change slower than the bar, so they can be read

let socket: WebSocket | null = null;
let state: State | null = null;
let frame: Frame | null = null;
let drawn: Frame | null = null;
let redraw = false;
let lastReadout = 0;

function send(request: Request) {
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(request));
}

const menus = createMenus(send);

function notice(html: string, kind: "normal" | "error" = "normal") {
  const element = $("measurement-notice");
  element.innerHTML = html;
  if (kind === "error") element.dataset.state = "error";
  else delete element.dataset.state;
}

const escapeHtml = (text: string) =>
  text.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

function connect() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  socket = ws;
  ws.onmessage = (e) => receive(JSON.parse(e.data) as ServerMessage);
  ws.onclose = () => {
    const connection = $("connection");
    connection.textContent = "Sin conexión";
    connection.dataset.state = "down";
    window.setTimeout(connect, 1000);
  };
}

function receive(m: ServerMessage) {
  switch (m.type) {
    case "state":
      if (m.contract !== CONTRACT) {
        notice(`La interfaz habla el contrato ${CONTRACT} y Python el ${m.contract}. Hay que compilarla de nuevo.`, "error");
      }
      state = m;
      redraw = true;
      menus.update(m);
      updateButtons(m);
      $("waveform-note").textContent = `Últimos ${m.waveform_ms} ms`;
      $("connection").textContent = `${m.sample_rate / 1000} kHz`;
      delete $("connection").dataset.state;
      break;
    case "frame":
      frame = m;
      updateClipping(m);
      break;
    case "measurement":
      showMeasurement(m);
      break;
    case "saved":
      menus.showSaved(m.measurements);
      break;
    case "error":
      notice(escapeHtml(m.message), "error");
      break;
  }
}

function updateButtons(s: State) {
  const container = $("buttons");
  if (container.childElementCount !== s.measurements.length) {
    container.replaceChildren(
      ...s.measurements.map((measurement) => {
        const button = document.createElement("button");
        button.className = "measure-button";
        button.dataset.measurement = measurement.id;
        button.textContent = measurement.name;
        button.addEventListener("click", () => send({ type: "measure", measurement: measurement.id }));
        return button;
      }),
    );
  }
  for (const button of container.querySelectorAll<HTMLButtonElement>(".measure-button")) {
    button.disabled = s.measuring !== null;
    if (button.dataset.measurement === s.measuring) button.dataset.measuring = "";
    else delete button.dataset.measuring;
  }
}

function showMeasurement(m: MeasurementUpdate) {
  const name = state?.measurements.find((x) => x.id === m.measurement)?.name ?? m.measurement;
  $("measurement-notice").title = m.status === "done" ? m.path : "";
  if (m.status === "running") notice(`${escapeHtml(name)}: ${escapeHtml(m.message)}`);
  else if (m.status === "done") {
    notice(`Guardado en <button class="folder-link" data-folder="${escapeHtml(m.folder_name)}">${escapeHtml(m.folder)}</button><br>${escapeHtml(m.summary)}`);
  } else notice(`${escapeHtml(name)} no terminó: ${escapeHtml(m.message)}`, "error");
}

function elapsed(s: number) {
  if (s < 60) return `${Math.floor(s)} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min`;
  return `${Math.floor(s / 3600)} h`;
}

function updateClipping(f: Frame) {
  const box = $("clipping");
  const text = $("clipping-text");
  const { now, seconds_ago, blocks } = f.clipping;
  let message = "Sin saturación en esta sesión";
  if (now) {
    message = "Saturando ahora";
    box.dataset.state = "now";
  } else if (blocks > 0 && seconds_ago !== null) {
    message = `Saturó hace ${elapsed(seconds_ago)}, ${blocks} ${blocks === 1 ? "bloque" : "bloques"} en esta sesión`;
    box.dataset.state = "before";
  } else {
    delete box.dataset.state;
  }
  if (text.textContent !== message) text.textContent = message;
  $("clear-clipping").hidden = now || blocks === 0;
}

$("clear-clipping").addEventListener("click", () => send({ type: "clear_clipping" }));
$("measurement-notice").addEventListener("click", (e) => {
  const button = (e.target as HTMLElement).closest<HTMLButtonElement>("[data-folder]");
  if (button?.dataset.folder) send({ type: "open_saved", folder: button.dataset.folder });
});
window.addEventListener("resize", () => (redraw = true));
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => (redraw = true));

function draw(t: number) {
  // Colors are read on every frame instead of once at startup: this way the canvas follows the stylesheet
  // even when it applies after the script runs or the system switches mode. Without ink yet, nothing is drawn.
  const ink = readInk();
  if (ink.ink && state && frame && (frame !== drawn || redraw)) {
    drawWaveform($<HTMLCanvasElement>("waveform"), frame.waveform, state.sample_rate, state.waveform_ms, ink);
    drawSpectrum($<HTMLCanvasElement>("spectrum"), state.frequencies_hz, frame, ink);
    drawMeter($<HTMLCanvasElement>("meter"), frame, ink);
    drawn = frame;
    redraw = false;
    if (t - lastReadout >= READOUT_EVERY_MS) {
      // The big figures use the typographic minus sign: it is as wide as a digit.
      $("peak-readout").textContent = formatDb(frame.level.readout_peak_dbfs).replace("-", "−");
      $("rms-readout").textContent = formatDb(frame.level.rms_dbfs).replace("-", "−");
      lastReadout = t;
    }
  }
  requestAnimationFrame(draw);
}

connect();
requestAnimationFrame(draw);
