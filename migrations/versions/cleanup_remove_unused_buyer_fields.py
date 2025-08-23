"""remove unused buyer fields: tags, requirements, solutions_presented, relationship_progression

Revision ID: d3f1b2a4c6e7
Revises: acc36b251f76
Create Date: 2025-08-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3f1b2a4c6e7'
down_revision = 'acc36b251f76'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('buyers', schema=None) as batch_op:
        batch_op.drop_column('tags')
        batch_op.drop_column('requirements')
        batch_op.drop_column('solutions_presented')
        batch_op.drop_column('relationship_progression')


def downgrade():
    with op.batch_alter_table('buyers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('relationship_progression', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('solutions_presented', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('requirements', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('tags', sa.JSON(), nullable=True))


