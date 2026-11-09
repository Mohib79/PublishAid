"""add_workspace_core_and_activity_logs

Revision ID: 7a9b1c2d3e4f
Revises: 2f4d0a5d0874
Create Date: 2026-11-09 18:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7a9b1c2d3e4f'
down_revision: Union[str, Sequence[str], None] = '2f4d0a5d0874'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. New columns on `projects`
    op.add_column('projects', sa.Column('research_field', sa.String(length=150), nullable=True))
    op.add_column('projects', sa.Column('status', sa.String(length=30), server_default='draft', nullable=False))
    op.add_column('projects', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.add_column('projects', sa.Column('manuscript_filename', sa.String(length=255), nullable=True))
    op.add_column('projects', sa.Column('manuscript_size_bytes', sa.BigInteger(), nullable=True))
    op.add_column('projects', sa.Column('manuscript_uploaded_at', sa.DateTime(timezone=True), nullable=True))

    # Backfill updated_at = created_at for existing rows
    op.execute("UPDATE projects SET updated_at = created_at WHERE updated_at IS NOT NULL")

    # Add CHECK constraints on `projects`
    op.create_check_constraint(
        'ck_projects_non_empty_title',
        'projects',
        sa.text("char_length(btrim(project_title)) > 0"),
    )
    op.create_check_constraint(
        'ck_projects_valid_status',
        'projects',
        sa.text("status IN ('draft', 'in_progress', 'ready_to_submit', 'submitted')"),
    )
    op.create_check_constraint(
        'ck_projects_manuscript_size_non_negative',
        'projects',
        sa.text("manuscript_size_bytes IS NULL OR manuscript_size_bytes >= 0"),
    )

    # Add Indexes on `projects`
    op.create_index('ix_projects_user_updated', 'projects', ['user_id', sa.text('updated_at DESC')])
    op.create_index('ix_projects_user_status', 'projects', ['user_id', 'status'])

    # 2. Backfill and CHECK constraint on `project_journals`
    op.execute("UPDATE project_journals SET is_shortlisted = true WHERE is_selected = true")
    op.create_check_constraint(
        'ck_project_journals_selected_implies_shortlisted',
        'project_journals',
        sa.text("NOT is_selected OR is_shortlisted"),
    )

    # 3. Create new `activity_logs` table (Audit log - Deviation D8)
    op.create_table(
        'activity_logs',
        sa.Column('log_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('project_title', sa.String(length=300), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.project_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('log_id'),
    )
    op.create_check_constraint(
        'ck_activity_logs_details_is_object',
        'activity_logs',
        sa.text("jsonb_typeof(details) = 'object'"),
    )
    op.create_index('ix_activity_logs_user_created', 'activity_logs', ['user_id', sa.text('created_at DESC')])
    op.create_index('ix_activity_logs_project_created', 'activity_logs', ['project_id', sa.text('created_at DESC')])


def downgrade() -> None:
    # 1. Drop activity_logs
    op.drop_index('ix_activity_logs_project_created', table_name='activity_logs')
    op.drop_index('ix_activity_logs_user_created', table_name='activity_logs')
    op.drop_table('activity_logs')

    # 2. Drop constraint on project_journals
    op.drop_constraint('ck_project_journals_selected_implies_shortlisted', 'project_journals', type_='check')

    # 3. Drop indexes and constraints on projects
    op.drop_index('ix_projects_user_status', table_name='projects')
    op.drop_index('ix_projects_user_updated', table_name='projects')
    op.drop_constraint('ck_projects_manuscript_size_non_negative', 'projects', type_='check')
    op.drop_constraint('ck_projects_valid_status', 'projects', type_='check')
    op.drop_constraint('ck_projects_non_empty_title', 'projects', type_='check')

    # Drop new columns from projects
    op.drop_column('projects', 'manuscript_uploaded_at')
    op.drop_column('projects', 'manuscript_size_bytes')
    op.drop_column('projects', 'manuscript_filename')
    op.drop_column('projects', 'updated_at')
    op.drop_column('projects', 'status')
    op.drop_column('projects', 'research_field')

