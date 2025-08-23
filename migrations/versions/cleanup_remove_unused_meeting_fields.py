"""remove unused meeting fields: call_purpose, buyer_pain_points, solutions_discussed, risks, overall_summary

Revision ID: e7a5c2d9ab10
Revises: d3f1b2a4c6e7
Create Date: 2025-08-23 00:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7a5c2d9ab10'
down_revision = 'd3f1b2a4c6e7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('meetings', schema=None) as batch_op:
        batch_op.drop_column('call_purpose')
        batch_op.drop_column('buyer_pain_points')
        batch_op.drop_column('solutions_discussed')
        batch_op.drop_column('risks')
        batch_op.drop_column('overall_summary')


def downgrade():
    with op.batch_alter_table('meetings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('overall_summary', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('risks', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('solutions_discussed', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('buyer_pain_points', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('call_purpose', sa.String(), nullable=True))


