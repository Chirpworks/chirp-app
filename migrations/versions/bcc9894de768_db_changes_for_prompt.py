"""db changes for prompt

Revision ID: bcc9894de768
Revises: 79dd9f55f47d
Create Date: 2025-04-29 23:19:20.027589

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bcc9894de768'
down_revision = '79dd9f55f47d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('agencies', schema=None) as batch_op:
        batch_op.add_column(sa.Column('products', sa.JSON(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('agencies', schema=None) as batch_op:
        batch_op.drop_column('products')

    # ### end Alembic commands ###
