/**
 * ★ ALTIN DOSYA TESTİ (GOLDEN FIXTURE TEST)
 * Şartname Md. 35 & Damla'nın önerdiği 'Yol 2' mimarisi.
 *
 * Bu test, web/js/tariff.js motorunu contracts/fixtures/tariff_golden.json
 * altın veri kümesine karşı test eder. pricing.py veya tariff.js motorlarından
 * herhangi biri sessizce ayrışırsa CI'da kırmızı yanarak build'i durdurur.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Yolları belirle
const rootDir = path.resolve(__dirname, '../..');
const fixturesDir = path.join(rootDir, 'contracts', 'fixtures');
const tariffsFile = path.join(fixturesDir, 'tariffs.json');
const goldenFile = path.join(fixturesDir, 'tariff_golden.json');
const tariffJsFile = path.join(rootDir, 'web', 'js', 'tariff.js');

console.log('🧪 [ALTIN DOSYA TESTİ] Başlatılıyor...');

// 1. Fixture'ları yükle
if (!fs.existsSync(tariffsFile)) {
  console.error(`❌ tariffs.json bulunamadı: ${tariffsFile}`);
  process.exit(1);
}
if (!fs.existsSync(goldenFile)) {
  console.error(`❌ tariff_golden.json bulunamadı: ${goldenFile}`);
  process.exit(1);
}

const tariffRules = JSON.parse(fs.readFileSync(tariffsFile, 'utf8'));
const goldenVectors = JSON.parse(fs.readFileSync(goldenFile, 'utf8'));

// 2. web/js/tariff.js motorunu yükle
const windowMock = {};
const tariffJsCode = fs.readFileSync(tariffJsFile, 'utf8');

try {
  const runner = new Function('window', tariffJsCode);
  runner(windowMock);
} catch (err) {
  console.error('❌ tariff.js yüklenirken hata oluştu:', err);
  process.exit(1);
}

const engine = windowMock.TariffEngine;
if (!engine || typeof engine.hesaplaDakikadan !== 'function') {
  console.error('❌ window.TariffEngine.hesaplaDakikadan bulunamadı!');
  process.exit(1);
}

// 3. Altın vektörleri test et
let passedCount = 0;
let failedCount = 0;

for (const vector of goldenVectors) {
  const { duration_min, expected_cents, description } = vector;
  const result = engine.hesaplaDakikadan(duration_min, tariffRules);

  if (result.total_cents !== expected_cents) {
    console.error(
      `❌ BAŞARISIZ: ${duration_min} dk için beklenen ${expected_cents} kr, hesaplanan ${result.total_cents} kr! (${description})`
    );
    failedCount++;
  } else {
    // Kademe dökümü toplamı kontrolü
    const linesSum = result.lines.reduce((sum, line) => sum + line.subtotal_cents, 0);
    if (linesSum !== result.total_cents) {
      console.error(
        `❌ DÖKÜM TOPLAMI HATASI: ${duration_min} dk için satır toplamı (${linesSum}) genel toplama (${result.total_cents}) uymuyor!`
      );
      failedCount++;
    } else {
      console.log(`  ✓ ${String(duration_min).padStart(3, ' ')} dk -> ${String(result.total_cents).padStart(5, ' ')} kr (${(result.total_cents / 100).toFixed(2)} TL) | ${description}`);
      passedCount++;
    }
  }
}

console.log('--------------------------------------------------');
if (failedCount > 0) {
  console.error(`💥 TEST BAŞARISIZ! Toplam: ${goldenVectors.length}, Geçen: ${passedCount}, Kalan: ${failedCount}`);
  process.exit(1);
} else {
  console.log(`✨ TÜM ALTIN TESTLER BAŞARIYLA GEÇTİ! (${passedCount}/${goldenVectors.length} test yeşil)`);
  console.log('🔒 web/js/tariff.js ile contracts/fixtures/tariff_golden.json %100 senkronize.');
  process.exit(0);
}
