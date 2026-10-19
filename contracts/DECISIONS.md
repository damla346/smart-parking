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

## ŞABLON · Mükerrer giriş (henüz karara bağlanmadı)
Varsayım: aynı plaka açık oturumu varken tekrar giriş yaparsa eskisi otomatik kapanır
ve ücreti hesaplanır.
Yazan: — · Durum: doğrulanacak
