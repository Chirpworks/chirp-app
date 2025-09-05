"""add_search_extensions_and_indexes

Revision ID: search_extensions_001
Revises: d70ff42eea7c
Create Date: 2025-09-06 03:43:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'search_extensions_001'
down_revision = 'd70ff42eea7c'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add PostgreSQL extensions and indexes for buyer search functionality.
    """
    # Enable required PostgreSQL extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")
    
    # Full-text search indexes for buyers table
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_buyers_name_fts 
        ON buyers USING gin(to_tsvector('english', COALESCE(name, '')));
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_buyers_phone_fts 
        ON buyers USING gin(to_tsvector('simple', phone));
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_buyers_email_fts 
        ON buyers USING gin(to_tsvector('english', COALESCE(email, '')));
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_buyers_company_fts 
        ON buyers USING gin(to_tsvector('english', COALESCE(company_name, '')));
    """)
    
    # Trigram indexes for fuzzy matching
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_buyers_name_trgm 
        ON buyers USING gin(COALESCE(name, '') gin_trgm_ops);
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_buyers_phone_trgm 
        ON buyers USING gin(phone gin_trgm_ops);
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_buyers_email_trgm 
        ON buyers USING gin(COALESCE(email, '') gin_trgm_ops);
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_buyers_company_trgm 
        ON buyers USING gin(COALESCE(company_name, '') gin_trgm_ops);
    """)
    
    # Composite index for agency isolation + common searches
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_buyers_search_composite 
        ON buyers (agency_id, name, phone, email);
    """)
    
    # Index for last contact queries (used in search results)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_meetings_buyer_start_time 
        ON meetings (buyer_id, start_time DESC);
    """)


def downgrade():
    """
    Remove search-related indexes and extensions.
    Note: Extensions are not dropped as they might be used by other features.
    """
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_buyers_name_fts;")
    op.execute("DROP INDEX IF EXISTS idx_buyers_phone_fts;")
    op.execute("DROP INDEX IF EXISTS idx_buyers_email_fts;")
    op.execute("DROP INDEX IF EXISTS idx_buyers_company_fts;")
    op.execute("DROP INDEX IF EXISTS idx_buyers_name_trgm;")
    op.execute("DROP INDEX IF EXISTS idx_buyers_phone_trgm;")
    op.execute("DROP INDEX IF EXISTS idx_buyers_email_trgm;")
    op.execute("DROP INDEX IF EXISTS idx_buyers_company_trgm;")
    op.execute("DROP INDEX IF EXISTS idx_buyers_search_composite;")
    op.execute("DROP INDEX IF EXISTS idx_meetings_buyer_start_time;")
    
    # Note: We don't drop extensions as they might be used elsewhere:
    # op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
    # op.execute("DROP EXTENSION IF EXISTS unaccent;")
