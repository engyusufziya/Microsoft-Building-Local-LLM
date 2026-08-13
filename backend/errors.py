"""Ortak hata sözleşmesi (docs/FEATURE_SPEC.md §2.2).

Tüm hata gövdeleri `{"code": ..., "message": ...}` şeklindedir. `ApiError`,
FastAPI'nin `HTTPException`'ını sarar; `backend.main` içindeki exception
handler'lar bu gövdeyi doğrudan JSON'a çevirir.
"""

from __future__ import annotations

from fastapi import HTTPException


class ApiError(HTTPException):
    """`{code, message}` gövdeli standart hata.

    SSE akışları dışındaki tüm endpoint hataları bunu fırlatır. SSE akışı
    içinde oluşan hatalar (INVALID_PDF, NO_CONTENT gibi) HTTP istisnası
    olarak değil, `event: error` çerçevesi olarak yayınlanır -- HTTP başlıkları
    akış başladığında zaten 200 ile gönderilmiş olur.
    """

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(status_code=status_code, detail={"code": code, "message": message})
