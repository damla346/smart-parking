# Karar Günlüğü

**Kural (YOL_HARITASI.md §7): bekleme — varsay ve not düş.**

Tasarım kararı gerektiren bir soruyla karşılaştığında kimseyi bekleme. Buraya varsayımını
yaz, kendi tarafını o varsayımla yaz, Cuma seansında 2 dakikada karara bağlanır.
Yanlış çıkarsa düzeltmesi 20 dakika; beklemek ise 2 gün.

Format:

```markdown
## YYYY-AA-GG · Kısa başlık
Varsayım: <ne varsaydın>
Yazan: <isim> · Durum: doğrulanacak | onaylandı | değişti
```

---

## 2026-10-19 · Ücret birimi
Varsayım: tüm para değerleri **kuruş cinsinden tamsayı** (`fee_cents`). Float kullanılmaz.
Yazan: Damla · Durum: onaylandı

## 2026-10-19 · Zaman dilimi
Varsayım: DB ve API'de tüm zamanlar **UTC**, ISO-8601. Yerel saate çevirme frontend'in işi.
Yazan: Damla · Durum: onaylandı

## 2026-10-19 · Açık uçlu son tarife kademesi
Varsayım: `tariff_rules.to_min = NULL` son kademeyi işaretler, sonsuza kadar geçerlidir.
Yazan: Damla · Durum: onaylandı

<!-- Yeni kararları buraya ekleyin -->

## 2026-11-01 · Frontend teknoloji yığını: vanilla
Varsayım: `web/` **saf HTML + CSS + JavaScript** ile yazılır; React/Vite/Tailwind/TS
kullanılmaz. Gerekçe: sunumda `node_modules` ve derleme zincirine bağımlı kalmamak —
`index.html` doğrudan `file://` ile açılabiliyor, çökme riski sıfırlanıyor. Sözleşme
sınırı değişmiyor: haberleşme yine `contracts/openapi.yaml` + `contracts/events.md`
üzerinden JSON ve WebSocket ile. Karar `/web/` sahibine ait (CODEOWNERS).
Takip: `src/` React iskeleti ve build yapılandırması kaldırılacak (PR #6).
Not: `file://` üzerinden `fetch()` CORS'a çarpar — REST uçları kullanılacaksa bu
avantaj kaybolur, bilinçli takas.
Yazan: Esra (kayda geçiren: Damla) · Durum: onaylandı

## 2026-11-01 · Tarife motorunun frontend kopyası
Varsayım: ücret hesabının **tek kaynağı `services/core/core/domain/pricing.py`**.
`web/js/tariff.js` onun portu olarak kalabilir, ancak aynı girdiye aynı kuruşu
döndürdüğünü kilitleyen bir test olmadan kopya tutulmaz — alternatifi
`POST /tariffs/quote` ucunu tüketmek. Gerekçe: `pricing.py`'de tavan ücret ve kademe
boşluğu halen açık; iki motor ayrışırsa ekranla veritabanı farklı toplam gösterir.
Yazan: Damla · Durum: doğrulanacak

## ŞABLON · Mükerrer giriş (henüz karara bağlanmadı)
Varsayım: aynı plaka açık oturumu varken tekrar giriş yaparsa eskisi otomatik kapanır
ve ücreti hesaplanır.
Yazan: — · Durum: doğrulanacak
