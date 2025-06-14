"""add created_at column on Actions, change description to JSON

Revision ID: 25c9aa5774d8
Revises: f92abdb1ba59
Create Date: 2025-05-11 23:01:13.551937

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '25c9aa5774d8'
down_revision = 'f92abdb1ba59'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('actions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.alter_column('description',
               existing_type=sa.TEXT(),
               type_=sa.JSON(),
               postgresql_using='description::json',
               existing_nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('actions', schema=None) as batch_op:
        batch_op.alter_column('description',
               existing_type=sa.JSON(),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.drop_column('created_at')

    # ### end Alembic commands ###
