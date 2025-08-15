"""add semantic_documents and enable pgvector

Revision ID: ba1234567890
Revises: ff31b2c9c3c
Create Date: 2025-08-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision = 'ba1234567890'
down_revision = 'ff31b2c9c3c'
branch_labels = None
depends_on = None


def upgrade():
    # Enable pgvector extension if available
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create table
    op.create_table(
        'semantic_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(length=64), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('meeting_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('buyer_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('seller_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('embedding', Vector(1536), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Basic indexes
    op.create_index('ix_semantic_documents_agency_id', 'semantic_documents', ['agency_id'])
    op.create_index('ix_semantic_documents_meeting_id', 'semantic_documents', ['meeting_id'])
    op.create_index('ix_semantic_documents_buyer_id', 'semantic_documents', ['buyer_id'])
    op.create_index('ix_semantic_documents_product_id', 'semantic_documents', ['product_id'])
    op.create_index('ix_semantic_documents_seller_id', 'semantic_documents', ['seller_id'])
    op.create_index('ix_semantic_documents_meta', 'semantic_documents', ['meta'], postgresql_using='gin')

    # Vector index (IVFFLAT requires specifying number of lists; default to 100)
    op.execute("CREATE INDEX IF NOT EXISTS ix_semantic_documents_embedding_ivfflat ON semantic_documents USING ivfflat (embedding vector_l2_ops) WITH (lists = 100)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_semantic_documents_embedding_ivfflat")
    op.drop_index('ix_semantic_documents_meta', table_name='semantic_documents')
    op.drop_index('ix_semantic_documents_seller_id', table_name='semantic_documents')
    op.drop_index('ix_semantic_documents_product_id', table_name='semantic_documents')
    op.drop_index('ix_semantic_documents_buyer_id', table_name='semantic_documents')
    op.drop_index('ix_semantic_documents_meeting_id', table_name='semantic_documents')
    op.drop_index('ix_semantic_documents_agency_id', table_name='semantic_documents')
    op.drop_table('semantic_documents')
    # Do not drop extension in downgrade to avoid impacting other objects


