"""
Database Initialization and Integrity Checker
Runs on every startup to ensure database and all tables exist
"""

import os
import sys
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import all models to register them with Base.metadata
from models import Base, Tenant, User, Student, Class, AcademicSession
from models import StudentAttendance, StudentAttendanceSummary, StudentHoliday
# Note: Deprecated Exam, ExamSubject, StudentMark models are in models.py but not imported
# They are replaced by examination_models.Examination and related models
from student_models import StudentAuth, StudentGuardian, StudentMedicalInfo, StudentPreviousSchool, StudentSibling, StudentDocument
from teacher_models import (
    Teacher, TeacherAuth, Subject, Department, Designation, 
    TeacherDepartment, TeacherDesignation, TeacherSubject,
    Qualification, TeacherExperience, TeacherCertification, TeacherDocument,
    TeacherBankingDetails, TeacherLeave, TeacherAttendance, TeacherSalary
)
from timetable_models import TimeSlot, TimeSlotClass, ClassTeacherAssignment, TimetableSchedule, ClassRoom, TimeSlotGroup, TimeSlotGroupClass, SubstituteAssignment, WorkloadSettings
from leave_models import LeaveQuotaSettings, TeacherLeaveBalance, TeacherLeaveApplication, StudentLeave
from fee_models import (
    FeeCategory, FeeStructure, FeeStructureDetail, StudentFee,
    StudentFeeConcession, FeeReceipt, FeeFine, FeeInstallment, FeeCollectionSummary
)
from library_models import LibraryCategory, LibraryBook, LibraryIssue, LibrarySettings
from examination_models import (
    Examination, ExaminationSubject, ExaminationSchedule,
    ExaminationMark, ExaminationResult, GradeScale,
    ExaminationPublication, ResultNotification
)
from notification_models import (
    NotificationTemplate, Notification, NotificationRecipient, NotificationDocument,
    WhatsAppSettings, WhatsAppMessageLog
)
from expense_models import Expense, Budget, RecurringExpense
from chat_models import ChatConversation, ChatMessage
from question_paper_models import QuestionPaperAssignment, QuestionPaper, QuestionPaperReview
from copy_checking_models import CopyCheckingAssignment
from transport_models import TransportVehicle, TransportRoute, TransportStop, TransportAssignment


def get_database_url():
    """Get database URL from environment or config"""
    # Try DATABASE_URL environment variable first
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        return db_url
    
    # Try individual DB environment variables (from .env)
    db_host = os.getenv('DB_HOST')
    db_port = os.getenv('DB_PORT', '3306')
    db_user = os.getenv('DB_USER')
    db_pass = os.getenv('DB_PASS')
    db_name = os.getenv('DB_NAME')
    db_charset = 'utf8mb4'
    
    if all([db_host, db_user, db_name]):
        # Import quote_plus for URL encoding
        from urllib.parse import quote_plus
        
        # Encode password to handle special characters
        encoded_pass = quote_plus(db_pass) if db_pass else ''
        
        # Construct MySQL URL (same pattern as config.py)
        if encoded_pass:
            return f'mysql+pymysql://{db_user}:{encoded_pass}@{db_host}:{db_port}/{db_name}?charset={db_charset}'
        else:
            return f'mysql+pymysql://{db_user}@{db_host}:{db_port}/{db_name}?charset={db_charset}'
    
    # Try from config.py
    try:
        from config import Config
        config_instance = Config()
        if hasattr(config_instance, 'get_database_uri'):
            return config_instance.get_database_uri()
        elif hasattr(Config, 'SQLALCHEMY_DATABASE_URI'):
            return Config.SQLALCHEMY_DATABASE_URI
    except ImportError:
        pass
    
    # Default SQLite database (fallback)
    return 'sqlite:///school_management.db'


def database_exists(engine, db_name=None):
    """Check if database exists"""
    try:
        # For SQLite, check if file exists
        if 'sqlite' in str(engine.url):
            db_path = str(engine.url).replace('sqlite:///', '')
            return os.path.exists(db_path)
        
        # For PostgreSQL/MySQL, try to connect
        with engine.connect() as conn:
            return True
    except (OperationalError, ProgrammingError):
        return False


def create_database_if_not_exists(db_url):
    """Create database if it doesn't exist (for PostgreSQL/MySQL)"""
    if 'postgresql' in db_url or 'mysql' in db_url:
        # Extract database name and create connection without database
        from sqlalchemy.engine.url import make_url
        url_obj = make_url(db_url)
        db_name = url_obj.database
        
        # Create engine without database
        url_obj = url_obj.set(database='postgres' if 'postgresql' in db_url else 'mysql')
        temp_engine = create_engine(str(url_obj))
        
        try:
            with temp_engine.connect() as conn:
                conn.execution_options(isolation_level="AUTOCOMMIT")
                # Check if database exists
                if 'postgresql' in db_url:
                    result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'"))
                    if not result.fetchone():
                        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                        print(f"Created database: {db_name}")
                else:  # MySQL
                    conn.execute(text(f'CREATE DATABASE IF NOT EXISTS `{db_name}`'))
                    print(f"Created database: {db_name}")
        except Exception as e:
            print(f"Warning: Could not create database: {e}")
        finally:
            temp_engine.dispose()


def get_existing_tables(engine):
    """Get list of existing tables in database"""
    inspector = inspect(engine)
    return set(inspector.get_table_names())


def get_expected_tables():
    """Get list of all expected tables from models"""
    return set(Base.metadata.tables.keys())


def create_missing_tables(engine, existing_tables, expected_tables):
    """Create any missing tables"""
    missing_tables = expected_tables - existing_tables
    
    if not missing_tables:
        print(" All tables exist")
        return []
    
    print(f"\n Found {len(missing_tables)} missing tables:")
    for table in sorted(missing_tables):
        print(f"  - {table}")
    
    print("\n Creating missing tables...")
    
    # Get tables in dependency order (sorted by foreign keys)
    from sqlalchemy.schema import sort_tables
    all_tables = [Base.metadata.tables[name] for name in missing_tables]
    sorted_tables = sort_tables(all_tables)
    
    created = []
    failed = []
    retry_queue = []
    
    # First pass: try to create all tables
    for table in sorted_tables:
        try:
            table.create(engine, checkfirst=True)
            created.append(table.name)
        except OperationalError as e:
            error_msg = str(e).lower()
            # Handle duplicate index/key errors
            if 'duplicate key' in error_msg or 'already exists' in error_msg or '1061' in error_msg:
                try:
                    # Table might exist but indexes failed
                    created.append(table.name)
                    print(f"   {table.name}: already exists (skipped duplicate indexes)")
                except Exception:
                    retry_queue.append(table)
            # Handle foreign key reference errors - retry later
            elif '1824' in str(e) or 'referenced table' in error_msg:
                retry_queue.append(table)
            else:
                failed.append((table.name, str(e)))
                print(f"   {table.name}: {str(e)[:80]}")
    
    # Second pass: retry failed tables (dependencies might be created now)
    if retry_queue:
        for table in retry_queue:
            try:
                table.create(engine, checkfirst=True)
                created.append(table.name)
            except Exception as e:
                failed.append((table.name, str(e)))
    
    if created:
        print(f"\n Successfully created {len(created)} tables")
    
    if failed:
        print(f"\n Failed to create {len(failed)} tables:")
        for table_name, error in failed:
            print(f"  - {table_name}: {error[:100]}")
    
    return created


def get_column_type_sql(column, dialect_name):
    """Generate SQL type string for a column based on database dialect"""
    col_type = column.type
    type_map = {
        'mysql': {
            'INTEGER': 'INT',
            'BIGINT': 'BIGINT',
            'VARCHAR': lambda: f'VARCHAR({col_type.length})' if hasattr(col_type, 'length') and col_type.length else 'VARCHAR(255)',
            'TEXT': 'TEXT',
            'BOOLEAN': 'TINYINT(1)',
            'DATETIME': 'DATETIME',
            'DATE': 'DATE',
            'TIME': 'TIME',
            'FLOAT': 'FLOAT',
            'NUMERIC': 'DECIMAL(10,2)',
            'DECIMAL': 'DECIMAL(10,2)',
        },
        'sqlite': {
            'INTEGER': 'INTEGER',
            'BIGINT': 'INTEGER',
            'VARCHAR': 'TEXT',
            'TEXT': 'TEXT',
            'BOOLEAN': 'INTEGER',
            'DATETIME': 'DATETIME',
            'DATE': 'DATE',
            'TIME': 'TIME',
            'FLOAT': 'REAL',
            'NUMERIC': 'REAL',
            'DECIMAL': 'REAL',
        }
    }
    
    type_str = str(col_type).split('(')[0].upper()
    
    if dialect_name == 'mysql':
        mapping = type_map['mysql']
        if type_str == 'VARCHAR':
            return mapping['VARCHAR']()
        elif type_str in mapping:
            return mapping[type_str]
        elif 'ENUM' in type_str:
            return 'VARCHAR(50)'
        else:
            return 'TEXT'
    elif dialect_name == 'sqlite':
        mapping = type_map['sqlite']
        return mapping.get(type_str, 'TEXT')
    else:
        return str(col_type)


def add_missing_columns(engine):
    """Add missing columns to existing tables"""
    inspector = inspect(engine)
    dialect_name = engine.dialect.name
    added_columns = []
    failed_columns = []
    
    for table_name, table in Base.metadata.tables.items():
        if table_name not in inspector.get_table_names():
            continue
        
        existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
        expected_columns = {col.name: col for col in table.columns}
        
        missing_column_names = set(expected_columns.keys()) - existing_columns
        
        if missing_column_names:
            print(f"\n Adding missing columns to '{table_name}':")
            
            for col_name in sorted(missing_column_names):
                column = expected_columns[col_name]
                
                try:
                    # Build ALTER TABLE statement
                    col_type_sql = get_column_type_sql(column, dialect_name)
                    
                    # Add NULL/NOT NULL constraint
                    null_constraint = 'NOT NULL' if not column.nullable else 'NULL'
                    
                    # Add default value if exists
                    default_clause = ''
                    if column.default is not None and hasattr(column.default, 'arg'):
                        default_val = column.default.arg
                        if callable(default_val):
                            # Skip callable defaults (like datetime.now)
                            default_clause = ''
                        elif isinstance(default_val, bool):
                            default_clause = f" DEFAULT {1 if default_val else 0}"
                        elif isinstance(default_val, (int, float)):
                            default_clause = f" DEFAULT {default_val}"
                        elif isinstance(default_val, str):
                            default_clause = f" DEFAULT '{default_val}'"
                    
                    # For NOT NULL columns without defaults, make them nullable to avoid errors
                    if not column.nullable and not default_clause and not column.server_default:
                        null_constraint = 'NULL'
                        print(f"   Warning: {col_name} - Making nullable (no default provided)")
                    
                    alter_sql = f"ALTER TABLE `{table_name}` ADD COLUMN `{col_name}` {col_type_sql}{default_clause} {null_constraint}"
                    
                    if dialect_name == 'sqlite':
                        # SQLite has limited ALTER TABLE support
                        alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type_sql}{default_clause}"
                    
                    with engine.connect() as conn:
                        conn.execute(text(alter_sql))
                        conn.commit()
                    
                    added_columns.append(f"{table_name}.{col_name}")
                    print(f"   ✓ Added column: {col_name} ({col_type_sql})")
                    
                except Exception as e:
                    error_msg = str(e)
                    # Skip if column already exists (race condition or duplicate)
                    if 'duplicate column' in error_msg.lower() or 'already exists' in error_msg.lower():
                        print(f"   ⊳ {col_name}: already exists")
                    else:
                        failed_columns.append(f"{table_name}.{col_name}: {error_msg[:80]}")
                        print(f"   ✗ {col_name}: {error_msg[:80]}")
    
    if added_columns:
        print(f"\n Successfully added {len(added_columns)} columns")
    
    if failed_columns:
        print(f"\n Failed to add {len(failed_columns)} columns:")
        for failure in failed_columns:
            print(f"  - {failure}")
    
    return added_columns, failed_columns


def sync_unique_constraints(engine):
    """
    Sync unique constraints between model definitions and database.
    Drops and recreates constraints that don't match the model definition.
    """
    inspector = inspect(engine)
    dialect_name = engine.dialect.name
    
    if dialect_name != 'mysql':
        print("  Constraint sync only supported for MySQL currently")
        return [], []
    
    fixed_constraints = []
    failed_constraints = []
    
    print("\n Checking unique constraints...")
    
    for table_name, table in Base.metadata.tables.items():
        if table_name not in inspector.get_table_names():
            continue
        
        # Get expected unique constraints from model
        expected_constraints = {}
        for constraint in table.constraints:
            if hasattr(constraint, 'name') and constraint.name and hasattr(constraint, 'columns'):
                from sqlalchemy import UniqueConstraint as UC
                if isinstance(constraint, UC):
                    col_names = tuple(sorted([c.name for c in constraint.columns]))
                    expected_constraints[constraint.name] = col_names
        
        # Also check indexes that are unique
        for index in table.indexes:
            if index.unique and index.name:
                col_names = tuple(sorted([c.name for c in index.columns]))
                expected_constraints[index.name] = col_names
        
        # Get actual unique constraints from database
        try:
            actual_constraints = {}
            
            # Get unique constraints
            for constraint in inspector.get_unique_constraints(table_name):
                if constraint['name']:
                    col_names = tuple(sorted(constraint['column_names']))
                    actual_constraints[constraint['name']] = col_names
            
            # Get unique indexes
            for index in inspector.get_indexes(table_name):
                if index.get('unique') and index['name']:
                    col_names = tuple(sorted(index['column_names']))
                    actual_constraints[index['name']] = col_names
            
            # Compare and fix mismatches
            for constraint_name, expected_cols in expected_constraints.items():
                actual_cols = actual_constraints.get(constraint_name)
                
                if actual_cols is None:
                    # Constraint doesn't exist - create it
                    try:
                        cols_sql = ', '.join([f'`{c}`' for c in expected_cols])
                        create_sql = f"ALTER TABLE `{table_name}` ADD UNIQUE INDEX `{constraint_name}` ({cols_sql})"
                        
                        with engine.connect() as conn:
                            conn.execute(text(create_sql))
                            conn.commit()
                        
                        fixed_constraints.append(f"{table_name}.{constraint_name} (created)")
                        print(f"   ✓ Created constraint: {table_name}.{constraint_name}")
                    except Exception as e:
                        if 'duplicate' in str(e).lower():
                            print(f"   ⊳ {table_name}.{constraint_name}: already exists")
                        else:
                            failed_constraints.append(f"{table_name}.{constraint_name}: {str(e)[:50]}")
                            print(f"   ✗ {table_name}.{constraint_name}: {str(e)[:80]}")
                
                elif actual_cols != expected_cols:
                    # Constraint exists but columns don't match - drop and recreate
                    try:
                        # Drop old constraint
                        drop_sql = f"ALTER TABLE `{table_name}` DROP INDEX `{constraint_name}`"
                        
                        # Create new constraint
                        cols_sql = ', '.join([f'`{c}`' for c in expected_cols])
                        create_sql = f"ALTER TABLE `{table_name}` ADD UNIQUE INDEX `{constraint_name}` ({cols_sql})"
                        
                        with engine.connect() as conn:
                            conn.execute(text(drop_sql))
                            conn.execute(text(create_sql))
                            conn.commit()
                        
                        fixed_constraints.append(f"{table_name}.{constraint_name} (updated)")
                        print(f"   ✓ Updated constraint: {table_name}.{constraint_name}")
                        print(f"     Old: {actual_cols}")
                        print(f"     New: {expected_cols}")
                    except Exception as e:
                        failed_constraints.append(f"{table_name}.{constraint_name}: {str(e)[:50]}")
                        print(f"   ✗ {table_name}.{constraint_name}: {str(e)[:80]}")
        
        except Exception as e:
            print(f"   Warning: Could not check constraints for {table_name}: {str(e)[:50]}")
    
    if fixed_constraints:
        print(f"\n Fixed {len(fixed_constraints)} constraints")
    elif not failed_constraints:
        print("   All constraints match model definitions")
    
    return fixed_constraints, failed_constraints


def create_default_admin_user(engine):
    """Create default portal admin user if no users exist"""
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Check if any users exist
        user_count = session.query(User).count()
        if user_count == 0:
            # Create default admin
            admin = User(
                username='admin',
                email='admin@school.com',
                role='portal_admin',
                first_name='Portal',
                last_name='Admin',
                is_active=True
            )
            admin.set_password('admin123')  # Change this in production!
            
            session.add(admin)
            session.commit()
            
            print("\nCreated default admin user:")
            print("  Username: admin")
            print("  Password: admin123")
            print("  IMPORTANT: Change this password immediately in production!")
            return True
        return False
    except Exception as e:
        session.rollback()
        print(f"Warning: Could not create default admin user: {e}")
        return False
    finally:
        session.close()


def initialize_database(verbose=True):
    """
    Main function to initialize and verify database integrity
    Returns: (success: bool, created_tables: list, issues: list)
    """
    if verbose:
        print("\n" + "="*60)
        print("DATABASE INITIALIZATION & INTEGRITY CHECK")
        print("="*60)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Get database URL
        db_url = get_database_url()
        if verbose:
            # Mask password in URL for display
            display_url = db_url
            if '@' in db_url:
                parts = db_url.split('@')
                user_pass = parts[0].split('://')[-1]
                if ':' in user_pass:
                    user = user_pass.split(':')[0]
                    display_url = db_url.replace(user_pass, f"{user}:****")
            print(f"\nDatabase URL: {display_url}")
        
        # Create database if needed (for PostgreSQL/MySQL)
        create_database_if_not_exists(db_url)
        
        # Create engine
        engine = create_engine(db_url, echo=False)
        
        if verbose:
            print(f"\n Checking database connection...")
        
        # Test connection
        try:
            with engine.connect() as conn:
                if verbose:
                    print("Database connection successful")
        except Exception as e:
            print(f" Database connection failed: {e}")
            return False, [], [{'error': str(e)}]
        
        # Get existing and expected tables
        existing_tables = get_existing_tables(engine)
        expected_tables = get_expected_tables()
        
        if verbose:
            print(f"\nExisting tables: {len(existing_tables)}")
            print(f"Expected tables: {len(expected_tables)}")
        
        # Create missing tables
        created_tables = create_missing_tables(engine, existing_tables, expected_tables)
        
        # Add missing columns to existing tables
        added_columns, failed_columns = add_missing_columns(engine)
        
        # Sync unique constraints (fix mismatched constraints)
        fixed_constraints, failed_constraint_fixes = sync_unique_constraints(engine)
        
        # Create default admin user if needed
        if len(existing_tables) == 0 or 'users' in created_tables:
            create_default_admin_user(engine)
        
        if verbose:
            print("\n" + "="*60)
            changes_made = created_tables or added_columns or fixed_constraints
            if changes_made:
                print("[OK] Database initialization completed")
                if created_tables:
                    print(f"    - Created {len(created_tables)} new tables")
                if added_columns:
                    print(f"    - Added {len(added_columns)} missing columns")
                if fixed_constraints:
                    print(f"    - Fixed {len(fixed_constraints)} constraints")
            elif failed_columns or failed_constraint_fixes:
                print("[WARNING] Database verified with some warnings")
            else:
                print("[OK] Database integrity verified - all structures match models")
            print("="*60 + "\n")
        
        engine.dispose()
        return True, created_tables, {
            'added_columns': added_columns, 
            'failed_columns': failed_columns,
            'fixed_constraints': fixed_constraints,
            'failed_constraints': failed_constraint_fixes
        }
        
    except Exception as e:
        print(f"\n[ERROR] Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False, [], [{'error': str(e)}]


def run_on_startup():
    """Wrapper function to run on application startup"""
    success, created_tables, issues = initialize_database(verbose=True)
    
    if not success:
        print("\n[WARNING] Database initialization failed!")
        print("The application may not work correctly.")
        print("Please check the database configuration and try again.\n")
        return False
    
    return True


if __name__ == '__main__':
    """Run standalone"""
    success = run_on_startup()
    sys.exit(0 if success else 1)
