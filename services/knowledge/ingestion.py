import hashlib
import json
import uuid
from pathlib import Path
from typing import Optional
import chromadb
from chromadb.config import Settings as ChromaSettings

from config.settings import settings
from providers.embeddings.gemini import get_embedder
from services.knowledge.chunker import chunk_text
from services.knowledge.extractor_pdf import extract_pdf
from services.knowledge.extractor_url import extract_url, extract_markdown_dir
from db.database import SessionLocal
from db import models


class KnowledgeIngestionService:
    def __init__(self):
        self.embedder = get_embedder()
        self.chroma = chromadb.PersistentClient(
            path=settings.CHROMA_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def _get_collection(self, source_id: str):
        return self.chroma.get_or_create_collection(
            name=f"source_{source_id.replace('-', '_')}",
            metadata={"hnsw:space": "cosine"},
        )

    def _hash_content(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def ingest(
        self,
        name: str,
        source_type: str,  # pdf | url | markdown_dir
        path_or_url: str,
        topic_tags: list[str] | None = None,
    ) -> str:
        """
        Ingest a knowledge source. Returns source_id.
        Skips re-embedding if content hash is unchanged.
        """
        topic_tags = topic_tags or []

        # extract raw text
        if source_type == "pdf":
            raw_text = extract_pdf(path_or_url)
        elif source_type == "url":
            raw_text = extract_url(path_or_url)
        elif source_type == "markdown_dir":
            raw_text = extract_markdown_dir(path_or_url)
        else:
            raise ValueError(f"Unknown source type: {source_type}")

        content_hash = self._hash_content(raw_text)

        # check if already ingested with same hash
        db = SessionLocal()
        try:
            existing = db.query(models.KnowledgeSource).filter(
                models.KnowledgeSource.content_hash == content_hash
            ).first()
            if existing:
                print(f"Content unchanged. Reusing source: {existing.id}")
                return existing.id

            source_id = str(uuid.uuid4())
            source = models.KnowledgeSource(
                id=source_id,
                name=name,
                type=source_type,
                file_path=path_or_url if source_type != "url" else None,
                original_url=path_or_url if source_type == "url" else None,
                content_hash=content_hash,
                topic_tags=json.dumps(topic_tags),
                status="processing",
            )
            db.add(source)
            db.commit()
        finally:
            db.close()

        # chunk the text
        chunks = chunk_text(raw_text)
        print(f"Created {len(chunks)} chunks from source.")

        # embed and store in ChromaDB
        collection = self._get_collection(source_id)
        chunk_ids = []
        chunk_texts = []
        chunk_metas = []

        for i, chunk in enumerate(chunks):
            chunk_ids.append(f"{source_id}_chunk_{i}")
            chunk_texts.append(chunk[:2000])  # chromadb text limit safety
            chunk_metas.append({
                "source_id": source_id,
                "chunk_index": i,
                "topic_tags": ",".join(topic_tags),
                "char_count": len(chunk),
            })

        # embed in batches
        print("Generating embeddings...")
        embeddings = self.embedder.embed_batch(chunk_texts)

        collection.add(
            ids=chunk_ids,
            documents=chunk_texts,
            embeddings=embeddings,
            metadatas=chunk_metas,
        )

        # update DB
        db = SessionLocal()
        try:
            source = db.get(models.KnowledgeSource, source_id)
            source.chunk_count = len(chunks)
            source.status = "ready"
            db.commit()
        finally:
            db.close()

        print(f"Ingested {len(chunks)} chunks. Source ID: {source_id}")
        return source_id

    def query(self, source_id: str, query: str, n_results: int = 5) -> list[str]:
        """RAG query. Returns top-n relevant chunks."""
        collection = self._get_collection(source_id)
        query_embedding = self.embedder.embed(query)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, collection.count()),
        )
        return results["documents"][0] if results["documents"] else []
