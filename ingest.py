"""
Ingestion pipeline: data/ klasöründeki .md belgelerini okur, paragraf bazlı
chunk'lara böler, her chunk için embedding hesaplar ve SQLite'a yazar.

Çalıştırma:
    python ingest.py

Beklenen çıktı: "N belge -> M chunk işlendi" ve rag.db dosyasının oluşması.
"""

import glob
import json
import os
import sqlite3

from foundry_local_sdk import Configuration, FoundryLocalManager

DATA_DIR = "data"
DB_PATH = "rag.db"
MAX_WORDS_PER_CHUNK = 150  # belgeler ~250-300 kelime, bu ayar her belgeyi ~2 chunk'a böler
EMBEDDING_MODEL = "phi-4-mini"


def load_documents(data_dir):
    """data/ klasöründeki her .md dosyasını okur, (kaynak_adı, tam_metin) döndürür."""
    docs = []
    for path in sorted(glob.glob(os.path.join(data_dir, "*.md"))):
        source = os.path.basename(path)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        docs.append((source, text))
    return docs


def chunk_text(text, max_words=MAX_WORDS_PER_CHUNK):
    """
    Metni paragraflara böler (boş satırla ayrılmış), sonra ardışık paragrafları
    max_words sınırını aşmayacak şekilde gruplar. Başlık satırı (# ...) ayrı
    tutulur, chunk içeriğine katılmaz.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    # İlk paragraf başlıksa (# ile başlıyorsa) at, sadece bilgi için sakla
    paragraphs = [p for p in paragraphs if not p.startswith("#")]

    chunks = []
    current_parts = []
    current_word_count = 0

    for para in paragraphs:
        para_word_count = len(para.split())
        if current_parts and current_word_count + para_word_count > max_words:
            chunks.append(" ".join(current_parts))
            current_parts = []
            current_word_count = 0
        current_parts.append(para)
        current_word_count += para_word_count

    if current_parts:
        chunks.append(" ".join(current_parts))

    return chunks


def setup_database(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            content TEXT NOT NULL,
            embedding TEXT NOT NULL
        )
    """)
    # Her çalıştırmada temiz başla (tekrar tekrar ingest edince veri katlanmasın)
    conn.execute("DELETE FROM chunks")
    conn.commit()
    return conn


def main():
    print("=== Foundry Local SDK başlatılıyor ===")
    config = Configuration(app_name="foundry_local_rag")
    FoundryLocalManager.initialize(config)
    manager = FoundryLocalManager.instance

    print(f"=== Embedding modeli yükleniyor: {EMBEDDING_MODEL} ===")
    embedding_model = manager.catalog.get_model(EMBEDDING_MODEL)
    print(f"Seçilen model ID: {embedding_model.id}")
    embedding_model.download(lambda p: print(f"\r  {p:.1f}%", end="", flush=True))
    print()
    embedding_model.load()
    embedding_client = embedding_model.get_embedding_client()
    print("Model yüklendi.\n")

    print(f"=== Belgeler okunuyor: {DATA_DIR}/ ===")
    docs = load_documents(DATA_DIR)
    if not docs:
        print(f"UYARI: {DATA_DIR}/ klasöründe .md dosyası bulunamadı.")
        return
    print(f"{len(docs)} belge bulundu: {[d[0] for d in docs]}\n")

    print("=== Belgeler chunk'lara bölünüyor ===")
    all_chunks = []  # (source, content) tuple listesi
    for source, text in docs:
        doc_chunks = chunk_text(text)
        print(f"  {source}: {len(doc_chunks)} chunk")
        for c in doc_chunks:
            all_chunks.append((source, c))
    print(f"Toplam {len(all_chunks)} chunk oluşturuldu.\n")

    print("=== Embedding'ler hesaplanıyor (toplu) ===")
    contents = [c for _, c in all_chunks]
    response = embedding_client.generate_embeddings(contents)
    embeddings = [item.embedding for item in response.data]
    print(f"{len(embeddings)} embedding hesaplandı. Vektör boyutu: {len(embeddings[0])}\n")

    print(f"=== SQLite'a yazılıyor: {DB_PATH} ===")
    conn = setup_database(DB_PATH)
    for (source, content), embedding in zip(all_chunks, embeddings):
        conn.execute(
            "INSERT INTO chunks (source, content, embedding) VALUES (?, ?, ?)",
            (source, content, json.dumps(embedding)),
        )
    conn.commit()

    # --- TEST: satır sayısı beklenenle eşleşiyor mu? ---
    row_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(f"\n=== DOĞRULAMA ===")
    print(f"Beklenen chunk sayısı: {len(all_chunks)}")
    print(f"Veritabanındaki satır sayısı: {row_count}")
    print("BAŞARILI" if row_count == len(all_chunks) else "HATA: sayılar eşleşmiyor!")

    print("\n--- Örnek: ilk 2 chunk ---")
    for row in conn.execute("SELECT id, source, content FROM chunks LIMIT 2"):
        print(f"[{row[0]}] ({row[1]}) {row[2][:100]}...")

    conn.close()
    embedding_model.unload()
    print("\nIngestion tamamlandı.")


if __name__ == "__main__":
    main()