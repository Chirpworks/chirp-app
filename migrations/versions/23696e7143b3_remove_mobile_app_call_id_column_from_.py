"""Remove mobile_app_call_id column from meetings table

Revision ID: 23696e7143b3
Revises: c6c253259f00
Create Date: 2025-08-12 01:14:12.182616

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '23696e7143b3'
down_revision = 'c6c253259f00'
branch_labels = None
depends_on = None


def upgrade():
    # Remove mobile_app_call_id column from meetings table
    op.drop_column('meetings', 'mobile_app_call_id')


def downgrade():
    # Add back mobile_app_call_id column to meetings table
    op.add_column('meetings', sa.Column('mobile_app_call_id', sa.String(length=50), nullable=True))
