"""Change detected_call_type and detected_product columns from String to JSON

Revision ID: e08ea5257b9a
Revises: bc7bb5cbaf96
Create Date: 2025-08-04 00:19:27.228442

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e08ea5257b9a'
down_revision = 'bc7bb5cbaf96'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
