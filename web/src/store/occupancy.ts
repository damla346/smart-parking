// Canlı doluluk state'i. Sahip: Esra.
// İSKELET — Hafta 1'de Dashboard ile birlikte doldurulacak.

import { useEffect, useState } from "react";

import { api } from "../api/client";
import { socket } from "../api/socket";
import type { Occupancy, WsEnvelope } from "../types/api";

export function useOccupancy(lotId: number) {
  const [data, setData] = useState<Occupancy | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // İlk tam durum REST'ten; sonrası WS olaylarıyla güncellenir.
    api.occupancy(lotId).then(setData).catch((e: Error) => setError(e.message));

    const offStatus = socket.onStatus((c) => {
      setConnected(c);
      // Yeniden bağlanınca tam durumu tazele — ara olaylar kaçmış olabilir (events.md)
      if (c) api.occupancy(lotId).then(setData).catch(() => undefined);
    });

    const off = socket.on((env: WsEnvelope) => {
      if (env.event === "lot.occupancy") {
        const payload = env.data as Occupancy;
        if (payload.lot_id === lotId) setData(payload);
      }
      // Bilinmeyen event sessizce yok sayılır (append-only kuralı)
    });

    socket.connect();
    return () => {
      off();
      offStatus();
      socket.close();
    };
  }, [lotId]);

  return { data, connected, error };
}
