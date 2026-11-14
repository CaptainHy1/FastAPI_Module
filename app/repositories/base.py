"""Generic SQLAlchemy 2.x async BaseRepository implementation."""

from typing import Any, Generic, NoReturn, TypeVar

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import messages
from app.core.constants import PG_FOREIGN_KEY_VIOLATION
from app.core.exceptions import BadRequestException, ConflictException
from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Generic async repository providing standard SQLAlchemy 2.x CRUD & pagination.

    All domain repositories inherit from BaseRepository to eliminate duplicate logic.
    """

    def __init__(self, model: type[ModelType], db: AsyncSession) -> None:
        self.model = model
        self.db = db

    @staticmethod
    def _raise_integrity_error(exc: IntegrityError) -> NoReturn:
        """Translate database IntegrityError into clean HTTP domain exceptions."""
        err_msg = str(exc.orig).lower() if exc.orig else str(exc).lower()
        pg_code = getattr(exc.orig, "sqlstate", None)
        if pg_code == PG_FOREIGN_KEY_VIOLATION or "foreign key" in err_msg:
            raise BadRequestException(message=messages.INVALID_REFERENCE) from exc
        raise ConflictException(message=messages.DATABASE_CONFLICT) from exc

    async def get_by_id(self, id_: Any) -> ModelType | None:
        """Retrieve a single record by primary key."""
        return await self.db.get(self.model, id_)

    async def list_items(
        self,
        skip: int = 0,
        limit: int = 10,
        **kwargs: Any,
    ) -> tuple[list[ModelType], int]:
        """List records with pagination."""
        count_stmt = select(func.count()).select_from(self.model)
        total_result = await self.db.execute(count_stmt)
        total = int(total_result.scalar_one())

        stmt = select(self.model).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def create(self, obj_in: CreateSchemaType, **extra_fields: Any) -> ModelType:
        """Persist a new record and handle IntegrityError safely."""
        data = obj_in.model_dump()
        data.update(extra_fields)
        db_obj = self.model(**data)
        self.db.add(db_obj)
        try:
            await self.db.commit()
            await self.db.refresh(db_obj)
        except IntegrityError as exc:
            await self.db.rollback()
            self._raise_integrity_error(exc)
        return db_obj

    async def update(
        self,
        id_: Any,
        obj_in: UpdateSchemaType,
        **kwargs: Any,
    ) -> ModelType | None:
        """Partially update an existing record by primary key."""
        db_obj = await self.get_by_id(id_)
        if not db_obj:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)
        if not update_data:
            return db_obj

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        try:
            await self.db.commit()
            await self.db.refresh(db_obj)
        except IntegrityError as exc:
            await self.db.rollback()
            self._raise_integrity_error(exc)
        return db_obj

    async def delete(self, id_: Any) -> bool:
        """Delete a record by primary key."""
        db_obj = await self.get_by_id(id_)
        if not db_obj:
            return False

        await self.db.delete(db_obj)
        await self.db.commit()
        return True
