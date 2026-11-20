"""change_review_weeks_to_float

Revision ID: 2f4d0a5d0874
Revises: 599b2cad8c55
Create Date: 2026-10-23 11:38:10.771800

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f4d0a5d0874'
down_revision: Union[str, Sequence[str], None] = '599b2cad8c55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'journals',
        'review_weeks',
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'journals',
        'review_weeks',
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
