# Olay Şemaları — Redis pub/sub → WebSocket

**Sahip:** Berat · **Kural: APPEND-ONLY.** Alan silmek veya yeniden adlandırmak üç kişiyi
aynı anda kırar. Yanlış tasarlanmış alanı `deprecated` işaretle, yenisini ekle.

Yayıncı: `services/core` (`core/publisher.py`)
Abone: `services/gateway` (`gateway/ws/bridge.py`) → bağlı WS istemcilerine fan-out
İstemci: `web/src/api/socket.ts`

Kanal adı = olay adı. Tüm zamanlar UTC ISO-8601.

---

## WebSocket zarfı

İstemciye giden her mesaj aynı zarfa sarılır:

```json
{
  "event": "slot.occupied",
  "ts": "2026-10-19T14:32:01Z",
  "data": { }
}
```

---

## slot.occupied

Bir slot dolduğunda.

```json
{
  "slot_id": 42,
  "lot_id": 1,
  "floor_id": 2,
  "slot_code": "K2-018",
  "plate": "01ABC123",
  "session_id": 884,
  "at": "2026-10-19T14:32:01Z"
}
```

## slot.freed

Bir slot boşaldığında.

```json
{
  "slot_id": 42,
  "lot_id": 1,
  "floor_id": 2,
  "slot_code": "K2-018",
  "at": "2026-10-19T16:05:44Z"
}
```

## session.started

Plaka okundu, slot atandı.

```json
{
  "session_id": 884,
  "plate": "01ABC123",
  "slot_id": 42,
  "lot_id": 1,
  "entry_at": "2026-10-19T14:32:01Z"
}
```

## session.closed

Araç çıktı, ücret hesaplandı ve DB'ye yazıldı.

```json
{
  "session_id": 884,
  "plate": "01ABC123",
  "slot_id": 42,
  "lot_id": 1,
  "entry_at": "2026-10-19T14:32:01Z",
  "exit_at": "2026-10-19T16:05:44Z",
  "duration_min": 94,
  "fee_cents": 3290
}
```

## lot.occupancy

Doluluk özeti. Her slot değişiminden sonra yayınlanır — dashboard'un ana beslemesi.

```json
{
  "lot_id": 1,
  "total": 120,
  "occupied": 83,
  "free": 37,
  "occupancy_rate": 0.69,
  "by_floor": [
    {"floor_id": 1, "level": 1, "total": 40, "occupied": 31, "free": 9},
    {"floor_id": 2, "level": 2, "total": 40, "occupied": 29, "free": 11},
    {"floor_id": 3, "level": 3, "total": 40, "occupied": 23, "free": 17}
  ],
  "at": "2026-10-19T16:05:44Z"
}
```

## anpr.read_failed

Plaka okunamadı (simülasyon hata senaryosu). Dashboard'da uyarı olarak gösterilir.

```json
{
  "lot_id": 1,
  "gate": "entry",
  "reason": "low_confidence",
  "confidence": 0.31,
  "at": "2026-10-19T14:31:58Z"
}
```

---

## İstemci davranışı (Esra)

- Bağlantı koparsa üstel geri çekilmeyle yeniden bağlan (1s → 2s → 4s, tavan 30s).
- Yeniden bağlanınca `GET /lots/{id}/occupancy` ile tam durumu çek — ara olaylar kaçmış olabilir.
- Bilinmeyen `event` değerini **sessizce yok say** (append-only kuralı yeni olay ekleyebilir).
