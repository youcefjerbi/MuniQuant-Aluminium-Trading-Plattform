"""Workspace baseline: the Workspace's own tables.

One straight starting point for the Workspace after the split (DC1 step B1). It creates the
Workspace tables exactly as the platform schema defines them on 2026-10-21 (revision d8317b920a11),
and nothing of the Data Core. Existing platform databases are not upgraded in place: the split
tool (tools/split.py) copies their rows into a new database created by this baseline.

Differences from today's platform tables, all from the split:
- Links to Core tables are plain reference fields holding Core IDs, never database links:
  lead.primary_document_id, lead.observation_id, investigation_entry.document_id,
  asset_location.entity_id/document_id, asset_dependency.from_entity_id/to_entity_id/document_id
  and market_observations.document_id.
- The licensed lead feed (Permutable) keeps its responses, saved copies, access decisions and
  capture logs in the Workspace's own lead store: lead_source, lead_source_access, lead_snapshot,
  lead_document, lead_document_version, lead_source_document, lead_run and lead_retrieval_attempt,
  shaped like the platform tables they came from. lead_source_access has no usage_scope column:
  every lead source is lead-only. lead, lead_revision and lead_headline link to this store.
- The PostgreSQL triggers that kept lead.search_text current, one of them on the plant table now
  in the Core, are replaced by application code (app.permutable.refresh_search). The GIN index on
  the same text stays.
"""
from alembic import op
import sqlalchemy as sa

revision = '851cabd681a0'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('asset_dependency',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('from_entity_id', sa.String(), nullable=False),
    sa.Column('to_entity_id', sa.String(), nullable=False),
    sa.Column('product', sa.String(length=32), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('valid_from', sa.String(), nullable=False),
    sa.Column('valid_to', sa.String(), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('note', sa.String(), nullable=False),
    sa.Column('synthetic', sa.Integer(), nullable=False),
    sa.Column('actor', sa.String(), nullable=False),
    sa.Column('recorded_at', sa.String(), nullable=False),
    sa.CheckConstraint('from_entity_id <> to_entity_id', name='ck_dependency_distinct'),
    sa.CheckConstraint('valid_to IS NULL OR valid_to >= valid_from', name='ck_dependency_dates'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('asset_dependency', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_asset_dependency_from_entity_id'), ['from_entity_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_asset_dependency_product'), ['product'], unique=False)
        batch_op.create_index(batch_op.f('ix_asset_dependency_to_entity_id'), ['to_entity_id'], unique=False)

    op.create_table('asset_location',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('entity_id', sa.String(), nullable=False),
    sa.Column('latitude', sa.Float(), nullable=False),
    sa.Column('longitude', sa.Float(), nullable=False),
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('precision', sa.String(length=32), nullable=False),
    sa.Column('synthetic', sa.Integer(), nullable=False),
    sa.Column('actor', sa.String(), nullable=False),
    sa.Column('recorded_at', sa.String(), nullable=False),
    sa.CheckConstraint('latitude BETWEEN -90 AND 90', name='ck_asset_latitude'),
    sa.CheckConstraint('longitude BETWEEN -180 AND 180', name='ck_asset_longitude'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('asset_location', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_asset_location_entity_id'), ['entity_id'], unique=False)

    op.create_table('audit',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('created_at', sa.String(), nullable=False),
    sa.Column('actor', sa.String(), nullable=False),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('record_id', sa.String(), nullable=False),
    sa.Column('detail', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('investigation',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('snapshot', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.String(), nullable=False),
    sa.Column('updated_at', sa.String(), nullable=False),
    sa.CheckConstraint("status IN ('investigating','confirmed','disproven','resolved','inconclusive')", name='ck_investigation_status'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('lead_run',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('started_at', sa.String(), nullable=False),
    sa.Column('pipeline_version', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('manifest', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('lead_snapshot',
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('storage_reference', sa.String(), nullable=False),
    sa.Column('byte_size', sa.Integer(), nullable=True),
    sa.CheckConstraint('byte_size >= 0', name='ck_snapshot_size'),
    sa.PrimaryKeyConstraint('content_hash')
    )
    op.create_table('lead_source',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('publisher', sa.String(), nullable=False),
    sa.Column('source_type', sa.String(), nullable=False),
    sa.Column('url', sa.String(), nullable=False),
    sa.Column('access_status', sa.String(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('market_observations',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('instrument', sa.String(), nullable=False),
    sa.Column('exchange', sa.String(), nullable=False),
    sa.Column('market', sa.String(), nullable=False),
    sa.Column('contract_code', sa.String(), nullable=True),
    sa.Column('prompt_date', sa.String(), nullable=True),
    sa.Column('commodity', sa.String(), nullable=False),
    sa.Column('grade', sa.String(), nullable=True),
    sa.Column('region', sa.String(), nullable=False),
    sa.Column('price_type', sa.String(), nullable=False),
    sa.Column('value', sa.String(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('unit', sa.String(), nullable=False),
    sa.Column('effective_at', sa.String(), nullable=False),
    sa.Column('published_at', sa.String(), nullable=True),
    sa.Column('volume', sa.Integer(), nullable=True),
    sa.Column('open_interest', sa.Integer(), nullable=True),
    sa.Column('data_status', sa.String(), nullable=False),
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('evidence_reference', sa.String(), nullable=False),
    sa.CheckConstraint('open_interest IS NULL OR open_interest >= 0'),
    sa.CheckConstraint('volume IS NULL OR volume >= 0'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('market_observations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_market_observations_effective_at'), ['effective_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_market_observations_instrument'), ['instrument'], unique=False)

    op.create_table('paper_accounts',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('cash_cents', sa.BigInteger(), nullable=False),
    sa.Column('cursor', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.CheckConstraint('cash_cents >= 0'),
    sa.CheckConstraint('cursor >= 0 AND cursor < 120'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('paper_orders',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('request_id', sa.String(), nullable=False),
    sa.Column('instrument', sa.String(), nullable=False),
    sa.Column('side', sa.String(), nullable=False),
    sa.Column('order_type', sa.String(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('limit_cents', sa.Integer(), nullable=True),
    sa.Column('fill_cents', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('created_at', sa.String(), nullable=False),
    sa.Column('filled_at', sa.String(), nullable=True),
    sa.Column('session_index', sa.Integer(), nullable=False),
    sa.Column('actor', sa.String(), nullable=False),
    sa.CheckConstraint("side IN ('buy','sell')"),
    sa.CheckConstraint("status IN ('open','filled','cancelled','expired','settled')"),
    sa.CheckConstraint('quantity > 0'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('request_id')
    )
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

    op.create_table('investigation_entry',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('case_id', sa.String(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('text', sa.String(), nullable=False),
    sa.Column('document_id', sa.String(), nullable=True),
    sa.Column('hypothesis_id', sa.String(), nullable=True),
    sa.Column('stance', sa.String(length=16), nullable=False),
    sa.Column('source_url', sa.String(), nullable=True),
    sa.Column('passage', sa.String(), nullable=False),
    sa.Column('published_at', sa.String(), nullable=True),
    sa.Column('actor', sa.String(), nullable=False),
    sa.Column('recorded_at', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['investigation.id'], ),
    sa.ForeignKeyConstraint(['hypothesis_id'], ['investigation_entry.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('investigation_entry', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_investigation_entry_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_investigation_entry_kind'), ['kind'], unique=False)

    op.create_table('investigation_revision',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('case_id', sa.String(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('actor', sa.String(), nullable=False),
    sa.Column('snapshot', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['investigation.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('case_id', 'version', name='uq_investigation_version')
    )
    op.create_table('investigation_task',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('case_id', sa.String(), nullable=False),
    sa.Column('question', sa.String(), nullable=False),
    sa.Column('assignee', sa.String(), nullable=False),
    sa.Column('due_at', sa.String(), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('answer', sa.String(), nullable=False),
    sa.Column('created_by', sa.String(), nullable=False),
    sa.Column('created_at', sa.String(), nullable=False),
    sa.Column('updated_by', sa.String(), nullable=False),
    sa.Column('updated_at', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['case_id'], ['investigation.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('investigation_task', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_investigation_task_assignee'), ['assignee'], unique=False)
        batch_op.create_index(batch_op.f('ix_investigation_task_case_id'), ['case_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_investigation_task_due_at'), ['due_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_investigation_task_status'), ['status'], unique=False)

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
    sa.Column('matched_entity_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('reviewer', sa.String(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('decided_at', sa.String(), nullable=True),
    sa.Column('primary_document_id', sa.String(), nullable=True),
    sa.Column('observation_id', sa.String(), nullable=True),
    sa.Column('search_text', sa.Text(), server_default='', nullable=False),
    sa.CheckConstraint("status <> 'confirmed' OR primary_document_id IS NOT NULL", name='ck_lead_confirmed_evidence'),
    sa.CheckConstraint("status IN ('new','follow_up','dismissed','confirmed')", name='ck_lead_status'),
    sa.ForeignKeyConstraint(['source_id'], ['lead_source.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source_id', 'external_id', name='uq_lead_source_external')
    )
    with op.batch_alter_table('lead', schema=None) as batch_op:
        batch_op.create_index('ix_lead_date_seen', ['event_date', 'last_seen_at', 'id'], unique=False)
        batch_op.create_index(batch_op.f('ix_lead_event_date'), ['event_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_lead_source_id'), ['source_id'], unique=False)
        batch_op.create_index('ix_lead_status_date', ['status', 'event_date', 'last_seen_at', 'id'], unique=False)
        batch_op.create_index('ix_lead_topic_date', ['topic_name', 'event_date', 'last_seen_at', 'id'], unique=False)
    if op.get_bind().dialect.name == 'postgresql':
        op.execute("CREATE INDEX ix_lead_search_gin ON lead USING gin(to_tsvector('simple'::regconfig, search_text))")

    op.create_table('lead_document',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('source_id', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('original_url', sa.String(), nullable=False),
    sa.Column('published_at', sa.String(), nullable=True),
    sa.Column('retrieved_at', sa.String(), nullable=False),
    sa.Column('media_type', sa.String(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.CheckConstraint('version > 0'),
    sa.ForeignKeyConstraint(['source_id'], ['lead_source.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source_id', 'original_url', 'content_hash'),
    sa.UniqueConstraint('source_id', 'original_url', 'version')
    )
    with op.batch_alter_table('lead_document', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lead_document_content_hash'), ['content_hash'], unique=False)
        batch_op.create_index(batch_op.f('ix_lead_document_source_id'), ['source_id'], unique=False)

    op.create_table('lead_retrieval_attempt',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('run_id', sa.String(), nullable=False),
    sa.Column('url', sa.String(), nullable=False),
    sa.Column('attempt', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('error', sa.String(), nullable=True),
    sa.Column('http_status', sa.Integer(), nullable=True),
    sa.Column('recorded_at', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['lead_run.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('lead_retrieval_attempt', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lead_retrieval_attempt_run_id'), ['run_id'], unique=False)

    op.create_table('lead_source_access',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('source_id', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('allowed_hosts', sa.JSON(), nullable=False),
    sa.Column('basis', sa.Text(), nullable=False),
    sa.Column('retention', sa.Text(), nullable=False),
    sa.Column('reviewer', sa.String(), nullable=False),
    sa.Column('decided_at', sa.String(), nullable=False),
    sa.Column('credential_ref', sa.String(length=64), nullable=True),
    sa.Column('auth_header', sa.String(length=64), nullable=True),
    sa.CheckConstraint("status IN ('permitted','review_required','restricted')", name='ck_source_access_status'),
    sa.CheckConstraint('(credential_ref IS NULL) = (auth_header IS NULL)', name='ck_source_access_credential'),
    sa.ForeignKeyConstraint(['source_id'], ['lead_source.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('lead_source_access', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lead_source_access_source_id'), ['source_id'], unique=False)

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
    op.create_table('investigation_task_evidence',
    sa.Column('task_id', sa.String(), nullable=False),
    sa.Column('entry_id', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['entry_id'], ['investigation_entry.id'], ),
    sa.ForeignKeyConstraint(['task_id'], ['investigation_task.id'], ),
    sa.PrimaryKeyConstraint('task_id', 'entry_id')
    )
    op.create_table('lead_document_version',
    sa.Column('document_id', sa.String(), nullable=False),
    sa.Column('snapshot_hash', sa.String(length=64), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.CheckConstraint('version > 0', name='ck_document_version_positive'),
    sa.ForeignKeyConstraint(['document_id'], ['lead_document.id'], ),
    sa.ForeignKeyConstraint(['snapshot_hash'], ['lead_snapshot.content_hash'], ),
    sa.PrimaryKeyConstraint('document_id')
    )
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
    sa.ForeignKeyConstraint(['document_id'], ['lead_document.id'], ),
    sa.ForeignKeyConstraint(['lead_id'], ['lead.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('lead_id', 'content_hash', name='uq_lead_headline_content')
    )
    with op.batch_alter_table('lead_headline', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lead_headline_document_id'), ['document_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_lead_headline_lead_id'), ['lead_id'], unique=False)

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
    sa.ForeignKeyConstraint(['document_id'], ['lead_document.id'], ),
    sa.ForeignKeyConstraint(['lead_id'], ['lead.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('lead_id', 'content_hash', name='uq_lead_revision_content')
    )
    with op.batch_alter_table('lead_revision', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lead_revision_document_id'), ['document_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_lead_revision_lead_id'), ['lead_id'], unique=False)

    op.create_table('lead_source_document',
    sa.Column('source_id', sa.String(), nullable=False),
    sa.Column('document_id', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['lead_document.id'], ),
    sa.ForeignKeyConstraint(['source_id'], ['lead_source.id'], ),
    sa.PrimaryKeyConstraint('source_id', 'document_id')
    )

def downgrade():
    op.drop_table('lead_source_document')
    with op.batch_alter_table('lead_revision', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lead_revision_lead_id'))
        batch_op.drop_index(batch_op.f('ix_lead_revision_document_id'))

    op.drop_table('lead_revision')
    with op.batch_alter_table('lead_headline', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lead_headline_lead_id'))
        batch_op.drop_index(batch_op.f('ix_lead_headline_document_id'))

    op.drop_table('lead_headline')
    op.drop_table('lead_document_version')
    op.drop_table('investigation_task_evidence')
    op.drop_table('research_paper_decision')
    op.drop_table('research_paper_account')
    op.drop_table('research_outcome')
    with op.batch_alter_table('lead_source_access', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lead_source_access_source_id'))

    op.drop_table('lead_source_access')
    with op.batch_alter_table('lead_retrieval_attempt', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lead_retrieval_attempt_run_id'))

    op.drop_table('lead_retrieval_attempt')
    with op.batch_alter_table('lead_document', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lead_document_source_id'))
        batch_op.drop_index(batch_op.f('ix_lead_document_content_hash'))

    op.drop_table('lead_document')
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('DROP INDEX ix_lead_search_gin')
    with op.batch_alter_table('lead', schema=None) as batch_op:
        batch_op.drop_index('ix_lead_topic_date')
        batch_op.drop_index('ix_lead_status_date')
        batch_op.drop_index(batch_op.f('ix_lead_source_id'))
        batch_op.drop_index(batch_op.f('ix_lead_event_date'))
        batch_op.drop_index('ix_lead_date_seen')

    op.drop_table('lead')
    with op.batch_alter_table('investigation_task', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_investigation_task_status'))
        batch_op.drop_index(batch_op.f('ix_investigation_task_due_at'))
        batch_op.drop_index(batch_op.f('ix_investigation_task_case_id'))
        batch_op.drop_index(batch_op.f('ix_investigation_task_assignee'))

    op.drop_table('investigation_task')
    op.drop_table('investigation_revision')
    with op.batch_alter_table('investigation_entry', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_investigation_entry_kind'))
        batch_op.drop_index(batch_op.f('ix_investigation_entry_case_id'))

    op.drop_table('investigation_entry')
    with op.batch_alter_table('research_quote', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_research_quote_instrument'))

    op.drop_table('research_quote')
    with op.batch_alter_table('research_event', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_research_event_known_at'))
        batch_op.drop_index(batch_op.f('ix_research_event_instrument'))

    op.drop_table('research_event')
    op.drop_table('paper_policy')
    op.drop_table('paper_orders')
    op.drop_table('paper_accounts')
    with op.batch_alter_table('market_observations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_market_observations_instrument'))
        batch_op.drop_index(batch_op.f('ix_market_observations_effective_at'))

    op.drop_table('market_observations')
    op.drop_table('lead_source')
    op.drop_table('lead_snapshot')
    op.drop_table('lead_run')
    op.drop_table('investigation')
    op.drop_table('audit')
    with op.batch_alter_table('asset_location', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_asset_location_entity_id'))

    op.drop_table('asset_location')
    with op.batch_alter_table('asset_dependency', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_asset_dependency_to_entity_id'))
        batch_op.drop_index(batch_op.f('ix_asset_dependency_product'))
        batch_op.drop_index(batch_op.f('ix_asset_dependency_from_entity_id'))

    op.drop_table('asset_dependency')
