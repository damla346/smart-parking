"""★ KADEMELİ DAKİKALIK TARİFE MOTORU — projenin kalbi. Sahip: Damla.

Saf fonksiyon: DB yok, `datetime.now()` yok, yan etki yok. Bu yüzden tamamen
parametrik testle doğrulanabilir (tests/test_pricing.py).

Şartname: "plaka giriş saatine göre dakikalık kademeli ücret tarifesi hesaplama
motorunun veritabanına entegre edilmesi". Motor burada, DB entegrasyonu
core/api/ katmanında — ikisi kasten ayrı.

Para birimi: KURUŞ cinsinden tamsayı (contracts/DECISIONS.md).
"""

from __future__ import annotations

import math
from datetime import datetime

from contracts.schemas.billing import FeeBreakdown, FeeLine, TariffRule


def sure_dakika(giris: datetime, cikis: datetime) -> int:
    """Oturum süresini dakikaya yuvarlar (yukarı — başlanan dakika tam sayılır).

    Negatif süre (çıkış girişten önce) 0 kabul edilir; veri hatasıdır, ücret doğurmaz.
    """
    saniye = (cikis - giris).total_seconds()
    if saniye <= 0:
        return 0
    return math.ceil(saniye / 60)


def hesapla_ucret(
    giris: datetime,
    cikis: datetime,
    kurallar: list[TariffRule],
    *,
    session_id: int = 0,
    plate: str = "",
) -> FeeBreakdown:
    """Kademeli tarifeye göre ücreti hesaplar ve kademe kademe dökümünü döndürür.

    Kurallar `from_min`'e göre sıralanır; her kademe yalnız kendi aralığına düşen
    dakikalar için ücretlendirilir. `to_min=None` açık uçlu son kademedir.

    Örnek: 0-30 dk ücretsiz, 30-120 dk 50 kr/dk, 120+ dk 35 kr/dk tarifesinde
    94 dakikalık oturum → (94-30) * 50 = 3200 kuruş.
    """
    dakika = sure_dakika(giris, cikis)
    if dakika == 0 or not kurallar:
        return FeeBreakdown(
            session_id=session_id, plate=plate, duration_min=dakika, total_cents=0, lines=[]
        )

    satirlar: list[FeeLine] = []
    toplam = 0

    for kural in sorted(kurallar, key=lambda k: k.from_min):
        if dakika <= kural.from_min:
            break  # bu kademeye hiç girilmemiş
        ust = dakika if kural.to_min is None else min(dakika, kural.to_min)
        kademe_dakika = ust - kural.from_min
        if kademe_dakika <= 0:
            continue
        ara_toplam = kademe_dakika * kural.price_per_min_cents
        toplam += ara_toplam
        satirlar.append(
            FeeLine(
                from_min=kural.from_min,
                to_min=kural.to_min,
                minutes=kademe_dakika,
                price_per_min_cents=kural.price_per_min_cents,
                subtotal_cents=ara_toplam,
            )
        )

    return FeeBreakdown(
        session_id=session_id,
        plate=plate,
        duration_min=dakika,
        total_cents=toplam,
        lines=satirlar,
    )


# TODO(Damla): tartışılacak uç durumlar — karara bağlanınca DECISIONS.md'ye yaz
#   - Kademeler arasında boşluk varsa (0-30, 60-120) aradaki dakikalar ne olacak?
#   - Günlük tavan ücret (max_daily_cents) olacak mı?
#   - Gece tarifesi / hafta sonu çarpanı şartnamede yok, kapsam dışı tutulabilir.
