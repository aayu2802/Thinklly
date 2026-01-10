"""
Flask CLI commands for single database multi-tenant system
"""

import click
from flask import Flask
from flask.cli import with_appcontext
from db_single import create_school, list_schools, get_session
from init_db import run_on_startup
from models import User, Tenant
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def register_cli_commands(app: Flask):
    """Register CLI commands with the Flask app"""
    
    @app.cli.command("setup-db")
    def setup_db_command():
        """Create database, tables, and default admin user"""
        click.echo("🚀 Setting up database...")
        if run_on_startup():
            click.echo("✅ Database setup completed successfully!")
        else:
            click.echo("❌ Database setup failed!")
    
    @app.cli.command("add-school")
    @click.option("--slug", required=True, help="URL-friendly school identifier (e.g., xyz)")
    @click.option("--name", required=True, help="Full school name (e.g., 'XYZ Public School')")
    @click.option("--sample-data", is_flag=True, help="Create sample students/teachers")
    def add_school_command(slug, name, sample_data):
        """Add a new school to the system"""
        click.echo(f"🏫 Creating school: {name} ({slug})")
        
        school_data = {}
        if sample_data:
            school_data['create_sample_data'] = True
        
        success, message = create_school(slug, name, **school_data)
        
        if success:
            click.echo(f"✅ {message}")
            click.echo(f"🌐 Access URL: http://your-domain.com/{slug}/")
        else:
            click.echo(f"❌ {message}")
    
    @app.cli.command("list-schools")
    def list_schools_command():
        """List all schools in the system"""
        schools = list_schools()
        if not schools:
            click.echo("📭 No schools found")
            return
        
        click.echo("🏫 Schools in system:")
        click.echo("-" * 60)
        for school in schools:
            click.echo(f"  {school.name}")
            click.echo(f"    Slug: {school.slug}")
            click.echo(f"    URL: /{school.slug}/")
            click.echo(f"    Status: {'Active' if school.is_active else 'Inactive'}")
            click.echo("-" * 60)
    
    @app.cli.command("create-school-admin")
    @click.option("--slug", required=True, help="School slug")
    @click.option("--username", required=True, help="Admin username")
    @click.option("--email", required=True, help="Admin email")
    @click.option("--password", required=True, help="Admin password")
    @click.option("--first-name", required=True, help="First name")
    @click.option("--last-name", required=True, help="Last name")
    def create_school_admin_command(slug, username, email, password, first_name, last_name):
        """Create a school admin user"""
        session = get_session()
        try:
            # Verify school exists
            school = session.query(Tenant).filter_by(slug=slug).first()
            if not school:
                click.echo(f"❌ School with slug '{slug}' not found")
                return
            
            # Check if username already exists
            existing = session.query(User).filter_by(username=username).first()
            if existing:
                click.echo(f"❌ Username '{username}' already exists")
                return
            
            # Create school admin
            admin = User(
                tenant_id=school.id,
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                role='school_admin',
                is_active=True
            )
            admin.set_password(password)
            
            session.add(admin)
            session.commit()
            
            click.echo(f"✅ School admin created for {school.name}")
            click.echo(f"   Username: {username}")
            click.echo(f"   Login URL: /{slug}/login")
            
        except Exception as e:
            session.rollback()
            click.echo(f"❌ Failed to create school admin: {e}")
        finally:
            session.close()
    
    @app.cli.command("list-users")
    @click.option("--slug", help="Filter by school slug")
    @click.option("--role", help="Filter by role (portal_admin, school_admin, teacher)")
    def list_users_command(slug, role):
        """List users in the system"""
        session = get_session()
        try:
            query = session.query(User)
            
            if slug:
                query = query.filter_by(tenant_id=slug)
            if role:
                query = query.filter_by(role=role)
            
            users = query.order_by(User.username).all()
            
            if not users:
                click.echo("📭 No users found")
                return
            
            click.echo("👥 Users in system:")
            click.echo("-" * 80)
            for user in users:
                school_name = "Portal" if not user.tenant_id else user.tenant_id
                click.echo(f"  {user.username} ({user.full_name})")
                click.echo(f"    Role: {user.role}")
                click.echo(f"    School: {school_name}")
                click.echo(f"    Email: {user.email}")
                click.echo(f"    Status: {'Active' if user.is_active else 'Inactive'}")
                click.echo("-" * 80)
                
        finally:
            session.close()
    
    @app.cli.command("seed-master-data")
    @click.option("--slug", required=True, help="School slug to seed data for")
    def seed_master_data_command(slug):
        """Seed master data (Departments, Designations, Subjects) for a school"""
        session = get_session()
        try:
            from teacher_models import Department, Designation, Subject
            
            # Verify school exists
            school = session.query(Tenant).filter_by(slug=slug).first()
            if not school:
                click.echo(f"❌ School with slug '{slug}' not found")
                return
            
            click.echo(f"🌱 Seeding master data for {school.name}...")
            
            # Define seed data
            departments_data = [
                {"name": "Science", "code": "SCI", "description": "Science and Mathematics Department"},
                {"name": "Arts", "code": "ART", "description": "Arts and Humanities Department"},
                {"name": "Commerce", "code": "COM", "description": "Commerce and Business Studies"},
                {"name": "Languages", "code": "LANG", "description": "Languages Department"},
                {"name": "Sports", "code": "SPT", "description": "Physical Education and Sports"},
                {"name": "Admin", "code": "ADM", "description": "Administrative Staff"},
                {"name": "Library", "code": "LIB", "description": "Library Management"},
                {"name": "Lab", "code": "LAB", "description": "Laboratory Management"},
                {"name": "IT", "code": "IT", "description": "Information Technology"},
            ]
            
            designations_data = [
                {"name": "Principal", "code": "PRIN", "hierarchy_level": 1, "description": "School Principal"},
                {"name": "Vice Principal", "code": "VP", "hierarchy_level": 2, "description": "Vice Principal"},
                {"name": "HOD", "code": "HOD", "hierarchy_level": 3, "description": "Head of Department"},
                {"name": "PGT", "code": "PGT", "hierarchy_level": 4, "description": "Post Graduate Teacher (Class 11-12)"},
                {"name": "TGT", "code": "TGT", "hierarchy_level": 5, "description": "Trained Graduate Teacher (Class 6-10)"},
                {"name": "PRT", "code": "PRT", "hierarchy_level": 6, "description": "Primary Teacher (Class 1-5)"},
                {"name": "Librarian", "code": "LIB", "hierarchy_level": 7, "description": "School Librarian"},
                {"name": "Lab Assistant", "code": "LAB", "hierarchy_level": 8, "description": "Laboratory Assistant"},
                {"name": "Sports Coach", "code": "COACH", "hierarchy_level": 8, "description": "Physical Education Coach"},
                {"name": "Counselor", "code": "COUN", "hierarchy_level": 7, "description": "Student Counselor"},
                {"name": "Admin Staff", "code": "ADMIN", "hierarchy_level": 9, "description": "Administrative Staff"},
            ]
            
            subjects_data = [
                # Academic - Science
                {"name": "Mathematics", "code": "MATH", "type": "Academic", "description": "Mathematics"},
                {"name": "Physics", "code": "PHY", "type": "Academic", "description": "Physics"},
                {"name": "Chemistry", "code": "CHEM", "type": "Academic", "description": "Chemistry"},
                {"name": "Biology", "code": "BIO", "type": "Academic", "description": "Biology"},
                {"name": "Computer Science", "code": "CS", "type": "Academic", "description": "Computer Science"},
                
                # Academic - Languages
                {"name": "English", "code": "ENG", "type": "Academic", "description": "English Language"},
                {"name": "Hindi", "code": "HIN", "type": "Academic", "description": "Hindi Language"},
                {"name": "Sanskrit", "code": "SAN", "type": "Academic", "description": "Sanskrit Language"},
                
                # Academic - Social Studies
                {"name": "History", "code": "HIST", "type": "Academic", "description": "History"},
                {"name": "Geography", "code": "GEO", "type": "Academic", "description": "Geography"},
                {"name": "Political Science", "code": "POL", "type": "Academic", "description": "Political Science"},
                {"name": "Economics", "code": "ECO", "type": "Academic", "description": "Economics"},
                
                # Academic - Commerce
                {"name": "Accountancy", "code": "ACC", "type": "Academic", "description": "Accountancy"},
                {"name": "Business Studies", "code": "BST", "type": "Academic", "description": "Business Studies"},
                
                # Co-curricular
                {"name": "Art & Craft", "code": "ART", "type": "Co-curricular", "description": "Arts and Crafts"},
                {"name": "Music", "code": "MUS", "type": "Co-curricular", "description": "Music"},
                {"name": "Dance", "code": "DAN", "type": "Co-curricular", "description": "Dance"},
                
                # Extra-curricular
                {"name": "Physical Education", "code": "PE", "type": "Extra-curricular", "description": "Physical Education"},
                {"name": "Yoga", "code": "YOGA", "type": "Extra-curricular", "description": "Yoga"},
            ]
            
            # Seed Departments
            dept_count = 0
            for dept_data in departments_data:
                existing = session.query(Department).filter_by(
                    tenant_id=school.id,
                    name=dept_data["name"]
                ).first()
                
                if not existing:
                    dept = Department(
                        tenant_id=school.id,
                        name=dept_data["name"],
                        code=dept_data["code"],
                        description=dept_data["description"],
                        is_active=True
                    )
                    session.add(dept)
                    dept_count += 1
            
            # Seed Designations
            desig_count = 0
            for desig_data in designations_data:
                existing = session.query(Designation).filter_by(
                    tenant_id=school.id,
                    name=desig_data["name"]
                ).first()
                
                if not existing:
                    desig = Designation(
                        tenant_id=school.id,
                        name=desig_data["name"],
                        code=desig_data["code"],
                        hierarchy_level=desig_data["hierarchy_level"],
                        description=desig_data["description"],
                        is_active=True
                    )
                    session.add(desig)
                    desig_count += 1
            
            # Seed Subjects
            subj_count = 0
            for subj_data in subjects_data:
                existing = session.query(Subject).filter_by(
                    tenant_id=school.id,
                    name=subj_data["name"]
                ).first()
                
                if not existing:
                    subj = Subject(
                        tenant_id=school.id,
                        name=subj_data["name"],
                        code=subj_data["code"],
                        subject_type=subj_data["type"],
                        description=subj_data["description"],
                        is_active=True
                    )
                    session.add(subj)
                    subj_count += 1
            
            session.commit()
            
            click.echo(f"✅ Master data seeded successfully!")
            click.echo(f"   📁 Departments added: {dept_count}")
            click.echo(f"   👔 Designations added: {desig_count}")
            click.echo(f"   📚 Subjects added: {subj_count}")
            
        except Exception as e:
            session.rollback()
            click.echo(f"❌ Failed to seed master data: {e}")
        finally:
            session.close()
    
    # ===== NOTIFICATION SCHEDULER COMMANDS =====
    
    @app.cli.command("send-scheduled-notifications")
    def send_scheduled_notifications_command():
        """Process and send all due scheduled notifications (for cron jobs)"""
        from notification_scheduler import process_scheduled_notifications
        
        click.echo(f"📬 Processing scheduled notifications at {datetime.utcnow().isoformat()}...")
        
        processed, recipients, errors = process_scheduled_notifications()
        
        if processed > 0:
            click.echo(f"✅ Sent {processed} notification(s) to {recipients} recipient(s)")
        else:
            click.echo("📭 No scheduled notifications due at this time")
        
        if errors:
            click.echo("⚠️  Errors encountered:")
            for error in errors:
                click.echo(f"   - {error}")
    
    @app.cli.command("list-scheduled-notifications")
    def list_scheduled_notifications_command():
        """List all pending scheduled notifications"""
        from notification_scheduler import get_pending_scheduled_notifications
        
        notifications = get_pending_scheduled_notifications()
        
        if not notifications:
            click.echo("📭 No scheduled notifications pending")
            return
        
        click.echo("📅 Pending Scheduled Notifications:")
        click.echo("-" * 80)
        for notif in notifications:
            click.echo(f"  ID: {notif['id']}")
            click.echo(f"    Title: {notif['title']}")
            click.echo(f"    Scheduled: {notif['scheduled_at']}")
            click.echo(f"    Tenant ID: {notif['tenant_id']}")
            click.echo(f"    Recipients: {notif['recipient_count']}")
            click.echo("-" * 80)
    
    @app.cli.command("start-notification-scheduler")
    @click.option("--interval", default=60, help="Check interval in seconds (default: 60)")
    def start_notification_scheduler_command(interval):
        """Start background notification scheduler (blocking - for development)"""
        from notification_scheduler import start_background_scheduler, _scheduler_running
        import time
        import signal
        
        click.echo(f"🚀 Starting notification scheduler (checking every {interval}s)")
        click.echo("   Press Ctrl+C to stop...")
        
        start_background_scheduler(interval)
        
        # Keep the main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            from notification_scheduler import stop_background_scheduler
            stop_background_scheduler()
            click.echo("\n👋 Scheduler stopped")

# Usage examples for documentation
USAGE_EXAMPLES = """
# Setup database (run once)
flask setup-db

# Seed master data for a school
flask seed-master-data --slug xyz

# Add a new school
flask add-school --slug "xyz" --name "XYZ Public School" --code "XYZ001" --email "admin@xyz.edu"

# Add school with sample data
flask add-school --slug "abc" --name "ABC High School" --sample-data

# Create school admin
flask create-school-admin --slug "xyz" --username "admin" --email "admin@xyz.edu" --password "admin123" --first-name "John" --last-name "Admin"

# List all schools
flask list-schools

# List all users
flask list-users

# List users for specific school
flask list-users --slug "xyz"
"""

if __name__ == "__main__":
    print("Flask CLI Commands for Single Database Multi-Tenant System")
    print("=" * 60)
    print(USAGE_EXAMPLES)
