"""Index versioning and zero-downtime re-indexing.

The IndexManager owns the collection-name/alias mapping so readers always
resolve chunks through a stable alias (`groundeddocs_chunks`) while writers can
build a brand-new collection (`<base>-v2`) and atomically flip the alias —
in-flight traffic is untouched. This satisfies the PRD's versioned /
zero-downtime re-indexing requirement.
"""

from __future__ import annotations

from qdrant_client import QdrantClient, models

from app.logging import get_logger

logger = get_logger("app.store.index")


class IndexManager:
    """Manage versioned Qdrant collections behind a stable alias."""

    def __init__(self, client: QdrantClient, base_collection: str, alias: str) -> None:
        self.client = client
        self.base = base_collection
        self.alias = alias

    def ensure_initial(self, vector_size: int) -> str:
        """Create the alias + first version if the alias has no target yet."""
        active = self.active_collection()
        if active:
            return active
        name = f"{self.base}-v1"
        if not self.client.collection_exists(name):
            self.client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(
                    size=vector_size, distance=models.Distance.COSINE
                ),
            )
            logger.info("index_version_created", extra={"collection": name})
        self.client.update_collection_aliases(
            [
                models.CreateAliasOperation(
                    create_alias=models.CreateAlias(alias_name=self.alias, collection_name=name)
                )
            ]
        )
        logger.info("alias_created", extra={"alias": self.alias, "collection": name})
        return name

    def active_collection(self) -> str | None:
        """Resolve the collection currently behind the alias (None if unset)."""
        try:
            result = self.client.get_aliases()
        except Exception:  # noqa: BLE001
            return None
        for item in result.aliases:
            if getattr(item, "alias_name", None) == self.alias:
                return getattr(item, "collection_name", None)
        return None

    def begin_reindex(self, vector_size: int) -> str:
        """Create and return the name of a new (not yet aliased) version."""
        version = self.next_version()
        name = f"{self.base}-v{version}"
        if not self.client.collection_exists(name):
            self.client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(
                    size=vector_size, distance=models.Distance.COSINE
                ),
            )
        logger.info("index_version_created", extra={"collection": name})
        return name

    def activate(self, collection_name: str) -> str | None:
        """Atomically point the alias at `collection_name`; returns the old target."""
        previous = self.active_collection()
        actions: list[models.CreateAliasOperation | models.DeleteAliasOperation] = []
        if previous and previous != collection_name:
            actions.append(
                models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=self.alias))
            )
        actions.append(
            models.CreateAliasOperation(
                create_alias=models.CreateAlias(
                    alias_name=self.alias, collection_name=collection_name
                )
            )
        )
        self.client.update_collection_aliases(actions)
        logger.info(
            "alias_swapped",
            extra={"alias": self.alias, "previous": previous, "current": collection_name},
        )
        return previous

    def next_version(self) -> int:
        """Next version number given the collections present."""
        versions = self.versions()
        if not versions:
            return 1
        return max(v for v in versions) + 1

    def versions(self) -> list[int]:
        """Sorted version numbers of collections matching the base prefix."""
        collections = self.client.get_collections().collections
        numbers: list[int] = []
        prefix = f"{self.base}-v"
        for info in collections:
            if info.name.startswith(prefix):
                try:
                    numbers.append(int(info.name[len(prefix) :]))
                except ValueError:
                    continue
        return sorted(numbers)

    def drop_version(self, collection_name: str) -> None:
        """Delete a versioned collection (call only after the alias moved away)."""
        if self.active_collection() == collection_name:
            raise ValueError(f"refusing to drop the active collection: {collection_name}")
        self.client.delete_collection(collection_name)
        logger.info("index_version_dropped", extra={"collection": collection_name})
