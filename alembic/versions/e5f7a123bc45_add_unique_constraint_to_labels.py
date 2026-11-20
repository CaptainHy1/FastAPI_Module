"""Add unique constraint to labels

Revision ID: e5f7a123bc45
Revises: dc4b15463907
Create Date: 2026-11-20 09:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f7a123bc45"
down_revision: str | Sequence[str] | None = "dc4b15463907"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("labels", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_labels_project_id_name", ["project_id", "name"]
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("labels", schema=None) as batch_op:
        batch_op.drop_constraint("uq_labels_project_id_name", type_="unique")
