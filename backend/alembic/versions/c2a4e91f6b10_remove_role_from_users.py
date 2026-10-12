"""remove role from users

Revision ID: c2a4e91f6b10
Revises: b83fd2b87f8a
Create Date: 2026-10-11

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c2a4e91f6b10'
down_revision: Union[str, Sequence[str], None] = 'b83fd2b87f8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop role column from users table."""
    op.drop_column('users', 'role')


def downgrade() -> None:
    """Re-add role column to users table."""
    op.add_column(
        'users',
        sa.Column(
            'role',
            sa.Enum('researcher', 'admin', name='ck_users_role', native_enum=False, create_constraint=True),
            server_default='researcher',
            nullable=False,
        )
    )
