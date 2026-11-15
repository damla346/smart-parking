/**
 * ★ MERKEZİ VERİ DEPOSU VE REST / WEBSOCKET ENTEGRASYONU
 * Şartname Md. 35 & YOL_HARITASI §3, §5, §6
 * contracts/fixtures/*.json & contracts/events.md & openapi.yaml yapısına tam uyumlu.
 *
 * Gerçek Core + Gateway entegrasyonu (Damla'nın 4 geliştirme maddesi):
 * 1. Canlı slot.occupied ve slot.freed olay dinleyicileri
 * 2. Açılışta GET /lots/1/floors ile gerçek kat ve slot kapasitesi
 * 3. GET /sessions?lot_id=1&limit=50 ile giriş-çıkış kayıtları
 * 4. POST /entry ve POST /exit ile canlı REST istekleri (bağlantı yoksa akıllı simülasyon fallback)
 */

(function (window) {
  'use strict';

  // Sunucu adresleri (Berat'ın gerçek gateway'i: 8000, Mock gateway: 8100)
  const WS_URL_GATEWAY = 'ws://localhost:8000/ws/occupancy'; // Berat'ın gateway servisi (gateway/config.py:14)
  const WS_URL_MOCK = 'ws://localhost:8100/ws/occupancy';    // infra/mocks/mock_gateway.py

  class ParkingStore {
    constructor() {
      this.lot = {
        id: 1,
        name: 'Adana Merkez Akıllı Otopark',
        address: 'Çukurova Bulvarı No:42, Seyhan / Adana',
        total_slots: 120,
      };

      this.floors = [];
      this.sessions = [];
      this.tariffs = window.TariffEngine ? window.TariffEngine.DEFAULT_TARIFF_RULES : [];
      this.subscribers = new Set();
      this.cameraLogs = [];

      // Bağlantı durumu: 'connected_gateway' | 'connected_mock' | 'waiting_gateway' | 'waiting_mock' | 'simulated'
      this.connectionStatus = 'simulated';
      this.connectedUrl = null;
      this.hasReceivedWsData = false;
      this.isRealDataLoaded = false;
      this.latestOccupancy = null;
      this.wsDataWatchdog = null;
      this.activeFloorLevel = 1;
      this.autoTrafficInterval = null;
      this.ws = null;
      this.wsRetryTimer = null;

      // 1. Başlangıç yerel verilerini oluştur (çevrimdışı / bağımsız mod garantisi)
      this.initDefaultData();

      // 2. Arka planda gerçek/mock WS varsa bağlanmayı dene
      this.tryWebSocket();

      // 3. Gerçek kat planını API'den çekmeyi dene
      this.fetchFloors();
    }

    /**
     * REST API kök adresini belirler (Gateway: 8000, Mock: 8100)
     */
    getApiBaseUrl() {
      if (this.connectedUrl) {
        if (this.connectedUrl.includes(':8100')) return 'http://localhost:8100';
        if (this.connectedUrl.includes(':8000')) return 'http://localhost:8000';
      }
      if (typeof window !== 'undefined' && window.location && window.location.port) {
        if (window.location.port === '8000' || window.location.port === '8100') {
          return window.location.origin;
        }
      }
      return 'http://localhost:8000';
    }

    /**
     * Gateway veya Mock servisine bağlı olup olmadığını kontrol eder
     */
    isConnected() {
      return (
        this.connectionStatus.startsWith('connected_') ||
        this.connectionStatus.startsWith('waiting_')
      );
    }

    /**
     * Fixture'lara ve gerçekçi senaryoya uygun 3 katlı 120 slotluk otoparkı başlatır.
     */
    initDefaultData() {
      const floors = [];
      let globalSlotId = 1;

      // 3 Kat (Kat 1: Zemin, Kat 2: 1. Bodrum, Kat 3: 2. Bodrum)
      for (let level = 1; level <= 3; level++) {
        const slots = [];
        const floorPrefix = `K${level}`;

        for (let num = 1; num <= 40; num++) {
          const code = `${floorPrefix}-${String(num).padStart(3, '0')}`;
          let type = 'standard';

          // Belirli slotları özel tip yap
          if (num === 1 || num === 2) {
            type = 'disabled'; // Engelli erişilebilir slotlar (girişe en yakın)
          } else if (num === 3 || num === 4 || num === 5) {
            type = 'ev'; // Elektrikli şarj istasyonlu slotlar
          } else if (num >= 38) {
            type = 'large'; // Geniş araç / SUV slotları
          }

          slots.push({
            id: globalSlotId++,
            floor_id: level,
            code: code,
            type: type,
            status: 'free',
            plate: null,
            entry_at: null,
          });
        }

        floors.push({
          id: level,
          lot_id: 1,
          level: level,
          slot_count: 40,
          slots: slots,
        });
      }

      this.floors = floors;

      // Başlangıç için gerçekçi oturumlar ekle (yaklaşık %48-%82 arası rastgele doluluk)
      this.initInitialVehicles();
    }

    initInitialVehicles() {
      const simdi = new Date();
      const ornekPlakalar = [
        '01ABC123', '34XYZ987', '06DEF456', '35GHI789', '16BUR016',
        '07ANT007', '01ADA001', '34ESR345', '01DAM789', '01BER555',
        '34KER123', '06ANK999', '35IZM035', '41KOC411', '54SAK054',
      ];

      let sessionId = 100;
      const allSlots = this.getAllSlots();

      // Önceki durumu temizle
      allSlots.forEach((s) => {
        s.status = 'free';
        s.plate = null;
        s.entry_at = null;
      });
      this.sessions = [];

      // Her açılışta %48 ile %82 arasında rastgele, doğal bir doluluk oranı üret
      const hedefOran = 0.48 + Math.random() * 0.34;
      const hedefDoluSayisi = Math.round(allSlots.length * hedefOran);

      // Slotları rastgele karıştır ve rastgele hedef kadarını doldur
      const karisikSlotlar = [...allSlots].sort(() => Math.random() - 0.5);

      for (let i = 0; i < karisikSlotlar.length; i++) {
        const slot = karisikSlotlar[i];
        if (i < hedefDoluSayisi) {
          const plaka = i < ornekPlakalar.length ? ornekPlakalar[i] : window.ANPR.rastgelePlaka();
          // 12 dk ile 340 dk arası rastgele giriş zamanı
          const gecenDakika = Math.floor(Math.random() * 320) + 12;
          const girisZamani = new Date(simdi.getTime() - gecenDakika * 60 * 1000).toISOString();

          slot.status = 'occupied';
          slot.plate = plaka;
          slot.entry_at = girisZamani;

          this.sessions.unshift({
            id: sessionId++,
            plate: plaka,
            lot_id: 1,
            slot_id: slot.id,
            slot_code: slot.code,
            entry_at: girisZamani,
            exit_at: null,
            duration_min: null,
            fee_cents: null,
            status: 'open',
          });
        }
      }

      // Birkaç tane de geçmişte tamamlanmış oturum ekle (log ekranı için)
      for (let i = 0; i < 8; i++) {
        const plaka = window.ANPR.rastgelePlaka();
        const sure = Math.floor(Math.random() * 200) + 20;
        const cikis = new Date(simdi.getTime() - (i * 25 + 10) * 60 * 1000);
        const giris = new Date(cikis.getTime() - sure * 60 * 1000);
        const ucret = window.TariffEngine.hesaplaDakikadan(sure, this.tariffs);

        this.sessions.push({
          id: sessionId++,
          plate: plaka,
          lot_id: 1,
          slot_id: 42,
          slot_code: `K${(i % 3) + 1}-${String(i * 3 + 1).padStart(3, '0')}`,
          entry_at: giris.toISOString(),
          exit_at: cikis.toISOString(),
          duration_min: sure,
          fee_cents: ucret.total_cents,
          status: 'closed',
        });
      }
    }

    /**
     * Otopark durumunu rastgele yeni bir doluluk oranıyla sıfırlar/yeniler
     */
    resetSimulationState() {
      this.isRealDataLoaded = false;
      this.initInitialVehicles();
      this.notifySubscribers({ event: 'state.reset' });
    }

    getAllSlots() {
      return this.floors.flatMap((f) => f.slots);
    }

    /**
     * Doluluk özeti (contracts/events.md -> lot.occupancy şeması)
     */
    getOccupancy() {
      const byFloor = this.floors.map((floor) => {
        const occupied = floor.slots.filter((s) => s.status === 'occupied').length;
        const total = floor.slots.length || floor.slot_count || 40;
        return {
          floor_id: floor.id,
          level: floor.level,
          total: total,
          occupied: occupied,
          free: total - occupied,
          occupancy_rate: total > 0 ? Math.round((occupied / total) * 100) : 0,
        };
      });

      const total = byFloor.reduce((acc, f) => acc + f.total, 0) || this.lot.total_slots || 120;
      const occupied = byFloor.reduce((acc, f) => acc + f.occupied, 0);
      const free = Math.max(0, total - occupied);
      const occupancyRate = total > 0 ? (occupied / total) : 0;

      return {
        lot_id: 1,
        total: total,
        occupied: occupied,
        free: free,
        occupancy_rate: occupancyRate,
        occupancy_percent: Math.round(occupancyRate * 100),
        by_floor: byFloor,
        at: new Date().toISOString(),
      };
    }

    /**
     * Boş bir slot bulur. Katlar arasında ve slotlar içinde dengeli ve gerçekçi dağıtım yapar.
     */
    findAvailableSlot(preferredType = null, floorLevel = null) {
      if (floorLevel) {
        const floor = this.floors.find((f) => f.level === floorLevel);
        if (floor) {
          const freeSlots = floor.slots.filter((s) => s.status === 'free');
          if (freeSlots.length > 0) {
            if (preferredType) {
              const typed = freeSlots.filter((s) => s.type === preferredType);
              if (typed.length > 0) return typed[Math.floor(Math.random() * typed.length)];
            }
            return freeSlots[Math.floor(Math.random() * freeSlots.length)];
          }
        }
        return null;
      }

      const allFreeSlots = this.getAllSlots().filter((s) => s.status === 'free');
      if (allFreeSlots.length === 0) return null;

      if (preferredType) {
        const typedSlots = allFreeSlots.filter((s) => s.type === preferredType);
        if (typedSlots.length > 0) {
          return typedSlots[Math.floor(Math.random() * typedSlots.length)];
        }
      }

      return allFreeSlots[Math.floor(Math.random() * allFreeSlots.length)];
    }

    /**
     * 2. Madde: Açılışta gerçek kat planı ve slotları Gateway'den çeker (GET /lots/1/floors)
     * openapi.yaml şemasına tam uyumlu
     */
    async fetchFloors() {
      try {
        const apiBase = this.getApiBaseUrl();
        const res = await fetch(`${apiBase}/lots/1/floors`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          this.floors = data.map((f) => ({
            id: f.id,
            lot_id: f.lot_id || 1,
            level: f.level,
            slot_count: f.slot_count || (f.slots ? f.slots.length : 40),
            slots: (f.slots || []).map((s) => ({
              id: s.id,
              floor_id: s.floor_id || f.id,
              code: s.code,
              type: s.type || 'standard',
              status: s.status || (s.plate ? 'occupied' : 'free'),
              plate: s.plate || null,
              entry_at: s.entry_at || (s.status === 'occupied' || s.plate ? new Date().toISOString() : null),
            })),
          }));

          const total = this.floors.reduce(
            (acc, f) => acc + (f.slot_count || f.slots.length),
            0
          );
          this.lot.total_slots = total;
          this.isRealDataLoaded = true;
          this.notifySubscribers({ event: 'floors.loaded', floors: this.floors });
          return this.floors;
        }
      } catch (err) {
        console.warn('API /lots/1/floors çağrısı yapılamadı, yerel kat planı devrede:', err.message);
        return null;
      }
    }

    /**
     * 3. Madde: Giriş-çıkış oturum kayıtlarını Gateway'den çeker (GET /sessions)
     * GET /sessions?plate=&lot_id=1&limit=50
     */
    async fetchSessions(params = {}) {
      try {
        const apiBase = this.getApiBaseUrl();
        const url = new URL(`${apiBase}/sessions`);
        url.searchParams.set('lot_id', '1');
        url.searchParams.set('limit', String(params.limit || 50));
        if (params.plate) {
          url.searchParams.set('plate', params.plate);
        }
        const res = await fetch(url.toString());
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (Array.isArray(data)) {
          this.sessions = data;
          this.notifySubscribers({ event: 'sessions.loaded', sessions: data });
          return data;
        }
      } catch (err) {
        console.warn('API /sessions çağrısı yapılamadı, yerel oturum kayıtları devrede:', err.message);
        return this.sessions;
      }
    }

    /**
     * 4. Madde: Araç girişi — Gateway'e gerçek REST POST /entry isteği gönderir
     * Bağlı değilse veya ağ hatasında yerel simülatöre güvenle geçer.
     */
    async vehicleEntry(plate, opts = {}) {
      const hamPlaka = (plate || '').toUpperCase().replace(/\s+/g, '');
      if (!window.ANPR.plakaGecerliMi(hamPlaka)) {
        throw new Error(`Geçersiz Türk plakası formatı: "${plate}". Örnek: 34ABC123`);
      }

      if (this.isConnected()) {
        const apiBase = this.getApiBaseUrl();
        let res;
        try {
          res = await fetch(`${apiBase}/entry`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plate: hamPlaka, lot_id: 1 }),
          });
        } catch (netErr) {
          // Sunucuya hiç ulaşılamadı (ağ hatası veya CORS engeli):
          // Simülasyona geç, rozeti güncelle ve kullanıcıya durumu göster
          this.connectionStatus = 'simulated';
          this.notifySubscribers({ event: 'connection.change', status: 'simulated' });
          return this.simulateLocalEntry(hamPlaka, opts);
        }

        // Sunucu 201 Created döndüyse başarılı
        if (res.status === 201) {
          const session = await res.json();
          // Damla'nın mimari kuralı: Ekrandaki doluluk ve slot güncellemesini elle yapmaya
          // gerek yok. Core olayları gönderiyor, gateway WebSocket'ten iletiyor (slot.occupied).
          return {
            session: session,
            slot: {
              code: session.slot_code || '—',
              plate: hamPlaka,
            },
            remote: true,
          };
        }

        // Sunucu cevap verdi ama "hayır" dedi (409, 404, 500 vb.): hatayı göster, sahte başarı üretme
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Giriş işlemi başarısız (HTTP ${res.status})`);
      }

      return this.simulateLocalEntry(hamPlaka, opts);
    }

    /**
     * Yerel Giriş Simülasyonu (file:// veya çevrimdışı fallback modu)
     */
    simulateLocalEntry(hamPlaka, opts = {}) {
      const existing = this.sessions.find((s) => s.plate === hamPlaka && s.status === 'open');
      if (existing) {
        throw new Error(`Bu plaka (${window.ANPR.formatPlaka(hamPlaka)}) zaten otoparkta! (Slot: ${existing.slot_code})`);
      }

      const slot = opts.slotCode
        ? this.getAllSlots().find((s) => s.code === opts.slotCode && s.status === 'free')
        : this.findAvailableSlot(opts.preferredType, opts.floorLevel);

      if (!slot) {
        throw new Error('Otoparkta uygun boş park yeri kalmadı!');
      }

      const now = new Date();
      slot.status = 'occupied';
      slot.plate = hamPlaka;
      slot.entry_at = now.toISOString();

      const newSession = {
        id: Math.floor(Math.random() * 90000) + 1000,
        plate: hamPlaka,
        lot_id: 1,
        slot_id: slot.id,
        slot_code: slot.code,
        entry_at: now.toISOString(),
        exit_at: null,
        duration_min: null,
        fee_cents: null,
        status: 'open',
      };

      this.sessions.unshift(newSession);

      this.addCameraLog({
        type: 'entry',
        plate: hamPlaka,
        slotCode: slot.code,
        timestamp: now.toISOString(),
        confidence: (0.92 + Math.random() * 0.07).toFixed(2),
        message: 'Giriş kamerası plakayı tanıdı, bariyer açıldı.',
      });

      this.notifySubscribers({
        event: 'slot.occupied',
        data: {
          slot_id: slot.id,
          slot_code: slot.code,
          plate: hamPlaka,
          session: newSession,
        },
      });

      return { slot, session: newSession };
    }

    /**
     * 4. Madde: Araç çıkışı — Gateway'e gerçek REST POST /exit isteği gönderir
     */
    async vehicleExit(plate) {
      const hamPlaka = (plate || '').toUpperCase().replace(/\s+/g, '');
      if (!hamPlaka) {
        throw new Error('Lütfen bir plaka girin.');
      }

      if (this.isConnected()) {
        const apiBase = this.getApiBaseUrl();
        let res;
        try {
          res = await fetch(`${apiBase}/exit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plate: hamPlaka }),
          });
        } catch (netErr) {
          // Sunucuya hiç ulaşılamadı (ağ hatası veya CORS engeli):
          // Simülasyona geç, rozeti güncelle ve kullanıcıya durumu göster
          this.connectionStatus = 'simulated';
          this.notifySubscribers({ event: 'connection.change', status: 'simulated' });
          return this.simulateLocalExit(hamPlaka);
        }

        // Sunucu 200 OK döndüyse ücret dökümünü formatla
        if (res.status === 200) {
          const breakdownData = await res.json();
          return this.formatRemoteFeeBreakdown(breakdownData, hamPlaka);
        }

        // Sunucu cevap verdi ama "hayır" dedi (404, 409, 500 vb.): hatayı göster, sahte başarı üretme
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Çıkış işlemi başarısız (HTTP ${res.status})`);
      }

      return this.simulateLocalExit(hamPlaka);
    }

    /**
     * openapi.yaml FeeBreakdown yanıtını arayüzün makbuz modal formatına dönüştürür
     */
    formatRemoteFeeBreakdown(feeData, plate) {
      const lines = (feeData.lines || []).map((l, idx) => ({
        label: `${idx + 1}. Kademe (${l.from_min} - ${l.to_min !== null ? l.to_min + ' dk' : 'Sınırsız'})`,
        from_min: l.from_min,
        to_min: l.to_min,
        minutes: l.minutes,
        price_per_min_cents: l.price_per_min_cents,
        price_per_min_tl: (l.price_per_min_cents / 100).toFixed(2),
        subtotal_cents: l.subtotal_cents,
        subtotal_tl: (l.subtotal_cents / 100).toFixed(2),
      }));

      const totalCents = feeData.total_cents || 0;
      return {
        session_id: feeData.session_id,
        plate: feeData.plate || plate,
        duration_min: feeData.duration_min || 0,
        total_cents: totalCents,
        total_tl: (totalCents / 100).toFixed(2),
        lines: lines,
        slot_code: feeData.slot_code || '—',
      };
    }

    /**
     * Yerel Çıkış Simülasyonu (file:// veya çevrimdışı fallback modu)
     */
    simulateLocalExit(hamPlaka) {
      const session = this.sessions.find((s) => s.plate === hamPlaka && s.status === 'open');

      if (!session) {
        throw new Error(`"${window.ANPR.formatPlaka(hamPlaka)}" plakalı araca ait aktif bir park oturumu bulunamadı.`);
      }

      const now = new Date();
      const breakdown = window.TariffEngine.hesaplaUcret(
        session.entry_at,
        now,
        this.tariffs,
        { sessionId: session.id, plate: hamPlaka }
      );

      // Slotu boşalt
      const slot = this.getAllSlots().find((s) => s.code === session.slot_code);
      if (slot) {
        slot.status = 'free';
        slot.plate = null;
        slot.entry_at = null;
      }

      // Oturumu kapat
      session.exit_at = now.toISOString();
      session.duration_min = breakdown.duration_min;
      session.fee_cents = breakdown.total_cents;
      session.status = 'closed';

      this.addCameraLog({
        type: 'exit',
        plate: hamPlaka,
        slotCode: session.slot_code,
        timestamp: now.toISOString(),
        confidence: (0.95 + Math.random() * 0.04).toFixed(2),
        feeTL: breakdown.total_tl,
        duration: window.TariffEngine.formatSure(breakdown.duration_min),
        message: 'Çıkış kamerası plakayı tanıdı, ücret hesaplandı.',
      });

      this.notifySubscribers({
        event: 'slot.freed',
        data: {
          slot_id: slot ? slot.id : null,
          slot_code: session.slot_code,
          plate: hamPlaka,
          breakdown: breakdown,
        },
      });

      return breakdown;
    }

    addCameraLog(entry) {
      this.cameraLogs.unshift(entry);
      if (this.cameraLogs.length > 25) {
        this.cameraLogs.pop();
      }
    }

    /**
     * Rastgele araç giriş simülasyonu
     */
    async simulateRandomEntry() {
      const plaka = window.ANPR.rastgelePlaka();
      return await this.vehicleEntry(plaka);
    }

    /**
     * Rastgele içerideki bir aracın çıkış simülasyonu
     */
    async simulateRandomExit() {
      const openSessions = this.sessions.filter((s) => s.status === 'open');
      if (openSessions.length > 0) {
        const randomSession = openSessions[Math.floor(Math.random() * openSessions.length)];
        return await this.vehicleExit(randomSession.plate);
      }

      // Eğer açık oturum listesinde yoksa dolu slotlardan birinin plakasını al
      const occupiedSlot = this.getAllSlots().find((s) => s.status === 'occupied' && s.plate);
      if (occupiedSlot) {
        return await this.vehicleExit(occupiedSlot.plate);
      }

      throw new Error('Şu an otoparkta çıkış yapabilecek araç yok!');
    }

    /**
     * Canlı trafik simülasyonunu başlatır / durdurur
     */
    toggleAutoTraffic(active) {
      if (this.autoTrafficInterval) {
        clearInterval(this.autoTrafficInterval);
        this.autoTrafficInterval = null;
      }

      if (active) {
        this.autoTrafficInterval = setInterval(async () => {
          try {
            const occ = this.getOccupancy();
            const shouldExit = occ.occupancy_rate > 0.85 ? Math.random() < 0.8 : Math.random() < 0.45;

            if (shouldExit && occ.occupied > 10) {
              await this.simulateRandomExit();
            } else if (occ.free > 0) {
              await this.simulateRandomEntry();
            }
          } catch (e) {
            console.warn('Otomatik simülasyon adımı atlandı:', e.message);
          }
        }, 3200);
      }
      return !!this.autoTrafficInterval;
    }

    /**
     * WebSocket bağlantısını dener:
     * 1. Önce Berat'ın gerçek gateway'i (port 8000) taranır.
     * 2. Kapalıysa mock_gateway (port 8100) taranır.
     * 3. İkisi de yoksa yerel simülasyon aktif kalır, 10 sn sonra yeniden denenir.
     */
    tryWebSocket() {
      if (typeof WebSocket === 'undefined') return;

      const params = typeof window !== 'undefined' && window.location ? new URLSearchParams(window.location.search) : null;
      const forceMock = params && (params.get('mock') === 'true' || params.get('use_mock') === 'true' || params.get('port') === '8100');
      const forceGateway = params && (params.get('gateway') === 'true' || params.get('port') === '8000');

      let targets = [WS_URL_GATEWAY, WS_URL_MOCK];
      if (forceMock) {
        targets = [WS_URL_MOCK];
      } else if (forceGateway) {
        targets = [WS_URL_GATEWAY];
      }

      this.connectWebSocketCandidates(targets, 0);
    }

    connectWebSocketCandidates(targets, index) {
      if (index >= targets.length) {
        this.connectionStatus = 'simulated';
        this.connectedUrl = null;
        this.notifySubscribers({ event: 'connection.change', status: 'simulated', url: null });
        this.scheduleWsReconnect();
        return;
      }

      const targetUrl = targets[index];
      const isGateway = targetUrl.includes(':8000');
      let opened = false;

      try {
        const ws = new WebSocket(targetUrl);

        ws.onopen = () => {
          opened = true;
          this.ws = ws;
          this.connectedUrl = targetUrl;
          this.hasReceivedWsData = false;
          // Bağlantı kuruldu ama henüz yayın mesajı gelmedi -> "veri bekleniyor" durumu
          this.connectionStatus = isGateway ? 'waiting_gateway' : 'waiting_mock';
          this.notifySubscribers({
            event: 'connection.change',
            status: this.connectionStatus,
            url: targetUrl,
            mode: isGateway ? 'Gerçek Gateway (8000)' : 'Mock Gateway (8100)',
            waiting: true,
          });

          // Bağlantı açıldığı gibi gerçek kat planını ve oturumları hemen çek
          this.fetchFloors();

          // 10 saniye içinde mesaj gelmezse durumu teyit et
          if (this.wsDataWatchdog) clearTimeout(this.wsDataWatchdog);
          this.wsDataWatchdog = setTimeout(() => {
            if (!this.hasReceivedWsData && this.ws === ws) {
              this.connectionStatus = isGateway ? 'waiting_gateway' : 'waiting_mock';
              this.notifySubscribers({
                event: 'connection.change',
                status: this.connectionStatus,
                url: targetUrl,
                mode: isGateway ? 'Gerçek Gateway (8000)' : 'Mock Gateway (8100)',
                waiting: true,
              });
            }
          }, 10000);
        };

        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data);
            if (!msg || !msg.event) return;

            // İlk mesaj geldiğinde rozeti canlı akış moduna geçir
            if (!this.hasReceivedWsData) {
              this.hasReceivedWsData = true;
              if (this.wsDataWatchdog) {
                clearTimeout(this.wsDataWatchdog);
                this.wsDataWatchdog = null;
              }
              this.connectionStatus = isGateway ? 'connected_gateway' : 'connected_mock';
              this.notifySubscribers({
                event: 'connection.change',
                status: this.connectionStatus,
                url: targetUrl,
                mode: isGateway ? 'Gerçek Gateway (8000)' : 'Mock Gateway (8100)',
                streaming: true,
              });
            }

            // 1. Madde: slot.occupied, slot.freed ve lot.occupancy olayları
            if (msg.event === 'slot.occupied' && msg.data) {
              this.handleSlotOccupiedEvent(msg.data);
            } else if (msg.event === 'slot.freed' && msg.data) {
              this.handleSlotFreedEvent(msg.data);
            } else if (msg.event === 'lot.occupancy' && msg.data) {
              this.applyExternalOccupancy(msg.data);
              this.notifySubscribers({ event: 'external.occupancy', data: msg.data });
            } else if (msg.event === 'anpr.read_failed' && msg.data) {
              this.addCameraLog({
                type: 'error',
                plate: '?? *** ??',
                slotCode: '—',
                timestamp: msg.data.at || new Date().toISOString(),
                confidence: String(msg.data.confidence || 0.3),
                message: `anpr.read_failed: ${msg.data.reason || 'Optik doğrulama başarısız'}.`,
              });
              this.notifySubscribers({ event: 'anpr.read_failed', data: msg.data });
            }
          } catch (e) {
            // sessizce geç
          }
        };

        ws.onclose = () => {
          if (this.wsDataWatchdog) {
            clearTimeout(this.wsDataWatchdog);
            this.wsDataWatchdog = null;
          }
          this.hasReceivedWsData = false;
          if (!opened) {
            this.connectWebSocketCandidates(targets, index + 1);
          } else {
            this.connectionStatus = 'simulated';
            this.connectedUrl = null;
            this.notifySubscribers({ event: 'connection.change', status: 'simulated', url: null });
            this.scheduleWsReconnect();
          }
        };

        ws.onerror = () => {
          try { ws.close(); } catch (_) {}
        };
      } catch (err) {
        this.connectWebSocketCandidates(targets, index + 1);
      }
    }

    scheduleWsReconnect() {
      if (!this.wsRetryTimer) {
        this.wsRetryTimer = setTimeout(() => {
          this.wsRetryTimer = null;
          this.tryWebSocket();
        }, 10000);
      }
    }

    /**
     * 1. Madde: WebSocket slot.occupied olayını işler
     * data: { slot_id, lot_id, floor_id, slot_code, plate, session_id, at }
     */
    handleSlotOccupiedEvent(data) {
      if (!data) return;
      const slot = this.getAllSlots().find(
        (s) => s.id === data.slot_id || s.code === data.slot_code
      );

      if (slot) {
        slot.status = 'occupied';
        slot.plate = data.plate;
        slot.entry_at = data.at || new Date().toISOString();
      }

      this.addCameraLog({
        type: 'entry',
        plate: data.plate,
        slotCode: data.slot_code || (slot ? slot.code : '—'),
        timestamp: data.at || new Date().toISOString(),
        confidence: '0.98',
        message: 'Giriş kamerası plakayı tanıdı, bariyer açıldı.',
      });

      this.notifySubscribers({
        event: 'slot.occupied',
        data: data,
        slot: slot,
      });
    }

    /**
     * 1. Madde: WebSocket slot.freed olayını işler
     * data: { slot_id, lot_id, floor_id, slot_code, at }
     */
    handleSlotFreedEvent(data) {
      if (!data) return;
      const slot = this.getAllSlots().find(
        (s) => s.id === data.slot_id || s.code === data.slot_code
      );

      if (slot) {
        slot.status = 'free';
        slot.plate = null;
        slot.entry_at = null;
      }

      this.addCameraLog({
        type: 'exit',
        plate: '—',
        slotCode: data.slot_code || (slot ? slot.code : '—'),
        timestamp: data.at || new Date().toISOString(),
        confidence: '0.99',
        message: 'Araç ayrıldı, slot boşaldı.',
      });

      this.notifySubscribers({
        event: 'slot.freed',
        data: data,
        slot: slot,
      });
    }

    /**
     * Canlı Gateway/Mock sayaç verisini (lot.occupancy) yerel arayüze uygular.
     */
    applyExternalOccupancy(data) {
      if (!data) return;
      this.latestOccupancy = data;
      if (typeof data.total === 'number') {
        this.lot.total_slots = data.total;
      }

      // Eğer gerçek kat planı henüz API'den yüklenmediyse (salt simülasyon modundaysak)
      // doluluk sayısını yakalamak için yerel tahminlemeyi sürdür:
      if (!this.isRealDataLoaded && Array.isArray(data.by_floor)) {
        for (const extFloor of data.by_floor) {
          const localFloor = this.floors.find((f) => f.level === extFloor.level || f.id === extFloor.floor_id);
          if (localFloor && typeof extFloor.occupied === 'number') {
            const currentOccupied = localFloor.slots.filter((s) => s.status === 'occupied').length;
            const diff = extFloor.occupied - currentOccupied;
            if (diff > 0) {
              const freeSlots = localFloor.slots.filter((s) => s.status === 'free');
              const count = Math.min(diff, freeSlots.length);
              for (let i = 0; i < count; i++) {
                const randIdx = Math.floor(Math.random() * freeSlots.length);
                const pickedSlot = freeSlots.splice(randIdx, 1)[0];
                pickedSlot.status = 'occupied';
                pickedSlot.plate = window.ANPR.rastgelePlaka();
                pickedSlot.entry_at = new Date().toISOString();
              }
            } else if (diff < 0) {
              const occSlots = localFloor.slots.filter((s) => s.status === 'occupied');
              const count = Math.min(Math.abs(diff), occSlots.length);
              for (let i = 0; i < count; i++) {
                const randIdx = Math.floor(Math.random() * occSlots.length);
                const pickedSlot = occSlots.splice(randIdx, 1)[0];
                pickedSlot.status = 'free';
                pickedSlot.plate = null;
                pickedSlot.entry_at = null;
              }
            }
          }
        }
      }
    }

    subscribe(callback) {
      this.subscribers.add(callback);
      return () => this.subscribers.delete(callback);
    }

    notifySubscribers(payload) {
      for (const cb of this.subscribers) {
        try {
          cb(payload);
        } catch (e) {
          console.error('Subscriber callback error:', e);
        }
      }
    }
  }

  window.ParkingStore = new ParkingStore();
})(window);
