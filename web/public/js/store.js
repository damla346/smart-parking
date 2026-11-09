/**
 * ★ MERKEZİ VERİ DEPOSU VE REST / WEBSOCKET ENTEGRASYONU
 * Şartname Md. 35 & YOL_HARITASI §3, §5, §6
 * contracts/fixtures/*.json yapısına tam uyumlu.
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
      this.tariffs = window.TariffEngine.DEFAULT_TARIFF_RULES;
      this.subscribers = new Set();
      this.cameraLogs = [];

      // Bağlantı durumu: 'connected_gateway' | 'connected_mock' | 'waiting_gateway' | 'waiting_mock' | 'simulated'
      this.connectionStatus = 'simulated';
      this.connectedUrl = null;
      this.hasReceivedWsData = false;
      this.wsDataWatchdog = null;
      this.activeFloorLevel = 1;
      this.autoTrafficInterval = null;
      this.ws = null;
      this.wsRetryTimer = null;

      // Başlangıç verilerini oluştur
      this.initDefaultData();

      // Arka planda gerçek/mock WS varsa bağlanmayı dene
      this.tryWebSocket();
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

      // Başlangıç için gerçekçi oturumlar ekle (yaklaşık %65-70 doluluk)
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

      // Belirli slotları başlangıçta doldur
      allSlots.forEach((slot, index) => {
        // %68 doluluk oranı elde edecek şekilde dağıt
        const shouldOccupy = (index % 3 !== 0) || (index % 7 === 0);
        if (shouldOccupy && index < 90) {
          const plaka = index < ornekPlakalar.length ? ornekPlakalar[index] : window.ANPR.rastgelePlaka();
          // 15 dk ile 360 dk arası rastgele giriş zamanı
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
      });

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

    getAllSlots() {
      return this.floors.flatMap((f) => f.slots);
    }

    /**
     * Doluluk özeti (contracts/events.md -> lot.occupancy şeması)
     */
    getOccupancy() {
      const byFloor = this.floors.map((floor) => {
        const occupied = floor.slots.filter((s) => s.status === 'occupied').length;
        const total = floor.slots.length;
        return {
          floor_id: floor.id,
          level: floor.level,
          total: total,
          occupied: occupied,
          free: total - occupied,
          occupancy_rate: total > 0 ? Math.round((occupied / total) * 100) : 0,
        };
      });

      const total = byFloor.reduce((acc, f) => acc + f.total, 0);
      const occupied = byFloor.reduce((acc, f) => acc + f.occupied, 0);
      const free = total - occupied;
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
      // 1. Belirli bir kat istenmişse sadece o kata bak
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

      // 2. Kat belirtilmemişse: Tüm katlardaki boş slotları topla
      const allFreeSlots = this.getAllSlots().filter((s) => s.status === 'free');
      if (allFreeSlots.length === 0) return null;

      if (preferredType) {
        const typedSlots = allFreeSlots.filter((s) => s.type === preferredType);
        if (typedSlots.length > 0) {
          return typedSlots[Math.floor(Math.random() * typedSlots.length)];
        }
      }

      // 1., 2. ve 3. katlara rastgele ve gerçekçi dağıt
      return allFreeSlots[Math.floor(Math.random() * allFreeSlots.length)];
    }

    /**
     * Plaka okundu, araç giriş yapıyor (ANPR Simülasyonu & REST POST /entry)
     */
    vehicleEntry(plate, opts = {}) {
      const hamPlaka = (plate || '').toUpperCase().replace(/\s+/g, '');

      if (!window.ANPR.plakaGecerliMi(hamPlaka)) {
        throw new Error(`Geçersiz Türk plakası formatı: "${plate}". Örnek: 34ABC123`);
      }

      // Plaka zaten içeride mi?
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
     * Araç çıkıyor, ücret hesaplanıyor (REST POST /exit)
     */
    vehicleExit(plate) {
      const hamPlaka = (plate || '').toUpperCase().replace(/\s+/g, '');
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
    simulateRandomEntry() {
      const plaka = window.ANPR.rastgelePlaka();
      return this.vehicleEntry(plaka);
    }

    /**
     * Rastgele içerideki bir aracın çıkış simülasyonu
     */
    simulateRandomExit() {
      const openSessions = this.sessions.filter((s) => s.status === 'open');
      if (openSessions.length === 0) {
        throw new Error('Şu an otoparkta çıkış yapabilecek araç yok!');
      }
      const randomSession = openSessions[Math.floor(Math.random() * openSessions.length)];
      return this.vehicleExit(randomSession.plate);
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
        this.autoTrafficInterval = setInterval(() => {
          try {
            const occ = this.getOccupancy();
            // Doluluk durumuna göre giriş veya çıkış ihtimalini ayarla
            const shouldExit = occ.occupancy_rate > 0.85 ? Math.random() < 0.8 : Math.random() < 0.45;

            if (shouldExit && occ.occupied > 10) {
              this.simulateRandomExit();
            } else if (occ.free > 0) {
              this.simulateRandomEntry();
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
            if (msg.event === 'lot.occupancy' && msg.data) {
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
              this.applyExternalOccupancy(msg.data);
              this.notifySubscribers({ event: 'external.occupancy', data: msg.data });
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
            // Port kapalıysa bir sonraki adayı dene
            this.connectWebSocketCandidates(targets, index + 1);
          } else {
            // Açık bağlantı koptuysa yerel simülasyona dön ve yeniden denemeyi planla
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
     * Canlı Gateway/Mock sayaç verisini (lot.occupancy) yerel arayüze uygular.
     * NOT: lot.occupancy bir sayaç olayıdır ve plaka bilgisi taşımaz. Aşağıdaki plaka üretimi,
     * arayüzdeki kat slot görselleştirmesini ve sayaçları beslemek için yapılan yerel bir tahminlemedir;
     * Gateway doğrudan bireysel vehicle.entry/vehicle.exit olayları yayınlamaya başladığında kaldırılacaktır.
     */
    applyExternalOccupancy(data) {
      if (!data) return;
      if (Array.isArray(data.by_floor)) {
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
                // Yerel tahminleme: Gateway'den münferit plaka gelene kadar slot doluluk illüzyonunu korur
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

