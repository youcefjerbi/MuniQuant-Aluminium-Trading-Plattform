"""Join map and paper-engine migration histories"""
from alembic import op
import sqlalchemy as sa

revision = '0ebd19f52e04'
down_revision = ('23d0f10a556a', '4b20deafb532')
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass
