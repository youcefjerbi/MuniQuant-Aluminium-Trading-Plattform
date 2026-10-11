"""Add isolated event chain research and paper engine"""
from alembic import op
import sqlalchemy as sa

revision = '23d0f10a556a'
down_revision = 'a7d3e19c5b42'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('paper_policy',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('settings', sa.JSON(), nullable=False),
    sa.Column('actor', sa.String(), nullable=False),
    sa.Column('created_at', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('research_event',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('external_key', sa.String(length=256), nullable=False),
    sa.Column('instrument', sa.String(length=64), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('occurred_at', sa.String(), nullable=False),
    sa.Column('known_at', sa.String(), nullable=False),
    sa.Column('recorded_at', sa.String(), nullable=False),
    sa.Column('historical', sa.Integer(), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('chain', sa.JSON(), nullable=False),
    sa.Column('features', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('external_key')
    )
    with op.batch_alter_table('research_event', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_research_event_instrument'), ['instrument'], unique=False)
        batch_op.create_index(batch_op.f('ix_research_event_known_at'), ['known_at'], unique=False)

    op.create_table('research_quote',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('external_key', sa.String(length=256), nullable=False),
    sa.Column('instrument', sa.String(length=64), nullable=False),
    sa.Column('price', sa.Text(), nullable=False),
    sa.Column('observed_at', sa.String(), nullable=False),
    sa.Column('known_at', sa.String(), nullable=False),
    sa.Column('recorded_at', sa.String(), nullable=False),
    sa.Column('source_reference', sa.Text(), nullable=False),
    sa.Column('historical', sa.Integer(), nullable=False),
    sa.CheckConstraint('CAST(price AS NUMERIC) > 0', name='ck_research_quote_positive'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('external_key')
    )
    with op.batch_alter_table('research_quote', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_research_quote_instrument'), ['instrument'], unique=False)

    op.create_table('research_outcome',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('event_id', sa.String(), nullable=False),
    sa.Column('entry_quote_id', sa.String(), nullable=False),
    sa.Column('exit_quote_id', sa.String(), nullable=False),
    sa.Column('return_fraction', sa.Text(), nullable=False),
    sa.Column('available_at', sa.String(), nullable=False),
    sa.Column('recorded_at', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['entry_quote_id'], ['research_quote.id'], ),
    sa.ForeignKeyConstraint(['event_id'], ['research_event.id'], ),
    sa.ForeignKeyConstraint(['exit_quote_id'], ['research_quote.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('event_id')
    )
    op.create_table('research_paper_account',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('policy_id', sa.String(), nullable=False),
    sa.Column('instrument', sa.String(length=64), nullable=False),
    sa.Column('cash', sa.Text(), nullable=False),
    sa.Column('quantity', sa.Text(), nullable=False),
    sa.Column('peak_equity', sa.Text(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['policy_id'], ['paper_policy.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('research_paper_decision',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('event_id', sa.String(), nullable=False),
    sa.Column('policy_id', sa.String(), nullable=False),
    sa.Column('quote_id', sa.String(), nullable=True),
    sa.Column('action', sa.String(length=8), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.Column('actor', sa.String(), nullable=False),
    sa.Column('created_at', sa.String(), nullable=False),
    sa.CheckConstraint("action IN ('BUY','SELL','HOLD')", name='ck_research_action'),
    sa.ForeignKeyConstraint(['event_id'], ['research_event.id'], ),
    sa.ForeignKeyConstraint(['policy_id'], ['paper_policy.id'], ),
    sa.ForeignKeyConstraint(['quote_id'], ['research_quote.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('event_id')
    )

def downgrade():
    op.drop_table('research_paper_decision')
    op.drop_table('research_paper_account')
    op.drop_table('research_outcome')
    with op.batch_alter_table('research_quote', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_research_quote_instrument'))

    op.drop_table('research_quote')
    with op.batch_alter_table('research_event', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_research_event_known_at'))
        batch_op.drop_index(batch_op.f('ix_research_event_instrument'))

    op.drop_table('research_event')
    op.drop_table('paper_policy')
