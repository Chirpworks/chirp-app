#!/usr/bin/env python3
"""
ChirpWorks Fresh Database Setup Script

This script sets up a completely fresh database by:
1. Dropping all existing tables
2. Creating all tables from SQLAlchemy models
3. Ignoring any migrations

Usage:
    python database_setup/fresh_db_setup.py

WARNING: This will destroy all existing data in the database!
"""

import sys
import os
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import create_app, db
from app.models.agency import Agency
from app.models.seller import Seller, SellerRole
from app.models.buyer import Buyer
from app.models.product import Product
from app.models.job import Job
from app.models.meeting import Meeting
from app.models.action import Action
from app.models.exotel_calls import ExotelCall
from app.models.mobile_app_calls import MobileAppCall
from app.models.jwt_token_blocklist import TokenBlocklist

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def confirm_action():
    """Ask for user confirmation before proceeding"""
    print("\n" + "="*60)
    print("🚨 WARNING: DESTRUCTIVE OPERATION 🚨")
    print("="*60)
    print("This script will:")
    print("  • DROP ALL existing tables and data")
    print("  • CREATE fresh tables from models")
    print("  • IGNORE all migration history")
    print("\n❌ ALL EXISTING DATA WILL BE PERMANENTLY LOST! ❌")
    print("="*60)
    
    response = input("\nDo you want to continue? Type 'YES' to proceed: ")
    return response.strip().upper() == 'YES'


def drop_all_tables(app):
    """Drop all existing tables"""
    with app.app_context():
        logger.info("🗑️  Dropping all existing tables...")
        
        # Drop all tables
        db.drop_all()
        logger.info("✅ All tables dropped successfully")


def create_all_tables(app):
    """Create all tables from SQLAlchemy models"""
    with app.app_context():
        logger.info("🏗️  Creating all tables from models...")
        
        # Create all tables
        db.create_all()
        logger.info("✅ All tables created successfully")


def verify_tables(app):
    """Verify that all expected tables exist"""
    with app.app_context():
        logger.info("🔍 Verifying table creation...")
        
        # Get all table names from metadata
        table_names = list(db.metadata.tables.keys())
        
        expected_tables = [
            'agencies',
            'sellers', 
            'buyers',
            'products',
            'jobs',
            'meetings',
            'actions',
            'exotel_calls',
            'mobile_app_calls',
            'token_blocklist'
        ]
        
        logger.info(f"📋 Expected tables: {expected_tables}")
        logger.info(f"📋 Created tables: {table_names}")
        
        missing_tables = set(expected_tables) - set(table_names)
        extra_tables = set(table_names) - set(expected_tables)
        
        if missing_tables:
            logger.warning(f"⚠️  Missing tables: {missing_tables}")
        
        if extra_tables:
            logger.info(f"ℹ️  Additional tables: {extra_tables}")
        
        logger.info(f"✅ Table verification complete - {len(table_names)} tables created")


def main():
    """Main function to set up fresh database"""
    logger.info("🚀 Starting ChirpWorks Fresh Database Setup")
    
    # Confirm destructive action
    if not confirm_action():
        logger.info("❌ Operation cancelled by user")
        return
    
    try:
        # Create Flask app
        logger.info("🔧 Initializing Flask application...")
        app = create_app()
        
        # Drop all existing tables
        drop_all_tables(app)
        
        # Create all tables fresh
        create_all_tables(app)
        
        # Verify table creation
        verify_tables(app)
        
        logger.info("🎉 Fresh database setup completed successfully!")
        logger.info("📝 Next step: Run the seed script to populate with sample data")
        print("\n" + "="*60)
        print("✅ DATABASE SETUP COMPLETE")
        print("="*60)
        print("Your fresh database is ready!")
        print("To populate with sample data, run:")
        print("  python database_setup/seed_script.py")
        print("="*60)
        
    except Exception as e:
        logger.error(f"❌ Database setup failed: {str(e)}")
        logger.error("🔧 Please check your database connection and try again")
        sys.exit(1)


if __name__ == "__main__":
    main() 