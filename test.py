"""
phi-4-mini için GERÇEKÇİ RAG testi.
Önceki test açık uçlu genel bilgi sorusu sordu (halüsinasyon riski yüksek).
Bu test, gerçek pipeline'daki gibi model'e bağlam (context) veriyor ve
sadece o bağlama dayanmasını zorluyor. Ayrıca tekrar döngüsünü önlemek için
üretim uzunluğu sınırlanıyor.
"""

from foundry_local_sdk import Configuration, FoundryLocalManager

# Gerçek RAG'de bu, SQLite'tan çekilen top-k chunk olacak.
# Şimdilik elle yazılmış kısa bir bağlam.
CONTEXT = """
Retrieval-Augmented Generation (RAG), bir dil modelinin cevap üretmeden önce
ilgili belgeleri aramasını ve bulduğu bilgiyi cevaba dahil etmesini sağlayan
bir yöntemdir. Üç adımdan oluşur: önce soru ile ilgili metin parçaları
belge veritabanından bulunur (retrieval), bulunan metin modelin girdisine
eklenir (augmentation), son olarak model bu bilgiyi kullanarak cevap üretir
(generation). Bu yöntem, modelin kendi ezberinden değil verilen kaynaktan
cevap vermesini sağlar.
"""

TEST_QUESTIONS = [
    "RAG kaç adımdan oluşur ve bu adımlar nelerdir?",
    "RAG'in amacı nedir, bağlamdaki cümleyle kısaca açıkla.",
]

SYSTEM_PROMPT = (
    "Sadece aşağıda verilen bağlamı kullanarak Türkçe cevap ver. "
    "Bağlam dışında bilgi ekleme, tekrar etme, en fazla 3 cümle kullan.\n\n"
    f"Bağlam:\n{CONTEXT}"
)


def stream_answer(chat_client, question):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    print(f"\nSoru: {question}")
    print("Cevap: ", end="", flush=True)
    token_count = 0
    max_tokens = 150  # tekrar döngüsüne karşı sert sınır
    for chunk in chat_client.complete_streaming_chat(messages):
        if not chunk.choices:
            continue
        content = chunk.choices[0].delta.content
        if content:
            print(content, end="", flush=True)
            token_count += 1
            if token_count > max_tokens:
                print(" [...kesildi, max_tokens sınırına ulaşıldı]", end="")
                break
    print()


def main():
    print("=== SDK başlatılıyor ===")
    config = Configuration(app_name="foundry_local_rag_test")
    FoundryLocalManager.initialize(config)
    manager = FoundryLocalManager.instance
    print("OK\n")

    print("=== phi-4-mini yükleniyor (önbellekte, hızlı olmalı) ===")
    chat_model = manager.catalog.get_model("phi-4-mini")
    print(f"Seçilen model ID: {chat_model.id}")
    chat_model.download(lambda p: print(f"\r  {p:.1f}%", end="", flush=True))
    print()
    chat_model.load()
    chat_client = chat_model.get_chat_client()
    print("Model yüklendi.\n")

    print("=== Bağlam verilerek (grounded) test ===")
    for q in TEST_QUESTIONS:
        stream_answer(chat_client, q)

    chat_model.unload()
    print("\nModel bellekten kaldırıldı. Test tamamlandı.")


if __name__ == "__main__":
    main()