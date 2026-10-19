"""Rastgele TR plaka üreteci. Sahip: Berat.

Format: <il 01-81><1-3 harf><2-4 rakam> — toplam 5-9 karakter.
Harf+rakam sayısı 7'yi aşmaz (örn. 34ABC12 ✓, 34ABC1234 ✗).
"""

from __future__ import annotations

import random
import string

# Türk plakalarında kullanılmayan harfler: Q, W, X
HARFLER = "".join(c for c in string.ascii_uppercase if c not in "QWX")


def rastgele_plaka(rng: random.Random | None = None) -> str:
    """Geçerli formatta rastgele TR plaka üretir.

    `rng` verilirse deterministik olur — testler bunu kullanır.
    """
    r = rng or random
    il = f"{r.randint(1, 81):02d}"
    harf_sayisi = r.choice([1, 2, 3])
    harfler = "".join(r.choice(HARFLER) for _ in range(harf_sayisi))
    # Toplam harf+rakam 5-7 olmalı
    rakam_sayisi = r.randint(2, min(4, 7 - harf_sayisi))
    rakamlar = "".join(str(r.randint(0, 9)) for _ in range(rakam_sayisi))
    return f"{il}{harfler}{rakamlar}"


def gecerli_mi(plaka: str) -> bool:
    """Plaka formatını doğrular.

    Sınırlar `rastgele_plaka` ile aynı olmalı: il 01-81, 1-3 harf, 2-4 rakam,
    harf+rakam toplamı en fazla 7.
    """
    if not 5 <= len(plaka) <= 9:
        return False
    if not plaka[:2].isdigit() or not 1 <= int(plaka[:2]) <= 81:
        return False

    govde = plaka[2:]
    harfler = "".join(c for c in govde if c.isalpha())
    rakamlar = "".join(c for c in govde if c.isdigit())
    if govde != harfler + rakamlar:  # harfler rakamlardan önce gelmeli
        return False
    if not 1 <= len(harfler) <= 3 or not 2 <= len(rakamlar) <= 4:
        return False
    if len(harfler) + len(rakamlar) > 7:
        return False
    return all(c in HARFLER for c in harfler)
