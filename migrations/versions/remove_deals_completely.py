"""remove deals completely

Revision ID: remove_deals_completely  
Revises: fa05238d7b8c
Create Date: 2025-01-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'remove_deals_completely'
down_revision = 'fa05238d7b8c'
branch_labels = None
depends_on = None


def upgrade():
    # Remove deal_id column from meetings table
    with op.batch_alter_table('meetings', schema=None) as batch_op:
        batch_op.drop_constraint('meetings_deal_id_fkey', type_='foreignkey')
        batch_op.drop_column('deal_id')
    
    # Drop deals table entirely
    op.drop_table('deals')
    
    # Drop the dealstatus enum type
    op.execute('DROP TYPE IF EXISTS dealstatus')


def downgrade():
    # Recreate dealstatus enum
    dealstatus_enum = postgresql.ENUM('OPEN', 'SUCCESS', 'FAILURE', name='dealstatus')
    dealstatus_enum.create(op.get_bind())
    
    # Recreate deals table
    op.create_table('deals',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=300), nullable=False),
        sa.Column('stage', sa.String(length=100), nullable=True),
        sa.Column('stage_signals', sa.JSON(), nullable=True),
        sa.Column('stage_reasoning', sa.JSON(), nullable=True),
        sa.Column('focus_areas', sa.JSON(), nullable=True),
        sa.Column('risks', sa.JSON(), nullable=True),
        sa.Column('lead_qualification', sa.JSON(), nullable=True),
        sa.Column('overview', sa.JSON(), nullable=True),
        sa.Column('key_stakeholders', sa.JSON(), nullable=True),
        sa.Column('buyer_number', sa.String(length=15), nullable=False),
        sa.Column('seller_number', sa.String(length=15), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('pain_points', sa.JSON(), nullable=True),
        sa.Column('solutions', sa.JSON(), nullable=True),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('history', sa.JSON(), nullable=True),
        sa.Column('status', dealstatus_enum, nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['sellers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add deal_id column back to meetings
    with op.batch_alter_table('meetings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('deal_id', sa.UUID(), nullable=True))
        batch_op.create_foreign_key('meetings_deal_id_fkey', 'deals', ['deal_id'], ['id']) 