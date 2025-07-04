#!/usr/bin/env python3
"""
ChirpWorks Database Seed Script

This script populates the fresh database with:
1. Sample agencies
2. Sample sellers (users) with different roles
3. Sample buyers (customers)
4. Sample products with features
5. NO calls/meetings (these are created during actual usage)

Usage:
    python database_setup/seed_script.py

Note: Run fresh_db_setup.py first to create the database structure
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime
import uuid

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import create_app, db
from app.models.agency import Agency
from app.models.seller import Seller, SellerRole
from app.models.buyer import Buyer
from app.models.product import Product
from app.services import AgencyService, SellerService, BuyerService, ProductService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_sample_agencies():
    """Create sample agencies"""
    logger.info("🏢 Creating sample agencies...")
    
    agencies_data = [
        {
            "name": "TechCorp Solutions",
            "description": "Leading technology solutions provider specializing in enterprise software and cloud services"
        },
        {
            "name": "FinanceFirst Advisory", 
            "description": "Premier financial advisory firm offering investment planning and wealth management services"
        },
        {
            "name": "HealthMax Insurance",
            "description": "Comprehensive health insurance provider with nationwide coverage and personalized plans"
        },
        {
            "name": "EduTech Academy",
            "description": "Online education platform providing professional courses and certification programs"
        },
        {
            "name": "GreenEnergy Solutions",
            "description": "Renewable energy solutions company specializing in solar and wind power installations"
        }
    ]
    
    created_agencies = []
    for agency_data in agencies_data:
        try:
            agency = AgencyService.create(**agency_data)
            AgencyService.commit_with_rollback()
            created_agencies.append(agency)
            logger.info(f"✅ Created agency: {agency.name}")
        except Exception as e:
            logger.error(f"❌ Failed to create agency {agency_data['name']}: {str(e)}")
            AgencyService.rollback()
    
    logger.info(f"🎉 Created {len(created_agencies)} agencies")
    return created_agencies


def create_sample_sellers(agencies):
    """Create sample sellers with different roles"""
    logger.info("👥 Creating sample sellers...")
    
    sellers_data = [
        # TechCorp Solutions
        {
            "name": "John Smith",
            "email": "john.smith@techcorp.com",
            "phone": "+919876543210",
            "password": "TechCorp@123",
            "role": SellerRole.ADMIN,
            "agency_id": agencies[0].id
        },
        {
            "name": "Sarah Johnson",
            "email": "sarah.johnson@techcorp.com", 
            "phone": "+919876543211",
            "password": "TechCorp@456",
            "role": SellerRole.MANAGER,
            "agency_id": agencies[0].id
        },
        {
            "name": "Mike Davis",
            "email": "mike.davis@techcorp.com",
            "phone": "+919876543212", 
            "password": "TechCorp@789",
            "role": SellerRole.USER,
            "agency_id": agencies[0].id
        },
        
        # FinanceFirst Advisory
        {
            "name": "Emma Wilson",
            "email": "emma.wilson@financefirst.com",
            "phone": "+919876543213",
            "password": "Finance@123",
            "role": SellerRole.ADMIN,
            "agency_id": agencies[1].id
        },
        {
            "name": "David Brown",
            "email": "david.brown@financefirst.com",
            "phone": "+919876543214",
            "password": "Finance@456", 
            "role": SellerRole.MANAGER,
            "agency_id": agencies[1].id
        },
        {
            "name": "Lisa Anderson",
            "email": "lisa.anderson@financefirst.com",
            "phone": "+919876543215",
            "password": "Finance@789",
            "role": SellerRole.USER,
            "agency_id": agencies[1].id
        },
        
        # HealthMax Insurance
        {
            "name": "Robert Taylor",
            "email": "robert.taylor@healthmax.com",
            "phone": "+919876543216",
            "password": "Health@123",
            "role": SellerRole.ADMIN,
            "agency_id": agencies[2].id
        },
        {
            "name": "Jennifer Martinez",
            "email": "jennifer.martinez@healthmax.com",
            "phone": "+919876543217",
            "password": "Health@456",
            "role": SellerRole.USER,
            "agency_id": agencies[2].id
        },
        
        # EduTech Academy
        {
            "name": "James Wilson",
            "email": "james.wilson@edutech.com",
            "phone": "+919876543218",
            "password": "EduTech@123",
            "role": SellerRole.MANAGER,
            "agency_id": agencies[3].id
        },
        {
            "name": "Amanda Garcia",
            "email": "amanda.garcia@edutech.com",
            "phone": "+919876543219",
            "password": "EduTech@456",
            "role": SellerRole.USER,
            "agency_id": agencies[3].id
        },
        
        # GreenEnergy Solutions
        {
            "name": "Christopher Lee",
            "email": "christopher.lee@greenenergy.com",
            "phone": "+919876543220",
            "password": "Green@123",
            "role": SellerRole.ADMIN,
            "agency_id": agencies[4].id
        },
        {
            "name": "Rachel Thompson",
            "email": "rachel.thompson@greenenergy.com",
            "phone": "+919876543221",
            "password": "Green@456",
            "role": SellerRole.USER,
            "agency_id": agencies[4].id
        }
    ]
    
    created_sellers = []
    for seller_data in sellers_data:
        try:
            seller = SellerService.create_seller(**seller_data)
            SellerService.commit_with_rollback()
            created_sellers.append(seller)
            logger.info(f"✅ Created seller: {seller.name} ({seller.role.value}) at {seller.agency.name}")
        except Exception as e:
            logger.error(f"❌ Failed to create seller {seller_data['name']}: {str(e)}")
            SellerService.rollback()
    
    logger.info(f"🎉 Created {len(created_sellers)} sellers")
    return created_sellers


def create_sample_buyers(agencies):
    """Create sample buyers for each agency"""
    logger.info("👤 Creating sample buyers...")
    
    buyers_data = [
        # TechCorp Solutions customers
        {
            "name": "Acme Corporation",
            "phone": "+919900001001",
            "email": "procurement@acme.com",
            "agency_id": agencies[0].id,
            "tags": ["enterprise", "technology", "high-value"],
            "requirements": ["cloud_migration", "data_analytics", "security_solutions"],
            "relationship_progression": "Initial contact -> Demo scheduled -> Proposal sent"
        },
        {
            "name": "Global Industries Ltd",
            "phone": "+919900001002", 
            "email": "it@globalindustries.com",
            "agency_id": agencies[0].id,
            "tags": ["large_enterprise", "manufacturing"],
            "requirements": ["erp_system", "automation", "integration"],
            "relationship_progression": "Cold call -> Interest shown -> Technical discussion ongoing"
        },
        {
            "name": "StartupXYZ",
            "phone": "+919900001003",
            "email": "cto@startupxyz.com", 
            "agency_id": agencies[0].id,
            "tags": ["startup", "tech_savvy", "budget_conscious"],
            "requirements": ["mvp_development", "scalable_architecture", "cost_effective"],
            "relationship_progression": "Referral -> Initial meeting -> Waiting for budget approval"
        },
        
        # FinanceFirst Advisory customers
        {
            "name": "Wealthy Individual - Rajesh Patel",
            "phone": "+919900002001",
            "email": "rajesh.patel@email.com",
            "agency_id": agencies[1].id,
            "tags": ["high_net_worth", "conservative_investor"],
            "requirements": ["retirement_planning", "tax_optimization", "portfolio_diversification"],
            "relationship_progression": "Referral -> Risk assessment done -> Investment plan proposed"
        },
        {
            "name": "Medium Business Owner - Priya Sharma",
            "phone": "+919900002002",
            "email": "priya.sharma@business.com",
            "agency_id": agencies[1].id,
            "tags": ["business_owner", "growth_focused"],
            "requirements": ["business_insurance", "employee_benefits", "expansion_funding"],
            "relationship_progression": "Cold outreach -> Business analysis -> Proposal under review"
        },
        
        # HealthMax Insurance customers  
        {
            "name": "Kumar Family",
            "phone": "+919900003001",
            "email": "amit.kumar@email.com",
            "agency_id": agencies[2].id,
            "tags": ["family", "health_conscious", "middle_income"],
            "requirements": ["family_health_insurance", "critical_illness_cover", "preventive_care"],
            "relationship_progression": "Web inquiry -> Needs assessment -> Plan comparison provided"
        },
        {
            "name": "Senior Citizen - Mrs. Lakshmi",
            "phone": "+919900003002",
            "email": "lakshmi.senior@email.com",
            "agency_id": agencies[2].id,
            "tags": ["senior_citizen", "chronic_conditions"],
            "requirements": ["senior_citizen_plan", "pre_existing_conditions_cover", "cashless_treatment"],
            "relationship_progression": "Daughter referred -> Medical history reviewed -> Suitable plan identified"
        },
        
        # EduTech Academy customers
        {
            "name": "Career Changer - Ankit Verma",
            "phone": "+919900004001",
            "email": "ankit.verma@email.com",
            "agency_id": agencies[3].id,
            "tags": ["career_change", "motivated_learner", "working_professional"],
            "requirements": ["data_science_course", "certification", "job_placement_support"],
            "relationship_progression": "Demo attended -> Course enrolled -> Payment plan set up"
        },
        {
            "name": "College Student - Neha Singh",
            "phone": "+919900004002",
            "email": "neha.singh@student.com",
            "agency_id": agencies[3].id,
            "tags": ["student", "budget_limited", "skill_building"],
            "requirements": ["digital_marketing_course", "internship_opportunities", "student_discount"],
            "relationship_progression": "Social media inquiry -> Free trial -> Considering enrollment"
        },
        
        # GreenEnergy Solutions customers
        {
            "name": "Residential Customer - Sharma Residence",
            "phone": "+919900005001",
            "email": "home.sharma@email.com",
            "agency_id": agencies[4].id,
            "tags": ["residential", "eco_conscious", "cost_savings"],
            "requirements": ["rooftop_solar", "energy_storage", "grid_tie_system"],
            "relationship_progression": "Site survey done -> Proposal submitted -> Financing options discussed"
        },
        {
            "name": "Commercial Client - Green Mall",
            "phone": "+919900005002",
            "email": "manager@greenmall.com",
            "agency_id": agencies[4].id,
            "tags": ["commercial", "large_installation", "sustainability_goals"],
            "requirements": ["large_scale_solar", "energy_management", "carbon_footprint_reduction"],
            "relationship_progression": "RFP received -> Technical proposal -> Commercial negotiation"
        }
    ]
    
    created_buyers = []
    for buyer_data in buyers_data:
        try:
            buyer = BuyerService.create_buyer(**buyer_data)
            BuyerService.commit_with_rollback()
            created_buyers.append(buyer)
            logger.info(f"✅ Created buyer: {buyer.name} for {buyer.agency.name}")
        except Exception as e:
            logger.error(f"❌ Failed to create buyer {buyer_data['name']}: {str(e)}")
            BuyerService.rollback()
    
    logger.info(f"🎉 Created {len(created_buyers)} buyers")
    return created_buyers


def create_sample_products(agencies):
    """Create sample products for each agency"""
    logger.info("📦 Creating sample products...")
    
    products_data = [
        # TechCorp Solutions products
        {
            "name": "Enterprise Cloud Platform",
            "description": "Comprehensive cloud infrastructure solution with auto-scaling, monitoring, and security features",
            "agency_id": agencies[0].id,
            "features": {
                "infrastructure": ["auto_scaling", "load_balancing", "cdn", "backup_recovery"],
                "security": ["encryption", "firewall", "identity_management", "compliance"],
                "monitoring": ["real_time_alerts", "performance_analytics", "log_management"],
                "support": ["24x7_support", "dedicated_account_manager", "training"]
            }
        },
        {
            "name": "Data Analytics Suite",
            "description": "Advanced data analytics and business intelligence platform with ML capabilities",
            "agency_id": agencies[0].id,
            "features": {
                "analytics": ["predictive_modeling", "real_time_dashboards", "custom_reports"],
                "data_processing": ["etl_tools", "data_cleansing", "data_integration"],
                "machine_learning": ["automated_ml", "model_deployment", "a_b_testing"],
                "visualization": ["interactive_charts", "mobile_dashboards", "white_labeling"]
            }
        },
        {
            "name": "Mobile App Development Platform",
            "description": "Low-code platform for rapid mobile app development and deployment",
            "agency_id": agencies[0].id,
            "features": {
                "development": ["drag_drop_interface", "pre_built_templates", "api_integration"],
                "deployment": ["multi_platform_support", "app_store_publishing", "over_the_air_updates"],
                "management": ["user_analytics", "crash_reporting", "performance_monitoring"],
                "collaboration": ["team_workspaces", "version_control", "review_workflows"]
            }
        },
        
        # FinanceFirst Advisory products
        {
            "name": "Wealth Management Portfolio",
            "description": "Comprehensive wealth management solution with diversified investment options",
            "agency_id": agencies[1].id,
            "features": {
                "investment_options": ["mutual_funds", "stocks", "bonds", "real_estate", "gold"],
                "planning": ["retirement_planning", "tax_optimization", "estate_planning"],
                "services": ["portfolio_rebalancing", "regular_reviews", "financial_advice"],
                "reporting": ["monthly_statements", "performance_tracking", "tax_reporting"]
            }
        },
        {
            "name": "Business Financial Advisory",
            "description": "Specialized financial advisory services for small and medium businesses",
            "agency_id": agencies[1].id,
            "features": {
                "services": ["cash_flow_management", "business_loans", "insurance_planning"],
                "compliance": ["tax_filing", "regulatory_compliance", "audit_support"],
                "growth": ["expansion_funding", "merger_acquisition", "risk_management"],
                "tools": ["financial_dashboard", "budget_tracking", "forecasting"]
            }
        },
        
        # HealthMax Insurance products
        {
            "name": "Comprehensive Health Insurance",
            "description": "Complete health insurance coverage with cashless treatment and wellness benefits",
            "agency_id": agencies[2].id,
            "features": {
                "coverage": ["hospitalization", "outpatient", "emergency", "maternity"],
                "benefits": ["cashless_treatment", "home_healthcare", "wellness_programs"],
                "network": ["nationwide_hospitals", "specialist_doctors", "diagnostic_centers"],
                "support": ["24x7_helpline", "claim_assistance", "health_coaching"]
            }
        },
        {
            "name": "Senior Citizen Health Plan",
            "description": "Specialized health insurance plan designed for senior citizens with pre-existing conditions",
            "agency_id": agencies[2].id,
            "features": {
                "coverage": ["pre_existing_conditions", "chronic_disease_management", "regular_checkups"],
                "benefits": ["no_medical_tests", "immediate_coverage", "domiciliary_treatment"],
                "services": ["dedicated_senior_helpline", "medicine_delivery", "teleconsultation"],
                "network": ["geriatric_specialists", "senior_friendly_hospitals"]
            }
        },
        
        # EduTech Academy products
        {
            "name": "Data Science Certification Program",
            "description": "Comprehensive data science course with hands-on projects and job placement support",
            "agency_id": agencies[3].id,
            "features": {
                "curriculum": ["python_programming", "statistics", "machine_learning", "data_visualization"],
                "projects": ["real_world_datasets", "industry_case_studies", "portfolio_development"],
                "support": ["mentor_guidance", "doubt_resolution", "peer_learning"],
                "placement": ["job_portal_access", "interview_preparation", "industry_connections"]
            }
        },
        {
            "name": "Digital Marketing Mastery",
            "description": "Complete digital marketing course covering all major platforms and strategies",
            "agency_id": agencies[3].id,
            "features": {
                "modules": ["seo_sem", "social_media_marketing", "content_marketing", "email_marketing"],
                "tools": ["google_analytics", "facebook_ads", "marketing_automation"],
                "practice": ["live_campaigns", "client_projects", "certification_exams"],
                "career": ["freelancing_guidance", "agency_placements", "startup_opportunities"]
            }
        },
        
        # GreenEnergy Solutions products
        {
            "name": "Residential Solar Power System",
            "description": "Complete rooftop solar installation with battery storage and monitoring",
            "agency_id": agencies[4].id,
            "features": {
                "system": ["high_efficiency_panels", "smart_inverters", "battery_storage"],
                "installation": ["site_survey", "custom_design", "professional_installation"],
                "monitoring": ["real_time_monitoring", "mobile_app", "performance_alerts"],
                "support": ["25_year_warranty", "maintenance_service", "performance_guarantee"]
            }
        },
        {
            "name": "Commercial Solar Solutions",
            "description": "Large-scale solar installations for commercial and industrial applications",
            "agency_id": agencies[4].id,
            "features": {
                "scale": ["megawatt_installations", "grid_tie_systems", "energy_storage"],
                "technology": ["tracking_systems", "advanced_inverters", "monitoring_platforms"],
                "services": ["feasibility_study", "financing_options", "o_m_contracts"],
                "benefits": ["carbon_footprint_reduction", "energy_cost_savings", "sustainability_reporting"]
            }
        }
    ]
    
    created_products = []
    for product_data in products_data:
        try:
            product = ProductService.create(**product_data)
            ProductService.commit_with_rollback()
            created_products.append(product)
            logger.info(f"✅ Created product: {product.name} for {product.agency.name}")
        except Exception as e:
            logger.error(f"❌ Failed to create product {product_data['name']}: {str(e)}")
            ProductService.rollback()
    
    logger.info(f"🎉 Created {len(created_products)} products")
    return created_products


def verify_seeded_data():
    """Verify that all seeded data was created correctly"""
    logger.info("🔍 Verifying seeded data...")
    
    agencies_count = AgencyService.get_all_count()
    sellers_count = SellerService.get_all_count()
    buyers_count = BuyerService.get_all_count()
    products_count = ProductService.get_all_count()
    
    logger.info(f"📊 Data verification:")
    logger.info(f"  • Agencies: {agencies_count}")
    logger.info(f"  • Sellers: {sellers_count}")
    logger.info(f"  • Buyers: {buyers_count}")
    logger.info(f"  • Products: {products_count}")
    
    # Verify relationships
    logger.info("🔗 Verifying relationships...")
    agencies = AgencyService.get_all()
    for agency in agencies:
        sellers_in_agency = SellerService.get_by_agency(str(agency.id))
        buyers_in_agency = BuyerService.get_by_agency(str(agency.id))
        products_in_agency = ProductService.get_by_agency(str(agency.id))
        
        logger.info(f"  • {agency.name}: {len(sellers_in_agency)} sellers, {len(buyers_in_agency)} buyers, {len(products_in_agency)} products")


def main():
    """Main function to seed the database"""
    logger.info("🌱 Starting ChirpWorks Database Seeding")
    
    try:
        # Create Flask app
        logger.info("🔧 Initializing Flask application...")
        app = create_app()
        
        with app.app_context():
            # Check if database has tables
            if not db.engine.table_names():
                logger.error("❌ No database tables found!")
                logger.error("🔧 Please run fresh_db_setup.py first to create the database structure")
                return
            
            # Check if data already exists
            existing_agencies_count = AgencyService.get_all_count()
            if existing_agencies_count > 0:
                logger.warning(f"⚠️  Database already contains {existing_agencies_count} agencies")
                response = input("Do you want to continue adding more data? (y/N): ")
                if response.lower() != 'y':
                    logger.info("❌ Seeding cancelled by user")
                    return
            
            # Create sample data
            agencies = create_sample_agencies()
            if not agencies:
                logger.error("❌ Failed to create agencies, stopping seeding process")
                return
            
            sellers = create_sample_sellers(agencies)
            buyers = create_sample_buyers(agencies)  
            products = create_sample_products(agencies)
            
            # Verify seeded data
            verify_seeded_data()
            
            logger.info("🎉 Database seeding completed successfully!")
            print("\n" + "="*60)
            print("✅ DATABASE SEEDING COMPLETE")
            print("="*60)
            print("Your database is now populated with sample data:")
            print(f"  • {len(agencies)} Agencies")
            print(f"  • {len(sellers)} Sellers (Users)")
            print(f"  • {len(buyers)} Buyers (Customers)")
            print(f"  • {len(products)} Products")
            print("\n📋 Sample Login Credentials:")
            print("  • john.smith@techcorp.com / TechCorp@123 (Admin)")
            print("  • sarah.johnson@techcorp.com / TechCorp@456 (Manager)")
            print("  • mike.davis@techcorp.com / TechCorp@789 (User)")
            print("\n🚀 Your ChirpWorks application is ready to use!")
            print("="*60)
            
    except Exception as e:
        logger.error(f"❌ Database seeding failed: {str(e)}")
        logger.error("🔧 Please check your database connection and try again")
        sys.exit(1)


if __name__ == "__main__":
    main() 