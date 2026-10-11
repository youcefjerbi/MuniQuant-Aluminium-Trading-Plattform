"""Licensed API credential references, lead-only source usage and Permutable event leads."""
from alembic import op
import sqlalchemy as sa

revision = 'a7d3e19c5b42'
down_revision = 'fcf5b3d9e812'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('source_access', schema=None) as batch_op:
        batch_op.add_column(sa.Column('credential_ref', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('auth_header', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('usage_scope', sa.String(), nullable=False, server_default='evidence'))
        batch_op.create_check_constraint('ck_source_access_usage', "usage_scope IN ('evidence','leads_only')")
        batch_op.create_check_constraint('ck_source_access_credential', '(credential_ref IS NULL) = (auth_header IS NULL)')
    op.create_table('lead',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('source_id', sa.String(), nullable=False),
    sa.Column('external_id', sa.String(length=128), nullable=False),
    sa.Column('ticker', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('first_seen_at', sa.String(), nullable=False),
    sa.Column('last_seen_at', sa.String(), nullable=False),
    sa.Column('event_date', sa.String(), nullable=True),
    sa.Column('topic_name', sa.String(), nullable=True),
    sa.Column('vendor_updated_at', sa.String(), nullable=True),
    sa.Column('current_revision_hash', sa.String(length=64), nullable=True),
    sa.Column('matched_entity_count', sa.Integer(), nullable=False, server_default='0'),
    sa.Column('reviewer', sa.String(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('decided_at', sa.String(), nullable=True),
    sa.Column('primary_document_id', sa.String(), nullable=True),
    sa.Column('observation_id', sa.String(), nullable=True),
    sa.CheckConstraint("status IN ('new','follow_up','dismissed','confirmed')", name='ck_lead_status'),
    sa.CheckConstraint("status <> 'confirmed' OR primary_document_id IS NOT NULL", name='ck_lead_confirmed_evidence'),
    sa.ForeignKeyConstraint(['observation_id'], ['observations.id'], ),
    sa.ForeignKeyConstraint(['primary_document_id'], ['documents.id'], ),
    sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source_id', 'external_id', name='uq_lead_source_external')
    )
    with op.batch_alter_table('lead', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lead_event_date'), ['event_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_lead_source_id'), ['source_id'], unique=False)
    op.create_table('lead_revision',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('lead_id', sa.String(), nullable=False),
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('parser_version', sa.String(), nullable=False),
    sa.Column('event_name', sa.Text(), nullable=False),
    sa.Column('event_date', sa.String(), nullable=True),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('topic_name', sa.String(), nullable=True),
    sa.Column('event_type', sa.String(), nullable=True),
    sa.Column('vendor_updated_at', sa.String(), nullable=True),
    sa.Column('matched_entity_ids', sa.JSON(), nullable=False),
    sa.Column('recorded_at', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
    sa.ForeignKeyConstraint(['lead_id'], ['lead.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('lead_id', 'content_hash', name='uq_lead_revision_content')
    )
    with op.batch_alter_table('lead_revision', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lead_revision_document_id'), ['document_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_lead_revision_lead_id'), ['lead_id'], unique=False)
    op.create_table('lead_headline',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('lead_id', sa.String(), nullable=False),
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('parser_version', sa.String(), nullable=False),
    sa.Column('headline', sa.Text(), nullable=False),
    sa.Column('source_name', sa.String(), nullable=True),
    sa.Column('link', sa.String(length=2048), nullable=True),
    sa.Column('published_at', sa.String(), nullable=True),
    sa.Column('language', sa.String(length=16), nullable=True),
    sa.Column('recorded_at', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
    sa.ForeignKeyConstraint(['lead_id'], ['lead.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('lead_id', 'content_hash', name='uq_lead_headline_content')
    )
    with op.batch_alter_table('lead_headline', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lead_headline_document_id'), ['document_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_lead_headline_lead_id'), ['lead_id'], unique=False)

def downgrade():
    with op.batch_alter_table('lead_headline', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lead_headline_lead_id'))
        batch_op.drop_index(batch_op.f('ix_lead_headline_document_id'))
    op.drop_table('lead_headline')
    with op.batch_alter_table('lead_revision', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lead_revision_lead_id'))
        batch_op.drop_index(batch_op.f('ix_lead_revision_document_id'))
    op.drop_table('lead_revision')
    with op.batch_alter_table('lead', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lead_source_id'))
        batch_op.drop_index(batch_op.f('ix_lead_event_date'))
    op.drop_table('lead')
    with op.batch_alter_table('source_access', schema=None) as batch_op:
        batch_op.drop_constraint('ck_source_access_credential', type_='check')
        batch_op.drop_constraint('ck_source_access_usage', type_='check')
        batch_op.drop_column('usage_scope')
        batch_op.drop_column('auth_header')
        batch_op.drop_column('credential_ref')
