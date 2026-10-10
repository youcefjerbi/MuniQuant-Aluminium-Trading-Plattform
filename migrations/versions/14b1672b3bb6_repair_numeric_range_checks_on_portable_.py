"""Repair numeric range checks on portable exact decimal storage"""
from alembic import op
import sqlalchemy as sa

revision = '14b1672b3bb6'
down_revision = 'ce047394cadf'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('company_facility_relationship') as batch:
        batch.drop_constraint('ck_relationship_share', type_='check')
        batch.create_check_constraint('ck_relationship_share', 'percentage IS NULL OR (CAST(percentage AS NUMERIC) >= 0 AND CAST(percentage AS NUMERIC) <= 100)')


def downgrade():
    # The prior revision now uses the same portable invariant; do not reintroduce a bad check.
    pass
