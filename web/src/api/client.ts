// REST istemcisi. Sahip: Esra.
// USE_MOCK bayrağı gerçeğe geçişi tek satıra indirir (YOL_HARITASI.md §6):
// iş mantığı kodu hiç değişmez, yalnız base URL değişir.

import type { Floor, Lot, Occupancy, Session, TariffRule } from "../types/api";

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";

export const API_URL = USE_MOCK
  ? (import.meta.env.VITE_MOCK_API_URL ?? "http://localhost:8100")
  : (import.meta.env.VITE_API_URL ?? "http://localhost:8000");

async function get<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const url = new URL(path, API_URL);
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined) url.searchParams.set(k, String(v));
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  lots: () => get<Lot[]>("/lots"),
  occupancy: (lotId: number) => get<Occupancy>(`/lots/${lotId}/occupancy`),
  floors: (lotId: number) => get<Floor[]>(`/lots/${lotId}/floors`),
  sessions: (params?: { plate?: string; limit?: number }) => get<Session[]>("/sessions", params),
  tariffs: (lotId = 1) => get<TariffRule[]>("/tariffs", { lot_id: lotId }),
};

export const isMock = USE_MOCK;
