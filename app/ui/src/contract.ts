// WebSocket messages, mirroring contract 4 in app/server.py. If it changes there, it changes here.
// Keys and values the code reads are in English; names, summaries and messages for the user come in Spanish.

export const CONTRACT = 4;

export type Shape = "sine" | "sweep" | "noise" | "silence";

export interface Signal {
  shape: Shape;
  frequency_hz: number;
  level_dbfs: number;
}

export interface State {
  type: "state";
  contract: number;
  sample_rate: number;
  inputs: { id: string; name: string }[];
  input: string;
  outputs: { id: string; name: string }[];
  output: string;
  signal: Signal;
  frequencies_hz: number[];
  waveform_ms: number;
  measurements: { id: string; name: string }[];
  measuring: string | null;
}

export interface Frame {
  type: "frame";
  samples: number;
  waveform: number[];
  spectrum_dbfs: number[];
  spectrum_peak: { frequency_hz: number; level_dbfs: number } | null;
  level: { peak_dbfs: number; readout_peak_dbfs: number; rms_dbfs: number };
  clipping: { now: boolean; seconds_ago: number | null; blocks: number };
}

export type MeasurementUpdate =
  | { type: "measurement"; measurement: string; status: "running"; message: string }
  | { type: "measurement"; measurement: string; status: "done"; folder_name: string; folder: string; path: string; summary: string }
  | { type: "measurement"; measurement: string; status: "error"; message: string };

export interface SavedMeasurement {
  folder: string;
  measurement: string;
  date_time: string;
  input: string | null;
  summary: string;
}

export type ServerMessage =
  | State
  | Frame
  | MeasurementUpdate
  | { type: "saved"; measurements: SavedMeasurement[] }
  | { type: "error"; message: string };

export type Request =
  | { type: "input"; id: string }
  | { type: "output"; id: string }
  | ({ type: "signal" } & Signal)
  | { type: "measure"; measurement: string; notes?: string }
  | { type: "clear_clipping" }
  | { type: "refresh_devices" }
  | { type: "list_saved" }
  | { type: "open_saved"; folder: string | null };
