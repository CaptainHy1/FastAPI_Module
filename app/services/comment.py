"""Comment business logic service layer."""

from app.core import messages
from app.core.constants import UserRole, WorkspaceRole
from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.user import User
from app.repositories.comment import CommentRepository
from app.repositories.project import ProjectRepository
from app.repositories.task import TaskRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.comment import CommentCreate, CommentResponse


class CommentService:
    """Service handling task comments with authorization."""

    def __init__(
        self,
        repository: CommentRepository,
        task_repository: TaskRepository,
        project_repository: ProjectRepository,
        workspace_repository: WorkspaceRepository,
    ) -> None:
        self.repository = repository
        self.task_repository = task_repository
        self.project_repository = project_repository
        self.workspace_repository = workspace_repository

    async def _verify_task_access(self, task_id: int, user: User) -> tuple[int, int]:
        """Verify task access and return (workspace_id, project_id)."""
        task = await self.task_repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)

        project = await self.project_repository.get_by_id(task.project_id)
        if not project:
            raise NotFoundException(message=messages.PROJECT_NOT_FOUND)

        if user.role != UserRole.ADMIN:
            membership = await self.workspace_repository.get_member(
                project.workspace_id, user.id
            )
            if not membership:
                raise ForbiddenException(message=messages.NOT_WORKSPACE_MEMBER)

        return project.workspace_id, task.project_id

    async def create_comment(
        self, task_id: int, comment_in: CommentCreate, current_user: User
    ) -> CommentResponse:
        """Create a new comment on a task (any workspace member)."""
        await self._verify_task_access(task_id=task_id, user=current_user)
        comment = await self.repository.create_comment(
            task_id=task_id,
            author_id=current_user.id,
            content=comment_in.content,
        )
        return CommentResponse(
            id=comment.id,
            task_id=comment.task_id,
            author_id=comment.author_id,
            content=comment.content,
            created_at=comment.created_at,
            author_name=comment.author.full_name if comment.author else None,
            author_email=comment.author.email if comment.author else None,
        )

    async def list_comments(
        self, task_id: int, current_user: User
    ) -> list[CommentResponse]:
        """List comments for a task (workspace members or ADMIN)."""
        await self._verify_task_access(task_id=task_id, user=current_user)
        comments = await self.repository.list_by_task(task_id)
        return [
            CommentResponse(
                id=c.id,
                task_id=c.task_id,
                author_id=c.author_id,
                content=c.content,
                created_at=c.created_at,
                author_name=c.author.full_name if c.author else None,
                author_email=c.author.email if c.author else None,
            )
            for c in comments
        ]

    async def delete_comment(self, comment_id: int, current_user: User) -> None:
        """Delete a comment (only author or workspace owner or ADMIN)."""
        comment = await self.repository.get_by_id(comment_id)
        if not comment:
            raise NotFoundException(message=messages.COMMENT_NOT_FOUND)

        task = await self.task_repository.get_by_id(comment.task_id)
        if not task:
            raise NotFoundException(message=messages.TASK_NOT_FOUND)

        project = await self.project_repository.get_by_id(task.project_id)
        if not project:
            raise NotFoundException(message=messages.PROJECT_NOT_FOUND)

        is_author = comment.author_id == current_user.id
        is_admin = current_user.role == UserRole.ADMIN

        is_owner = False
        membership = await self.workspace_repository.get_member(
            project.workspace_id, current_user.id
        )
        if membership and membership.role == WorkspaceRole.OWNER:
            is_owner = True

        if not (is_author or is_owner or is_admin):
            raise ForbiddenException(message=messages.COMMENT_DELETE_PERMISSION_DENIED)

        await self.repository.delete(comment_id)
