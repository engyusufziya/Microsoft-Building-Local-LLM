"""
Streamlit arayüzü — PDF yükle, soru sor, kaynaklı cevap al. Tamamen offline.

    streamlit run streamlit_app.py

Modeller @st.cache_resource ile SÜREÇ BAŞINA bir kez yüklenir. Bu olmadan
Streamlit her etkileşimde script'i baştan çalıştırdığı için modeller her
soruda yeniden yüklenir ve arayüz kullanılamaz hale gelir.
"""

from __future__ import annotations

import streamlit as st

from rag import answer, config, ingest, models, ocr, store

st.set_page_config(page_title="Yerel Belge Asistanı", page_icon="📄", layout="wide")


@st.cache_resource(show_spinner=False)
def get_connection():
    """Veritabanı bağlantısı. store.connect() check_same_thread=False kullanır;
    Streamlit her yeniden çalıştırmayı farklı bir thread'de koşabilir."""
    return store.connect()


@st.cache_resource(show_spinner=False)
def warm_models(chat_model: str):
    """Embedding ve chat modellerini belleğe alır. Dönen değer önemsiz;
    amaç pahalı yüklemeyi önbelleğe almak."""
    models.get_embedding_client()
    models.get_chat_client(chat_model)
    return True


def refresh_corpus():
    """Belge kümesi değişti: embedding matrisi önbelleğini geçersiz kıl."""
    store.clear_cache()


# --------------------------------------------------------------------------- kenar çubuğu

with st.sidebar:
    st.header("Belgeler")

    uploaded = st.file_uploader(
        "PDF yükleyin", type="pdf", accept_multiple_files=True,
        help=(
            "Metin tabanlı PDF'ler doğrudan okunur. Taranmış sayfalar "
            + ("macOS Vision ile OCR'lanır." if ocr.is_available()
               else "atlanır (OCR kurulu değil).")
        ),
    )

    if uploaded and st.button("Yüklenenleri işle", type="primary", width="stretch"):
        conn = get_connection()
        warm_models(config.CHAT_MODEL)
        bar = st.progress(0.0)
        status = st.empty()
        for file in uploaded:
            try:
                result = ingest.ingest_pdf(
                    file, filename=file.name, conn=conn,
                    progress_cb=lambda pct, msg: (bar.progress(pct), status.text(f"{file.name}: {msg}")),
                )
                st.success(f"{result.filename}: {result.page_count} sayfa, {result.chunk_count} chunk")
                if result.skipped_pages:
                    reason = ("OCR de metin çıkaramadı" if ocr.is_available()
                              else "metin katmanı yok ve OCR kurulu değil")
                    st.warning(
                        f"{len(result.skipped_pages)} sayfa okunamadı ({reason}): "
                        f"{', '.join(map(str, result.skipped_pages))}"
                    )
            except Exception as exc:
                st.error(f"{file.name}: {exc}")
        bar.empty()
        status.empty()
        refresh_corpus()
        st.rerun()

    st.divider()

    conn = get_connection()
    docs = store.list_documents(conn)
    if not docs:
        st.info("Henüz belge yok. Yukarıdan PDF yükleyin.")
    else:
        total = sum(d["chunk_count"] for d in docs)
        st.caption(f"{len(docs)} belge, {total} chunk")
        for doc in docs:
            row = st.columns([5, 1])
            row[0].write(f"**{doc['filename']}**")
            row[0].caption(f"{doc['page_count']} sayfa · {doc['chunk_count']} chunk")
            if row[1].button("Sil", key=f"del_{doc['filename']}"):
                store.delete_document(conn, doc["filename"])
                refresh_corpus()
                st.rerun()

    st.divider()
    st.caption(
        f"Chat: `{config.CHAT_MODEL}`  \n"
        f"Embedding: `{config.EMBEDDING_MODEL}`  \n"
        f"top-k={config.TOP_K} · eşik={config.MIN_SCORE}  \n"
        f"OCR: {'macOS Vision' if ocr.is_available() else 'kapalı'}"
    )
    st.caption("Tüm işlem cihazda, internet bağlantısı olmadan yapılır.")


# --------------------------------------------------------------------------- ana bölüm

st.title("📄 Yerel Belge Asistanı")
st.caption("Foundry Local + RAG · sorular yalnızca yüklediğiniz belgelerden cevaplanır")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("hits"):
            with st.expander(f"Getirilen bağlam ({len(msg['hits'])} parça)"):
                for hit in msg["hits"]:
                    flag = " · OCR" if hit["via_ocr"] else ""
                    st.markdown(f"**{hit['citation']}** — benzerlik {hit['score']:.3f}{flag}")
                    st.text(hit["content"])

if not docs:
    st.info("Soru sorabilmek için önce soldaki panelden bir PDF yükleyin.")
else:
    if question := st.chat_input("Belgeleriniz hakkında bir soru sorun"):
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Modeller hazırlanıyor..."):
                warm_models(config.CHAT_MODEL)
            with st.spinner("Belgeler aranıyor ve cevap üretiliyor..."):
                result = answer.answer_query(question, conn=get_connection())

            st.markdown(result.text)
            if result.answered and result.sources:
                st.caption(" ".join(result.sources))

            hits = [
                {"citation": h.citation(), "score": h.score,
                 "content": h.content, "via_ocr": h.via_ocr}
                for h in result.hits
            ]
            if hits:
                with st.expander(f"Getirilen bağlam ({len(hits)} parça)"):
                    for hit in hits:
                        flag = " · OCR" if hit["via_ocr"] else ""
                        st.markdown(f"**{hit['citation']}** — benzerlik {hit['score']:.3f}{flag}")
                        st.text(hit["content"])

        content = result.text
        if result.answered and result.sources:
            content += f"\n\n_{' '.join(result.sources)}_"
        st.session_state.messages.append(
            {"role": "assistant", "content": content, "hits": hits}
        )
