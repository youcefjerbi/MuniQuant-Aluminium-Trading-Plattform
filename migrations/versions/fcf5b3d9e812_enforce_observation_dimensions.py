"""Enforce known industrial attribute/unit dimensions in the database."""
from alembic import op
revision='fcf5b3d9e812'
down_revision='14b1672b3bb6'
branch_labels=None
depends_on=None
EXPRESSION="(attribute='capacity' AND reported_unit IN ('t/year','kt/year','Mt/year')) OR (attribute='power' AND reported_unit='MW') OR (attribute='ownership_percentage' AND reported_unit='percentage') OR (attribute='status' AND reported_unit='status')"
def views(drop):
    if op.get_bind().dialect.name!='sqlite': return
    for name,attribute in [('capacity_observation','capacity'),('status_observation','status')]:
        if drop: op.execute('DROP VIEW '+name)
        else:
            query="SELECT o.*, d.normalized_value AS exact_value FROM observations o JOIN observation_detail d ON d.observation_id=o.id WHERE o.attribute='capacity'" if attribute=='capacity' else "SELECT * FROM observations WHERE attribute='status'"
            op.execute(f'CREATE VIEW {name} AS {query}')
def upgrade():
    views(True)
    with op.batch_alter_table('observations') as batch:
        batch.create_check_constraint('ck_observation_dimension',EXPRESSION)
    views(False)
def downgrade():
    views(True)
    with op.batch_alter_table('observations') as batch:
        batch.drop_constraint('ck_observation_dimension',type_='check')
    views(False)
