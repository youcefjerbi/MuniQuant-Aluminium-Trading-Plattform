"""Workspace TradingAgents proposal history; no Core schema changes."""
from alembic import op
import sqlalchemy as sa

revision = 'e7b120ad4310'
down_revision = 'd8317b920a11'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('trading_agent_run',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('request_key', sa.String(64), nullable=False),
        sa.Column('instrument', sa.String(64), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('active_slot', sa.String(32)),
        sa.Column('actor', sa.String(), nullable=False),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.Column('completed_at', sa.String()),
        sa.Column('inputs', sa.JSON(), nullable=False),
        sa.Column('result', sa.JSON()),
        sa.Column('error', sa.Text()),
        sa.Column('paper_decision_id', sa.String(), sa.ForeignKey('research_paper_decision.id')),
        sa.UniqueConstraint('request_key'), sa.UniqueConstraint('active_slot'), sa.UniqueConstraint('paper_decision_id'),
        sa.CheckConstraint("status IN ('queued','running','completed','failed','cancelled')", name='ck_trading_agent_run_status'))
    op.create_index('ix_trading_agent_run_created_at', 'trading_agent_run', ['created_at'])


def downgrade():
    op.drop_index('ix_trading_agent_run_created_at', table_name='trading_agent_run')
    op.drop_table('trading_agent_run')
