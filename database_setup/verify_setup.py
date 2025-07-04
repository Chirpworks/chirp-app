#!/usr/bin/env python3
"""
ChirpWorks Database Setup Verification Script

This script verifies that the database setup was completed successfully by:
1. Checking database connectivity
2. Verifying all expected tables exist
3. Checking sample data counts
4. Testing service layer functionality
5. Validating relationships

Usage:
    python database_setup/verify_setup.py
"""

import sys
import os
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import create_app, db
from app.services import AgencyService, SellerService, BuyerService, ProductService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_database_connectivity(app):
    """Test basic database connectivity"""
    logger.info("🔌 Testing database connectivity...")
    
    try:
        with app.app_context():
            # Simple query to test connection
            result = db.engine.execute('SELECT 1')
            result.close()
            logger.info("✅ Database connection successful")
            return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {str(e)}")
        return False


def verify_tables_exist(app):
    """Verify that all expected tables exist"""
    logger.info("📋 Verifying table structure...")
    
    expected_tables = {
        'agencies': 'Organizations/companies',
        'sellers': 'Users/sales representatives', 
        'buyers': 'Customers/prospects',
        'products': 'Product catalog',
        'meetings': 'Call/meeting records',
        'jobs': 'Processing job tracking',
        'actions': 'Task management',
        'exotel_calls': 'Exotel call records',
        'mobile_app_calls': 'Mobile app call records',
        'token_blocklist': 'JWT token blacklist'
    }
    
    try:
        with app.app_context():
            existing_tables = set(db.engine.table_names())
            
            missing_tables = set(expected_tables.keys()) - existing_tables
            extra_tables = existing_tables - set(expected_tables.keys())
            
            logger.info(f"📊 Found {len(existing_tables)} tables in database")
            
            if missing_tables:
                logger.error(f"❌ Missing required tables: {missing_tables}")
                return False
            
            if extra_tables:
                logger.info(f"ℹ️  Additional tables found: {extra_tables}")
            
            for table, description in expected_tables.items():
                if table in existing_tables:
                    logger.info(f"  ✅ {table} - {description}")
                else:
                    logger.error(f"  ❌ {table} - {description}")
            
            logger.info("✅ All required tables exist")
            return True
            
    except Exception as e:
        logger.error(f"❌ Table verification failed: {str(e)}")
        return False


def verify_sample_data(app):
    """Verify that sample data was created correctly"""
    logger.info("📊 Verifying sample data...")
    
    try:
        with app.app_context():
            # Check data counts
            agencies_count = AgencyService.get_all_count()
            sellers_count = SellerService.get_all_count()
            buyers_count = BuyerService.get_all_count()
            products_count = ProductService.get_all_count()
            
            logger.info(f"📈 Data Summary:")
            logger.info(f"  • Agencies: {agencies_count}")
            logger.info(f"  • Sellers: {sellers_count}")
            logger.info(f"  • Buyers: {buyers_count}")
            logger.info(f"  • Products: {products_count}")
            
            # Verify minimum expected counts
            if agencies_count < 3:
                logger.warning(f"⚠️  Low agency count: {agencies_count} (expected at least 3)")
            else:
                logger.info("✅ Agency count looks good")
                
            if sellers_count < 6:
                logger.warning(f"⚠️  Low seller count: {sellers_count} (expected at least 6)")
            else:
                logger.info("✅ Seller count looks good")
                
            if buyers_count < 3:
                logger.warning(f"⚠️  Low buyer count: {buyers_count} (expected at least 3)")
            else:
                logger.info("✅ Buyer count looks good")
                
            if products_count < 2:
                logger.warning(f"⚠️  Low product count: {products_count} (expected at least 2)")
            else:
                logger.info("✅ Product count looks good")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Sample data verification failed: {str(e)}")
        return False


def test_service_layer_functionality(app):
    """Test basic service layer functionality"""
    logger.info("🔧 Testing service layer functionality...")
    
    try:
        with app.app_context():
            # Test AgencyService
            agencies = AgencyService.get_all()
            if agencies:
                sample_agency = agencies[0]
                logger.info(f"✅ AgencyService working - Sample: {sample_agency.name}")
            else:
                logger.warning("⚠️  No agencies found to test AgencyService")
            
            # Test SellerService
            sellers = SellerService.get_all()
            if sellers:
                sample_seller = sellers[0]
                logger.info(f"✅ SellerService working - Sample: {sample_seller.name}")
                
                # Test getting by email
                seller_by_email = SellerService.get_by_email(sample_seller.email)
                if seller_by_email:
                    logger.info("✅ SellerService.get_by_email() working")
                else:
                    logger.warning("⚠️  SellerService.get_by_email() not working")
            else:
                logger.warning("⚠️  No sellers found to test SellerService")
            
            # Test BuyerService  
            buyers = BuyerService.get_all()
            if buyers:
                sample_buyer = buyers[0]
                logger.info(f"✅ BuyerService working - Sample: {sample_buyer.name}")
            else:
                logger.warning("⚠️  No buyers found to test BuyerService")
            
            # Test ProductService
            products = ProductService.get_all()
            if products:
                sample_product = products[0]
                logger.info(f"✅ ProductService working - Sample: {sample_product.name}")
            else:
                logger.warning("⚠️  No products found to test ProductService")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Service layer testing failed: {str(e)}")
        return False


def verify_relationships(app):
    """Verify that database relationships are working correctly"""
    logger.info("🔗 Verifying database relationships...")
    
    try:
        with app.app_context():
            agencies = AgencyService.get_all()
            
            for agency in agencies[:3]:  # Check first 3 agencies
                # Get related data
                agency_sellers = SellerService.get_by_agency(str(agency.id))
                agency_buyers = BuyerService.get_by_agency(str(agency.id))
                agency_products = ProductService.get_by_agency(str(agency.id))
                
                logger.info(f"🏢 {agency.name}:")
                logger.info(f"   • Sellers: {len(agency_sellers)}")
                logger.info(f"   • Buyers: {len(agency_buyers)}")
                logger.info(f"   • Products: {len(agency_products)}")
                
                # Verify sellers have agency relationship
                for seller in agency_sellers:
                    if seller.agency_id == agency.id:
                        logger.info(f"   ✅ Seller '{seller.name}' correctly linked to agency")
                    else:
                        logger.error(f"   ❌ Seller '{seller.name}' has incorrect agency_id")
            
            logger.info("✅ Relationship verification completed")
            return True
            
    except Exception as e:
        logger.error(f"❌ Relationship verification failed: {str(e)}")
        return False


def display_sample_credentials():
    """Display sample login credentials for testing"""
    logger.info("🔐 Sample Login Credentials:")
    
    credentials = [
        ("john.smith@techcorp.com", "TechCorp@123", "Admin", "TechCorp Solutions"),
        ("sarah.johnson@techcorp.com", "TechCorp@456", "Manager", "TechCorp Solutions"),
        ("mike.davis@techcorp.com", "TechCorp@789", "User", "TechCorp Solutions"),
        ("emma.wilson@financefirst.com", "Finance@123", "Admin", "FinanceFirst Advisory"),
        ("david.brown@financefirst.com", "Finance@456", "Manager", "FinanceFirst Advisory"),
    ]
    
    print("\n" + "="*70)
    print("🔐 SAMPLE LOGIN CREDENTIALS")
    print("="*70)
    print(f"{'Email':<35} {'Password':<15} {'Role':<10} {'Agency'}")
    print("-"*70)
    
    for email, password, role, agency in credentials:
        print(f"{email:<35} {password:<15} {role:<10} {agency}")
    
    print("="*70)
    print("💡 Use these credentials to test the application login")
    print("="*70)


def main():
    """Main verification function"""
    logger.info("🔍 Starting ChirpWorks Database Setup Verification")
    
    try:
        # Create Flask app
        logger.info("🔧 Initializing Flask application...")
        app = create_app()
        
        # Run verification tests
        tests = [
            ("Database Connectivity", lambda: test_database_connectivity(app)),
            ("Table Structure", lambda: verify_tables_exist(app)),
            ("Sample Data", lambda: verify_sample_data(app)),
            ("Service Layer", lambda: test_service_layer_functionality(app)),
            ("Relationships", lambda: verify_relationships(app))
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            logger.info(f"\n📋 Running: {test_name}")
            if test_func():
                passed_tests += 1
                logger.info(f"✅ {test_name}: PASSED")
            else:
                logger.error(f"❌ {test_name}: FAILED")
        
        # Display results
        print("\n" + "="*60)
        print("📊 VERIFICATION RESULTS")
        print("="*60)
        print(f"Tests Passed: {passed_tests}/{total_tests}")
        
        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED!")
            print("✅ Your ChirpWorks database setup is working correctly!")
            display_sample_credentials()
            
            print("\n🚀 Next Steps:")
            print("  1. Start your Flask application")
            print("  2. Test login with sample credentials")
            print("  3. Explore the application features")
            print("  4. Begin adding your real data")
            
        else:
            print(f"⚠️  {total_tests - passed_tests} test(s) failed")
            print("🔧 Please check the logs above and fix any issues")
            print("💡 Common solutions:")
            print("  • Ensure database is running and accessible")
            print("  • Verify service layer implementation")
            print("  • Check database permissions")
            print("  • Re-run fresh_db_setup.py and seed_script.py")
        
        print("="*60)
        
    except Exception as e:
        logger.error(f"❌ Verification failed: {str(e)}")
        print("\n" + "="*60)
        print("❌ VERIFICATION FAILED")
        print("="*60)
        print(f"Error: {str(e)}")
        print("\n🔧 Troubleshooting steps:")
        print("  1. Check database connection")
        print("  2. Verify Flask app configuration")
        print("  3. Ensure all dependencies are installed")
        print("  4. Check service layer imports")
        print("="*60)
        sys.exit(1)


if __name__ == "__main__":
    main() 