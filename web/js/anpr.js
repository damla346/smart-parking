/**
 * ★ PLAKA TANIMA (ANPR) & PLAKA ÜRETEÇ / DOĞRULAYICI
 * Şartname Md. 35 & YOL_HARITASI §3
 * services/gateway/gateway/anpr/plate_gen.py kuralları ile %100 uyumludur.
 * Format: <il 01-81><1-3 harf><2-4 rakam> — harf+rakam 5-7 arası. Q, W, X kullanılmaz.
 */

(function (window) {
  'use strict';

  // Türk plakalarında kullanılmayan harfler: Q, W, X
  const GECERLI_HARFLER = 'ABCDEFGHJKLMNPRSTUVYZ';

  /**
   * Standartlara uygun rastgele bir TR plakası üretir.
   */
  function rastgelePlaka() {
    const ilNo = Math.floor(Math.random() * 81) + 1;
    const il = String(ilNo).padStart(2, '0');

    // 1-3 harf
    const harfSayisi = Math.floor(Math.random() * 3) + 1;
    let harfler = '';
    for (let i = 0; i < harfSayisi; i++) {
      const idx = Math.floor(Math.random() * GECERLI_HARFLER.length);
      harfler += GECERLI_HARFLER[idx];
    }

    // Harf + rakam toplamı 5-7 olmalı
    const minRakam = 2;
    const maxRakam = Math.min(4, 7 - harfSayisi);
    const rakamSayisi = Math.floor(Math.random() * (maxRakam - minRakam + 1)) + minRakam;

    let rakamlar = '';
    for (let i = 0; i < rakamSayisi; i++) {
      rakamlar += Math.floor(Math.random() * 10);
    }

    return `${il}${harfler}${rakamlar}`;
  }

  /**
   * Plaka formatını doğrular.
   */
  function plakaGecerliMi(hamPlaka) {
    if (!hamPlaka || typeof hamPlaka !== 'string') return false;
    const temiz = hamPlaka.toUpperCase().replace(/\s+/g, '');

    if (temiz.length < 5 || temiz.length > 9) return false;

    // İlk 2 hane il kodu (01-81)
    const ilKodu = parseInt(temiz.slice(0, 2), 10);
    if (isNaN(ilKodu) || ilKodu < 1 || ilKodu > 81) return false;

    const govde = temiz.slice(2);
    const harfler = govde.replace(/[^A-Z]/g, '');
    const rakamlar = govde.replace(/[^0-9]/g, '');

    // Harfler rakamlardan önce gelmeli
    if (govde !== harfler + rakamlar) return false;
    if (harfler.length < 1 || harfler.length > 3) return false;
    if (rakamlar.length < 2 || rakamlar.length > 4) return false;
    if (harfler.length + rakamlar.length > 7) return false;

    // Q, W, X kontrolü
    for (const ch of harfler) {
      if (!GECERLI_HARFLER.includes(ch)) return false;
    }

    return true;
  }

  /**
   * "34ABC789" formatını "34 ABC 789" gibi okunaklı boşluklu hâle getirir.
   */
  function formatPlaka(hamPlaka) {
    if (!hamPlaka) return '';
    const temiz = hamPlaka.toUpperCase().replace(/\s+/g, '');
    if (temiz.length < 5) return temiz;

    const il = temiz.slice(0, 2);
    const govde = temiz.slice(2);
    const harfler = govde.replace(/[^A-Z]/g, '');
    const rakamlar = govde.replace(/[^0-9]/g, '');

    if (harfler && rakamlar && govde === harfler + rakamlar) {
      return `${il} ${harfler} ${rakamlar}`;
    }
    return temiz;
  }

  /**
   * Otantik Türk Plakası HTML bileşeni üretir.
   * Sol mavi "TR" şeridi, kalın siyah plaka fontu ve kabartma çerçeve içerir.
   */
  function renderPlateBadge(plaka, opts = {}) {
    const gorunen = formatPlaka(plaka) || '—';
    const boy = opts.size === 'sm' ? 'plate-sm' : opts.size === 'lg' ? 'plate-lg' : 'plate-md';
    const cls = opts.className || '';

    return `
      <div class="tr-plate ${boy} ${cls}" title="${gorunen}">
        <div class="tr-plate-blue">
          <span class="tr-plate-flag">TR</span>
        </div>
        <div class="tr-plate-text">${gorunen}</div>
      </div>
    `;
  }

  // Dışa aç
  window.ANPR = {
    rastgelePlaka,
    plakaGecerliMi,
    formatPlaka,
    renderPlateBadge,
  };
})(window);

