// Conecta con Python, guarda el último estado y el último cuadro, y dibuja al ritmo de la pantalla.
// Los cuadros llegan hasta 30 veces por segundo; se dibuja solo cuando llegó uno nuevo.

import "./estilos.css";
import { CONTRATO, type AvisoMedicion, type Cuadro, type Estado, type MensajeServidor, type Pedido } from "./contrato";
import { decimal, dibujarEspectro, dibujarMedidor, dibujarOnda, leerTinta } from "./dibujo";
import { crearMenus } from "./menus";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const LECTURAS_CADA_MS = 200; // las cifras cambian más lento que la barra, para que se alcancen a leer

let socket: WebSocket | null = null;
let estado: Estado | null = null;
let cuadro: Cuadro | null = null;
let dibujado: Cuadro | null = null;
let redibujar = false;
let tinta = leerTinta();
let ultimaLectura = 0;

function enviar(pedido: Pedido) {
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(pedido));
}

const menus = crearMenus(enviar);

function avisar(html: string, tipo: "normal" | "error" = "normal") {
  const aviso = $("aviso-medicion");
  aviso.innerHTML = html;
  if (tipo === "error") aviso.dataset.estado = "error";
  else delete aviso.dataset.estado;
}

const escapar = (texto: string) =>
  texto.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

function conectar() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  socket = ws;
  ws.onmessage = (e) => recibir(JSON.parse(e.data) as MensajeServidor);
  ws.onclose = () => {
    const conexion = $("conexion");
    conexion.textContent = "Sin conexión";
    conexion.dataset.estado = "caida";
    window.setTimeout(conectar, 1000);
  };
}

function recibir(m: MensajeServidor) {
  switch (m.tipo) {
    case "estado":
      if (m.contrato !== CONTRATO) {
        avisar(`La interfaz habla el contrato ${CONTRATO} y Python el ${m.contrato}. Hay que compilarla de nuevo.`, "error");
      }
      estado = m;
      redibujar = true;
      menus.actualizar(m);
      actualizarBotones(m);
      $("nota-onda").textContent = `Últimos ${m.onda_ms} ms`;
      $("conexion").textContent = `${m.fs / 1000} kHz`;
      delete $("conexion").dataset.estado;
      break;
    case "cuadro":
      cuadro = m;
      actualizarSaturacion(m);
      break;
    case "medicion":
      avisarMedicion(m);
      break;
    case "error":
      avisar(escapar(m.mensaje), "error");
      break;
  }
}

function actualizarBotones(e: Estado) {
  const botones = $("botones");
  if (botones.childElementCount !== e.mediciones.length) {
    botones.replaceChildren(
      ...e.mediciones.map((medicion) => {
        const boton = document.createElement("button");
        boton.className = "boton-medir";
        boton.dataset.medicion = medicion.id;
        boton.textContent = medicion.nombre;
        boton.addEventListener("click", () => enviar({ tipo: "medir", medicion: medicion.id }));
        return boton;
      }),
    );
  }
  for (const boton of botones.querySelectorAll<HTMLButtonElement>(".boton-medir")) {
    boton.disabled = e.midiendo !== null;
    if (boton.dataset.medicion === e.midiendo) boton.dataset.midiendo = "";
    else delete boton.dataset.midiendo;
  }
}

function avisarMedicion(m: AvisoMedicion) {
  const nombre = estado?.mediciones.find((x) => x.id === m.medicion)?.nombre ?? m.medicion;
  $("aviso-medicion").title = m.estado === "lista" ? m.ruta : "";
  if (m.estado === "en_curso") avisar(`${escapar(nombre)}: ${escapar(m.mensaje)}`);
  else if (m.estado === "lista") avisar(`Guardado en <strong>${escapar(m.carpeta)}</strong><br>${escapar(m.resumen)}`);
  else avisar(`${escapar(nombre)} no terminó: ${escapar(m.mensaje)}`, "error");
}

function tiempo(s: number) {
  if (s < 60) return `${Math.floor(s)} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min`;
  return `${Math.floor(s / 3600)} h`;
}

function actualizarSaturacion(c: Cuadro) {
  const caja = $("saturacion");
  const texto = $("saturacion-texto");
  const { ahora, hace_s, bloques } = c.saturacion;
  let nuevo = "Sin saturación en esta sesión";
  if (ahora) {
    nuevo = "Saturando ahora";
    caja.dataset.estado = "ahora";
  } else if (bloques > 0 && hace_s !== null) {
    nuevo = `Saturó hace ${tiempo(hace_s)}, ${bloques} ${bloques === 1 ? "bloque" : "bloques"} en esta sesión`;
    caja.dataset.estado = "antes";
  } else {
    delete caja.dataset.estado;
  }
  if (texto.textContent !== nuevo) texto.textContent = nuevo;
  $("borrar-saturacion").hidden = ahora || bloques === 0;
}

$("borrar-saturacion").addEventListener("click", () => enviar({ tipo: "borrar_saturacion" }));
window.addEventListener("resize", () => (redibujar = true));
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  tinta = leerTinta();
  redibujar = true;
});

function dibujar(t: number) {
  if (estado && cuadro && (cuadro !== dibujado || redibujar)) {
    dibujarOnda($<HTMLCanvasElement>("onda"), cuadro.onda, estado.fs, estado.onda_ms, tinta);
    dibujarEspectro($<HTMLCanvasElement>("espectro"), estado.frecuencias_hz, cuadro, tinta);
    dibujarMedidor($<HTMLCanvasElement>("medidor"), cuadro, tinta);
    dibujado = cuadro;
    redibujar = false;
    if (t - ultimaLectura >= LECTURAS_CADA_MS) {
      // En las cifras grandes va el signo menos tipográfico: tiene el ancho de un dígito.
      $("lectura-pico").textContent = decimal(cuadro.nivel.pico_lectura_dbfs).replace("-", "−");
      $("lectura-rms").textContent = decimal(cuadro.nivel.rms_dbfs).replace("-", "−");
      ultimaLectura = t;
    }
  }
  requestAnimationFrame(dibujar);
}

conectar();
requestAnimationFrame(dibujar);
