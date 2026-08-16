"""rag/models.py::get_chat_client — bölüm başına token bütçesi (FEATURE_SPEC §10.9).

Foundry Local'a HİÇ dokunulmaz: `rag.models._load_model` monkeypatch'lenir,
gerçek model yüklenmez. Tek amaç: önbellek anahtarının artık `(alias,
max_tokens)` olduğunu ve `max_tokens=None`'ın `config.MAX_ANSWER_TOKENS`'a
düştüğünü doğrulamak -- `client.settings.max_tokens` gömülü kalıyor, bu yüzden
farklı bütçeler ayrı client gerektiriyor (bkz. models.py docstring'i).
"""

from __future__ import annotations

from rag import config, models


class _FakeModel:
    """`_load_model`'in döndürdüğü şeyin yerine geçer; her çağrıda yeni bir
    sahte chat client üretir ki client kimliği önbellekleme davranışını
    ele versin."""

    def get_chat_client(self):
        return _FakeChatClient()


class _FakeChatClient:
    settings = None


def test_get_chat_client_farkli_max_tokens_ayri_onbellek_girdisi(monkeypatch):
    monkeypatch.setattr(models, "_load_model", lambda alias, progress_cb=None: _FakeModel())
    models._chat_clients.clear()

    client_default = models.get_chat_client()
    client_700 = models.get_chat_client(max_tokens=700)

    assert client_default is not client_700
    assert client_default.settings.max_tokens == config.MAX_ANSWER_TOKENS
    assert client_700.settings.max_tokens == 700
    assert (config.CHAT_MODEL, config.MAX_ANSWER_TOKENS) in models._chat_clients
    assert (config.CHAT_MODEL, 700) in models._chat_clients


def test_get_chat_client_none_mevcut_davranisa_dusuyor(monkeypatch):
    monkeypatch.setattr(models, "_load_model", lambda alias, progress_cb=None: _FakeModel())
    models._chat_clients.clear()

    client_none = models.get_chat_client()
    client_explicit = models.get_chat_client(max_tokens=config.MAX_ANSWER_TOKENS)

    # max_tokens=None ile config.MAX_ANSWER_TOKENS'ı açıkça vermek aynı
    # önbellek girdisine düşmeli -- davranış birebir aynı.
    assert client_none is client_explicit
