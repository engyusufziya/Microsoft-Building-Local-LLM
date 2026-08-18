"""
Foundry Local ile tek temas noktası.

Manager ve modeller modül seviyesinde önbelleklenir; bir süreç içinde model bir
kez indirilip bir kez yüklenir. Streamlit tarafında bunun üstüne ayrıca
@st.cache_resource gelir.

Smoke test:
    python -m rag.models --smoke
"""

from __future__ import annotations

import sys
from typing import Callable, List, Optional

from foundry_local_sdk import Configuration, FoundryLocalManager
from foundry_local_sdk.openai import ChatClientSettings

from . import config

_manager = None
_models: dict[str, object] = {}
_embedding_client = None
_chat_clients: dict[tuple[str, int], object] = {}


def get_manager():
    """SDK'yı bir kez başlatır ve donanım hızlandırma sağlayıcılarını kaydeder."""
    global _manager
    if _manager is not None:
        return _manager

    FoundryLocalManager.initialize(Configuration(app_name=config.APP_NAME))
    _manager = FoundryLocalManager.instance

    # Execution provider'lar kayıtlı değilse GPU varyantları CPU'ya düşer.
    # Kayıt bir kez yapılır ve kalıcıdır; ağ yoksa sessizce devam ederiz.
    try:
        if not any(ep.is_registered for ep in _manager.discover_eps()):
            _manager.download_and_register_eps()
    except Exception as exc:  # offline çalışırken beklenen durum
        print(f"  [uyarı] EP kaydı atlandı: {exc}", file=sys.stderr)

    return _manager


def _load_model(alias: str, progress_cb: Optional[Callable[[float], None]] = None):
    """Modeli indirip belleğe yükler. Aynı alias ikinci kez çağrılırsa önbellekten döner."""
    if alias in _models:
        return _models[alias]

    manager = get_manager()
    model = manager.catalog.get_model(alias)
    if model is None:
        raise RuntimeError(
            f"'{alias}' Foundry Local katalogunda bulunamadı. "
            f"`foundry model list` ile mevcut alias'ları kontrol edin."
        )

    if not model.is_cached:
        print(f"  '{alias}' indiriliyor (id={model.id})...")
        model.download(progress_cb or _print_progress)
        print()

    model.load()
    _models[alias] = model
    return model


def _print_progress(pct: float) -> None:
    print(f"\r  {pct:.1f}%", end="", flush=True)


def get_embedding_client():
    global _embedding_client
    if _embedding_client is None:
        model = _load_model(config.EMBEDDING_MODEL)
        _embedding_client = model.get_embedding_client()
    return _embedding_client


def get_chat_client(alias: Optional[str] = None, max_tokens: Optional[int] = None):
    """Chat client'ı ayarlarıyla birlikte döndürür.

    max_tokens ve düşük temperature, küçük modellerde görülen tekrar döngüsünü
    engellemek için burada merkezî olarak uygulanır.

    SDK çağrı başına ayar kabul etmiyor (`complete_chat(messages, tools=None)`),
    ayarlar client'a önbellekleme anında gömülüyor. Bu yüzden farklı token
    bütçeleri (sohbet: MAX_ANSWER_TOKENS=220 runaway kesicisi, rapor bölümü:
    ARTIFACT_SECTION_MAX_TOKENS=700) aynı client'ı paylaşamaz — önbellek anahtarı
    `(alias, max_tokens)` olarak genişletildi. `max_tokens=None` mevcut
    çağıranların davranışını birebir korur (`config.MAX_ANSWER_TOKENS`'a düşer).
    """
    alias = alias or config.CHAT_MODEL
    tokens = max_tokens or config.MAX_ANSWER_TOKENS
    key = (alias, tokens)
    if key not in _chat_clients:
        model = _load_model(alias)
        client = model.get_chat_client()
        client.settings = ChatClientSettings(
            max_tokens=tokens,
            temperature=config.TEMPERATURE,
            top_p=config.TOP_P,
        )
        _chat_clients[key] = client
    return _chat_clients[key]


def embed_texts(texts: List[str], is_query: bool = False) -> List[List[float]]:
    """Metin listesini vektörlere çevirir.

    Sorgular ve pasajlar asimetrik işlenir: Qwen3 embedding modelleri sorguya
    talimat öneki bekler, pasajlara beklemez.
    """
    if not texts:
        return []

    if is_query and config.USE_QUERY_INSTRUCTION:
        texts = [config.QUERY_INSTRUCTION + t for t in texts]

    client = get_embedding_client()
    vectors: List[List[float]] = []
    for start in range(0, len(texts), config.EMBED_BATCH_SIZE):
        batch = texts[start : start + config.EMBED_BATCH_SIZE]
        response = client.generate_embeddings(batch)
        vectors.extend(item.embedding for item in response.data)
    return vectors


def unload_all() -> None:
    """Yüklü modelleri bellekten kaldırır. Model kıyasında sırayla yükleme için gerekir."""
    global _embedding_client
    for model in _models.values():
        try:
            model.unload()
        except Exception:
            pass
    _models.clear()
    _chat_clients.clear()
    _embedding_client = None


# --------------------------------------------------------------------------- smoke


def _smoke() -> int:
    print("=== Foundry Local başlatılıyor ===")
    manager = get_manager()
    for ep in manager.discover_eps():
        print(f"  EP: {ep.name} kayıtlı={ep.is_registered}")

    print(f"\n=== Embedding modeli: {config.EMBEDDING_MODEL} ===")
    emb_model = _load_model(config.EMBEDDING_MODEL)
    print(f"  id={emb_model.id}")
    vectors = embed_texts(["RAG üç adımdan oluşur."])
    dim = len(vectors[0])
    print(f"  vektör boyutu: {dim}")

    print(f"\n=== Chat modeli: {config.CHAT_MODEL} ===")
    chat_model = _load_model(config.CHAT_MODEL)
    print(f"  id={chat_model.id}")
    client = get_chat_client()
    result = client.complete_chat(
        [
            {"role": "system", "content": "Türkçe, tek cümlede cevap ver."},
            {"role": "user", "content": "RAG'in açılımı nedir?"},
        ]
    )
    print(f"  cevap: {result.choices[0].message.content.strip()}")

    ok = dim > 0 and "-gpu" in emb_model.id and "-gpu" in chat_model.id
    print(f"\n{'BAŞARILI' if ok else 'UYARI: modellerden biri GPU varyantı değil'}")
    return 0


if __name__ == "__main__":
    if "--smoke" in sys.argv:
        raise SystemExit(_smoke())
    print(__doc__)
