# Smart Parking Management System — Yol Haritası

**Ekip:** Esra (Frontend) · Berat (İletişim) · Damla (Hesap & Veri)
**Tarih:** 2026-10-19
**Şartname maddesi:** 35 — Smart Parking Management System

> Otoparklardaki kat ve boş slotların anlık takip edildiği, plaka tanıma simülasyonu ile
> giriş-çıkış ve ücret hesaplanan sistem. Otopark doluluk durumlarının WebSockets ile anlık
> olarak güncellenmesi, plaka giriş saatine göre dakikalık kademeli ücret tarifesi hesaplama
> motorunun veritabanına entegre edilmesi gerekir.

---

## 1. Temel ilke: kimse kimseyi beklemez

Bu projenin tüm yapısı tek bir cümleye dayanıyor:

> **Kimse başkasının kodunu çağırmaz. Herkes sözleşmeyi (`contracts/`) çağırır.**

Bunun üç sonucu var:

1. Üçümüz de birbirimizin kodu hiç hazır olmadan kendi kısmımızı tamamen yazıp test edebiliriz.
2. Çakışma yüzeyi birkaç dosyaya iner, çünkü kimse başkasının dizinine girmez.
3. Entegrasyon "son hafta yapılan korkunç iş" olmaktan çıkar, haftalık 1 saatlik rutine döner.

Gün 0'dan sonra tek senkron nokta **haftada 1 saat** (Cuma entegrasyon seansı). Geri kalan tüm
zaman tam bağımsız çalışmadır.

---

## 2. Mimari

```
                 ┌──────────────────────────────┐
   Tarayıcı ──── │  web/           (Esra)       │
                 │  React + Vite + TS           │
                 └───────┬──────────────┬───────┘
                      REST            WebSocket
                         │              │
                 ┌───────▼──────────────▼───────┐
                 │  services/gateway/  (Berat)  │   ← dışa bakan TEK servis
                 │  REST API · WS sunucu        │
                 │  ANPR simülasyonu            │
                 │  giriş/çıkış akışı           │
                 └───────┬──────────────▲───────┘
                    HTTP │              │ Redis pub/sub
                         │              │
                 ┌───────▼──────────────┴───────┐
                 │  services/core/     (Damla)  │   ← dışa kapalı
                 │  DB domain · doluluk         │
                 │  TARİFE MOTORU · ücret       │
                 └───────┬──────────────────────┘
                         │
                 ┌───────▼───────┐   ┌───────────┐
                 │  PostgreSQL   │   │   Redis   │
                 └───────────────┘   └───────────┘
```

### Yönlü kurallar (ihlal edilmez)

| Kural | Sebep |
|---|---|
| `web/` sadece `gateway`'i tanır | Esra ile Damla'nın hiç teması olmaz |
| `gateway` DB'ye **asla** yazmaz/okumaz | Aynı tabloya iki yerden yazma kaosu olmaz |
| `core` dışarıya HTTP sunmaz (sadece Docker ağı içi) | Veri sahipliği tek noktada |
| `core` dış dünyaya sadece **Redis olayı** basar | Servisler gevşek bağlı kalır |

---

## 3. Ekip ve sorumluluklar

### 🎨 Esra — Frontend

**Dizin:** `web/`
**Şartnamedeki karşılığı:** "doluluk durumlarının anlık olarak güncellenmesi" (istemci tarafı)

| İş | Açıklama | Gün |
|---|---|--:|
| Proje kurulumu | Vite + TypeScript + TailwindCSS | 1 |
| Layout + tasarım sistemi | Sayfa iskeleti, navigasyon, renk/tipografi | 2 |
| Dashboard | Canlı doluluk: toplam/dolu/boş, kat kırılımı, gauge | 3 |
| FloorPlan | Kat seçimi + slot ızgarası, renk kodlu durum | 3 |
| SessionLog | Giriş-çıkış kayıtları tablosu, plaka arama, tarih filtresi | 2 |
| WS istemcisi | Bağlanma, otomatik yeniden bağlanma, bağlantı rozeti | 2 |
| Responsive + cila | Mobil/tablet uyumu, boş durum ve hata ekranları | 2 |
| `web/Dockerfile` | Son hafta, kendi servisinin paketlenmesi | 0.3 |
| **Çekirdek toplam** | | **15.3** |

**Esra hiç DB bilmez, hiç Python yazmaz.** Sadece `contracts/openapi.yaml` ve
`contracts/events.md` dosyalarına bakar.

---

### 🔌 Berat — İletişim

**Dizin:** `services/gateway/`
**Şartnamedeki karşılığı:** "plaka tanıma simülasyonu ile giriş-çıkış", "WebSockets ile anlık güncelleme" (sunucu tarafı)

| İş | Açıklama | Gün |
|---|---|--:|
| FastAPI iskelet | Config, logging, sağlık uçları | 1 |
| REST endpoint seti | `/lots`, `/lots/{id}/occupancy`, `/sessions`, `/tariffs` (core'a proxy) | 3 |
| WS sunucu + fan-out | `/ws/occupancy`, bağlantı havuzu, yayın yönetimi | 3 |
| Redis olay altyapısı | Subscribe → WS köprüsü, yeniden bağlanma | 2 |
| **ANPR simülasyonu** | Rastgele TR plaka üreteci, okuma gecikmesi, hata senaryoları | 3 |
| Giriş/çıkış akışı | Plaka okundu → slot ata → çıkışta core'dan ücret iste | 3 |
| CI workflow | `.github/workflows/ci.yml` | 0.5 |
| `gateway/Dockerfile` | Son hafta | 0.3 |
| **Çekirdek toplam** | | **15.8** |

**Berat DB'ye hiç dokunmaz.** Veriye ihtiyacı olduğunda `core`'a HTTP ile sorar.

---

### 🧮 Damla — Hesap & Veri

**Dizin:** `services/core/` + `docker-compose.yml`
**Şartnamedeki karşılığı:** "kat ve boş slotların anlık takibi", "dakikalık kademeli ücret tarifesi hesaplama motorunun veritabanına entegre edilmesi"

| İş | Açıklama | Gün |
|---|---|--:|
| dev `docker-compose.yml` | Postgres + Redis konteynerleri, `.env.example`, `Makefile` | 1 |
| Şema + migration'lar | SQLAlchemy modelleri + Alembic (tek sahip = sıfır çakışma) | 2 |
| Domain CRUD | Otopark / kat / slot yönetimi | 3 |
| Doluluk + olay yayını | Doluluk hesabı, Redis'e `slot.*` ve `lot.occupancy` olayları | 2 |
| **Tarife motoru** | Kademeli dakikalık ücret — saf fonksiyon, DB'siz test edilir | 3 |
| Ücret + ödeme kaydı | Oturum kapanınca ücreti hesapla ve DB'ye yaz | 2 |
| Birim testler | Özellikle `test_pricing.py` parametrik | 2 |
| `core/Dockerfile` | Son hafta | 0.3 |
| **Çekirdek toplam** | | **15.3** |

**Damla kimseye bağlı değil** — zincirin en altında. Dışarıya sadece olay basar.

---

### Tarife motoru — projenin kalbi

```python
def hesapla_ucret(giris: datetime, cikis: datetime, kurallar: list[TariffRule]) -> FeeBreakdown
```

Saf fonksiyon: DB yok, zaman yok, yan etki yok. Bu yüzden 20 satırlık parametrik testle
tamamen doğrulanabilir. Kademeler `tariff_rules` tablosundan okunur:

| from_min | to_min | price_per_min_cents |
|---:|---:|---:|
| 0 | 30 | 0 (ilk yarım saat ücretsiz) |
| 30 | 120 | 50 |
| 120 | 480 | 35 |
| 480 | NULL | 20 |

Test edilecek uç durumlar: 0 dakika · tam sınırda çıkış (30. dk) · gece yarısını aşan oturum ·
tek kademeyi aşan oturum · boş kural listesi · açık uçlu son kademe.

---

## 4. Dizin yapısı ve sahiplik

`[E]` Esra · `[B]` Berat · `[D]` Damla · `[*]` Ortak

```
smart_parking_ws/
│
├── YOL_HARITASI.md                 [*]  bu dosya
├── BACKLOG.md                      [*]  havuz görevleri (bkz. §10)
├── README.md                       [*]  üç ayrı bölüm, her bölüm sahibinde
├── docker-compose.yml              [D]  postgres + redis (dev)
├── docker-compose.prod.yml         [B]  son hafta, üç servisi birleştirir
├── .env.example                    [D]
├── Makefile                        [D]  make up / test / seed
├── .gitignore                      [D]
├── ruff.toml                       [B]  ortak lint ayarı (dar tutuldu, §9)
├── CODEOWNERS                      [*]
│
├── contracts/                      ── SÖZLEŞME · append-only
│   ├── openapi.yaml                [B]  REST sözleşmesi
│   ├── events.md                   [B]  Redis + WS olay şemaları
│   ├── DECISIONS.md                [*]  varsayım günlüğü (bkz. §7)
│   ├── schemas/                    [D]  paylaşılan Pydantic modelleri
│   │   ├── lot.py                       Lot, Floor, Slot, SlotStatus
│   │   ├── session.py                   Session, PlateRead
│   │   ├── billing.py                   TariffRule, FeeBreakdown, Payment
│   │   └── events.py                    SlotOccupied, SessionClosed, LotOccupancy
│   └── fixtures/                   [E]  örnek yanıtlar — tek doğru kaynak
│       ├── lots.json
│       ├── floors.json
│       ├── occupancy.json
│       ├── sessions.json
│       └── tariffs.json
│
├── services/
│   ├── core/                       ══ DAMLA
│   │   ├── pyproject.toml · Dockerfile · alembic.ini
│   │   ├── migrations/versions/
│   │   ├── core/
│   │   │   ├── main.py             iç servis, portu dışarı açılmaz
│   │   │   ├── db.py
│   │   │   ├── models/             lot.py · session.py · billing.py
│   │   │   ├── domain/
│   │   │   │   ├── occupancy.py    doluluk hesabı
│   │   │   │   └── pricing.py      ★ TARİFE MOTORU
│   │   │   ├── api/                CRUD router'ları
│   │   │   ├── reports.py          gelir raporu sorguları (havuz)
│   │   │   └── publisher.py        Redis'e olay basar
│   │   └── tests/
│   │       ├── test_pricing.py     ★ parametrik, DB'siz
│   │       ├── test_contracts.py   ★ fixture ↔ şema tutarlılığı (CI'ın kalbi)
│   │       ├── test_occupancy.py
│   │       └── test_migrations.py
│   │
│   └── gateway/                    ══ BERAT
│       ├── pyproject.toml · Dockerfile
│       ├── gateway/
│       │   ├── main.py             dışa bakan TEK servis
│       │   ├── api/                lots.py · sessions.py · tariffs.py
│       │   ├── ws/
│       │   │   ├── server.py       ★ /ws/occupancy
│       │   │   ├── manager.py      bağlantı havuzu
│       │   │   └── bridge.py       Redis subscribe → WS yayını
│       │   ├── anpr/
│       │   │   ├── simulator.py    ★ PLAKA TANIMA SİMÜLASYONU
│       │   │   ├── plate_gen.py    rastgele TR plaka
│       │   │   └── scenarios.py    okunamadı · mükerrer · hayalet okuma
│       │   ├── flow/session_flow.py
│       │   └── clients/core_client.py
│       └── tests/                  test_ws.py · test_anpr.py · test_session_flow.py
│
├── web/                            ══ ESRA
│   ├── package.json · vite.config.ts · tailwind.config.js · Dockerfile
│   └── src/
│       ├── main.tsx · App.tsx
│       ├── api/
│       │   ├── client.ts           REST istemcisi (USE_MOCK bayrağını okur)
│       │   └── socket.ts           ★ WS istemcisi + reconnect
│       ├── store/occupancy.ts      canlı state
│       ├── types/                  openapi.yaml'dan üretilir
│       ├── pages/
│       │   ├── Dashboard.tsx · FloorPlan.tsx · SessionLog.tsx
│       │   └── Tariffs.tsx · Reports.tsx          (havuz)
│       └── components/
│           ├── SlotGrid.tsx · OccupancyGauge.tsx · LiveBadge.tsx
│
├── infra/
│   ├── mocks/
│   │   ├── mock_core.py            [D]  Damla kendi sahtesini yazar
│   │   └── mock_gateway.py         [B]  Berat kendi sahtesini yazar
│   ├── seed/seed_data.py           [havuz]
│   └── postgres/init.sql           [D]
│
├── tests/e2e/test_full_flow.py     [havuz]
│
└── .github/
    ├── workflows/ci.yml            [B]
    └── pull_request_template.md    [*]
```

### Ortak dosyaların sahipliği

Çakışma sadece iki kişinin aynı dosyaya dokunmasından çıkar. Projede böyle **7 dosya** var,
hepsinin tek sahibi belli:

| Dosya | Sahip | Kural |
|---|---|---|
| `contracts/openapi.yaml` | Berat | Değişiklik = ayrı PR, 3 onay, başka değişiklik içermez |
| `contracts/events.md` | Berat | Aynı kural, **sadece ekleme** |
| `contracts/schemas/*.py` | Damla | DB şemasının yansıması |
| `contracts/fixtures/*.json` | Esra | Hem mock hem gerçek bunu döndürmek zorunda |
| `docker-compose.yml`, `.env.example`, `Makefile` | Damla | Servis eklenecekse issue açılır |
| `.github/workflows/ci.yml` | Berat | İçerik sahibinin isteğiyle güncellenir |
| `README.md` | Üçü | Üç ayrı bölüm, aralarda boş satır bırakılır |

Bunların dışındaki **her dosyanın tek sahibi var** → çakışma teknik olarak imkânsız.

---

## 5. Gün 0 — projenin tek senkron günü

Bu gün bittiğinde üçümüz haftalarca birbirimize hiç bakmadan çalışabiliriz.

### Sabah (3 saat) — Sözleşme Oturumu · üçü birlikte

Kod yazılmaz. Sadece `contracts/` doldurulur.

**Karara bağlanacaklar:**

```
Veri modeli
  lots(id, name, address)
  floors(id, lot_id, level, slot_count)
  slots(id, floor_id, code, type, status)        status: free|occupied|reserved
  sessions(id, plate, slot_id, entry_at, exit_at, fee_cents, status)
  tariff_rules(id, lot_id, from_min, to_min, price_per_min_cents)
  payments(id, session_id, amount_cents, paid_at, method)

Olay şeması (Redis → WS)
  slot.occupied     {slot_id, lot_id, floor_id, plate, at}
  slot.freed        {slot_id, lot_id, floor_id, at}
  session.started   {session_id, plate, slot_id, entry_at}
  session.closed    {session_id, plate, duration_min, fee_cents, exit_at}
  lot.occupancy     {lot_id, total, occupied, free, by_floor:[...]}

REST uçları
  GET  /lots
  GET  /lots/{id}/occupancy
  GET  /lots/{id}/floors
  POST /entry            {plate}            → session.started
  POST /exit             {plate}            → session.closed + fee
  GET  /sessions         ?plate=&from=&to=
  GET  /tariffs          ?lot_id=
  WS   /ws/occupancy
```

### Öğleden sonra (2 saat) — Herkes KENDİ sahtesini yazar

| Kim | Dosya | İçerik |
|---|---|---|
| Damla | `infra/mocks/mock_core.py` | Sabit JSON: 2 otopark, 3 kat, 120 slot, tarife, sahte ücret |
| Berat | `infra/mocks/mock_gateway.py` | Sabit REST yanıtları + 2 sn'de bir sahte WS olayı |
| Esra | `contracts/fixtures/*.json` | Mock'ların döndüreceği örnek yanıtlar |

> **Neden herkes kendi sahtesini yazıyor?** "Berat benim mock'umu yazsın da başlayayım"
> diye bir bekleme doğmasın diye. Her biri 1 saatlik iş — içinde mantık yok, sabit JSON.

### Akşam

Herkes kendi dalını açar. **Bu andan sonra kimse kimseyi beklemez.**

### Gün 0 sonrası bağımlılık grafiği

```
Esra   →  mock_gateway (sahte)     ← gerçek gateway'i beklemez
Berat  →  mock_core    (sahte)     ← gerçek core'u ve DB'yi beklemez
Damla  →  (hiçbir şey)             ← zincirin en altında
```

Üç ok da sahteye gidiyor. Gerçek servisler arasında **hiç ok yok.**

---

## 6. USE_MOCK mekanizması

`.env` dosyasında tek bayrak:

```bash
USE_MOCK=true    # günlük geliştirme — herkes sahteye karşı çalışır
USE_MOCK=false   # Cuma entegrasyon seansı — gerçekler konuşur
```

- Esra'nın `api/client.ts`'i bu bayrağa göre base URL seçer.
- Berat'ın `clients/core_client.py`'si aynı şekilde.
- **Gerçeğe geçiş = base URL değişimi.** Hiçbir iş mantığı kodu değişmez.

Fixture'lar tek doğru kaynak olduğu için mock ve gerçek aynı şeyi döndürmek zorunda; CI bunu
doğrular.

---

## 7. Sözleşme kuralları

**1. Append-only.** Alan silmek veya yeniden adlandırmak üç kişiyi aynı anda kırar — projedeki
tek gerçek bekleme sebebi budur. Yanlış tasarlanmış alanı `deprecated` işaretle, yenisini ekle,
projenin sonunda temizle.

**2. İhtiyacın olan alanı sen eklersin, izin istemezsin.** Esra raporda `occupancy_rate` istiyor
ama sözleşmede yok → kendisi `contracts/`'a ekler, kendi fixture'ında döndürür, Berat'a haber
verir. Berat müsait olduğunda gerçeğini yazar. Ekleme olduğu için kimse kırılmaz.

**3. Bekleme — varsay ve not düş.** Tasarım kararı gerektiren bir soru çıktığında
(ör. "aynı plaka iki kez giriş yaparsa ne olur?") `contracts/DECISIONS.md`'ye yaz:

```markdown
## 2026-10-23 · Mükerrer giriş
Varsayım: aynı plaka açık oturumu varken tekrar giriş yaparsa eskisi otomatik kapanır.
Yazan: Berat · Durum: doğrulanacak
```

Kendi tarafını o varsayımla yaz, Cuma seansında 2 dakikada karara bağlanır. Yanlış çıkarsa
düzeltmesi 20 dakika; beklemek ise 2 gün.

---

## 8. Git kuralları

| Kural | Neden |
|---|---|
| `main`'e doğrudan push **kapalı**, PR zorunlu | Sahiplik sınırlarını makine korur |
| `CODEOWNERS` ile otomatik reviewer | Yanlışlıkla başkasının alanına girmek imkânsızlaşır |
| Dal ömrü **≤ 2 gün** | Uzun dal = büyük diff = çakışma |
| `git pull --rebase` | Düz geçmiş, tekil çakışma çözümü |
| Dal adları: `feat/...`, `fix/...`, `docs/...` | |
| `develop` dalı **kurulmaz** | 3 kişilik projede en büyük merge acısı kaynağı |
| Bağımlılık eklerken gruba haber | `package-lock` / `poetry.lock` çakışması önlenir |
| `__pycache__`, `node_modules`, `dist/` → `.gitignore` | |

### CODEOWNERS

```
/web/                 @esra
/contracts/fixtures/  @esra
/services/gateway/    @berat
/contracts/openapi.yaml  @berat
/contracts/events.md     @berat
/.github/             @berat
/services/core/       @damla
/contracts/schemas/   @damla
/docker-compose.yml   @damla
/infra/               @damla
```

---

## 9. CI (CD yok)

**CD kurulmuyor.** Otomatik deploy, secrets yönetimi, ortam ayrımı bu projede hiçbir şey
kazandırmaz, 2-3 gün yer. Teslim anında `docker compose up` yeterli.

**CI kuruluyor** çünkü "çakışmasız, kolay birleşen yapı" hedefinin fiili uygulayıcısı o.
Sahiplik sınırlarını insan disiplini değil makine korur.

`.github/workflows/ci.yml` — tek dosya, ~40 satır, path-filtreli:

| Job | Tetikleyici | Adımlar |
|---|---|---|
| `core` | `services/core/**` veya `contracts/**` | ruff · pytest |
| `gateway` | `services/gateway/**` veya `contracts/**` | ruff · pytest |
| `web` | `web/**` veya `contracts/**` | npm ci · tsc --noEmit · build |

**Üç tasarım kararı:**
- Path filter şart — Esra bir CSS değiştirdiğinde backend testleri koşmasın, yoksa herkes
  her PR'da 5 dakika bekler ve CI'dan nefret eder.
- `contracts/` değişikliği **üçünü birden** tetikler. CI'ın asıl varlık sebebi bu.
- Başta DB gerekmesin; `test_pricing.py` saf fonksiyon testidir. Postgres gerektiren testler
  2. haftaya bırakılır.

**Ne zaman kurulur:** Gün 2-3. Erken kurulmazsa hiç kurulmaz — proje ortasında eklenince
40 kırmızı test birikmiş olur ve kimse düzeltmek istemez.

**İçerik:** `ruff check` + `pytest` + `tsc --noEmit`. Coverage eşiği, mutation testing,
güvenlik taraması **yok** — gürültü yaparsa ekip CI'ı görmezden gelmeye başlar.

**Python sürümü: 3.10** (Ubuntu 22.04 varsayılanı). `StrEnum` ve `datetime.UTC` 3.11+
özellikleri olduğu için kullanılmıyor; yerine `(str, Enum)` ve `timezone.utc`.

---

## 10. Docker

| Aşama | Kapsam | Sahip |
|---|---|---|
| Gün 0 → son hafta | Sadece `postgres` + `redis` konteyner. **Kod natif çalışır**, hot-reload açık | Damla |
| Son hafta | Her servis **kendi** Dockerfile'ını yazar + `docker-compose.prod.yml` | Esra / Berat / Damla, birleştirme Berat |

**Neden kod natif çalışıyor:** Docker içinde hot-reload bozulur, debugger bağlamak zorlaşır,
her bağımlılık eklemede imaj yeniden build olur. Geliştirme döngüsü 1 saniyeden 30 saniyeye
çıkar. Buna karşılık Postgres/Redis'i konteynerde tutmanın maliyeti sıfır (hazır imaj) ve
getirisi yüksek (sürüm tutarlılığı, `docker compose down -v` ile tek komutluk sıfırlama).

**Neden herkes kendi Dockerfile'ını yazıyor:** `web/` için Dockerfile yazmak node sürümünü,
build komutunu, çıktı dizinini bilmeyi gerektirir. Başkasının alanı hakkında bilgi gerektiren
iş = sınır ihlali. Kendi servisini en iyi sahibi bilir, 1-2 saatlik iştir.

### Günlük komutlar

```bash
docker compose up -d                       # postgres + redis
make seed                                  # demo verisi yükle
uvicorn core.main:app --reload             # Damla
uvicorn gateway.main:app --reload          # Berat
npm run dev                                # Esra
docker compose down -v                     # DB'yi sıfırla
```

---

## 11. Havuz (BACKLOG) — denge nasıl korunuyor

Çekirdek görevler neredeyse eşit: **Esra 15.3 · Berat 15.8 · Damla 15.3** gün.

Ama bu tahminlerin gerçek hata payı ±%30. Bu yüzden kalan işler **kimseye atanmıyor** —
havuzda duruyor, işini bitiren çeker. Denge tahminle değil **akışla** sağlanır.

| Havuz görevi | Gün | Kimler alabilir |
|---|--:|---|
| `infra/seed/` + demo verisi | 2 | Damla · Berat |
| `tests/e2e/` uçtan uca senaryo | 2 | Berat · Damla |
| Rapor sorguları (backend) | 2 | Damla · Berat |
| `Tariffs.tsx` + `Reports.tsx` sayfaları | 3 | Esra · Berat |
| `docker-compose.prod.yml` + paketleme | 1 | Berat · Damla |
| README + sunum/demo | 1 | Herkes |

**Toplam 11 gün ÷ 3 ≈ 3.7 kişi başı** → beklenen toplam ~19 gün/kişi.

**Kurallar:** Aynı anda havuzdan tek iş (WIP = 1) · Çekince `BACKLOG.md`'de işaretle ·
Her Cuma kalan gözden geçirilir.

---

## 12. Haftalık yol haritası

### Gün 0 — Sözleşme + mock'lar (§5)

### Hafta 1 — iskelet

| Esra | Berat | Damla |
|---|---|---|
| Vite kurulum, layout | FastAPI iskelet, Redis altyapısı | **compose (gün 0, 1 saat)** |
| Dashboard (mock'a karşı) | WS sunucu iskeleti | `contracts/schemas/` |
| | CI workflow | Şema + ilk migration |
| | | Domain CRUD |

> **Sıralama notu:** Damla tarife motorunu 1. haftaya koymasın — kritik yolda değil, kimse
> onu beklemiyor. Önce başkalarını açan işler. Aynı şekilde Berat ANPR'ı 1. güne koymasın;
> önce Redis + olay altyapısı ki Esra'nın WS istemcisi bağlanacak bir şey bulsun.

### Hafta 2 — ana işlevler

| Esra | Berat | Damla |
|---|---|---|
| FloorPlan, SlotGrid | ANPR simülasyonu | **Tarife motoru + testleri** |
| WS istemcisi + reconnect | Giriş/çıkış akışı | Doluluk + olay yayını |

### Hafta 3 — tamamlama

| Esra | Berat | Damla |
|---|---|---|
| SessionLog, filtreler | REST seti tamamlanır | Ücret + ödeme kaydı |
| Havuzdan çek | Havuzdan çek | Havuzdan çek |

### Hafta 4 — cila ve teslim

| Esra | Berat | Damla |
|---|---|---|
| Responsive, boş/hata ekranları | `compose.prod` + e2e | Uç durumlar, performans |
| `web/Dockerfile` | `gateway/Dockerfile` | `core/Dockerfile` |
| Demo provası — üçü birlikte | | |

---

## 13. Cuma entegrasyon seansı (1 saat)

Haftada tek senkron nokta.

| Dk | Ne |
|--:|---|
| 0-5 | `.env`'de `USE_MOCK=false`, `docker compose up`, üç servis ayağa |
| 5-25 | Uçtan uca senaryo: **araç girer → slot dolar → dashboard anında güncellenir → araç çıkar → ücret hesaplanır → DB'ye yazılır** |
| 25-40 | Sapmaları düzelt (gerçek fixture'ı döndürmüyorsa kim düzeltecek, ne zaman) |
| 40-50 | `DECISIONS.md`'deki açık varsayımları karara bağla |
| 50-60 | Havuz ayarı: *"Kim geride? Kim havuzdan çekmesin?"* |

Bozuksa `USE_MOCK=true`'ya dönülür, herkes devam eder. **"Entegrasyon haftası" diye bir şey
yok**, dolayısıyla son haftada toplu bekleme de yok.

---

## 14. Bir iş ne zaman "bitti" sayılır

- [ ] Sözleşmeye uygun çalışıyor (fixture'daki yanıtı döndürüyor)
- [ ] Birim testi var ve geçiyor
- [ ] CI yeşil
- [ ] PR açıldı, CODEOWNERS onayı alındı, merge edildi
- [ ] `BACKLOG.md` / tahta güncellendi
- [ ] Sözleşme değiştiyse diğer ikisine haber verildi

---

## 15. Riskler ve önlemler

| Risk | Önlem |
|---|---|
| Sözleşmede alan silinir, üçü birden kırılır | **Append-only kuralı** — asla silme, `deprecated` işaretle |
| Tahminler tutmaz, biri geride kalır | **Havuz** + Cuma ayarı |
| Son haftada entegrasyon kabusu | **Haftalık `USE_MOCK=false` koşumu** |
| Damla 1. haftada darboğaz olur | compose gün 0'da (1 saat), tarife motoru 2. haftaya ertelenir |
| CI gürültü yapar, ekip görmezden gelir | Sadece ruff + pytest + tsc; coverage eşiği yok |
| Docker bilmeyen ekip üyesi takılır | Docker bilmeyen kişi **Esra'nın rolünde** olsun — tek `docker compose up -d` yeter |
| Aynı tabloya iki yerden yazma | `gateway` DB'ye **hiç** dokunmaz kuralı |
| Plaka tanıma gerçek OCR'a kayar, zaman yer | Simülasyon yeterli (şartname "simülasyonu" diyor); gerçek OCR isteğe bağlı, `simulator.py` içinde izole strategy |

---

## 16. Hızlı referans

| Soru | Cevap |
|---|---|
| Esra kimin API'sini çağırır? | Sadece `gateway` (ve `USE_MOCK=true` iken `mock_gateway`) |
| Berat DB'ye yazabilir mi? | Hayır. `core`'a HTTP ile sorar |
| Damla dışarıya HTTP sunar mı? | Hayır. Sadece Docker ağı içi + Redis olayı |
| Sözleşmede alan eksik, ne yapayım? | Kendin ekle, mock'unda döndür, sahibine haber ver |
| Cevabı bilinmeyen tasarım sorusu | `DECISIONS.md`'ye varsayımını yaz, devam et, Cuma karara bağla |
| Çakışma çıktı | Muhtemelen ortak dosyadasın (§4) — sahibine danış |
| İşim bitti, boşum | `BACKLOG.md`'den tek iş çek (WIP = 1) |
