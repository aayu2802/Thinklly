"""
Database management for single database multi-tenant system
"""

import os
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from config import Config
# Models imported only when needed inside functions to avoid unused imports
from models import Base, Tenant, User
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Global engine and session factory
ENGINE = None
SessionLocal = None

def init_database():
    """Initialize database engine and session factory"""
    global ENGINE, SessionLocal
    
    config = Config()
    database_uri = config.get_database_uri()
    
    ENGINE = create_engine(
        database_uri,
        **config.SQLALCHEMY_ENGINE_OPTIONS
    )
    
    SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)
    
    logger.info(f"Database initialized: {config.MYSQL_DATABASE}")
    return ENGINE, SessionLocal

def get_session():
    """Get a database session"""
    if SessionLocal is None:
        init_database()
    return SessionLocal()

def create_school(slug: str, name: str, **kwargs) -> tuple[bool, str]:
    """
    Create a new school (tenant) with optional sample data
    
    Args:
        slug: URL-friendly identifier (e.g., 'xyz')
        name: Full school name (e.g., 'XYZ Public School')
        **kwargs: Additional school data (create_sample_data, etc.)
    
    Returns:
        tuple: (success: bool, message: str)
    """
    session = get_session()
    try:
        # Check if slug already exists
        existing = session.query(Tenant).filter_by(slug=slug).first()
        if existing:
            return False, f"School with slug '{slug}' already exists"
        
        # Create school/tenant (no auto-generation of code since new model doesn't have it)
        school = Tenant(
            slug=slug,
            name=name,
            is_active=True
        )
        
        session.add(school)
        session.flush()  # Get the ID but don't commit yet
        
        # Create sample data if requested
        if kwargs.get('create_sample_data', False):
            _create_sample_school_data(session, slug)
        
        session.commit()
        
        logger.info(f"✅ Created school: {name} ({slug})")
        return True, f"School '{name}' created successfully with slug '{slug}'"
        
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Failed to create school: {e}")
        return False, f"Error creating school: {str(e)}"
    finally:
        session.close()

def _create_sample_school_data(session, tenant_id: str):
    """Create sample data for a new school"""
    from models import Student, Exam
    from teacher_models import Teacher
    
    # Sample students
    students = [
        Student(
            tenant_id=tenant_id,
            admission_number="2024001",
            name="John Doe",
            email="john.doe@example.com",
            gender="M",
            class_name="10",
            section="A",
            roll_number="1",
            status="Active"
        ),
        Student(
            tenant_id=tenant_id,
            admission_number="2024002", 
            name="Jane Smith",
            email="jane.smith@example.com",
            gender="F",
            class_name="10",
            section="A",
            roll_number="2",
            status="Active"
        )
    ]
    
    # Sample teacher
    teacher = Teacher(
        tenant_id=tenant_id,
        employee_id="TCH001",
        name="Dr. Alice Johnson",
        email="alice.johnson@example.com",
        phone="+1-555-0123",
        subject="Mathematics",
        is_active=True
    )
    
    # Sample examination
    exam = Exam(
        tenant_id=tenant_id,
        exam_name="First Unit Test",
        class_name="10",
        subject="Mathematics",
        date=datetime.now().date(),
        max_marks=100,
        exam_type="Unit Test"
    )
    
    session.add_all(students + [teacher, exam])
    logger.info(f"📚 Created sample data for {tenant_id}")

def get_tenant_scoped_session(tenant_id: str):
    """
    Get a session that's pre-configured for tenant-scoped queries
    Note: This is a convenience wrapper - filtering still needs to be done in queries
    """
    session = get_session()
    # You could add session-level events here to automatically filter by tenant_id
    session.info['tenant_id'] = tenant_id
    return session

def list_schools() -> list:
    """List all schools/tenants"""
    session = get_session()
    try:
        schools = session.query(Tenant).filter_by(is_active=True).order_by(Tenant.name).all()
        return schools
    finally:
        session.close()

if __name__ == "__main__":
    # For direct execution: setup database with init_db
    logging.basicConfig(level=logging.INFO)
    try:
        from init_db import run_on_startup
        run_on_startup()
    except ImportError:
        print("Could not import init_db. Please ensure project path is correct.")
