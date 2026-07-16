"""RAG Knowledge Store — индексация чанков и retrieval.

Использует:
- ChromaDB — векторная БД (локальная, без сервера)
- sentence-transformers — эмбеддинги (мультиязычная модель)

Пример:
    store = RAGStore()
    store.index_chunks(chunks)
    results = store.search("вопрос")
"""

from __future__ import annotations

from typing import Any


# Мультиязычная модель — хорошо работает с русским и английским
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


class RAGStore:
    """Обёртка над ChromaDB для индексации и retrieval."""

    def __init__(self, collection_name: str = "neuro_multi_agent", persist_dir: str = "data/rag_store") -> None:
        self._collection_name = collection_name
        self._persist_dir = persist_dir
        self._collection = None
        self._embedding_fn = None

    @property
    def collection(self) -> Any:
        """Ленивая инициализация коллекции."""
        if self._collection is None:
            import chromadb
            from chromadb.config import Settings

            client = chromadb.PersistentClient(
                path=self._persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )

            # Подключаем мультиязычную модель
            embedding_fn = self._get_embedding_fn()

            try:
                self._collection = client.get_collection(
                    self._collection_name,
                    embedding_function=embedding_fn,
                )
                print(
                    f"[rag_store] Подключена коллекция '{self._collection_name}' "
                    f"({self._collection.count()} чанков, модель: {EMBEDDING_MODEL})"
                )
            except Exception:
                self._collection = client.create_collection(
                    self._collection_name,
                    embedding_function=embedding_fn,
                    metadata={"hnsw:space": "cosine"},
                )
                print(
                    f"[rag_store] Создана новая коллекция '{self._collection_name}' "
                    f"(модель: {EMBEDDING_MODEL})"
                )

        return self._collection

    def _get_embedding_fn(self):
        """Создаёт функцию эмбеддинга на sentence-transformers."""
        if self._embedding_fn is None:
            from chromadb.utils import embedding_functions

            self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=EMBEDDING_MODEL,
            )
            print(f"[rag_store] Загружена модель: {EMBEDDING_MODEL}")
        return self._embedding_fn

    @property
    def count(self) -> int:
        try:
            return self.collection.count()
        except Exception:
            return 0

    def index_chunks(self, chunks: list[dict[str, Any]]) -> int:
        if not chunks:
            return 0

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for chunk in chunks:
            chunk_id = str(chunk.get("chunk_id", ""))
            text = str(chunk.get("text", ""))
            if not chunk_id or not text:
                continue

            ids.append(chunk_id)
            documents.append(text)
            metadatas.append(
                {
                    "source": str(chunk.get("source", "")),
                    "section": str(chunk.get("section", "")),
                    "title": str(chunk.get("title", "")),
                    **(chunk.get("metadata") or {}),
                }
            )

        if not ids:
            return 0

        self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
        print(f"[rag_store] Добавлено {len(ids)} чанков (всего: {self.collection.count()})")
        return len(ids)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if not query or self.count == 0:
            return []

        results = self.collection.query(query_texts=[query], n_results=top_k)

        formatted: list[dict[str, Any]] = []
        ids_list = results.get("ids", [[]])[0]
        docs_list = results.get("documents", [[]])[0]
        meta_list = results.get("metadatas", [[]])[0]
        dist_list = results.get("distances", [[]])[0]

        for i in range(len(ids_list)):
            formatted.append(
                {
                    "chunk_id": ids_list[i],
                    "text": docs_list[i] if i < len(docs_list) else "",
                    "source": meta_list[i].get("source", "") if i < len(meta_list) else "",
                    "section": meta_list[i].get("section", "") if i < len(meta_list) else "",
                    "title": meta_list[i].get("title", "") if i < len(meta_list) else "",
                    "score": round(1.0 - dist_list[i], 4) if i < len(dist_list) else 0.0,
                }
            )

        return formatted

    def clear(self) -> None:
        import chromadb

        client = chromadb.PersistentClient(path=self._persist_dir)
        try:
            client.delete_collection(self._collection_name)
            self._collection = None
            self._embedding_fn = None
            print(f"[rag_store] Коллекция '{self._collection_name}' удалена")
        except Exception:
            pass