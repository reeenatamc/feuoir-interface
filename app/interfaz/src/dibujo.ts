// Dibuja un cuadro en los tres canvas. No calcula nada del audio: todo llega hecho desde Python.

import type { Cuadro } from "./contrato";

const DB_MIN = -140;
const DB_MAX = 10; // sobre 0 dBFS: el fundamental de un seno recortado pasa de 0 dBFS
const F_MIN = 20;
const F_MAX = 20000;
const MEDIDOR_MIN = -60;
const AVISO_DBFS = -3;
const FUENTE = '10px "Inter Variable", ui-sans-serif, system-ui, sans-serif';

interface Tinta {
  ink: string;
  surface: string;
  sunken: string;
  naranja: string;
  rojo: string;
}

// Los colores salen de las variables de estilos.css, así el canvas sigue al modo claro u oscuro.
export function leerTinta(): Tinta {
  const css = getComputedStyle(document.documentElement);
  const v = (nombre: string) => css.getPropertyValue(nombre).trim();
  return { ink: v("--ink"), surface: v("--surface"), sunken: v("--surface-sunken"), naranja: v("--fire-orange"), rojo: v("--fire-red") };
}

// canvas no garantiza entender color-mix(), así que la transparencia se arma a mano.
function alfa(hex: string, a: number): string {
  const n = parseInt(hex.replace("#", ""), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}

export function decimal(v: number): string {
  if (v < -120) return "< -120";
  const s = v.toFixed(1);
  if (s === "-0.0") return "0.0";
  return v > 0 && s !== "0.0" ? `+${s}` : s;
}

function frecuenciaTexto(f: number): string {
  return f >= 1000 ? `${(f / 1000).toFixed(3)} kHz` : `${f.toFixed(1)} Hz`;
}

function preparar(canvas: HTMLCanvasElement) {
  const r = canvas.getBoundingClientRect();
  const k = window.devicePixelRatio || 1;
  const ancho = Math.round(r.width * k);
  const alto = Math.round(r.height * k);
  if (canvas.width !== ancho || canvas.height !== alto) {
    canvas.width = ancho;
    canvas.height = alto;
  }
  const g = canvas.getContext("2d")!;
  g.setTransform(k, 0, 0, k, 0, 0);
  g.clearRect(0, 0, r.width, r.height);
  g.font = FUENTE;
  return { g, w: r.width, h: r.height };
}

function lineaHorizontal(g: CanvasRenderingContext2D, x0: number, x1: number, y: number) {
  g.beginPath();
  g.moveTo(x0, Math.round(y) + 0.5);
  g.lineTo(x1, Math.round(y) + 0.5);
  g.stroke();
}

export function dibujarOnda(canvas: HTMLCanvasElement, onda: number[], fs: number, ms: number, t: Tinta) {
  const { g, w, h } = preparar(canvas);
  const izq = 34, der = 8, arr = 8, aba = 22;
  const ancho = w - izq - der, alto = h - arr - aba;
  const y = (v: number) => arr + (alto * (1 - v)) / 2;

  g.lineWidth = 1;
  g.textAlign = "right";
  g.textBaseline = "middle";
  for (const v of [1, 0.5, 0, -0.5, -1]) {
    g.strokeStyle = alfa(t.ink, v === 0 ? 0.14 : 0.06);
    lineaHorizontal(g, izq, izq + ancho, y(v));
    g.fillStyle = alfa(t.ink, 0.45);
    g.fillText(String(v), izq - 10, y(v));
  }
  g.textBaseline = "top";
  for (let m = 0; m <= ms; m += 2) {
    g.textAlign = m === 0 ? "left" : m === ms ? "right" : "center";
    g.fillText(`${m} ms`, izq + (ancho * m) / ms, arr + alto + 8);
  }

  g.strokeStyle = t.ink;
  g.lineWidth = 1.5;
  g.lineJoin = "round";
  g.beginPath();
  onda.forEach((v, i) => {
    const px = izq + (ancho * (i * 1000)) / fs / ms;
    const py = y(Math.max(-1, Math.min(1, v)));
    if (i === 0) g.moveTo(px, py);
    else g.lineTo(px, py);
  });
  g.stroke();
}

export function dibujarEspectro(canvas: HTMLCanvasElement, frecuencias: number[], cuadro: Cuadro, t: Tinta) {
  const { g, w, h } = preparar(canvas);
  const izq = 40, der = 10, arr = 10, aba = 22;
  const ancho = w - izq - der, alto = h - arr - aba;
  const x = (f: number) => izq + (ancho * Math.log(f / F_MIN)) / Math.log(F_MAX / F_MIN);
  const y = (d: number) => arr + (alto * (DB_MAX - Math.max(DB_MIN, Math.min(DB_MAX, d)))) / (DB_MAX - DB_MIN);

  g.lineWidth = 1;
  g.textAlign = "right";
  g.textBaseline = "middle";
  for (let d = 0; d >= DB_MIN; d -= 20) {
    g.strokeStyle = alfa(t.ink, d === 0 ? 0.14 : 0.06);
    lineaHorizontal(g, izq, izq + ancho, y(d));
    g.fillStyle = alfa(t.ink, 0.45);
    g.fillText(String(d), izq - 10, y(d));
  }
  g.textBaseline = "top";
  const marcas: [number, string][] = [[20, "20"], [50, "50"], [100, "100"], [200, "200"], [500, "500"], [1000, "1 k"], [2000, "2 k"], [5000, "5 k"], [10000, "10 k"], [20000, "20 k"]];
  for (const [f, texto] of marcas) {
    const px = Math.round(x(f)) + 0.5;
    g.strokeStyle = alfa(t.ink, 0.06);
    g.beginPath();
    g.moveTo(px, arr);
    g.lineTo(px, arr + alto);
    g.stroke();
    g.textAlign = f === F_MIN ? "left" : f === F_MAX ? "right" : "center";
    g.fillText(texto, px, arr + alto + 8);
  }

  g.strokeStyle = t.ink;
  g.lineWidth = 1.5;
  g.lineJoin = "round";
  g.beginPath();
  cuadro.espectro_dbfs.forEach((d, i) => {
    if (i === 0) g.moveTo(x(frecuencias[i]), y(d));
    else g.lineTo(x(frecuencias[i]), y(d));
  });
  g.stroke();

  const pico = cuadro.pico_espectral;
  if (pico) {
    const px = x(pico.frecuencia_hz), py = y(pico.nivel_dbfs);
    g.fillStyle = t.surface;
    g.beginPath();
    g.arc(px, py, 4.5, 0, 2 * Math.PI);
    g.fill();
    g.strokeStyle = t.ink;
    g.lineWidth = 1.5;
    g.stroke();
    g.font = '500 12px "Inter Variable", ui-sans-serif, system-ui, sans-serif';
    g.fillStyle = t.ink;
    g.textBaseline = "middle";
    const texto = `${frecuenciaTexto(pico.frecuencia_hz)}   ${decimal(pico.nivel_dbfs)} dBFS`;
    const derecha = px + 12 + g.measureText(texto).width < izq + ancho;
    g.textAlign = derecha ? "left" : "right";
    g.fillText(texto, derecha ? px + 12 : px - 12, Math.max(py, arr + 8));
  }
}

export function dibujarMedidor(canvas: HTMLCanvasElement, cuadro: Cuadro, t: Tinta) {
  const { g, h } = preparar(canvas);
  const izq = 34, barra = 20, arr = 6, aba = 6;
  const alto = h - arr - aba;
  const y = (d: number) => arr + (alto * -Math.max(MEDIDOR_MIN, Math.min(0, d))) / -MEDIDOR_MIN;
  const { nivel, saturacion } = cuadro;

  g.textAlign = "right";
  g.textBaseline = "middle";
  g.fillStyle = alfa(t.ink, 0.45);
  for (const d of [0, -6, -12, -24, -36, -48, -60]) g.fillText(String(d), izq - 10, y(d));

  g.fillStyle = t.sunken;
  g.fillRect(izq, arr, barra, alto);
  // Zona de aviso desde -3 dBFS: tenue mientras no satura, roja cuando satura.
  g.fillStyle = saturacion.ahora ? t.rojo : alfa(t.naranja, 0.18);
  g.fillRect(izq, arr, barra, y(AVISO_DBFS) - arr);

  const tope = Math.max(y(nivel.pico_dbfs), y(AVISO_DBFS));
  if (nivel.pico_dbfs > MEDIDOR_MIN) {
    g.fillStyle = t.ink;
    g.fillRect(izq, tope, barra, arr + alto - tope);
  }
  // Pico de lectura: la marca que sostiene el máximo del último medio segundo.
  if (nivel.pico_lectura_dbfs > MEDIDOR_MIN) {
    g.fillStyle = saturacion.ahora ? t.rojo : t.ink;
    g.fillRect(izq - 4, Math.round(y(nivel.pico_lectura_dbfs)) - 1, barra + 8, 2);
  }
  if (nivel.rms_dbfs > MEDIDOR_MIN) {
    g.fillStyle = t.surface;
    g.fillRect(izq + 5, Math.round(y(nivel.rms_dbfs)) - 1, barra - 10, 2);
  }
}
