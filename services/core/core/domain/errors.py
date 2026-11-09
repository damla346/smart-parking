"""Domain hataları. Sahip: Damla.

Domain katmanı HTTP bilmez; bu hataları core/main.py durum koduna çevirir.
"""


class Bulunamadi(Exception):
    """İstenen kayıt yok → 404."""


class Cakisma(Exception):
    """İstek mevcut durumla çelişiyor → 409."""
