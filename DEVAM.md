# Devam Notu

Bu dosya, iskeletin kurulduğu oturumdan devralınan bağlamı taşır.
**Yeni bir Claude Code oturumunda önce bunu, sonra `YOL_HARITASI.md`'yi oku.**

Tarih: 2026-10-19 · Durum: iskelet kuruldu, Gün 0 yapılmadı

---

## Bir cümlede

TEKNOFEST şartnamesi md. 35 "Smart Parking Management System" için 3 kişilik
(Esra/Berat/Damla) çakışmasız çalışma yapısı kuruldu; sözleşme-önce mimari,
üç bağımsız servis, gün 0 mock'ları hazır. Ekip henüz başlamadı.

---

## Yapılanlar

- `YOL_HARITASI.md` — 17 bölüm: mimari, görev dağılımı, dizin sahipliği, Gün 0
  planı, sözleşme kuralları, git/CI/Docker kuralları, 4 haftalık takvim, risk tablosu
- `~/smart_parking_ws` altında 86 dosyalık iskelet, tek commit (`e2900a8`)
- `contracts/`: 8 REST ucu, 6 olay şeması, 5 Pydantic modül, 5 fixture, karar günlüğü
- Üç servis + mock'lar + CI + dev compose

## Doğrulananlar (gerçekten koşturuldu)

| Kontrol | Sonuç |
|---|---|
| `services/core` pytest | 23 geçti |
| `services/gateway` pytest | 16 geçti |
| `ruff check .` | temiz |
| Fixture ↔ şema uyumu | 5/5 |
| Mutasyon kontrolü | 5 mutasyonun 5'i yakalandı |

Kurulum sırasında çıkan 3 gerçek hata düzeltildi: plaka doğrulayıcının uzunluk
aralığı üreteçle uyuşmuyordu; `34XY12` test verisi yanlıştı (X, TR plakalarında
kullanılmaz); "sırasız kurallar" testi zayıftı (600 dk senaryosu `break` dalını
tetiklemiyordu, 94 dk eklendi).

## Doğrulanmayanlar

- `web/` hiç çalıştırılmadı — `npm install` yapılmadı, `npm run dev` denenmedi
- Mock sunucular ayağa kaldırılmadı — `fastapi`/`uvicorn` sistemde yok
- Makinede `python3-venv` kurulu değil; testler geçici bir dizine kurulan
  bağımlılıklarla koşturuldu (`sudo apt install python3-venv` gerekiyor)

---

## Karara bağlananlar

**1. Dizin:** `~/smart_parking_ws` (robotaksi_ws'den tamamen ayrı workspace).

**2. Görev dağılımı:** Esra → frontend (`web/`), Berat → iletişim
(`services/gateway/`), Damla → hesap & veri (`services/core/` + dev compose).
Gerekçeler YOL_HARITASI §3.

**3. Docker:** yalnız Postgres + Redis konteynerde, uygulama kodu natif çalışır
(hot-reload). Servis Dockerfile'ları son haftada, her sahibi kendisininkini yazar.

**4. CD yok, CI var:** path-filtreli tek workflow, sahibi Berat.

**5. Python 3.10** hedefleniyor (makinedeki sürüm). `StrEnum` / `datetime.UTC`
kullanılmıyor.

**6. Hazır gelen kod iskelete geri çekilmeyecek** — hız önceliklendirildi.
Karşılığında YOL_HARITASI §17 eklendi: revize gün tablosu + "kod okuma turu"
ritüeli (herkes kendi alanındaki hazır kodu okuyup diğerlerine anlatır).

---

## Sıradaki adım: Gün 0

1. `sudo apt install python3-venv`, sonra `pip install fastapi uvicorn` ile
   mock'ları ayağa kaldırıp doğrula; `cd web && npm install && npm run dev`
2. **Sözleşme oturumu** (üçü birlikte): `contracts/` zaten dolu olduğu için
   3 saat yerine ~1 saat — gözden geçirip onaylamak yeterli
3. **Kod okuma turu** (45 dk, YOL_HARITASI §17)
4. GitHub deposu aç, `CODEOWNERS`'daki `@esra`/`@berat`/`@damla` yerine gerçek
   kullanıcı adlarını yaz, `main`'e branch protection koy

---

## Açık uçlar

- `contracts/DECISIONS.md`'de "mükerrer giriş" varsayımı henüz karara bağlanmadı
- `CODEOWNERS` placeholder kullanıcı adları içeriyor
- Havuz görevlerinin hiçbiri çekilmedi (`BACKLOG.md`)
