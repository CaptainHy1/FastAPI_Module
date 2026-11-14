"""Workspace and WorkspaceMember repository layer."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import messages
from app.core.constants import WorkspaceRole
from app.core.exceptions import ConflictException
from app.models.workspace import Workspace, WorkspaceMember
from app.repositories.base import BaseRepository
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate


class WorkspaceRepository(BaseRepository[Workspace, WorkspaceCreate, WorkspaceUpdate]):
    """Repository handling Workspace and WorkspaceMember persistence."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Workspace, db)

    async def create_workspace_with_owner(self, name: str, owner_id: int) -> Workspace:
        """Create a workspace and assign the creator as primary OWNER member."""
        workspace = Workspace(name=name, owner_id=owner_id)
        self.db.add(workspace)
        await self.db.flush()

        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=owner_id,
            role=WorkspaceRole.OWNER,
        )
        self.db.add(member)

        try:
            await self.db.commit()
            await self.db.refresh(workspace)
        except IntegrityError as exc:
            await self.db.rollback()
            self._raise_integrity_error(exc)

        return workspace

    async def list_user_workspaces(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 10,
        is_admin: bool = False,
    ) -> tuple[list[Workspace], int]:
        """List workspaces accessible to user (all for admin, membership for user)."""
        if is_admin:
            return await self.list_items(skip=skip, limit=limit)

        count_stmt = (
            select(func.count(Workspace.id))
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id)
        )
        total_res = await self.db.execute(count_stmt)
        total = int(total_res.scalar_one())

        stmt = (
            select(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id)
            .order_by(Workspace.id.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def get_member(
        self, workspace_id: int, user_id: int
    ) -> WorkspaceMember | None:
        """Retrieve membership record for a given user in a workspace."""
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_members(self, workspace_id: int) -> list[WorkspaceMember]:
        """List all members of a workspace including user profiles."""
        stmt = (
            select(WorkspaceMember)
            .options(selectinload(WorkspaceMember.user))
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.user_id.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add_member(
        self, workspace_id: int, user_id: int, role: WorkspaceRole
    ) -> WorkspaceMember:
        """Add a new member to a workspace."""
        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
        )
        self.db.add(member)
        try:
            await self.db.commit()
            # Eager load user relationship
            stmt = (
                select(WorkspaceMember)
                .options(selectinload(WorkspaceMember.user))
                .where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id == user_id,
                )
            )
            result = await self.db.execute(stmt)
            loaded_member = result.scalars().first()
            return loaded_member or member
        except IntegrityError as exc:
            await self.db.rollback()
            err_msg = str(exc.orig).lower() if exc.orig else str(exc).lower()
            is_dup = (
                "unique" in err_msg
                or "duplicate" in err_msg
                or "primary key" in err_msg
            )
            if is_dup:
                raise ConflictException(message=messages.MEMBER_ALREADY_EXISTS) from exc
            self._raise_integrity_error(exc)

    async def remove_member(self, workspace_id: int, user_id: int) -> bool:
        """Remove a member from a workspace."""
        member = await self.get_member(workspace_id, user_id)
        if not member:
            return False
        await self.db.delete(member)
        await self.db.commit()
        return True
