"""Uçtan uca senaryo — HAVUZ GÖREVİ #2 (BACKLOG.md).

Cuma entegrasyon seansının otomatikleştirilmiş hali (YOL_HARITASI.md §13):
    araç girer → slot dolar → WS olayı gelir → araç çıkar → ücret hesaplanır → DB'ye yazılır

USE_MOCK=false ile koşar; postgres + redis + core + gateway ayakta olmalı.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Havuz görevi #2 — henüz çekilmedi")


def test_giris_cikis_ucret_zinciri() -> None:
    raise NotImplementedError
