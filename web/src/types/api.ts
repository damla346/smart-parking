// Sözleşme tipleri — contracts/openapi.yaml'ın TS karşılığı. Sahip: Esra.
// İleride openapi-typescript ile otomatik üretilebilir; şimdilik elle.

export type SlotStatus = "free" | "occupied" | "reserved";
export type SlotType = "standard" | "disabled" | "ev" | "large";
export type SessionStatus = "open" | "closed";

export interface Lot {
  id: number;
  name: string;
  address: string;
  total_slots: number;
}

export interface Slot {
  id: number;
  floor_id: number;
  code: string;
  type: SlotType;
  status: SlotStatus;
  plate: string | null;
}

export interface Floor {
  id: number;
  lot_id: number;
  level: number;
  slot_count: number;
  slots: Slot[];
}

export interface FloorOccupancy {
  floor_id: number;
  level: number;
  total: number;
  occupied: number;
  free: number;
}

export interface Occupancy {
  lot_id: number;
  total: number;
  occupied: number;
  free: number;
  occupancy_rate: number;
  by_floor: FloorOccupancy[];
  at: string;
}

export interface Session {
  id: number;
  plate: string;
  lot_id: number;
  slot_id: number;
  slot_code: string;
  entry_at: string;
  exit_at: string | null;
  duration_min: number | null;
  fee_cents: number | null;
  status: SessionStatus;
}

export interface TariffRule {
  id: number;
  lot_id: number;
  from_min: number;
  to_min: number | null;
  price_per_min_cents: number;
}

export interface FeeLine {
  from_min: number;
  to_min: number | null;
  minutes: number;
  price_per_min_cents: number;
  subtotal_cents: number;
}

export interface FeeBreakdown {
  session_id: number;
  plate: string;
  duration_min: number;
  total_cents: number;
  lines: FeeLine[];
}

// contracts/events.md — WS zarfı
export interface WsEnvelope<T = unknown> {
  event: string;
  ts: string;
  data: T;
}
