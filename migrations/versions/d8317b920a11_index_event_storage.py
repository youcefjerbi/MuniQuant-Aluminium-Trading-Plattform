"""Database-maintained event search projection and query indexes."""
from alembic import op
import sqlalchemy as sa

revision = 'd8317b920a11'
down_revision = 'bd298b7e2b38'
branch_labels = None
depends_on = None

# Projection derived only from factual event fields, current asset names and
# headlines. Exact vendor snapshots and all immutable revisions stay separate.
REFRESH = """
CREATE FUNCTION refresh_lead_search(target text) RETURNS void
LANGUAGE sql AS $$
UPDATE lead l SET search_text = concat_ws(' ', l.topic_name,
    (SELECT concat_ws(' ', r.event_name, r.summary,
         (SELECT string_agg(e.name, ' ' ORDER BY e.id) FROM entities e
          WHERE r.matched_entity_ids::jsonb ? e.id))
     FROM lead_revision r WHERE r.lead_id=l.id
     ORDER BY (r.content_hash=l.current_revision_hash) DESC,
              r.recorded_at DESC, r.id LIMIT 1),
    (SELECT string_agg(h.headline, ' ' ORDER BY h.id)
     FROM lead_headline h WHERE h.lead_id=l.id))
WHERE l.id=target;
$$
"""

def upgrade():
    op.add_column('lead', sa.Column('search_text', sa.Text(), nullable=False, server_default=''))
    for name, fields in [
        ('ix_lead_status_date', ['status','event_date','last_seen_at','id']),
        ('ix_lead_topic_date', ['topic_name','event_date','last_seen_at','id']),
        ('ix_lead_date_seen', ['event_date','last_seen_at','id']),
    ]:
        op.create_index(name, 'lead', fields)
    if op.get_bind().dialect.name != 'postgresql':
        return
    op.execute(REFRESH)
    op.execute("""
    CREATE FUNCTION lead_search_child_changed() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP <> 'INSERT' THEN PERFORM refresh_lead_search(OLD.lead_id); END IF;
      IF TG_OP <> 'DELETE' THEN PERFORM refresh_lead_search(NEW.lead_id); END IF;
      RETURN NULL;
    END $$""")
    for table in ('lead_revision','lead_headline'):
        op.execute(f"""CREATE TRIGGER search_child_changed AFTER INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION lead_search_child_changed()""")
    op.execute("""
    CREATE FUNCTION lead_search_parent_changed() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN PERFORM refresh_lead_search(NEW.id); RETURN NULL; END $$""")
    op.execute("""
    CREATE TRIGGER search_parent_changed AFTER INSERT OR UPDATE OF topic_name,current_revision_hash ON lead
    FOR EACH ROW EXECUTE FUNCTION lead_search_parent_changed()""")
    op.execute("""
    CREATE FUNCTION lead_search_entity_changed() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE target text;
    BEGIN
      FOR target IN SELECT DISTINCT lead_id FROM lead_revision
        WHERE matched_entity_ids::jsonb ? NEW.id
      LOOP PERFORM refresh_lead_search(target); END LOOP;
      RETURN NULL;
    END $$""")
    op.execute("""
    CREATE TRIGGER search_entity_changed AFTER UPDATE OF name ON entities
    FOR EACH ROW WHEN (OLD.name IS DISTINCT FROM NEW.name)
    EXECUTE FUNCTION lead_search_entity_changed()""")
    op.execute("SELECT refresh_lead_search(id) FROM lead")
    op.execute("CREATE INDEX ix_lead_search_gin ON lead USING gin(to_tsvector('simple'::regconfig, search_text))")

def downgrade():
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('DROP INDEX ix_lead_search_gin')
        op.execute('DROP TRIGGER search_entity_changed ON entities')
        op.execute('DROP TRIGGER search_parent_changed ON lead')
        for table in ('lead_revision','lead_headline'):
            op.execute(f'DROP TRIGGER search_child_changed ON {table}')
        for name in ('lead_search_entity_changed','lead_search_parent_changed','lead_search_child_changed'):
            op.execute(f'DROP FUNCTION {name}()')
        op.execute('DROP FUNCTION refresh_lead_search(text)')
    for name in ('ix_lead_status_date','ix_lead_topic_date','ix_lead_date_seen'):
        op.drop_index(name, table_name='lead')
    op.drop_column('lead','search_text')
