"""add_guideline_extractions_and_rule_sets

Revision ID: 8b1c2d3e4f5a
Revises: 7a9b1c2d3e4f
Create Date: 2026-11-11 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8b1c2d3e4f5a'
down_revision: Union[str, Sequence[str], None] = '7a9b1c2d3e4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create `guideline_extractions` table
    op.create_table(
        'guideline_extractions',
        sa.Column('extraction_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('journal_id', sa.Integer(), nullable=True),
        sa.Column('source_type', sa.String(length=10), nullable=False),
        sa.Column('source_url', sa.String(length=2048), nullable=True),
        sa.Column('final_url', sa.String(length=2048), nullable=True),
        sa.Column('source_text', sa.Text(), nullable=True),
        sa.Column('source_text_hash', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='queued', nullable=False),
        sa.Column('step', sa.String(length=20), server_default='queued', nullable=False),
        sa.Column('error_code', sa.String(length=40), nullable=True),
        sa.Column('error_message', sa.String(length=300), nullable=True),
        sa.Column('warnings', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('draft', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('llm_model', sa.String(length=100), nullable=True),
        sa.Column('prompt_version', sa.String(length=20), nullable=True),
        sa.Column('schema_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('llm_called', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('cached', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('confirmed_rule_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.project_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['journal_id'], ['journals.journal_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['confirmed_rule_id'], ['guideline_rules.rule_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('extraction_id'),
    )

    # Check constraints on `guideline_extractions`
    op.create_check_constraint(
        'ck_guideline_extractions_source_type',
        'guideline_extractions',
        sa.text("source_type IN ('url', 'text')"),
    )
    op.create_check_constraint(
        'ck_guideline_extractions_status',
        'guideline_extractions',
        sa.text("status IN ('queued', 'running', 'completed', 'failed', 'cancelled')"),
    )
    op.create_check_constraint(
        'ck_guideline_extractions_step',
        'guideline_extractions',
        sa.text("step IN ('queued', 'fetching', 'cleaning', 'extracting', 'validating', 'done')"),
    )
    op.create_check_constraint(
        'ck_guideline_extractions_tokens_non_negative',
        'guideline_extractions',
        sa.text("(input_tokens IS NULL OR input_tokens >= 0) AND (output_tokens IS NULL OR output_tokens >= 0)"),
    )
    op.create_check_constraint(
        'ck_guideline_extractions_warnings_array',
        'guideline_extractions',
        sa.text("jsonb_typeof(warnings) = 'array'"),
    )

    # Indexes on `guideline_extractions`
    op.create_index(
        'ix_guideline_extractions_user_created',
        'guideline_extractions',
        ['user_id', sa.text('created_at DESC')],
    )
    op.create_index(
        'ix_guideline_extractions_user_status',
        'guideline_extractions',
        ['user_id', 'status'],
    )
    op.create_index(
        'ix_guideline_extractions_user_hash',
        'guideline_extractions',
        ['user_id', 'source_text_hash'],
    )

    # 2. Add columns to `guideline_rules`
    op.add_column('guideline_rules', sa.Column('owner_user_id', sa.Integer(), nullable=True))
    op.add_column('guideline_rules', sa.Column('name', sa.String(length=200), server_default='Default Rules', nullable=False))
    op.add_column('guideline_rules', sa.Column('origin', sa.String(length=20), server_default='seed', nullable=False))
    op.add_column('guideline_rules', sa.Column('schema_version', sa.Integer(), server_default='1', nullable=False))
    op.add_column('guideline_rules', sa.Column('provenance', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column('guideline_rules', sa.Column('lineage_id', sa.Integer(), nullable=True))
    op.add_column('guideline_rules', sa.Column('source_text_hash', sa.String(length=64), nullable=True))
    op.add_column('guideline_rules', sa.Column('created_from_extraction_id', sa.Integer(), nullable=True))
    op.add_column('guideline_rules', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

    # Widen source_url on `guideline_rules` from String(1000) to String(2048)
    op.alter_column(
        'guideline_rules',
        'source_url',
        existing_type=sa.String(length=1000),
        type_=sa.String(length=2048),
        existing_nullable=True,
    )

    # Foreign keys on `guideline_rules`
    op.create_foreign_key(
        'fk_guideline_rules_owner_user_id',
        'guideline_rules',
        'users',
        ['owner_user_id'],
        ['user_id'],
        ondelete='CASCADE',
    )
    op.create_foreign_key(
        'fk_guideline_rules_lineage_id',
        'guideline_rules',
        'guideline_rules',
        ['lineage_id'],
        ['rule_id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_guideline_rules_created_from_extraction_id',
        'guideline_rules',
        'guideline_extractions',
        ['created_from_extraction_id'],
        ['extraction_id'],
        ondelete='SET NULL',
    )

    # Check constraints on `guideline_rules`
    op.create_check_constraint(
        'ck_guideline_rules_origin',
        'guideline_rules',
        sa.text("origin IN ('extracted', 'manual', 'seed')"),
    )
    op.create_check_constraint(
        'ck_guideline_rules_provenance_object',
        'guideline_rules',
        sa.text("jsonb_typeof(provenance) = 'object'"),
    )

    # Indexes on `guideline_rules`
    # At most one active version per lineage
    op.execute(
        "CREATE UNIQUE INDEX uq_guideline_rules_active_lineage ON guideline_rules "
        "(COALESCE(lineage_id, rule_id)) WHERE is_active = true;"
    )
    # At most one active rule set per owner and journal
    op.execute(
        "CREATE UNIQUE INDEX uq_guideline_rules_owner_journal_active ON guideline_rules "
        "(COALESCE(owner_user_id, 0), journal_id) WHERE is_active = true AND journal_id IS NOT NULL;"
    )
    op.create_index(
        'ix_guideline_rules_owner_journal_active',
        'guideline_rules',
        ['owner_user_id', 'journal_id', 'is_active'],
    )

    # 3. Add `guideline_rule_id` to `projects`
    op.add_column('projects', sa.Column('guideline_rule_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_projects_guideline_rule_id',
        'projects',
        'guideline_rules',
        ['guideline_rule_id'],
        ['rule_id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_projects_guideline_rule_id',
        'projects',
        ['guideline_rule_id'],
    )


def downgrade() -> None:
    # 3. Revert `projects`
    op.drop_index('ix_projects_guideline_rule_id', table_name='projects')
    op.drop_constraint('fk_projects_guideline_rule_id', 'projects', type_='foreignkey')
    op.drop_column('projects', 'guideline_rule_id')

    # 2. Revert `guideline_rules`
    op.drop_index('ix_guideline_rules_owner_journal_active', table_name='guideline_rules')
    op.execute("DROP INDEX IF EXISTS uq_guideline_rules_owner_journal_active;")
    op.execute("DROP INDEX IF EXISTS uq_guideline_rules_active_lineage;")
    op.drop_constraint('ck_guideline_rules_provenance_object', 'guideline_rules', type_='check')
    op.drop_constraint('ck_guideline_rules_origin', 'guideline_rules', type_='check')
    op.drop_constraint('fk_guideline_rules_created_from_extraction_id', 'guideline_rules', type_='foreignkey')
    op.drop_constraint('fk_guideline_rules_lineage_id', 'guideline_rules', type_='foreignkey')
    op.drop_constraint('fk_guideline_rules_owner_user_id', 'guideline_rules', type_='foreignkey')

    op.alter_column(
        'guideline_rules',
        'source_url',
        existing_type=sa.String(length=2048),
        type_=sa.String(length=1000),
        existing_nullable=True,
    )

    op.drop_column('guideline_rules', 'created_at')
    op.drop_column('guideline_rules', 'created_from_extraction_id')
    op.drop_column('guideline_rules', 'source_text_hash')
    op.drop_column('guideline_rules', 'lineage_id')
    op.drop_column('guideline_rules', 'provenance')
    op.drop_column('guideline_rules', 'schema_version')
    op.drop_column('guideline_rules', 'origin')
    op.drop_column('guideline_rules', 'name')
    op.drop_column('guideline_rules', 'owner_user_id')

    # 1. Revert `guideline_extractions`
    op.drop_index('ix_guideline_extractions_user_hash', table_name='guideline_extractions')
    op.drop_index('ix_guideline_extractions_user_status', table_name='guideline_extractions')
    op.drop_index('ix_guideline_extractions_user_created', table_name='guideline_extractions')
    op.drop_constraint('ck_guideline_extractions_warnings_array', 'guideline_extractions', type_='check')
    op.drop_constraint('ck_guideline_extractions_tokens_non_negative', 'guideline_extractions', type_='check')
    op.drop_constraint('ck_guideline_extractions_step', 'guideline_extractions', type_='check')
    op.drop_constraint('ck_guideline_extractions_status', 'guideline_extractions', type_='check')
    op.drop_constraint('ck_guideline_extractions_source_type', 'guideline_extractions', type_='check')
    op.drop_table('guideline_extractions')

