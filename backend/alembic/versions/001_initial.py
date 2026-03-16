"""Initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'repositories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('github_url', sa.String(length=512), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('owner', sa.String(length=255), nullable=False),
        sa.Column('default_branch', sa.String(length=100), nullable=True),
        sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('health_score', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('webhook_configured', sa.Boolean(), nullable=True),
        sa.Column('total_files_indexed', sa.Integer(), nullable=True),
        sa.Column('indexing_status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('github_url'),
    )
    op.create_index('ix_repositories_id', 'repositories', ['id'], unique=False)
    op.create_index('ix_repositories_owner_name', 'repositories', ['owner', 'name'], unique=False)

    op.create_table(
        'events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('repo_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('github_delivery_id', sa.String(length=255), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('raw_headers', sa.JSON(), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_status', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('celery_task_id', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['repo_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('github_delivery_id'),
    )
    op.create_index('ix_events_id', 'events', ['id'], unique=False)
    op.create_index('ix_events_repo_id_received_at', 'events', ['repo_id', 'received_at'], unique=False)
    op.create_index('ix_events_processing_status', 'events', ['processing_status'], unique=False)

    op.create_table(
        'pull_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('repo_id', sa.Integer(), nullable=False),
        sa.Column('github_pr_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=False),
        sa.Column('author', sa.String(length=255), nullable=False),
        sa.Column('author_avatar_url', sa.String(length=512), nullable=True),
        sa.Column('github_pr_url', sa.String(length=512), nullable=False),
        sa.Column('base_branch', sa.String(length=255), nullable=True),
        sa.Column('head_branch', sa.String(length=255), nullable=True),
        sa.Column('risk_level', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='risklevel'), nullable=True),
        sa.Column('debt_score', sa.Float(), nullable=True),
        sa.Column('blast_radius_count', sa.Integer(), nullable=True),
        sa.Column('files_changed', sa.Integer(), nullable=True),
        sa.Column('lines_added', sa.Integer(), nullable=True),
        sa.Column('lines_removed', sa.Integer(), nullable=True),
        sa.Column('analysis_json', sa.JSON(), nullable=True),
        sa.Column('github_comment_id', sa.Integer(), nullable=True),
        sa.Column('labels_applied', sa.JSON(), nullable=True),
        sa.Column('analysis_status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('merged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_stale', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['repo_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pull_requests_id', 'pull_requests', ['id'], unique=False)
    op.create_index('ix_pr_repo_id_number', 'pull_requests', ['repo_id', 'github_pr_number'], unique=True)
    op.create_index('ix_pr_risk_level', 'pull_requests', ['risk_level'], unique=False)
    op.create_index('ix_pr_created_at', 'pull_requests', ['created_at'], unique=False)

    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pr_id', sa.Integer(), nullable=False),
        sa.Column('channel', sa.String(length=50), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['pr_id'], ['pull_requests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notifications_id', 'notifications', ['id'], unique=False)

    op.create_table(
        'health_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('repo_id', sa.Integer(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('calculated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('metrics_json', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['repo_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_health_history_id', 'health_history', ['id'], unique=False)
    op.create_index('ix_health_history_repo_id_calculated_at', 'health_history', ['repo_id', 'calculated_at'], unique=False)


def downgrade() -> None:
    op.drop_table('health_history')
    op.drop_table('notifications')
    op.drop_table('pull_requests')
    op.drop_table('events')
    op.drop_table('repositories')
