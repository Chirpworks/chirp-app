"""Change detected_call_type and detected_product columns to JSON

Revision ID: 36d1f017185a
Revises: e08ea5257b9a
Create Date: 2025-08-04 00:27:38.043401

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '36d1f017185a'
down_revision = 'e08ea5257b9a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands to change detected_call_type and detected_product to JSON ###
    
    # Change detected_call_type from VARCHAR to JSON
    # Using raw SQL to handle potential data conversion
    op.execute("""
        ALTER TABLE meetings 
        ALTER COLUMN detected_call_type TYPE JSON 
        USING CASE 
            WHEN detected_call_type IS NULL OR detected_call_type = '' THEN NULL
            ELSE ('"' || detected_call_type || '"')::json 
        END
    """)
    
    # Change detected_product from VARCHAR to JSON  
    op.execute("""
        ALTER TABLE meetings 
        ALTER COLUMN detected_product TYPE JSON 
        USING CASE 
            WHEN detected_product IS NULL OR detected_product = '' THEN NULL
            ELSE ('"' || detected_product || '"')::json 
        END
    """)


def downgrade():
    # ### commands to revert JSON columns back to VARCHAR ###
    
    # Change detected_call_type from JSON back to VARCHAR
    op.execute("""
        ALTER TABLE meetings 
        ALTER COLUMN detected_call_type TYPE VARCHAR 
        USING CASE 
            WHEN detected_call_type IS NULL THEN NULL
            ELSE detected_call_type #>> '{}'
        END
    """)
    
    # Change detected_product from JSON back to VARCHAR
    op.execute("""
        ALTER TABLE meetings 
        ALTER COLUMN detected_product TYPE VARCHAR 
        USING CASE 
            WHEN detected_product IS NULL THEN NULL
            ELSE detected_product #>> '{}'
        END
    """)
