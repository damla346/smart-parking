// ★ WebSocket istemcisi. Sahip: Esra.
// Sözleşme: contracts/events.md
//
// İki kural oradan geliyor:
//  1) Kopunca üstel geri çekilmeyle yeniden bağlan (1s → 2s → 4s, tavan 30s).
//  2) Yeniden bağlanınca tam durumu REST'ten çek — ara olaylar kaçmış olabilir.
//  3) Bilinmeyen event'i SESSİZCE yok say (append-only kuralı yeni olay ekleyebilir).

import type { WsEnvelope } from "../types/api";

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";

const WS_URL = USE_MOCK
  ? (import.meta.env.VITE_MOCK_WS_URL ?? "ws://localhost:8100/ws/occupancy")
  : (import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws/occupancy");

type Handler = (envelope: WsEnvelope) => void;
type StatusHandler = (connected: boolean) => void;

export class OccupancySocket {
  private ws: WebSocket | null = null;
  private handlers = new Set<Handler>();
  private statusHandlers = new Set<StatusHandler>();
  private retry = 0;
  private timer: number | null = null;
  private closedByUs = false;

  connect(): void {
    this.closedByUs = false;
    this.ws = new WebSocket(WS_URL);

    this.ws.onopen = () => {
      this.retry = 0;
      this.statusHandlers.forEach((h) => h(true));
    };

    this.ws.onmessage = (ev) => {
      let envelope: WsEnvelope;
      try {
        envelope = JSON.parse(ev.data as string) as WsEnvelope;
      } catch {
        return; // bozuk mesaj akışı durdurmaz
      }
      this.handlers.forEach((h) => h(envelope));
    };

    this.ws.onclose = () => {
      this.statusHandlers.forEach((h) => h(false));
      if (!this.closedByUs) this.scheduleReconnect();
    };

    this.ws.onerror = () => this.ws?.close();
  }

  private scheduleReconnect(): void {
    const delay = Math.min(1000 * 2 ** this.retry, 30_000);
    this.retry += 1;
    this.timer = window.setTimeout(() => this.connect(), delay);
  }

  on(handler: Handler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  onStatus(handler: StatusHandler): () => void {
    this.statusHandlers.add(handler);
    return () => this.statusHandlers.delete(handler);
  }

  close(): void {
    this.closedByUs = true;
    if (this.timer !== null) window.clearTimeout(this.timer);
    this.ws?.close();
  }
}

export const socket = new OccupancySocket();
