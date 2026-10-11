"""Independent analyst investigations and immutable revisions."""
from alembic import op
import sqlalchemy as sa
revision='b8e21ad4c902'
down_revision='a7d3e19c5b42'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('investigation',sa.Column('id',sa.String(),primary_key=True),
        sa.Column('title',sa.String(200),nullable=False),sa.Column('status',sa.String(32),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),sa.Column('snapshot',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.String(),nullable=False),sa.Column('updated_at',sa.String(),nullable=False),
        sa.CheckConstraint("status IN ('investigating','confirmed','disproven','resolved','inconclusive')",name='ck_investigation_status'))
    op.create_table('investigation_revision',sa.Column('id',sa.String(),primary_key=True),
        sa.Column('case_id',sa.String(),sa.ForeignKey('investigation.id'),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),sa.Column('actor',sa.String(),nullable=False),
        sa.Column('snapshot',sa.JSON(),nullable=False),sa.Column('created_at',sa.String(),nullable=False),
        sa.UniqueConstraint('case_id','version',name='uq_investigation_version'))

def downgrade():
    op.drop_table('investigation_revision');op.drop_table('investigation')
