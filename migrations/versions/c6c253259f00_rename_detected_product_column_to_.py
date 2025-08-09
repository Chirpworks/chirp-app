"""Rename detected_product column to detected_products

Revision ID: c6c253259f00
Revises: 36d1f017185a
Create Date: 2025-08-04 00:32:01.568648

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c6c253259f00'
down_revision = '36d1f017185a'
branch_labels = None
depends_on = None


def upgrade():
    # ### Rename detected_product column to detected_products ###
    op.alter_column('meetings', 'detected_product', new_column_name='detected_products')


def downgrade():
    # ### Rename detected_products column back to detected_product ###
    op.alter_column('meetings', 'detected_products', new_column_name='detected_product')
