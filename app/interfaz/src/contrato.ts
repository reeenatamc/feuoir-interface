// Los mensajes del WebSocket, espejo del contrato 1 de app/servidor.py. Si cambia allá, cambia acá.

export const CONTRATO = 1;

export type Forma = "seno" | "barrido" | "ruido" | "silencio";

export interface Senal {
  forma: Forma;
  frecuencia_hz: number;
  nivel_dbfs: number;
}

export interface Estado {
  tipo: "estado";
  contrato: number;
  fs: number;
  entradas: { id: string; nombre: string }[];
  entrada: string;
  senal: Senal;
  frecuencias_hz: number[];
  onda_ms: number;
  mediciones: { id: string; nombre: string }[];
  midiendo: string | null;
}

export interface Cuadro {
  tipo: "cuadro";
  muestras: number;
  onda: number[];
  espectro_dbfs: number[];
  pico_espectral: { frecuencia_hz: number; nivel_dbfs: number } | null;
  nivel: { pico_dbfs: number; pico_lectura_dbfs: number; rms_dbfs: number };
  saturacion: { ahora: boolean; hace_s: number | null; bloques: number };
}

export type AvisoMedicion =
  | { tipo: "medicion"; medicion: string; estado: "en_curso"; mensaje: string }
  | { tipo: "medicion"; medicion: string; estado: "lista"; carpeta: string; ruta: string; resumen: string }
  | { tipo: "medicion"; medicion: string; estado: "error"; mensaje: string };

export type MensajeServidor = Estado | Cuadro | AvisoMedicion | { tipo: "error"; mensaje: string };

export type Pedido =
  | { tipo: "entrada"; id: string }
  | ({ tipo: "senal" } & Senal)
  | { tipo: "medir"; medicion: string }
  | { tipo: "borrar_saturacion" }
  | { tipo: "actualizar_entradas" };
