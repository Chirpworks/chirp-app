"""add qa_pairs and facts columns to meetings

Revision ID: 20250815_add_meeting_qa_and_facts
Revises: acc36b251f76
Create Date: 2025-08-15 14:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '20250815_add_meeting_qa_and_facts'
down_revision = 'acc36b251f76'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('meetings', sa.Column('qa_pairs', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('meetings', sa.Column('facts', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('meetings', 'facts')
    op.drop_column('meetings', 'qa_pairs')


