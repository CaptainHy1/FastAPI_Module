"""Project repository layer."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ProjectStatus
from app.models.project import Project
from app.repositories.base import BaseRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectRepository(BaseRepository[Project, ProjectCreate, ProjectUpdate]):
    """Repository handling Project persistence."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Project, db)

    async def list_by_workspace(
        self,
        workspace_id: int,
        status: ProjectStatus | None = None,
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[list[Project], int]:
        """List paginated projects within a specific workspace with optional filter."""
        conditions = [Project.workspace_id == workspace_id]
        if status is not None:
            conditions.append(Project.status == status)

        count_stmt = select(func.count()).select_from(Project).where(*conditions)
        total_res = await self.db.execute(count_stmt)
        total = int(total_res.scalar_one())

        stmt = (
            select(Project)
            .where(*conditions)
            .order_by(Project.id.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total
