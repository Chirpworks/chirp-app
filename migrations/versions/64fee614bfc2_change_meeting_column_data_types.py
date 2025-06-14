"""change meeting column data types

Revision ID: 64fee614bfc2
Revises: 25c9aa5774d8
Create Date: 2025-05-12 22:14:04.964359

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '64fee614bfc2'
down_revision = '25c9aa5774d8'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('meetings', schema=None) as batch_op:
        batch_op.alter_column('summary',
               existing_type=sa.TEXT(),
               type_=sa.JSON(),
               postgresql_using='summary::json',
               existing_nullable=True)
        batch_op.alter_column('call_notes',
               existing_type=sa.TEXT(),
               type_=sa.JSON(),
               postgresql_using='call_notes::json',
               existing_nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('meetings', schema=None) as batch_op:
        batch_op.alter_column('call_notes',
               existing_type=sa.JSON(),
               type_=sa.TEXT(),
               existing_nullable=True)
        batch_op.alter_column('summary',
               existing_type=sa.JSON(),
               type_=sa.TEXT(),
               existing_nullable=True)

    # ### end Alembic commands ###
