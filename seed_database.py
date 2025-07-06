#!/usr/bin/env python3
"""
Database Seed Script
Adds one row of sample data to each table for testing API integration.
Maintains referential integrity across all relationships.
"""

import sys
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.agency import Agency
from app.models.seller import Seller, SellerRole
from app.models.buyer import Buyer
from app.models.product import Product
from app.models.meeting import Meeting
from app.models.job import Job
from app.models.action import Action
from app.models.exotel_calls import ExotelCall
from app.models.mobile_app_calls import MobileAppCall
from app.models.jwt_token_blocklist import TokenBlocklist
from app.constants import MeetingSource, JobStatus, ActionStatus

def seed_database():
    """Seed the database with sample data."""
    app = create_app()
    
    with app.app_context():
        print("🌱 Starting database seeding...")
        print("=" * 60)
        
        try:
            # Clear existing data (optional - comment out if you want to keep existing data)
            # clear_existing_data()
            
            # 1. Create Agency (required for other entities)
            print("1. Creating Agency...")
            agency = Agency(
                name="Test Agency"
            )
            agency.description = "A test agency for API integration testing"
            db.session.add(agency)
            db.session.flush()  # Get the ID without committing
            print(f"   ✅ Created Agency: {agency.name} (ID: {agency.id})")
            
            # 2. Create Seller (required for meetings, actions, mobile calls)
            print("\n2. Creating Seller...")
            seller = Seller(
                email="test.seller@testagency.com",
                phone="00919560696999",
                password="TestPassword123!",
                agency_id=agency.id,
                name="Test Seller",
                role=SellerRole.MANAGER
            )
            db.session.add(seller)
            db.session.flush()
            print(f"   ✅ Created Seller: {seller.name} (ID: {seller.id})")
            
            # 3. Create Buyer (required for meetings and actions)
            print("\n3. Creating Buyer...")
            buyer = Buyer()
            buyer.phone = "00919560696999"
            buyer.name = "Test Buyer"
            buyer.email = "test.buyer@example.com"
            buyer.agency_id = agency.id
            buyer.tags = ["prospect", "enterprise"]
            buyer.requirements = {"budget": "100k-500k", "timeline": "3 months"}
            buyer.solutions_presented = ["Product A", "Product B"]
            buyer.relationship_progression = "Qualified"
            buyer.risks = ["budget constraints", "timeline pressure"]
            buyer.products_discussed = ["CRM Solution", "Analytics Platform"]
            db.session.add(buyer)
            db.session.flush()
            print(f"   ✅ Created Buyer: {buyer.name} (ID: {buyer.id})")
            
            # 4. Create Product (belongs to agency)
            print("\n4. Creating Product...")
            product = Product()
            product.agency_id = agency.id
            product.name = "Test Product"
            product.description = "A comprehensive test product for demonstration"
            product.features = {
                "feature1": "Advanced Analytics",
                "feature2": "Real-time Reporting",
                "feature3": "Mobile App"
            }
            db.session.add(product)
            db.session.flush()
            print(f"   ✅ Created Product: {product.name} (ID: {product.id})")
            
            # 5. Create Meeting (requires buyer and seller)
            print("\n5. Creating Meeting...")
            meeting_start = datetime.now(ZoneInfo("Asia/Kolkata")) - timedelta(hours=2)
            meeting_end = meeting_start + timedelta(hours=1)
            
            meeting = Meeting()
            meeting.mobile_app_call_id = "test_call_123"
            meeting.buyer_id = buyer.id
            meeting.seller_id = seller.id
            meeting.source = MeetingSource.PHONE
            meeting.start_time = meeting_start
            meeting.end_time = meeting_end
            meeting.transcription = "This is a sample transcription of the meeting conversation."
            meeting.direction = "incoming"
            meeting.title = "Product Demo Meeting"
            meeting.call_purpose = "Product demonstration and requirements discussion"
            meeting.key_discussion_points = [
                "Product features overview",
                "Pricing discussion",
                "Implementation timeline"
            ]
            meeting.buyer_pain_points = [
                "Current system is outdated",
                "Manual processes are time-consuming",
                "Lack of real-time insights"
            ]
            meeting.solutions_discussed = [
                "Automated workflow",
                "Real-time dashboard",
                "Integration capabilities"
            ]
            meeting.risks = [
                "Budget approval pending",
                "Technical integration challenges"
            ]
            meeting.summary = {
                "outcome": "Positive discussion, follow-up scheduled",
                "next_steps": "Send proposal and technical specifications"
            }
            meeting.type = "sales_demo"
            db.session.add(meeting)
            db.session.flush()
            print(f"   ✅ Created Meeting: {meeting.title} (ID: {meeting.id})")
            
            # 6. Create Job (belongs to meeting)
            print("\n6. Creating Job...")
            job = Job()
            job.start_time = meeting_start
            job.end_time = meeting_end
            job.status = JobStatus.COMPLETED
            job.s3_audio_url = "https://test-bucket.s3.amazonaws.com/recordings/meeting_123.mp3"
            job.meeting_id = meeting.id
            db.session.add(job)
            db.session.flush()
            print(f"   ✅ Created Job: {job.status.value} (ID: {job.id})")
            
            # 7. Create Action (requires meeting, buyer, and seller)
            print("\n7. Creating Action...")
            action_due_date = datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(days=7)
            
            action = Action()
            action.title = "Send Product Proposal"
            action.due_date = action_due_date
            action.status = ActionStatus.PENDING
            action.description = {
                "task": "Prepare and send detailed product proposal",
                "priority": "high",
                "estimated_effort": "2 hours"
            }
            action.reasoning = "Buyer showed strong interest and requested detailed proposal"
            action.signals = {
                "buyer_engagement": "high",
                "budget_available": "likely",
                "decision_maker": "present"
            }
            action.meeting_id = meeting.id
            action.buyer_id = buyer.id
            action.seller_id = seller.id
            action.created_at = datetime.now(ZoneInfo("Asia/Kolkata"))
            db.session.add(action)
            db.session.flush()
            print(f"   ✅ Created Action: {action.title} (ID: {action.id})")
            
            # 8. Create ExotelCall (standalone, no foreign keys)
            print("\n8. Creating ExotelCall...")
            call_start = datetime.now(ZoneInfo("Asia/Kolkata")) - timedelta(hours=3)
            call_end = call_start + timedelta(minutes=45)
            
            exotel_call = ExotelCall()
            exotel_call.call_from = "00919876543210"
            exotel_call.start_time = call_start
            exotel_call.end_time = call_end
            exotel_call.duration = 2700  # 45 minutes in seconds
            exotel_call.call_recording_url = "https://exotel-recordings.s3.amazonaws.com/call_456.mp3"
            db.session.add(exotel_call)
            db.session.flush()
            print(f"   ✅ Created ExotelCall: {exotel_call.duration}s duration (ID: {exotel_call.id})")
            
            # 9. Create MobileAppCall (requires seller)
            print("\n9. Creating MobileAppCall...")
            app_call_start = datetime.now(ZoneInfo("Asia/Kolkata")) - timedelta(hours=1)
            app_call_end = app_call_start + timedelta(minutes=30)
            
            mobile_call = MobileAppCall()
            mobile_call.mobile_app_call_id = "app_call_789"
            mobile_call.buyer_number = "00918765432109"
            mobile_call.seller_number = "00919876543210"
            mobile_call.call_type = "incoming"
            mobile_call.start_time = app_call_start
            mobile_call.end_time = app_call_end
            mobile_call.duration = 1800  # 30 minutes in seconds
            mobile_call.user_id = seller.id
            mobile_call.status = "completed"
            db.session.add(mobile_call)
            db.session.flush()
            print(f"   ✅ Created MobileAppCall: {mobile_call.call_type} (ID: {mobile_call.id})")
            
            # 10. Create TokenBlocklist (standalone, no foreign keys)
            print("\n10. Creating TokenBlocklist...")
            token_blocklist = TokenBlocklist()
            token_blocklist.jti = "test-jwt-token-id-12345"
            token_blocklist.created_at = datetime.now(ZoneInfo("Asia/Kolkata"))
            db.session.add(token_blocklist)
            db.session.flush()
            print(f"   ✅ Created TokenBlocklist: {token_blocklist.jti} (ID: {token_blocklist.id})")
            
            # Commit all changes
            db.session.commit()
            print("\n" + "=" * 60)
            print("🎉 Database seeding completed successfully!")
            print("\n📊 Summary of created records:")
            print(f"   • Agency: {agency.name}")
            print(f"   • Seller: {seller.name} ({seller.email})")
            print(f"   • Buyer: {buyer.name} ({buyer.email})")
            print(f"   • Product: {product.name}")
            print(f"   • Meeting: {meeting.title}")
            print(f"   • Job: {job.status.value}")
            print(f"   • Action: {action.title}")
            print(f"   • ExotelCall: {exotel_call.duration}s")
            print(f"   • MobileAppCall: {mobile_call.call_type}")
            print(f"   • TokenBlocklist: {token_blocklist.jti}")
            
            print("\n🔑 Test Credentials:")
            print(f"   Email: {seller.email}")
            print(f"   Password: TestPassword123!")
            print(f"   Phone: {seller.phone}")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error during seeding: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            raise

def clear_existing_data():
    """Clear all existing data from tables (optional)."""
    print("🗑️  Clearing existing data...")
    
    # Delete in reverse dependency order
    tables_to_clear = [
        TokenBlocklist,
        MobileAppCall,
        ExotelCall,
        Action,
        Job,
        Meeting,
        Product,
        Buyer,
        Seller,
        Agency
    ]
    
    for table in tables_to_clear:
        try:
            count = table.query.delete()
            print(f"   Deleted {count} records from {table.__name__}")
        except Exception as e:
            print(f"   Warning: Could not clear {table.__name__}: {e}")
    
    db.session.commit()
    print("   ✅ Data clearing completed")

if __name__ == "__main__":
    seed_database() 