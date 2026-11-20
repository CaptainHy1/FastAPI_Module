"""Comment repository layer."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.task import Comment
from app.repositories.base import BaseRepository
from app.schemas.comment import CommentCreate


class CommentRepository(BaseRepository[Comment, CommentCreate, CommentCreate]):
    """Repository handling task comments persistence."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Comment, db)

    async def create_comment(
        self, task_id: int, author_id: int, content: str
    ) -> Comment:
        """Create a comment on a task and load author metadata."""
        comment = Comment(task_id=task_id, author_id=author_id, content=content)
        self.db.add(comment)
        await self.db.commit()

        # Eager load author relationship
        stmt = (
            select(Comment)
            .where(Comment.id == comment.id)
            .options(selectinload(Comment.author))
        )
        result = await self.db.execute(stmt)
        return result.scalars().one()

    async def list_by_task(
        self,
        task_id: int,
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[list[Comment], int]:
        """List comments for a task ordered chronologically with author profile."""
        stmt = (
            select(Comment)
            .where(Comment.task_id == task_id)
            .options(selectinload(Comment.author))
            .order_by(Comment.created_at.asc(), Comment.id.asc())
            .offset(skip)
            .limit(limit)
        )
        count_stmt = (
            select(func.count(Comment.id))
            .select_from(Comment)
            .where(Comment.task_id == task_id)
        )
        total_result = await self.db.execute(count_stmt)
        total = int(total_result.scalar_one())

        result = await self.db.execute(stmt)
        items = list(result.scalars().all())
        return items, total

    async def get_by_id(self, comment_id: int) -> Comment | None:
        """Fetch comment by ID with author metadata."""
        stmt = (
            select(Comment)
            .where(Comment.id == comment_id)
            .options(selectinload(Comment.author))
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
