"""SSE çerçeveleme yardımcıları.

Wire format docs/FEATURE_SPEC.md §3'te dondurulmuştur:

    event: <isim>
    data: <tek satır JSON>
    <boş satır>
"""

from __future__ import annotations

import json
from typing import Any


def sse_event(event: str, data: Any) -> str:
    """Tek bir SSE çerçevesi üretir. `data` JSON-serileştirilebilir olmalı."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"
