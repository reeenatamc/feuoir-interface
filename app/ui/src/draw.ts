// Draws a frame on the three canvases. It computes nothing about the audio: everything arrives ready from Python.

import type { Frame } from "./contract";

const DB_MIN = -140;
const DB_MAX = 10; // above 0 dBFS: the fundamental of a clipped sine goes over 0 dBFS
const F_MIN = 20;
const F_MAX = 20000;
const METER_MIN = -60;
const WARNING_DBFS = -3;
const FONT = '10px "Inter Variable", ui-sans-serif, system-ui, sans-serif';

export interface Ink {
  ink: string;
  surface: string;
  sunken: string;
  orange: string;
  red: string;
}

// Colors come from the variables in styles.css, so the canvas follows the light or dark mode.
export function readInk(): Ink {
  const css = getComputedStyle(document.documentElement);
  const v = (name: string) => css.getPropertyValue(name).trim();
  return { ink: v("--ink"), surface: v("--surface"), sunken: v("--surface-sunken"), orange: v("--fire-orange"), red: v("--fire-red") };
}

// canvas does not reliably understand color-mix(), so transparency is built by hand.
function withAlpha(hex: string, a: number): string {
  const n = parseInt(hex.replace("#", ""), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}

export function formatDb(v: number): string {
  if (v < -120) return "< -120";
  const s = v.toFixed(1);
  if (s === "-0.0") return "0.0";
  return v > 0 && s !== "0.0" ? `+${s}` : s;
}

function formatFrequency(f: number): string {
  return f >= 1000 ? `${(f / 1000).toFixed(3)} kHz` : `${f.toFixed(1)} Hz`;
}

function prepare(canvas: HTMLCanvasElement) {
  const r = canvas.getBoundingClientRect();
  const k = window.devicePixelRatio || 1;
  const width = Math.round(r.width * k);
  const height = Math.round(r.height * k);
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const g = canvas.getContext("2d")!;
  g.setTransform(k, 0, 0, k, 0, 0);
  g.clearRect(0, 0, r.width, r.height);
  g.font = FONT;
  return { g, w: r.width, h: r.height };
}

function horizontalLine(g: CanvasRenderingContext2D, x0: number, x1: number, y: number) {
  g.beginPath();
  g.moveTo(x0, Math.round(y) + 0.5);
  g.lineTo(x1, Math.round(y) + 0.5);
  g.stroke();
}

export function drawWaveform(canvas: HTMLCanvasElement, waveform: number[], sampleRate: number, ms: number, ink: Ink) {
  const { g, w, h } = prepare(canvas);
  const left = 34, right = 8, top = 8, bottom = 22;
  const width = w - left - right, height = h - top - bottom;
  const y = (v: number) => top + (height * (1 - v)) / 2;

  g.lineWidth = 1;
  g.textAlign = "right";
  g.textBaseline = "middle";
  for (const v of [1, 0.5, 0, -0.5, -1]) {
    g.strokeStyle = withAlpha(ink.ink, v === 0 ? 0.14 : 0.06);
    horizontalLine(g, left, left + width, y(v));
    g.fillStyle = withAlpha(ink.ink, 0.45);
    g.fillText(String(v), left - 10, y(v));
  }
  g.textBaseline = "top";
  for (let m = 0; m <= ms; m += 2) {
    g.textAlign = m === 0 ? "left" : m === ms ? "right" : "center";
    g.fillText(`${m} ms`, left + (width * m) / ms, top + height + 8);
  }

  g.strokeStyle = ink.ink;
  g.lineWidth = 1.5;
  g.lineJoin = "round";
  g.beginPath();
  waveform.forEach((v, i) => {
    const px = left + (width * (i * 1000)) / sampleRate / ms;
    const py = y(Math.max(-1, Math.min(1, v)));
    if (i === 0) g.moveTo(px, py);
    else g.lineTo(px, py);
  });
  g.stroke();
}

export function drawSpectrum(canvas: HTMLCanvasElement, frequencies: number[], frame: Frame, ink: Ink) {
  const { g, w, h } = prepare(canvas);
  const left = 40, right = 10, top = 10, bottom = 22;
  const width = w - left - right, height = h - top - bottom;
  const x = (f: number) => left + (width * Math.log(f / F_MIN)) / Math.log(F_MAX / F_MIN);
  const y = (d: number) => top + (height * (DB_MAX - Math.max(DB_MIN, Math.min(DB_MAX, d)))) / (DB_MAX - DB_MIN);

  g.lineWidth = 1;
  g.textAlign = "right";
  g.textBaseline = "middle";
  for (let d = 0; d >= DB_MIN; d -= 20) {
    g.strokeStyle = withAlpha(ink.ink, d === 0 ? 0.14 : 0.06);
    horizontalLine(g, left, left + width, y(d));
    g.fillStyle = withAlpha(ink.ink, 0.45);
    g.fillText(String(d), left - 10, y(d));
  }
  g.textBaseline = "top";
  const ticks: [number, string][] = [[20, "20"], [50, "50"], [100, "100"], [200, "200"], [500, "500"], [1000, "1 k"], [2000, "2 k"], [5000, "5 k"], [10000, "10 k"], [20000, "20 k"]];
  for (const [f, text] of ticks) {
    const px = Math.round(x(f)) + 0.5;
    g.strokeStyle = withAlpha(ink.ink, 0.06);
    g.beginPath();
    g.moveTo(px, top);
    g.lineTo(px, top + height);
    g.stroke();
    g.textAlign = f === F_MIN ? "left" : f === F_MAX ? "right" : "center";
    g.fillText(text, px, top + height + 8);
  }

  g.strokeStyle = ink.ink;
  g.lineWidth = 1.5;
  g.lineJoin = "round";
  g.beginPath();
  frame.spectrum_dbfs.forEach((d, i) => {
    if (i === 0) g.moveTo(x(frequencies[i]), y(d));
    else g.lineTo(x(frequencies[i]), y(d));
  });
  g.stroke();

  const peak = frame.spectrum_peak;
  if (peak) {
    const px = x(peak.frequency_hz), py = y(peak.level_dbfs);
    g.fillStyle = ink.surface;
    g.beginPath();
    g.arc(px, py, 4.5, 0, 2 * Math.PI);
    g.fill();
    g.strokeStyle = ink.ink;
    g.lineWidth = 1.5;
    g.stroke();
    g.font = '500 12px "Inter Variable", ui-sans-serif, system-ui, sans-serif';
    g.fillStyle = ink.ink;
    g.textBaseline = "middle";
    const text = `${formatFrequency(peak.frequency_hz)}   ${formatDb(peak.level_dbfs)} dBFS`;
    const fitsRight = px + 12 + g.measureText(text).width < left + width;
    g.textAlign = fitsRight ? "left" : "right";
    g.fillText(text, fitsRight ? px + 12 : px - 12, Math.max(py, top + 8));
  }
}

export function drawMeter(canvas: HTMLCanvasElement, frame: Frame, ink: Ink) {
  const { g, h } = prepare(canvas);
  const left = 34, bar = 20, top = 6, bottom = 6;
  const height = h - top - bottom;
  const y = (d: number) => top + (height * -Math.max(METER_MIN, Math.min(0, d))) / -METER_MIN;
  const { level, clipping } = frame;

  g.textAlign = "right";
  g.textBaseline = "middle";
  g.fillStyle = withAlpha(ink.ink, 0.45);
  for (const d of [0, -6, -12, -24, -36, -48, -60]) g.fillText(String(d), left - 10, y(d));

  g.fillStyle = ink.sunken;
  g.fillRect(left, top, bar, height);
  // Warning zone from -3 dBFS: faint while not clipping, red when clipping.
  g.fillStyle = clipping.now ? ink.red : withAlpha(ink.orange, 0.18);
  g.fillRect(left, top, bar, y(WARNING_DBFS) - top);

  const barTop = Math.max(y(level.peak_dbfs), y(WARNING_DBFS));
  if (level.peak_dbfs > METER_MIN) {
    g.fillStyle = ink.ink;
    g.fillRect(left, barTop, bar, top + height - barTop);
  }
  // Readout peak: the mark that holds the maximum of the last half second.
  if (level.readout_peak_dbfs > METER_MIN) {
    g.fillStyle = clipping.now ? ink.red : ink.ink;
    g.fillRect(left - 4, Math.round(y(level.readout_peak_dbfs)) - 1, bar + 8, 2);
  }
  if (level.rms_dbfs > METER_MIN) {
    g.fillStyle = ink.surface;
    g.fillRect(left + 5, Math.round(y(level.rms_dbfs)) - 1, bar - 10, 2);
  }
}
