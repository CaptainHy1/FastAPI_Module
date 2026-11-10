"""Base repository interface for CRUD operations."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

T = TypeVar("T")
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")


class BaseRepository(ABC, Generic[T, CreateSchemaType, UpdateSchemaType]):
    """Abstract base repository defining standard async CRUD operations.

    Adheres to the Repository Pattern required in the internship syllabus:
    BaseRepository[ModelType, CreateSchemaType, UpdateSchemaType].
    """

    @abstractmethod
    async def get_by_id(self, id_: int) -> T | None:
        """Retrieve an entity by its integer ID."""
        raise NotImplementedError

    @abstractmethod
    async def list_items(
        self,
        skip: int = 0,
        limit: int = 10,
        **kwargs: Any,
    ) -> tuple[list[T], int]:
        """List entities with pagination and optional filters.

        Returns a tuple of (items, total_count).
        """
        raise NotImplementedError

    @abstractmethod
    async def create(self, obj_in: CreateSchemaType, **kwargs: Any) -> T:
        """Persist a new entity and return it."""
        raise NotImplementedError

    @abstractmethod
    async def update(
        self, id_: int, obj_in: UpdateSchemaType, **kwargs: Any
    ) -> T | None:
        """Update an existing entity and return the updated version."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, id_: int) -> bool:
        """Delete an entity by its integer ID.

        Returns True if deleted, False if not found.
        """
        raise NotImplementedError
