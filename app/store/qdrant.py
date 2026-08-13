"""Qdrant-backed vector store.

Wraps qdrant-client behind the `VectorStore` protocol. Chunk ids are UUIDs
(see `Chunk.new`), which Qdrant accepts directly. Cosine distance is used to
match the normalized embeddings produced by the embedding service.
"""

from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient, models

from app.logging import get_logger
from app.store.base import SearchHit, VectorPoint

logger = get_logger("app.store.qdrant")


class QdrantStore:
    """Production vector store adapter."""

    def __init__(
        self,
        url: str,
        collection: str,
        vector_size: int,
        distance: models.Distance = models.Distance.COSINE,
    ) -> None:
        self.client = QdrantClient(url=url)
        self.collection = collection
        self.vector_size = vector_size
        self.distance = distance

    def ensure_collection(self) -> None:
        if self.client.collection_exists(self.collection):
            logger.info("collection_exists", extra={"collection": self.collection})
            return
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(size=self.vector_size, distance=self.distance),
        )
        logger.info(
            "collection_created",
            extra={"collection": self.collection, "vector_size": self.vector_size},
        )

    def upsert(self, points: list[VectorPoint]) -> None:
        if not points:
            return
        self.client.upsert(
            collection_name=self.collection,
            points=[
                models.PointStruct(id=point.id, vector=point.vector, payload=point.payload)
                for point in points
            ],
        )

    def search(
        self,
        vector: list[float],
        limit: int = 10,
        filter_payload: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        query_filter = None
        if filter_payload:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value),
                    )
                    for key, value in filter_payload.items()
                ]
            )
        response = self.client.query_points(
            collection_name=self.collection,
            query=vector,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )
        return [
            SearchHit(id=point.id, score=float(point.score), payload=point.payload or {})
            for point in response.points
        ]

    def count(self) -> int:
        return self.client.count(collection_name=self.collection).count

    def delete_by_document(self, document_id: str) -> int:
        selector = models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id", match=models.MatchValue(value=document_id)
                    )
                ]
            )
        )
        result = self.client.delete(collection_name=self.collection, points_selector=selector)
        logger.info("deleted_document_chunks", extra={"document_id": document_id})
        return getattr(result, "status", None) == "ok"
