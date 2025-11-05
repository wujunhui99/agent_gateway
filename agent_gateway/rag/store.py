from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from .loaders import load_documents


class RAGStore:
    def __init__(
        self,
        persist_directory: str,
        embedding_model: str,
        embedding_api_key: Optional[str] = None,
        embedding_api_base: Optional[str] = None,
        chunk_size: int = 800,
        chunk_overlap: int = 80,
        collection_name: str = "agent_gateway_rag",
        search_type: str = "mmr",
        fetch_k: Optional[int] = None,
        mmr_lambda: Optional[float] = 0.5,
    ) -> None:
        self._persist_directory = persist_directory
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        self._embedding = self._build_embedding(
            embedding_model, embedding_api_key, embedding_api_base
        )
        self._collection_name = collection_name
        self._search_type = search_type
        self._fetch_k = fetch_k
        self._mmr_lambda = mmr_lambda
        db_path = Path(self._persist_directory)
        db_path.mkdir(parents=True, exist_ok=True)
        self._qdrant_client = QdrantClient(path=str(db_path))

        # Check if collection exists, create it if not
        try:
            self._qdrant_client.get_collection(collection_name=self._collection_name)
        except (ValueError, Exception):
            # Collection doesn't exist, create it
            # Get embedding dimension by creating a test embedding
            test_embedding = self._embedding.embed_query("test")
            vector_size = len(test_embedding)

            self._qdrant_client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

        self._vectorstore = QdrantVectorStore.from_existing_collection(
            embedding=self._embedding,
            collection_name=self._collection_name,
            client=self._qdrant_client,
        )

    @staticmethod
    def _build_embedding(
        model: str, api_key: Optional[str], api_base: Optional[str]
    ) -> Embeddings:
        params: Dict[str, str] = {"model": model}
        if api_key:
            params["api_key"] = api_key
        if api_base:
            params["base_url"] = api_base
        return OpenAIEmbeddings(**params)

    async def add_file(self, file_path: str, filename: str) -> Dict[str, int]:
        docs = await asyncio.to_thread(load_documents, file_path, filename)
        if not docs:
            return {"documents": 0, "chunks": 0}

        chunks = self._splitter.split_documents(docs)
        for doc in chunks:
            doc.metadata.setdefault("source", filename)

        await asyncio.to_thread(self._vectorstore.add_documents, chunks)

        return {"documents": len(docs), "chunks": len(chunks)}

    def as_retriever(self, k: int = 4) -> VectorStoreRetriever:
        search_kwargs: Dict[str, Any] = {"k": k}
        search_type = (self._search_type or "similarity").lower()

        if search_type == "mmr":
            fetch_k = self._fetch_k or max(k * 2, k)
            if fetch_k < k:
                fetch_k = k
            search_kwargs["fetch_k"] = fetch_k
            if self._mmr_lambda is not None:
                search_kwargs["lambda_mult"] = self._mmr_lambda

        return self._vectorstore.as_retriever(
            search_type=search_type,
            search_kwargs=search_kwargs,
        )


__all__ = ["RAGStore"]
