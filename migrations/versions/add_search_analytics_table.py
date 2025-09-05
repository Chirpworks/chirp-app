"""add_search_analytics_table

Revision ID: search_analytics_001
Revises: search_extensions_001
Create Date: 2025-09-06 03:44:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'search_analytics_001'
down_revision = 'search_extensions_001'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create search analytics table for tracking search queries and performance.
    """
    op.create_table('search_analytics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, 
                 server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('query', sa.String(255), nullable=False),
        sa.Column('results_count', sa.Integer(), nullable=False),
        sa.Column('search_time_ms', sa.Integer(), nullable=False),
        sa.Column('cached', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, 
                 server_default=sa.text('NOW()')),
        
        # Foreign key constraints
        sa.ForeignKeyConstraint(['user_id'], ['sellers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
    )
    
    # Indexes for analytics queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_search_analytics_agency_created 
        ON search_analytics (agency_id, created_at DESC);
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_search_analytics_user_created 
        ON search_analytics (user_id, created_at DESC);
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_search_analytics_query 
        ON search_analytics (query);
    """)


def downgrade():
    """
    Drop search analytics table and related indexes.
    """
    op.drop_table('search_analytics')
