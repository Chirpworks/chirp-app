# ChirpWorks Database Setup

This directory contains scripts to set up a fresh ChirpWorks database with sample data.

## Overview

The database setup process consists of two main scripts:

1. **`fresh_db_setup.py`** - Creates a fresh database structure (⚠️ **DESTRUCTIVE**)
2. **`seed_script.py`** - Populates the database with sample data

## Prerequisites

- Python 3.8+
- PostgreSQL database running and accessible
- All required Python dependencies installed (`pip install -r requirements.txt`)
- Proper database configuration in `app/config.py`

## ⚠️ Important Warning

**`fresh_db_setup.py` will completely destroy all existing data!**

This script:
- Drops ALL existing tables
- Creates fresh tables from SQLAlchemy models
- Ignores migration history
- **PERMANENTLY DELETES ALL DATA**

## Usage

### Step 1: Fresh Database Setup

```bash
# Navigate to project root
cd /path/to/chirp-app

# Run the fresh database setup (DESTRUCTIVE)
python database_setup/fresh_db_setup.py
```

**You will be prompted to confirm this destructive operation.**

### Step 2: Seed with Sample Data

```bash
# Populate with sample data
python database_setup/seed_script.py
```

## What Gets Created

### Sample Agencies (5)
- **TechCorp Solutions** - Technology solutions provider
- **FinanceFirst Advisory** - Financial advisory firm  
- **HealthMax Insurance** - Health insurance provider
- **EduTech Academy** - Online education platform
- **GreenEnergy Solutions** - Renewable energy company

### Sample Sellers/Users (12)
Each agency has 2-3 users with different roles:
- **Admin** - Full system access
- **Manager** - Team management capabilities
- **User** - Standard user access

#### Sample Login Credentials
| Email | Password | Role | Agency |
|-------|----------|------|--------|
| john.smith@techcorp.com | TechCorp@123 | Admin | TechCorp Solutions |
| sarah.johnson@techcorp.com | TechCorp@456 | Manager | TechCorp Solutions |
| mike.davis@techcorp.com | TechCorp@789 | User | TechCorp Solutions |
| emma.wilson@financefirst.com | Finance@123 | Admin | FinanceFirst Advisory |
| david.brown@financefirst.com | Finance@456 | Manager | FinanceFirst Advisory |

### Sample Buyers/Customers (3+)
- **Acme Corporation** - Enterprise technology customer
- **Global Industries Ltd** - Manufacturing company
- **StartupXYZ** - Tech startup

Each buyer includes:
- Contact information
- Tags and requirements
- Relationship progression notes
- Agency association

### Sample Products (2+)
- **Enterprise Cloud Platform** - Cloud infrastructure solution
- **Data Analytics Suite** - Analytics and ML platform

Each product includes:
- Detailed descriptions
- Feature categorization (JSON)
- Agency association

## Database Structure

The following tables are created:

| Table | Purpose |
|-------|---------|
| `agencies` | Organizations/companies |
| `sellers` | Users/sales representatives |
| `buyers` | Customers/prospects |
| `products` | Product catalog |
| `meetings` | Call/meeting records |
| `jobs` | Processing job tracking |
| `actions` | Task management |
| `exotel_calls` | Exotel call records |
| `mobile_app_calls` | Mobile app call records |
| `token_blocklist` | JWT token blacklist |

## Service Layer Integration

The seed script uses the new service layer for all database operations:

- **AgencyService** - Agency management
- **SellerService** - User management and authentication
- **BuyerService** - Customer management
- **ProductService** - Product catalog management

This ensures:
- Consistent data validation
- Proper error handling
- Transaction management
- Business logic compliance

## Verification

After running both scripts, you can verify the setup:

```bash
# Check if tables were created
python -c "
from app import create_app, db
app = create_app()
with app.app_context():
    print('Tables:', list(db.metadata.tables.keys()))
"

# Check sample data counts
python -c "
from app import create_app
from app.services import AgencyService, SellerService, BuyerService, ProductService
app = create_app()
with app.app_context():
    print(f'Agencies: {AgencyService.get_all_count()}')
    print(f'Sellers: {SellerService.get_all_count()}')
    print(f'Buyers: {BuyerService.get_all_count()}')
    print(f'Products: {ProductService.get_all_count()}')
"
```

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Check `app/config.py` database URL
   - Ensure PostgreSQL is running
   - Verify database credentials

2. **Permission Errors**
   - Ensure database user has CREATE/DROP privileges
   - Check file permissions on scripts

3. **Import Errors**
   - Verify you're in the project root directory
   - Check that all dependencies are installed
   - Ensure `PYTHONPATH` includes project root

4. **Service Layer Errors**
   - Ensure service layer is properly implemented
   - Check for any missing service methods
   - Verify model relationships

### Getting Help

If you encounter issues:

1. Check the logs - scripts provide detailed logging
2. Verify database connectivity independently
3. Ensure all models are properly defined
4. Check service layer implementation

## Next Steps

After successful database setup:

1. **Start the application** - Run the Flask app
2. **Test login** - Use sample credentials to log in
3. **Explore features** - Test different user roles and functionalities
4. **Add real data** - Replace sample data with actual business data
5. **Configure production** - Set up proper production database

## Security Notes

⚠️ **Important for Production:**

- Change all sample passwords before deploying
- Use strong, unique passwords
- Enable proper authentication mechanisms
- Configure database security properly
- Remove or secure sample accounts

## File Structure

```
database_setup/
├── README.md              # This file
├── fresh_db_setup.py      # Fresh database creation script
├── seed_script.py         # Sample data population script
└── (future scripts...)    # Additional setup scripts
```

---

**Remember: Always backup your data before running destructive operations!** 