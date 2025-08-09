"""Merge migration heads

Revision ID: 5a631b3a2295
Revises: 80573c70a4ad, f2f92ff9f21d
Create Date: 2025-08-02 15:28:40.829633

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5a631b3a2295'
down_revision = ('80573c70a4ad', 'f2f92ff9f21d')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
