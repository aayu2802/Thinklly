"""
Library Management Migration Script
Run this script to create library management tables in your database
"""

from db_single import get_session, create_all_tables
from library_models import LibraryCategory, LibraryBook, LibraryIssue, LibrarySettings
from models import Base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_library_tables():
    """Create library management tables"""
    try:
        logger.info("Creating library management tables...")
        
        # This will create all tables including library tables
        success = create_all_tables()
        
        if success:
            logger.info("✅ Library tables created successfully!")
            logger.info("Tables created:")
            logger.info("  - library_categories")
            logger.info("  - library_books")
            logger.info("  - library_issues")
            logger.info("  - library_settings")
            return True
        else:
            logger.error("❌ Failed to create library tables")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error creating library tables: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def seed_sample_categories():
    """Add sample library categories"""
    session = get_session()
    try:
        from models import Tenant
        
        # Get all tenants
        tenants = session.query(Tenant).all()
        
        if not tenants:
            logger.warning("No tenants found. Please create a school first.")
            return
        
        sample_categories = [
            {"name": "Fiction", "description": "Fictional stories and novels"},
            {"name": "Non-Fiction", "description": "Non-fictional books"},
            {"name": "Science", "description": "Science and technology books"},
            {"name": "Mathematics", "description": "Mathematics textbooks and references"},
            {"name": "History", "description": "History and social studies"},
            {"name": "Literature", "description": "Classic and modern literature"},
            {"name": "Reference", "description": "Dictionaries, encyclopedias, etc."},
            {"name": "Textbooks", "description": "School textbooks"},
            {"name": "Magazines", "description": "Periodicals and magazines"},
            {"name": "Comics", "description": "Comic books and graphic novels"}
        ]
        
        for tenant in tenants:
            logger.info(f"\nAdding sample categories for {tenant.name}...")
            
            for cat_data in sample_categories:
                # Check if category already exists
                existing = session.query(LibraryCategory).filter_by(
                    tenant_id=tenant.id,
                    name=cat_data["name"]
                ).first()
                
                if not existing:
                    category = LibraryCategory(
                        tenant_id=tenant.id,
                        **cat_data
                    )
                    session.add(category)
                    logger.info(f"  ✓ Added category: {cat_data['name']}")
                else:
                    logger.info(f"  - Category already exists: {cat_data['name']}")
            
            session.commit()
            logger.info(f"✅ Sample categories added for {tenant.name}")
            
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Error adding sample categories: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        session.close()

if __name__ == "__main__":
    print("="*60)
    print("LIBRARY MANAGEMENT SYSTEM - DATABASE SETUP")
    print("="*60)
    
    # Create tables
    if create_library_tables():
        print("\n" + "="*60)
        print("Would you like to add sample library categories? (y/n)")
        response = input("> ").strip().lower()
        
        if response == 'y':
            seed_sample_categories()
        
        print("\n" + "="*60)
        print("✅ LIBRARY SYSTEM SETUP COMPLETE!")
        print("="*60)
        print("\nYou can now:")
        print("1. Access Library Dashboard from the sidebar")
        print("2. Add books individually or in bulk via CSV")
        print("3. Issue books to students")
        print("4. Track issued and overdue books")
        print("5. Configure library settings")
        print("\nNavigate to: /<school-slug>/library")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("❌ LIBRARY SYSTEM SETUP FAILED")
        print("Please check the error messages above.")
        print("="*60)
