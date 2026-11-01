/**
 * ★ SMART PARKING MANAGEMENT SYSTEM — ANA UYGULAMA MANTIĞI
 * Şartname Md. 35 & YOL_HARITASI §3
 * Esra'nın Frontend Teslimatı (HTML + CSS + JavaScript)
 */

(function () {
  'use strict';

  // State ve referanslar
  let currentActiveTab = 'dashboard';
  let selectedFloorLevel = 1;
  let activeSlotFilter = 'all';
  let sessionSearchQuery = '';
  let sessionStatusFilter = 'all';
  let appStarted = false;

  function startApp() {
    if (appStarted) return;
    appStarted = true;

    initClock();
    initTabs();
    initSimulationToggle();
    initFloorPlanControls();
    initAnprControls();
    initTariffSimulator();
    initSessionsControls();
    initModals();
    updateConnectionBadge();

    // Store değişikliklerini dinle
    if (window.ParkingStore && typeof window.ParkingStore.subscribe === 'function') {
      window.ParkingStore.subscribe((payload) => {
        handleStoreUpdate(payload);
      });
    }

    // İlk çizimi yap
    renderAll();
  }

  // DOM hazır olduğunda güvenle başlat
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startApp);
  } else {
    startApp();
  }
  window.addEventListener('load', startApp);

  /* ==========================================================================
     1. SAAT VE ÜST BAR
     ========================================================================== */

  function initClock() {
    const clockEl = document.getElementById('live-clock');
    if (!clockEl) return;

    function update() {
      const now = new Date();
      const options = {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      };
      clockEl.textContent = now.toLocaleDateString('tr-TR', options);
    }
    update();
    setInterval(update, 1000);
  }

  function initSimulationToggle() {
    const toggleBtn = document.getElementById('toggle-traffic');
    const toggleSwitch = document.getElementById('toggle-switch');
    if (!toggleBtn || !toggleSwitch) return;

    toggleBtn.addEventListener('click', () => {
      const isActive = toggleSwitch.classList.toggle('active');
      const running = window.ParkingStore.toggleAutoTraffic(isActive);

      if (running) {
        showToast('Canlı trafik simülasyonu başlatıldı (5 sn periyot)', 'info');
      } else {
        showToast('Trafik simülasyonu durduruldu', 'info');
      }
    });
  }

  /* ==========================================================================
     2. SEKME (TAB) YÖNETİMİ
     ========================================================================== */

  function initTabs() {
    const tabs = document.querySelectorAll('.nav-tab');
    tabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        const target = tab.dataset.tab;
        switchTab(target);
      });
    });
  }

  function switchTab(tabId) {
    currentActiveTab = tabId;

    document.querySelectorAll('.nav-tab').forEach((t) => {
      t.classList.toggle('active', t.dataset.tab === tabId);
    });

    document.querySelectorAll('.tab-pane').forEach((p) => {
      p.classList.toggle('active', p.id === `pane-${tabId}`);
    });

    // Sekmeye özel tazelemeler
    if (tabId === 'floorplan') renderFloorPlan();
    if (tabId === 'sessions') renderSessionsTable();
    if (tabId === 'tariffs') updateTariffSimulation();
  }

  /* ==========================================================================
     3. DASHBOARD (GENEL BAKIŞ) RENDER
     ========================================================================== */

  function renderDashboard() {
    if (!window.ParkingStore) return;
    const occ = window.ParkingStore.getOccupancy();

    // İstatistik Değerleri (Ciro kaldırıldı, 4 temel metrik)
    setText('stat-total', occ.total);
    setText('stat-occupied', occ.occupied);
    setText('stat-free', occ.free);
    setText('stat-rate', `%${occ.occupancy_percent}`);

    // Gauge bar
    const gaugeFill = document.getElementById('dashboard-gauge-fill');
    if (gaugeFill) {
      gaugeFill.style.width = `${occ.occupancy_percent}%`;
    }

    // Katlar İlerleme Kartları (Düzenli & Derli Toplu)
    const floorsContainer = document.getElementById('dashboard-floors-container');
    if (floorsContainer) {
      floorsContainer.innerHTML = occ.by_floor
        .map((f) => {
          const percent = Math.round((f.occupied / f.total) * 100);
          return `
          <div class="floor-progress-card" onclick="window.App.goToFloor(${f.level})">
            <div class="floor-progress-header">
              <span class="floor-name">${f.level}. Kat Durumu</span>
              <span class="floor-counts"><strong>${f.occupied}</strong> / ${f.total} Dolu</span>
            </div>
            <div class="progress-track">
              <div class="progress-fill" style="width: ${percent}%;"></div>
            </div>
            <div class="floor-progress-footer">
              <span>Boş: <strong style="color:#059669;">${f.free}</strong></span>
              <span>Doluluk: <strong>%${percent}</strong></span>
            </div>
          </div>
        `;
        })
        .join('');
    }

    // Son Kamera Okumaları Akışı
    renderDashboardRecentLogs();
  }

  function renderDashboardRecentLogs() {
    const container = document.getElementById('dashboard-recent-logs');
    if (!container) return;

    const logs = window.ParkingStore.cameraLogs.slice(0, 5);
    if (logs.length === 0) {
      container.innerHTML = '<div class="text-muted p-3 text-center">Henüz kamera kaydı oluşmadı.</div>';
      return;
    }

    container.innerHTML = logs
      .map((log) => {
        const isEntry = log.type === 'entry';
        const saat = new Date(log.timestamp).toLocaleTimeString('tr-TR');
        return `
        <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 0; border-bottom:1px solid #f1f5f9;">
          <div style="display:flex; align-items:center; gap:10px;">
            <span style="font-size:18px;">${isEntry ? '📥' : '📤'}</span>
            <div>
              ${window.ANPR.renderPlateBadge(log.plate, { size: 'sm' })}
              <span style="font-size:11px; color:#64748b; margin-left:6px;">Slot: <strong>${log.slotCode}</strong></span>
            </div>
          </div>
          <div style="text-align:right;">
            <div style="font-size:11px; font-weight:600; color:${isEntry ? '#059669' : '#e11d48'};">
              ${isEntry ? 'Giriş Yaptı' : `Çıkış (${log.feeTL || '0.00'} ₺)`}
            </div>
            <div style="font-size:10px; color:#64748b;">${saat}</div>
          </div>
        </div>
      `;
      })
      .join('');
  }

  /* ==========================================================================
     4. KAT VE SLOT PLANI (FLOOR PLAN)
     ========================================================================== */

  function initFloorPlanControls() {
    // Kat Seçici Butonlar
    const floorBtns = document.querySelectorAll('.floor-tab-btn');
    floorBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        floorBtns.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        selectedFloorLevel = parseInt(btn.dataset.floor, 10);
        renderFloorPlan();
      });
    });

    // Filtre Butonları
    const filterBtns = document.querySelectorAll('.filter-btn');
    filterBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        filterBtns.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        activeSlotFilter = btn.dataset.filter;
        renderFloorPlan();
      });
    });
  }

  function renderFloorPlan() {
    const containerTop = document.getElementById('slots-row-top');
    const containerBottom = document.getElementById('slots-row-bottom');
    if (!containerTop || !containerBottom) return;

    const floor = window.ParkingStore.floors.find((f) => f.level === selectedFloorLevel);
    if (!floor) return;

    // Filtre uygula
    let filteredSlots = floor.slots;
    if (activeSlotFilter === 'free') {
      filteredSlots = floor.slots.filter((s) => s.status === 'free');
    } else if (activeSlotFilter === 'occupied') {
      filteredSlots = floor.slots.filter((s) => s.status === 'occupied');
    } else if (activeSlotFilter !== 'all') {
      filteredSlots = floor.slots.filter((s) => s.type === activeSlotFilter);
    }

    // İki sıraya böl (üst sıra 1-20, alt sıra 21-40 gibi)
    const topSlots = filteredSlots.filter((_, idx) => idx % 2 === 0);
    const bottomSlots = filteredSlots.filter((_, idx) => idx % 2 === 1);

    containerTop.innerHTML = topSlots.map((s) => renderSlotCard(s)).join('');
    containerBottom.innerHTML = bottomSlots.map((s) => renderSlotCard(s)).join('');

    // Kat başlığı ve doluluk özeti
    const occupiedCount = floor.slots.filter((s) => s.status === 'occupied').length;
    setText('floorplan-current-title', `${floor.level}. Kat Yerleşim Planı`);
    setText('floorplan-current-summary', `${occupiedCount} / ${floor.slots.length} Dolu (Boş: ${floor.slots.length - occupiedCount})`);
  }

  function renderSlotCard(slot) {
    const isOccupied = slot.status === 'occupied';
    let typeIcon = '🚗';
    let typeClass = 'standard';

    if (slot.type === 'disabled') {
      typeIcon = '♿';
      typeClass = 'disabled';
    } else if (slot.type === 'ev') {
      typeIcon = '⚡';
      typeClass = 'ev';
    } else if (slot.type === 'large') {
      typeIcon = '🚙';
      typeClass = 'large';
    }

    // Geçen süre
    let timeText = 'Müsait';
    if (isOccupied && slot.entry_at) {
      const minutes = window.TariffEngine.sureDakika(slot.entry_at, new Date());
      timeText = window.TariffEngine.formatSure(minutes);
    }

    return `
      <div class="slot-bay status-${slot.status}" onclick="window.App.openSlotModal('${slot.code}')">
        <div class="slot-top-row">
          <span class="slot-code">${slot.code}</span>
          <span class="slot-type-icon ${typeClass}" title="${slot.type.toUpperCase()}">${typeIcon}</span>
        </div>
        <div class="slot-middle">
          ${isOccupied
        ? `
              <div class="car-silhouette" style="color:${typeClass === 'ev' ? '#06b6d4' : '#f43f5e'}">🚘</div>
              <div style="margin-top:4px;">${window.ANPR.renderPlateBadge(slot.plate, { size: 'sm' })}</div>
            `
        : `<span class="free-indicator">BOŞ</span>`
      }
        </div>
        <div class="slot-bottom-row">
          <span>${isOccupied ? 'Kalış' : 'Durum'}</span>
          <span class="slot-time">${timeText}</span>
        </div>
      </div>
    `;
  }

  /* ==========================================================================
     5. PLAKA TANIMA (ANPR) SİMÜLASYONU
     ========================================================================== */

  function initAnprControls() {
    const inputPlate = document.getElementById('anpr-manual-plate');
    const platePreview = document.getElementById('anpr-plate-preview');
    const btnRandomEntry = document.getElementById('btn-random-entry');
    const btnRandomExit = document.getElementById('btn-random-exit');
    const btnManualEntry = document.getElementById('btn-manual-entry');
    const btnManualExit = document.getElementById('btn-manual-exit');
    const btnSimulateError = document.getElementById('btn-simulate-error');

    // Plaka yazıldıkça önizlemeyi güncelle
    if (inputPlate && platePreview) {
      inputPlate.addEventListener('input', (e) => {
        const val = e.target.value.toUpperCase();
        inputPlate.value = val;
        platePreview.innerHTML = window.ANPR.renderPlateBadge(val || '34ABC123', { size: 'lg' });
      });
    }

    // Rastgele Giriş
    if (btnRandomEntry) {
      btnRandomEntry.addEventListener('click', () => {
        try {
          flashCameraTarget('success');
          const result = window.ParkingStore.simulateRandomEntry();
          showToast(`Plaka Tanındı: ${window.ANPR.formatPlaka(result.slot.plate)} ➔ Slot: ${result.slot.code}`, 'success');
        } catch (err) {
          showToast(err.message, 'danger');
        }
      });
    }

    // Rastgele Çıkış
    if (btnRandomExit) {
      btnRandomExit.addEventListener('click', () => {
        try {
          flashCameraTarget('danger');
          const breakdown = window.ParkingStore.simulateRandomExit();
          openReceiptModal(breakdown);
        } catch (err) {
          showToast(err.message, 'danger');
        }
      });
    }

    // Manuel Giriş
    if (btnManualEntry && inputPlate) {
      btnManualEntry.addEventListener('click', () => {
        const plaka = inputPlate.value.trim();
        if (!plaka) {
          showToast('Lütfen önce bir plaka yazın!', 'danger');
          return;
        }
        try {
          flashCameraTarget('success');
          const result = window.ParkingStore.vehicleEntry(plaka);
          inputPlate.value = '';
          showToast(`Giriş Başarılı: ${window.ANPR.formatPlaka(result.slot.plate)} ➔ Slot: ${result.slot.code}`, 'success');
        } catch (err) {
          showToast(err.message, 'danger');
        }
      });
    }

    // Manuel Çıkış
    if (btnManualExit && inputPlate) {
      btnManualExit.addEventListener('click', () => {
        const plaka = inputPlate.value.trim();
        if (!plaka) {
          showToast('Lütfen önce bir plaka yazın!', 'danger');
          return;
        }
        try {
          flashCameraTarget('danger');
          const breakdown = window.ParkingStore.vehicleExit(plaka);
          inputPlate.value = '';
          openReceiptModal(breakdown);
        } catch (err) {
          showToast(err.message, 'danger');
        }
      });
    }

    // Hata Senaryosu (Okunamayan Plaka)
    if (btnSimulateError) {
      btnSimulateError.addEventListener('click', () => {
        flashCameraTarget('error');
        window.ParkingStore.addCameraLog({
          type: 'error',
          plate: '?? *** ??',
          slotCode: '—',
          timestamp: new Date().toISOString(),
          confidence: '0.28',
          message: 'anpr.read_failed: Çamurlu veya aşınmış plaka, optik doğrulama başarısız.',
        });
        showToast('ANPR Uyarısı: Plaka net okunamadı (Düşük Güvenilirlik %28)', 'danger');
        renderAnprLogTable();
      });
    }
  }

  function flashCameraTarget(type) {
    const target = document.querySelector('.viewfinder-target');
    if (!target) return;
    target.style.transition = 'all 0.15s ease';
    target.style.transform = 'scale(1.05)';
    setTimeout(() => {
      target.style.transform = 'scale(1)';
    }, 250);
  }

  function renderAnprLogTable() {
    const tbody = document.getElementById('anpr-log-table-body');
    if (!tbody) return;

    const logs = window.ParkingStore.cameraLogs;
    if (logs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted p-4">Henüz kamera olayı kaydedilmedi.</td></tr>';
      return;
    }

    tbody.innerHTML = logs
      .map((log) => {
        const isEntry = log.type === 'entry';
        const isError = log.type === 'error';
        const saat = new Date(log.timestamp).toLocaleTimeString('tr-TR');

        return `
        <tr>
          <td>${saat}</td>
          <td>
            <span class="status-tag ${isEntry ? 'active' : isError ? 'closed' : 'active'}" style="${isError ? 'background:rgba(244,63,94,0.15); color:#f43f5e;' : ''
          }">
              ${isEntry ? 'Giriş Kapısı' : isError ? 'Hata / Red' : 'Çıkış Kapısı'}
            </span>
          </td>
          <td>${isError ? '<span style="font-family:monospace; color:#f43f5e;">OKUNAMADI</span>' : window.ANPR.renderPlateBadge(log.plate, { size: 'sm' })}</td>
          <td style="font-family:monospace;">${log.slotCode}</td>
          <td>
            <span style="font-size:11px; color:#10b981; font-weight:600;">%${Math.round(parseFloat(log.confidence) * 100)}</span>
            <span style="font-size:11px; color:#94a3b8; margin-left:6px;">${log.message}</span>
          </td>
        </tr>
      `;
      })
      .join('');
  }

  /* ==========================================================================
     6. KADEMELİ TARİFE VE İNTERAKTİF HESAPLAMA KONSOLU
     ========================================================================== */

  function initTariffSimulator() {
    const slider = document.getElementById('calc-slider');
    const inputHours = document.getElementById('calc-input-hours');
    const inputMins = document.getElementById('calc-input-mins');
    const presets = document.querySelectorAll('.preset-chip');

    // Sürgü değiştiğinde
    if (slider) {
      slider.addEventListener('input', (e) => {
        const totalMin = parseInt(e.target.value, 10);
        syncTimeInputs(totalMin);
        updateTariffSimulation(totalMin);
      });
    }

    // Saat kutusu değiştiğinde
    if (inputHours) {
      inputHours.addEventListener('input', () => {
        const h = Math.max(0, parseInt(inputHours.value, 10) || 0);
        const m = Math.max(0, Math.min(59, parseInt(inputMins ? inputMins.value : 0, 10) || 0));
        const total = Math.min(1440, h * 60 + m);
        if (slider) slider.value = total;
        updateTariffSimulation(total);
      });
    }

    // Dakika kutusu değiştiğinde
    if (inputMins) {
      inputMins.addEventListener('input', () => {
        const h = Math.max(0, parseInt(inputHours ? inputHours.value : 0, 10) || 0);
        const m = Math.max(0, Math.min(59, parseInt(inputMins.value, 10) || 0));
        const total = Math.min(1440, h * 60 + m);
        if (slider) slider.value = total;
        updateTariffSimulation(total);
      });
    }

    // Hızlı seçim butonları
    presets.forEach((chip) => {
      chip.addEventListener('click', () => {
        presets.forEach((c) => c.classList.remove('active'));
        chip.classList.add('active');
        const minutes = parseInt(chip.dataset.minutes, 10);
        if (slider) slider.value = minutes;
        syncTimeInputs(minutes);
        updateTariffSimulation(minutes);
      });
    });

    // Başlangıç değeri: 94 dakika (1 sa 34 dk)
    syncTimeInputs(94);
    updateTariffSimulation(94);
  }

  function syncTimeInputs(totalMinutes) {
    const inputHours = document.getElementById('calc-input-hours');
    const inputMins = document.getElementById('calc-input-mins');
    const hours = Math.floor(totalMinutes / 60);
    const mins = totalMinutes % 60;
    if (inputHours) inputHours.value = hours;
    if (inputMins) inputMins.value = mins;
  }

  function updateTariffSimulation(customMinutes) {
    const slider = document.getElementById('calc-slider');
    const minutes = customMinutes !== undefined ? customMinutes : slider ? parseInt(slider.value, 10) : 94;

    const breakdown = window.TariffEngine.hesaplaDakikadan(minutes, window.ParkingStore.tariffs);

    setText('sim-duration-display', window.TariffEngine.formatSure(minutes));
    setText('sim-total-due', `${breakdown.total_tl} ₺`);

    const tbody = document.getElementById('sim-breakdown-tbody');
    if (!tbody) return;

    if (breakdown.lines.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td><strong>0 - 30 dk (Ücretsiz Dönem)</strong></td>
          <td>${minutes} dk</td>
          <td>0.00 ₺ / dk</td>
          <td style="font-weight:700; color:#059669; text-align:right;">0.00 ₺ (Ücretsiz)</td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = breakdown.lines
      .map((line) => {
        const isFree = line.price_per_min_cents === 0;
        return `
        <tr>
          <td><strong>${line.label}</strong></td>
          <td>${line.minutes} dakika</td>
          <td style="color:#64748b;">${line.price_per_min_tl} ₺ / dk</td>
          <td style="font-weight:700; color:${isFree ? '#059669' : '#0f172a'}; text-align:right;">
            ${isFree ? '0.00 ₺' : `${line.subtotal_tl} ₺`}
          </td>
        </tr>
      `;
      })
      .join('');
  }

  /* ==========================================================================
     7. GİRİŞ-ÇIKIŞ OTURUM KAYITLARI (SESSION LOGS)
     ========================================================================== */

  function initSessionsControls() {
  const searchInput = document.getElementById('session-search-input');
  const statusSelect = document.getElementById('session-status-filter');
  const exportBtn = document.getElementById('btn-export-csv');

  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      sessionSearchQuery = e.target.value.trim().toUpperCase();
      renderSessionsTable();
    });
  }

  if (statusSelect) {
    statusSelect.addEventListener('change', (e) => {
      sessionStatusFilter = e.target.value;
      renderSessionsTable();
    });
  }

  if (exportBtn) {
    exportBtn.addEventListener('click', exportSessionsCsv);
  }
}

function renderSessionsTable() {
  const tbody = document.getElementById('sessions-table-body');
  if (!tbody) return;

  let list = window.ParkingStore.sessions;

  // Filtreleme
  if (sessionStatusFilter !== 'all') {
    list = list.filter((s) => s.status === sessionStatusFilter);
  }
  if (sessionSearchQuery) {
    list = list.filter((s) => s.plate.includes(sessionSearchQuery) || s.slot_code.includes(sessionSearchQuery));
  }

  if (list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted p-4">Kayıt bulunamadı.</td></tr>';
    return;
  }

  tbody.innerHTML = list
    .map((session) => {
      const isOpen = session.status === 'open';
      const entryDate = new Date(session.entry_at).toLocaleString('tr-TR');
      const exitDate = session.exit_at ? new Date(session.exit_at).toLocaleString('tr-TR') : '—';

      // Süre ve Tutar
      let durationText = '—';
      let feeText = '—';

      if (isOpen) {
        const liveMin = window.TariffEngine.sureDakika(session.entry_at, new Date());
        durationText = window.TariffEngine.formatSure(liveMin);
        const liveFee = window.TariffEngine.hesaplaDakikadan(liveMin, window.ParkingStore.tariffs);
        feeText = `${liveFee.total_tl} ₺ (Canlı)`;
      } else {
        durationText = window.TariffEngine.formatSure(session.duration_min);
        feeText = session.fee_cents !== null ? window.TariffEngine.formatPara(session.fee_cents) : '—';
      }

      return `
        <tr>
          <td>${window.ANPR.renderPlateBadge(session.plate, { size: 'sm' })}</td>
          <td style="font-family:monospace; font-weight:600;">${session.slot_code}</td>
          <td>${entryDate}</td>
          <td>${exitDate}</td>
          <td style="font-family:monospace;">${durationText}</td>
          <td style="font-weight:700; color:${isOpen ? '#60a5fa' : '#10b981'};">${feeText}</td>
          <td>
            <span class="status-tag ${isOpen ? 'active' : 'closed'}">
              ${isOpen ? '● Park Halinde' : '✓ Tamamlandı'}
            </span>
          </td>
          <td>
            ${isOpen
          ? `<button class="btn btn-secondary" style="padding:4px 8px; font-size:11px;" onclick="window.App.exitSessionPlate('${session.plate}')">Çıkış Yap</button>`
          : `<span style="font-size:11px; color:#64748b;">Kapandı</span>`
        }
          </td>
        </tr>
      `;
    })
    .join('');
}

function exportSessionsCsv() {
  const list = window.ParkingStore.sessions;
  if (list.length === 0) {
    showToast('Dışa aktarılacak kayıt yok!', 'danger');
    return;
  }

  const headers = ['ID', 'Plaka', 'Slot Kodu', 'Giris Zamani', 'Cikis Zamani', 'Sure (Dk)', 'Ucret (TL)', 'Durum'];
  const rows = list.map((s) => [
    s.id,
    s.plate,
    s.slot_code,
    s.entry_at,
    s.exit_at || '',
    s.duration_min || '',
    s.fee_cents ? (s.fee_cents / 100).toFixed(2) : '0.00',
    s.status,
  ]);

  let csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');

  const encodedUri = encodeURI(csvContent);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  link.setAttribute('download', `otopark_oturumlari_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  showToast('Oturum kayıtları CSV dosyası olarak indirildi.', 'success');
}

/* ==========================================================================
   8. MODALLAR: ÇIKIŞ FİŞİ VE SLOT DETAYI
   ========================================================================== */

function initModals() {
  // Backdrop tıklaması ile kapat
  document.querySelectorAll('.modal-backdrop').forEach((backdrop) => {
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) {
        backdrop.classList.remove('open');
      }
    });
  });

  // Kapatma butonları
  document.querySelectorAll('.modal-close-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      btn.closest('.modal-backdrop').classList.remove('open');
    });
  });
}

function openReceiptModal(breakdown) {
  const modal = document.getElementById('receipt-modal');
  if (!modal) return;

  setText('receipt-plate-box', window.ANPR.formatPlaka(breakdown.plate));
  setText('receipt-duration', `${breakdown.duration_min} dakika (${window.TariffEngine.formatSure(breakdown.duration_min)})`);
  setText('receipt-total-due', `${breakdown.total_tl} ₺`);

  const tbody = document.getElementById('receipt-lines-tbody');
  if (tbody) {
    if (breakdown.lines.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:#10b981;">İlk 30 dakika ücretsiz — Ücret yok</td></tr>';
    } else {
      tbody.innerHTML = breakdown.lines
        .map(
          (l) => `
          <tr class="receipt-row" style="font-size:12px;">
            <td class="receipt-label">${l.label}</td>
            <td style="text-align:center;">${l.minutes} dk</td>
            <td style="text-align:center;">${l.price_per_min_tl} ₺</td>
            <td style="text-align:right; font-weight:700;">${l.subtotal_tl} ₺</td>
          </tr>
        `
        )
        .join('');
    }
  }

  modal.classList.add('open');
}

function openSlotModal(slotCode) {
  const slot = window.ParkingStore.getAllSlots().find((s) => s.code === slotCode);
  if (!slot) return;

  const modal = document.getElementById('slot-detail-modal');
  if (!modal) return;

  setText('slot-modal-code', slot.code);
  setText('slot-modal-type', slot.type.toUpperCase());
  setText('slot-modal-floor', `${slot.floor_id}. Kat`);

  const isOccupied = slot.status === 'occupied';
  const statusBox = document.getElementById('slot-modal-status-box');
  const actionsBox = document.getElementById('slot-modal-actions-box');

  if (isOccupied) {
    const minutes = window.TariffEngine.sureDakika(slot.entry_at, new Date());
    const fee = window.TariffEngine.hesaplaDakikadan(minutes, window.ParkingStore.tariffs);

    statusBox.innerHTML = `
        <div style="background:#fff1f2; padding:16px; border-radius:8px; border:1px solid #fecdd3;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <span style="color:#64748b; font-size:12px;">Park Eden Araç:</span>
            ${window.ANPR.renderPlateBadge(slot.plate, { size: 'md' })}
          </div>
          <div style="font-size:12px; display:flex; justify-content:space-between; margin-bottom:6px;">
            <span style="color:#64748b;">Giriş Saati:</span>
            <span style="font-weight:600; color:#1e1b4b;">${new Date(slot.entry_at).toLocaleTimeString('tr-TR')}</span>
          </div>
          <div style="font-size:12px; display:flex; justify-content:space-between; margin-bottom:6px;">
            <span style="color:#64748b;">Geçen Süre:</span>
            <span style="font-family:monospace; font-weight:700; color:#1e1b4b;">${window.TariffEngine.formatSure(minutes)}</span>
          </div>
          <div style="font-size:13px; display:flex; justify-content:space-between; border-top:1px dashed #cbd5e1; padding-top:8px; margin-top:8px;">
            <span style="color:#64748b; font-weight:600;">Anlık Biriken Ücret:</span>
            <span style="color:#059669; font-weight:800; font-size:16px;">${fee.total_tl} ₺</span>
          </div>
        </div>
      `;

    actionsBox.innerHTML = `
        <button class="btn btn-danger" onclick="window.App.exitSlotVehicle('${slot.plate}')">
          🚗 Bu Aracı Çıkart ve Ücreti Hesapla
        </button>
      `;
  } else {
    statusBox.innerHTML = `
        <div style="background:#ecfdf5; border:1px solid #a7f3d0; border-radius:8px; padding:16px; text-align:center;">
          <span style="color:#059669; font-weight:700; font-size:16px;">Bu Park Yeri Boş</span>
          <p style="color:#64748b; font-size:12px; margin-top:4px;">Aşağıdan hızlıca plaka atayarak araç park edebilirsiniz.</p>
        </div>
        <div style="margin-top:16px;">
          <label style="font-size:12px; color:#475569; display:block; margin-bottom:6px;">Park Edecek Plaka:</label>
          <input type="text" id="slot-modal-plate-input" class="input-plate" value="${window.ANPR.rastgelePlaka()}" placeholder="34ABC123" />
        </div>
      `;

    actionsBox.innerHTML = `
        <button class="btn btn-success" onclick="window.App.parkVehicleToSlot('${slot.code}')">
          🅿️ Bu Slota Park Et
        </button>
      `;
  }

  modal.classList.add('open');
}

/* ==========================================================================
   9. TOAST BİLDİRİMLERİ & YARDIMCILAR
   ========================================================================== */

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  const icon = type === 'success' ? '✅' : type === 'danger' ? '⚠️' : 'ℹ️';

  toast.innerHTML = `
      <span style="font-size:16px;">${icon}</span>
      <div style="flex:1;">${message}</div>
    `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(40px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function handleStoreUpdate(payload) {
  if (payload && payload.event === 'connection.change') {
    updateConnectionBadge(payload);
  }
  renderAll();
}

function updateConnectionBadge(payload) {
  const badge = document.getElementById('connection-status-badge');
  const textEl = document.getElementById('connection-status-text');
  if (!badge || !textEl) return;

  const status = payload ? payload.status : (window.ParkingStore ? window.ParkingStore.connectionStatus : 'simulated');
  badge.className = 'status-badge';

  if (status === 'connected_gateway') {
    badge.classList.add('connected');
    textEl.textContent = 'Canlı Gateway (8000)';
    badge.title = "Berat'ın Gateway servisine bağlı (ws://localhost:8000/ws/occupancy)";
  } else if (status === 'connected_mock') {
    badge.classList.add('connected');
    badge.classList.add('mock');
    textEl.textContent = 'Mock Gateway (8100)';
    badge.title = 'Mock Gateway servisine bağlı (ws://localhost:8100/ws/occupancy)';
  } else {
    badge.classList.add('simulated');
    textEl.textContent = 'Yerel Simülasyon';
    badge.title = 'Backend kapalı; yerel simülatör devrede (8000 ve 8100 portları taranıyor)';
  }
}

function renderAll() {
  renderDashboard();
  renderFloorPlan();
  renderAnprLogTable();
  renderSessionsTable();
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

/* ==========================================================================
   10. GLOBAL WINDOW.APP KÖPRÜSÜ
   ========================================================================== */

window.App = {
  goToFloor(level) {
    selectedFloorLevel = level;
    switchTab('floorplan');
    const btn = document.querySelector(`.floor-tab-btn[data-floor="${level}"]`);
    if (btn) btn.click();
  },

  openSlotModal(code) {
    openSlotModal(code);
  },

  exitSlotVehicle(plate) {
    document.getElementById('slot-detail-modal').classList.remove('open');
    try {
      const breakdown = window.ParkingStore.vehicleExit(plate);
      openReceiptModal(breakdown);
    } catch (err) {
      showToast(err.message, 'danger');
    }
  },

  parkVehicleToSlot(slotCode) {
    const input = document.getElementById('slot-modal-plate-input');
    const plate = input ? input.value.trim() : '';
    document.getElementById('slot-detail-modal').classList.remove('open');

    try {
      const result = window.ParkingStore.vehicleEntry(plate, { slotCode: slotCode });
      showToast(`Araç başarıyla park edildi: ${window.ANPR.formatPlaka(result.slot.plate)}`, 'success');
    } catch (err) {
      showToast(err.message, 'danger');
    }
  },

  exitSessionPlate(plate) {
    try {
      const breakdown = window.ParkingStore.vehicleExit(plate);
      openReceiptModal(breakdown);
    } catch (err) {
      showToast(err.message, 'danger');
    }
  },
};
}) ();

