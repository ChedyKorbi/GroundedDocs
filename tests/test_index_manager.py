"""IndexManager tests: alias/version lifecycle + atomic swap."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.store.index import IndexManager


class FakeQdrant:
    """Duck-typed QdrantClient for IndexManager logic tests."""

    def __init__(self) -> None:
        self.collections: set[str] = set()
        self.aliases: dict[str, str] = {}

    def collection_exists(self, name: str) -> bool:
        return name in self.collections

    def create_collection(self, collection_name: str, vectors_config=None) -> None:
        self.collections.add(collection_name)

    def delete_collection(self, collection_name: str) -> None:
        self.collections.discard(collection_name)

    def get_collections(self) -> SimpleNamespace:
        return SimpleNamespace(collections=[SimpleNamespace(name=c) for c in self.collections])

    def get_aliases(self) -> SimpleNamespace:
        return SimpleNamespace(
            aliases=[
                SimpleNamespace(alias_name=name, collection_name=target)
                for name, target in self.aliases.items()
            ]
        )

    def update_collection_aliases(self, change_aliases_operations: list) -> None:
        for action in change_aliases_operations:
            create = getattr(action, "create_alias", None)
            if create is not None:
                self.aliases[create.alias_name] = create.collection_name
                self.collections.add(create.collection_name)
                continue
            delete = getattr(action, "delete_alias", None)
            if delete is not None:
                self.aliases.pop(delete.alias_name, None)


@pytest.fixture
def manager() -> IndexManager:
    return IndexManager(FakeQdrant(), base_collection="chunks", alias="chunks_alias")


def test_ensure_initial_creates_v1_and_alias(manager) -> None:
    name = manager.ensure_initial(vector_size=1024)
    assert name == "chunks-v1"
    assert manager.active_collection() == "chunks-v1"


def test_ensure_initial_is_idempotent(manager) -> None:
    manager.ensure_initial(1024)
    assert manager.ensure_initial(1024) == "chunks-v1"


def test_reindex_and_atomic_swap(manager) -> None:
    manager.ensure_initial(1024)
    new_col = manager.begin_reindex(vector_size=1024)
    assert new_col == "chunks-v2"
    assert manager.active_collection() == "chunks-v1"  # not yet active
    previous = manager.activate(new_col)
    assert previous == "chunks-v1"
    assert manager.active_collection() == "chunks-v2"


def test_versions_and_next_version(manager) -> None:
    manager.ensure_initial(1024)
    manager.begin_reindex(1024)
    assert manager.versions() == [1, 2]
    assert manager.next_version() == 3


def test_drop_refuses_active_collection(manager) -> None:
    manager.ensure_initial(1024)
    with pytest.raises(ValueError, match="refusing"):
        manager.drop_version("chunks-v1")


def test_drop_old_version_after_swap(manager) -> None:
    manager.ensure_initial(1024)
    new_col = manager.begin_reindex(1024)
    manager.activate(new_col)
    manager.drop_version("chunks-v1")
    assert "chunks-v1" not in manager.client.collections
    assert manager.versions() == [2]
