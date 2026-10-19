# Smart Parking Management System

Otopark kat/slot doluluğunun anlık takibi, plaka tanıma simülasyonu ile giriş-çıkış ve
kademeli dakikalık tarifeye göre ücret hesaplama sistemi.

**Ekip:** Esra (Frontend) · Berat (İletişim) · Damla (Hesap & Veri)
**Yol haritası ve görev dağılımı:** [YOL_HARITASI.md](YOL_HARITASI.md)
**Havuz görevleri:** [BACKLOG.md](BACKLOG.md)

---

## Hızlı başlangıç

```bash
cp .env.example .env
docker compose up -d          # postgres + redis
make install                  # üç paketin bağımlılıkları
make mocks                    # mock_core:8101 + mock_gateway:8100
```

`USE_MOCK=true` iken herkes sahte servislere karşı çalışır, kimse kimseyi beklemez.
Detay: YOL_HARITASI.md §6.

---

## Esra — Frontend

```bash
cd web && npm install && npm run dev        # http://localhost:5173
```

`.env` içinde `VITE_USE_MOCK=true` iken `mock_gateway` (:8100), `false` iken gerçek
gateway (:8000) kullanılır. Sadece `contracts/openapi.yaml` ve `contracts/events.md`
dosyalarına bakılır.

<!-- Esra: kendi notlarını buraya ekle -->

---

## Berat — İletişim

```bash
cd services/gateway && pip install -e . && uvicorn gateway.main:app --reload --port 8000
```

`core`'a doğrudan DB erişimi yoktur, `clients/core_client.py` üzerinden HTTP ile sorar.
`USE_MOCK=true` iken `mock_core` (:8101) hedeflenir.

<!-- Berat: kendi notlarını buraya ekle -->

---

## Damla — Hesap & Veri

```bash
docker compose up -d
cd services/core && pip install -e .
alembic upgrade head
uvicorn core.main:app --reload --port 8001
```

Tarife motoru: `services/core/core/domain/pricing.py` — saf fonksiyon, DB'siz test edilir.

```bash
cd services/core && pytest tests/test_pricing.py -v
```

<!-- Damla: kendi notlarını buraya ekle -->
