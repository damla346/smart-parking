# Smart Parking Management System — Frontend (web/)

Bu dizin, **Teknofest Şartname Maddesi 35 (Smart Parking Management System)** ve **YOL_HARITASI.md** sözleşmesi doğrultusunda **Esra (Frontend)** tarafından geliştirilmiş akıllı otopark kontrol merkezi arayüzüdür.

---

## 📌 Proje Genel Bakışı ve Ekip İş Bölümü

Projemiz gevşek bağlı (loosely-coupled), bağımsız çalışılabilir üçlü mimari üzerine kuruludur:
* **Esra (Frontend - `web/`):** Tek ekran üzerinden canlı kat/slot doluluk takibi, kademeli tarife hesaplayıcı, ANPR plaka tanıma simülatörü ve oturum logları.
* **Berat (İletişim & Ağ - `services/gateway/`):** REST API, WebSocket yayını (`ws://localhost:8100/ws/occupancy`), kamera ANPR servisi ve CI süreçleri.
* **Damla (Hesap & Veri - `services/core/`):** PostgreSQL veri modelleri, kademeli tarife motoru (`pricing.py`), doluluk motoru ve Redis olay yayıncısı.

> **Temel İlke:** Kimse kimsenin kodunu beklemez; herkes `contracts/` altındaki sözleşmelere ve veri şemalarına göre çalışır.

---

## 🚀 Öne Çıkan Özellikler ve Modüller

### 1. Kademeli Ücret Tarifesi Tablosu ve Canlı Hesaplama Konsolu
* **Resmi Tarife Cetveli Tablosu:** 
  Şartname Md. 35 uyarınca dakika bazlı 4 kademeli ücret tarifesi derli toplu ve şık bir tablo olarak sunulur:
  * **1. Kademe (0 - 30 dk):** Ücretsiz (0.00 ₺)
  * **2. Kademe (30 - 120 dk):** 0.50 ₺ / dk (50 kr/dk — 30.00 ₺ / saat)
  * **3. Kademe (120 - 480 dk):** 0.35 ₺ / dk (35 kr/dk — 21.00 ₺ / saat)
  * **4. Kademe (480+ dk):** 0.20 ₺ / dk (20 kr/dk — 12.00 ₺ / saat)
* **İnteraktif Test Konsolu:**
  Saat ve dakika kutuları, 1-1440 dakika kaydırıcısı ve hazır preset butonları (`30 dk`, `1 saat`, `1 sa 34 dk`, `4 saat`, `Tam Gün`) ile anlık kademeli hesaplama yapar.
* **Kalem Kalem Hesap Dökümü:**
  Hangi kademede kaç dakika kalındığını ve ara toplamları fiş dökümü olarak listeler.

### 2. Mimari Kat ve Slot Planı (Floor Plan)
* **3 Katlı 120 Slotluk Mimari:** Zemin Kat (K1), 1. Bodrum (K2), 2. Bodrum (K3). Kat başına 40 slot.
* **Slot Tipleri:** Standart (🚗), Engelli Öncelikli (♿ - K1-001/002), Elektrikli Şarj İstasyonlu (⚡ - K1-003/004/005), Geniş SUV Alanı (🚙 - K1-038/039/040).
* **İnteraktif Slot Etkileşimi:** Herhangi bir slota tıklandığında açılan modal ile aracın plakası, giriş zamanı, geçen süre ve anlık biriken ücret görüntülenir; araç çıkışı veya yeni araç parkı tek tıkla yapılabilir.

### 3. Plaka Tanıma (ANPR) Modülü
* **Standart TR Plaka Motoru:** `contracts/` ve `services/gateway/gateway/anpr/plate_gen.py` kurallarına tam uyumludur (01-81 il kodu, Q/W/X içermez, harf+rakam 5-7 hane).
* **Otantik Görsel Plaka Bileşeni:** Sol tarafında mavi "TR" şeridi, kalın kabartmalı çerçeve ve gerçekçi plaka tipografisi (`34 ABC 789`).
* **Kamera HUD Vizörü:** Hedefleme köşeleri, lazer tarama çizgisi ve hata senaryoları simülasyonu (okunamayan/çamurlu plaka testi).

### 4. Giriş-Çıkış Oturum Kayıtları (Session Logs)
* Gerçekleşen tüm araç hareketlerini listeler.
* Anlık plaka ve slot kodu arama filtresi.
* Açık (park halinde) / Kapalı oturum filtreleme.
* Tek tıkla **CSV Olarak İndir** özelliği.

### 5. Modern ve Ferah Tasarım Sistemi
* Göz yormayan, aydınlık ve ferah **"Toz Pembe & Rose"** kurumsal renk paleti (`#fff0f5`, `#1e1b4b`, `#f43f5e`, `#10b981`).
* Düzenli kart mimarisi ve yüksek okunabilirlikli tipografi.

---

## 👥 Takım Arkadaşlarımız İçin Entegrasyon Notları

### 🔹 Berat İçin (Gateway, WebSocket & ANPR Entegrasyonu)
1. **WebSocket Bağlantı Noktası:**
   - Frontend `web/js/store.js` dosyasında `ws://localhost:8100/ws/occupancy` adresini dinleyecek şekilde yapılandırılmıştır.
   - Gateway ayağa kalktığında arayüz sağ üstteki rozeti otomatik olarak **"Bağlı (Canlı)"** durumuna getirir.
   - Gateway kapalıyken veya henüz çalıştırılmadığında arayüz **asla çökmez**; yerel simülasyon moduna geçer (`simulated`).
2. **WebSocket Olay Şeması (`contracts/events.md`):**
   - Frontend şu formatta gelen mesajları doğrudan karşılar:
     ```json
     {
       "event": "lot.occupancy",
       "data": {
         "lot_id": 1,
         "total": 120,
         "occupied": 82,
         "free": 38,
         "occupancy_percent": 68.3,
         "by_floor": [
           { "floor_id": 1, "level": 1, "total": 40, "occupied": 28, "free": 12 },
           { "floor_id": 2, "level": 2, "total": 40, "occupied": 27, "free": 13 },
           { "floor_id": 3, "level": 3, "total": 40, "occupied": 27, "free": 13 }
         ]
       }
     }
     ```
3. **ANPR Kuralları:**
   - `web/js/anpr.js` içerisindeki plaka üretim ve doğrulama mantığı senin yazdığın `plate_gen.py` ile birebir aynı kuralları uygular.

### 🔹 Damla İçin (Core, Tarife Motoru & Veri Uyumu)
1. **Kademeli Tarife Uyumu (`pricing.py`):**
   - `web/js/tariff.js` hesaplama mantığı, `services/core/core/domain/pricing.py` saf fonksiyon mantığı ile %100 özdeştir.
   - **Tüm hesaplamalar KURUŞ (cents) cinsinden tam sayı olarak yapılır**, ekranda ₺ olarak formatlanır (1 ₺ = 100 kr). Kuruş kaybı veya yuvarlama farkı oluşmaz.
   - Süre yuvarlaması: Başlanan dakika tam sayı kabul edilir (`Math.ceil` / `pricing.py` ile aynı).
2. **Fixture ve Model Uyumu:**
   - Kat yapısı, slot kodlama formatı (`K1-001` .. `K3-040`) ve sözleşme modelleri `contracts/fixtures/*.json` şemalarıyla tam uyumludur.

### 🔹 CI & Repository Notları
* `.github/workflows/ci.yml` dosyasında `paths-filter` ile `web/**` dizini dinlenmektedir.
* `web/package.json` içerisindeki `typecheck` (`tsc --noEmit`) ve `build` (`tsc && vite build`) komutları tam uyumlu hale getirilmiştir.
* `web/src/vite-env.d.ts` ve `web/tsconfig.json` yapılandırması hatasızdır; CI kontrolleri yeşil geçer.

---

## 📁 Dizin ve Dosya Mimarisi

```
web/
├── index.html            # Ana kontrol paneli (tek tıkla çalışabilen arayüz)
├── package.json          # React + Vite ve derleme scriptleri
├── tsconfig.json         # TypeScript derleyici yapılandırması
├── vite.config.ts        # Vite yapılandırması
├── css/
│   └── style.css         # Toz pembe, ferah ve responsive tasarım sistemi
├── js/
│   ├── tariff.js         # Kademeli dakika bazlı ücret motoru (pricing.py eşleniği)
│   ├── anpr.js           # TR plaka üreteci, doğrulayıcısı ve HTML bileşeni
│   ├── store.js          # Merkezi veri deposu, doluluk takibi ve WS istemcisi
│   └── app.js            # UI kontrolcüsü, sekme ve modal yönetim mantığı
├── public/               # Vite derlemesi ve statik dağıtım kopyaları
├── src/                  # React + Vite iskeleti ve TypeScript bileşenleri
│   └── vite-env.d.ts     # Vite ortam tipleri bildirimi
└── README.md             # Bu dokümantasyon dosyası
```

---

## 🖥️ Nasıl Çalıştırılır?

### Seçenek 1: Sıfır Bağımlılıkla Doğrudan Açma (Node.js Gerekmez)
En hızlı yöntemdir. Herhangi bir kuruluma ihtiyaç duymadan:
* `web/index.html` dosyasına çift tıklayarak tarayıcınızda (Microsoft Edge, Chrome, Safari, Firefox) anında açabilirsiniz.

### Seçenek 2: Hafif Yerel Sunucu ile Açma
```bash
# Python ile:
cd web
python -m http.server 5173

# veya VS Code eklentisi ile:
# index.html dosyasına sağ tıklayıp "Open with Live Server" seçin.
```

### Seçenek 3: Vite ile Çalıştırma
```bash
cd web
npm install
npm run dev
```

### Gateway (Mock) ile Test Etmek İçin:
```bash
# Proje kök dizininde:
python infra/mocks/mock_gateway.py
```
Arayüz, `ws://localhost:8100/ws/occupancy` yayınını otomatik olarak yakalayıp gerçek zamanlı verilerle senkronize olacaktır.
