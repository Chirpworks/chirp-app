# Database Seed Script

This script populates your database with sample data for testing API integration with your frontend.

## 🚀 Quick Start

1. **Activate your virtual environment:**
   ```bash
   source venv/bin/activate
   ```

2. **Run the seed script:**
   ```bash
   python seed_database.py
   ```

## 📊 What Gets Created

The script creates **one row of data** in each table with realistic, interconnected data:

### Core Entities
- **Agency**: "Test Agency" (parent entity for all others)
- **Seller**: "Test Seller" (manager role, can log in)
- **Buyer**: "Test Buyer" (with comprehensive profile data)
- **Product**: "Test Product" (with features and description)

### Meeting & Actions
- **Meeting**: "Product Demo Meeting" (with full LLM-generated content)
- **Job**: Processing job for the meeting (completed status)
- **Action**: "Send Product Proposal" (pending action item)

### Call Records
- **ExotelCall**: Sample call record (45 minutes)
- **MobileAppCall**: App call record (30 minutes, linked to seller)

### System
- **TokenBlocklist**: Sample JWT token blocklist entry

## 🔑 Test Credentials

After running the script, you can use these credentials to test your API:

```
Email: test.seller@testagency.com
Password: TestPassword123!
Phone: 00919876543210
```

## 🧪 Testing Your API

### 1. Login
```bash
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test.seller@testagency.com",
    "password": "TestPassword123!"
  }'
```

### 2. Get Actions (requires JWT token)
```bash
curl -X GET http://localhost:5000/actions/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 3. Get Meetings
```bash
curl -X GET http://localhost:5000/meetings/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 🔄 Data Relationships

The seed data maintains proper referential integrity:

```
Agency (1)
├── Seller (1) - Manager role
├── Buyer (1) - With tags, requirements, etc.
└── Product (1) - With features

Meeting (1) - Links Buyer + Seller
├── Job (1) - Processing job
└── Action (1) - Follow-up task

MobileAppCall (1) - Links to Seller
ExotelCall (1) - Standalone call record
TokenBlocklist (1) - System table
```

## 🛠️ Customization

### To Clear Existing Data
Uncomment this line in the script:
```python
# clear_existing_data()
```

### To Modify Sample Data
Edit the values in `seed_database.py` to match your testing needs.

## ⚠️ Important Notes

1. **Phone Numbers**: All phone numbers are normalized with Indian country code (0091)
2. **Timestamps**: All dates use Asia/Kolkata timezone
3. **JSON Fields**: Buyer and Product have realistic JSON data for testing
4. **Relationships**: All foreign key relationships are properly maintained
5. **Unique Constraints**: The script respects unique constraints (emails, phones, etc.)

## 🐛 Troubleshooting

If you encounter errors:

1. **Check database connection** - Ensure your database is running
2. **Check migrations** - Run `flask db upgrade` if needed
3. **Check unique constraints** - The script will fail if duplicate data exists
4. **Check timezone** - Ensure your system supports Asia/Kolkata timezone

## 📝 Sample API Responses

The seeded data will provide realistic responses for testing:

- **Meetings**: Full meeting details with transcription and analysis
- **Actions**: Actionable follow-up items with due dates
- **Buyers**: Rich buyer profiles with tags and requirements
- **Products**: Product details with feature lists
- **Calls**: Call records with durations and URLs 