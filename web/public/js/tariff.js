/**
 * ★ KADEMELİ DAKİKALIK TARİFE MOTORU
 * Şartname Md. 35 & YOL_HARITASI §3
 * services/core/core/domain/pricing.py ile %100 birebir uyumludur.
 * Para birimi: KURUŞ (cents) cinsinden tam sayı.
 */

(function (window) {
  'use strict';

  // Varsayılan sözleşme tarifesi (contracts/fixtures/tariffs.json)
  const DEFAULT_TARIFF_RULES = [
    { id: 1, lot_id: 1, from_min: 0, to_min: 30, price_per_min_cents: 0 },
    { id: 2, lot_id: 1, from_min: 30, to_min: 120, price_per_min_cents: 50 },
    { id: 3, lot_id: 1, from_min: 120, to_min: 480, price_per_min_cents: 35 },
    { id: 4, lot_id: 1, from_min: 480, to_min: null, price_per_min_cents: 20 },
  ];

  /**
   * Oturum süresini dakikaya yuvarlar (yukarı — başlanan dakika tam sayılır).
   * Negatif süre 0 kabul edilir.
   */
  function sureDakika(giris, cikis) {
    const girisTime = giris instanceof Date ? giris.getTime() : new Date(giris).getTime();
    const cikisTime = cikis instanceof Date ? cikis.getTime() : new Date(cikis).getTime();
    const saniye = (cikisTime - girisTime) / 1000;
    if (saniye <= 0 || isNaN(saniye)) return 0;
    return Math.ceil(saniye / 60);
  }

  /**
   * Kademeli tarifeye göre ücreti hesaplar ve kademe kademe dökümünü döndürür.
   *
   * @param {Date|string} giris - Giriş zamanı
   * @param {Date|string} cikis - Çıkış zamanı
   * @param {Array} [kurallar] - Tarife kuralları listesi
   * @param {Object} [meta] - { sessionId, plate }
   * @returns {Object} FeeBreakdown
   */
  function hesaplaUcret(giris, cikis, kurallar = DEFAULT_TARIFF_RULES, meta = {}) {
    const dakika = sureDakika(giris, cikis);
    return hesaplaDakikadan(dakika, kurallar, meta);
  }

  /**
   * Verilen doğrudan dakika değerine göre kademeli ücret hesaplar.
   * Simülatör ve test ekranlarında doğrudan dakika sürgüsü için kullanılır.
   */
  function hesaplaDakikadan(dakika, kurallar = DEFAULT_TARIFF_RULES, meta = {}) {
    const { sessionId = 0, plate = '' } = meta;

    if (dakika <= 0 || !kurallar || kurallar.length === 0) {
      return {
        session_id: sessionId,
        plate: plate,
        duration_min: Math.max(0, dakika),
        total_cents: 0,
        total_tl: '0.00',
        lines: [],
      };
    }

    // from_min'e göre küçükten büyüğe sırala
    const siraliKurallar = [...kurallar].sort((a, b) => a.from_min - b.from_min);
    const satirlar = [];
    let toplamKurus = 0;

    for (const kural of siraliKurallar) {
      if (dakika <= kural.from_min) {
        break; // Bu kademeye hiç girilmemiş
      }

      const ustSinir = kural.to_min === null || kural.to_min === undefined
        ? dakika
        : Math.min(dakika, kural.to_min);

      const kademeDakika = ustSinir - kural.from_min;
      if (kademeDakika <= 0) continue;

      const araToplamKurus = kademeDakika * kural.price_per_min_cents;
      toplamKurus += araToplamKurus;

      satirlar.push({
        from_min: kural.from_min,
        to_min: kural.to_min,
        minutes: kademeDakika,
        price_per_min_cents: kural.price_per_min_cents,
        price_per_min_tl: (kural.price_per_min_cents / 100).toFixed(2),
        subtotal_cents: araToplamKurus,
        subtotal_tl: (araToplamKurus / 100).toFixed(2),
        label: formatKademeEtiketi(kural.from_min, kural.to_min),
      });
    }

    return {
      session_id: sessionId,
      plate: plate,
      duration_min: dakika,
      total_cents: toplamKurus,
      total_tl: (toplamKurus / 100).toFixed(2),
      lines: satirlar,
    };
  }

  function formatKademeEtiketi(fromMin, toMin) {
    if (fromMin === 0 && toMin !== null) {
      return `0 - ${toMin} dk`;
    }
    if (toMin === null || toMin === undefined) {
      return `${fromMin}+ dk`;
    }
    return `${fromMin} - ${toMin} dk`;
  }

  function formatPara(kurus) {
    if (typeof kurus !== 'number') return '0.00 ₺';
    return `${(kurus / 100).toFixed(2)} ₺`;
  }

  function formatSure(dakika) {
    if (!dakika || dakika <= 0) return '0 dk';
    const saat = Math.floor(dakika / 60);
    const kalanDk = dakika % 60;
    if (saat === 0) return `${kalanDk} dk`;
    if (kalanDk === 0) return `${saat} sa`;
    return `${saat} sa ${kalanDk} dk`;
  }

  // Dışa aç
  window.TariffEngine = {
    DEFAULT_TARIFF_RULES,
    sureDakika,
    hesaplaUcret,
    hesaplaDakikadan,
    formatKademeEtiketi,
    formatPara,
    formatSure,
  };
})(window);

