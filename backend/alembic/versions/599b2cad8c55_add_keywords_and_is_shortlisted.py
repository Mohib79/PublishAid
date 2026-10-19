"""add_keywords_and_is_shortlisted

Revision ID: 599b2cad8c55
Revises: c2a4e91f6b10
Create Date: 2026-10-19 16:41:35.793872

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '599b2cad8c55'
down_revision: Union[str, Sequence[str], None] = 'c2a4e91f6b10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'projects',
        sa.Column(
            'keywords',
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
    )
    op.add_column(
        'project_journals',
        sa.Column(
            'is_shortlisted',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('project_journals', 'is_shortlisted')
    op.drop_column('projects', 'keywords')
