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
            chunk_texts.append(chunk)  # chunker already enforces length limit
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

    def query(self, source_ids: list[str], query: str, n_results: int = 5) -> list[str]:
        """RAG query across multiple sources. Returns top-n relevant chunks."""
        if not source_ids:
            return []
        query_embedding = self.embedder.embed(query)
        
        all_results = []
        for sid in source_ids:
            collection = self._get_collection(sid)
            count = collection.count()
            if count == 0: continue
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(n_results, count),
            )
            if results["documents"] and results["distances"]:
                docs = results["documents"][0]
                dists = results["distances"][0]
                for doc, dist in zip(docs, dists):
                    all_results.append((dist, doc))
                    
        # Sort by distance (lower is closer)
        all_results.sort(key=lambda x: x[0])
        top_n = all_results[:n_results]
        return [doc for _, doc in top_n]

    def get_first_chunks(self, source_ids: list[str], n_chunks: int = 15) -> list[str]:
        """Fetch the first N chunks of the document to guarantee Table of Contents capture."""
        if not source_ids:
            return []
            
        all_docs = []
        for sid in source_ids:
            collection = self._get_collection(sid)
            ids_to_fetch = [f"{sid}_chunk_{i}" for i in range(n_chunks)]
            results = collection.get(ids=ids_to_fetch)
            
            if not results or not results["documents"]:
                continue
                
            docs_with_indices = []
            for doc_id, doc_text in zip(results["ids"], results["documents"]):
                try:
                    idx = int(doc_id.split("_chunk_")[-1])
                    docs_with_indices.append((idx, doc_text))
                except ValueError:
                    continue
                    
            docs_with_indices.sort(key=lambda x: x[0])
            all_docs.extend([doc for _, doc in docs_with_indices])
            
        return all_docs
