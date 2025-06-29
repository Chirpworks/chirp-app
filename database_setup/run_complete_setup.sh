#!/bin/bash
# ChirpWorks Complete Database Setup Script
# 
# This script runs the complete database setup process:
# 1. Fresh database setup (destructive)
# 2. Sample data seeding
# 3. Verification of setup
#
# Usage: ./database_setup/run_complete_setup.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if we're in the right directory
check_directory() {
    if [ ! -f "app/__init__.py" ] || [ ! -d "database_setup" ]; then
        print_error "Please run this script from the project root directory"
        print_error "Expected files: app/__init__.py, database_setup/"
        exit 1
    fi
}

# Function to check Python environment
check_python_env() {
    print_step "Checking Python environment..."
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 is not installed or not in PATH"
        exit 1
    fi
    
    print_success "Python3 found: $(python3 --version)"
    
    # Check if required packages are installed
    if ! python3 -c "import flask, sqlalchemy" &> /dev/null; then
        print_warning "Some required packages may not be installed"
        print_warning "Please run: pip install -r requirements.txt"
    else
        print_success "Core packages available"
    fi
}

# Function to show warning and get confirmation
show_warning_and_confirm() {
    echo ""
    echo "=================================================================="
    echo -e "${RED}🚨 WARNING: DESTRUCTIVE DATABASE OPERATION 🚨${NC}"
    echo "=================================================================="
    echo ""
    echo "This script will:"
    echo "  • DROP ALL existing database tables and data"
    echo "  • CREATE fresh tables from SQLAlchemy models"
    echo "  • POPULATE with sample data"
    echo "  • IGNORE all migration history"
    echo ""
    echo -e "${RED}❌ ALL EXISTING DATA WILL BE PERMANENTLY LOST! ❌${NC}"
    echo ""
    echo "=================================================================="
    echo ""
    
    read -p "Do you want to continue? Type 'YES' to proceed: " confirmation
    
    if [ "$confirmation" != "YES" ]; then
        print_warning "Operation cancelled by user"
        exit 0
    fi
}

# Function to run fresh database setup
run_fresh_setup() {
    print_step "Running fresh database setup..."
    
    # Use expect to automatically answer 'YES' to the confirmation
    if command -v expect &> /dev/null; then
        expect << EOF
spawn python3 database_setup/fresh_db_setup.py
expect "Type 'YES' to proceed:"
send "YES\r"
expect eof
EOF
    else
        # Fallback: run with manual confirmation
        print_warning "expect command not found, you'll need to confirm manually"
        python3 database_setup/fresh_db_setup.py
    fi
    
    if [ $? -eq 0 ]; then
        print_success "Fresh database setup completed"
    else
        print_error "Fresh database setup failed"
        exit 1
    fi
}

# Function to run seed script
run_seed_script() {
    print_step "Running seed script..."
    
    python3 database_setup/seed_script.py
    
    if [ $? -eq 0 ]; then
        print_success "Database seeding completed"
    else
        print_error "Database seeding failed"
        exit 1
    fi
}

# Function to run verification
run_verification() {
    print_step "Running setup verification..."
    
    python3 database_setup/verify_setup.py
    
    if [ $? -eq 0 ]; then
        print_success "Setup verification completed"
    else
        print_error "Setup verification failed"
        exit 1
    fi
}

# Main execution
main() {
    echo ""
    echo "🚀 ChirpWorks Complete Database Setup"
    echo "====================================="
    echo ""
    
    # Check prerequisites
    check_directory
    check_python_env
    
    # Show warning and get confirmation
    show_warning_and_confirm
    
    echo ""
    print_step "Starting complete database setup process..."
    echo ""
    
    # Run setup steps
    run_fresh_setup
    echo ""
    
    run_seed_script
    echo ""
    
    run_verification
    echo ""
    
    # Final success message
    echo "=================================================================="
    echo -e "${GREEN}🎉 COMPLETE DATABASE SETUP SUCCESSFUL! 🎉${NC}"
    echo "=================================================================="
    echo ""
    echo "Your ChirpWorks database is now ready to use!"
    echo ""
    echo "Sample login credentials:"
    echo "  • john.smith@techcorp.com / TechCorp@123 (Admin)"
    echo "  • sarah.johnson@techcorp.com / TechCorp@456 (Manager)"
    echo "  • mike.davis@techcorp.com / TechCorp@789 (User)"
    echo ""
    echo "Next steps:"
    echo "  1. Start your Flask application: python run.py"
    echo "  2. Test login with sample credentials"
    echo "  3. Explore the application features"
    echo ""
    echo "=================================================================="
}

# Run main function
main "$@" 