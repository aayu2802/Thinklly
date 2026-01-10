"""
Admin Routes for Single Database Multi-Tenant System
Handles portal admin authentication and school management
"""

from flask import Blueprint, render_template, render_template_string, request, redirect, url_for, flash, session, g
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import text
import logging
import json

from db_single import get_session
from models import User, Tenant, Student
from teacher_models import Teacher

logger = logging.getLogger(__name__)

def create_admin_blueprint():
    """Create admin blueprint for portal administration"""
    
    admin_bp = Blueprint('admin', __name__, template_folder='admin/templates')
    
    @admin_bp.route('/')
    def dashboard():
        """Admin dashboard showing all schools and statistics"""
        if not current_user.is_authenticated or current_user.role != 'portal_admin':
            return redirect(url_for('admin.login'))
        
        session_db = get_session()
        try:
            # Get all tenants/schools
            schools = session_db.query(Tenant).order_by(Tenant.created_at.desc()).all()
            
            # Get basic statistics
            total_schools = len(schools)
            active_schools = len([s for s in schools if s.is_active])
            
            # Get total users, students, teachers across all schools
            total_users = session_db.query(User).filter(User.tenant_id.isnot(None)).count()
            total_students = session_db.query(Student).count()
            total_teachers = session_db.query(Teacher).count()
            
            stats = {
                'total_schools': total_schools,
                'active_schools': active_schools,
                'total_users': total_users,
                'total_students': total_students,
                'total_teachers': total_teachers
            }
            
            return render_template('admin_dashboard.html', 
                                 schools=schools, 
                                 stats=stats)
                                 
        except Exception as e:
            logger.error(f"Error loading admin dashboard: {e}")
            flash('Error loading dashboard data', 'error')
            return render_template('admin_dashboard.html', 
                                 schools=[], 
                                 stats={})
        finally:
            session_db.close()
    
    @admin_bp.route('/login', methods=['GET', 'POST'])
    def login():
        """Portal admin login"""
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            if not username or not password:
                flash('Please enter both username and password', 'error')
                return render_template('admin_login.html')
            
            session_db = get_session()
            try:
                # Find portal admin user
                user = session_db.query(User).filter_by(
                    username=username,
                    role='portal_admin'
                ).first()
                
                if user and check_password_hash(user.password_hash, password):
                    # Set custom user ID format for Flask-Login
                    user.get_id = lambda: f'admin_{user.id}'
                    login_user(user, remember=True)
                    flash(f'Welcome back, {user.first_name}!', 'success')
                    return redirect(url_for('admin.dashboard'))
                else:
                    flash('Invalid username or password', 'error')
                    
            except Exception as e:
                logger.error(f"Login error: {e}")
                flash('Login error occurred', 'error')
            finally:
                session_db.close()
        
        return render_template('admin_login.html')
    
    @admin_bp.route('/logout')
    @login_required
    def logout():
        """Logout portal admin"""
        logout_user()
        flash('You have been logged out successfully', 'info')
        return redirect(url_for('admin.login'))
    
    @admin_bp.route('/schools')
    @login_required
    def manage_schools():
        """Manage all schools"""
        if current_user.role != 'portal_admin':
            flash('Access denied', 'error')
            return redirect(url_for('admin.login'))
        
        session_db = get_session()
        try:
            schools = session_db.query(Tenant).order_by(Tenant.created_at.desc()).all()
            
            # Add user counts for each school
            for school in schools:
                school.user_count = session_db.query(User).filter_by(tenant_id=school.slug).count()
                school.student_count = session_db.query(Student).filter_by(tenant_id=school.slug).count()
                school.teacher_count = session_db.query(Teacher).filter_by(tenant_id=school.slug).count()
            
            return render_template('manage_schools.html', schools=schools)
            
        except Exception as e:
            logger.error(f"Error loading schools: {e}")
            flash('Error loading schools', 'error')
            return render_template('manage_schools.html', schools=[])
        finally:
            session_db.close()
    
    @admin_bp.route('/schools/add', methods=['GET', 'POST'])
    @login_required
    def add_school():
        """Add new school"""
        if current_user.role != 'portal_admin':
            flash('Access denied', 'error')
            return redirect(url_for('admin.login'))
        
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            slug = request.form.get('slug', '').strip().lower()
            description = request.form.get('description', '').strip()
            address = request.form.get('address', '').strip()
            phone = request.form.get('phone', '').strip()
            email = request.form.get('email', '').strip()
            website = request.form.get('website', '').strip()
            
            # Admin user fields
            create_admin = request.form.get('create_admin') == 'on'
            admin_username = request.form.get('admin_username', '').strip()
            admin_email = request.form.get('admin_email', '').strip()
            admin_first_name = request.form.get('admin_first_name', '').strip()
            admin_last_name = request.form.get('admin_last_name', '').strip()
            admin_password = request.form.get('admin_password', '').strip()
            
            if not name or not slug:
                flash('School name and slug are required', 'error')
                return render_template('add_school.html')
            
            # Validate admin user fields if creating admin
            if create_admin:
                if not admin_username or not admin_email or not admin_password:
                    flash('Admin username, email, and password are required when creating admin user', 'error')
                    return render_template('add_school.html')
            
            # Validate slug format
            if not slug.replace('-', '').replace('_', '').isalnum():
                flash('Slug must contain only letters, numbers, hyphens, and underscores', 'error')
                return render_template('add_school.html')
            
            session_db = get_session()
            try:
                # Check if slug already exists
                existing = session_db.query(Tenant).filter_by(slug=slug).first()
                if existing:
                    flash(f'A school with slug "{slug}" already exists', 'error')
                    return render_template('add_school.html')
                
                # Generate a unique code from the name
                code = name.upper().replace(' ', '')[:6]
                
                # Create new school
                new_school = Tenant(
                    name=name,
                    slug=slug,
                    is_active=True,
                    settings=json.dumps({
                        'created_via': 'admin_panel',
                        'code': code,
                        'description': description,
                        'address': address,
                        'contact_phone': phone,
                        'contact_email': email,
                        'website': website
                    })
                )
                
                session_db.add(new_school)
                session_db.commit()
                
                # Create school admin user if requested
                if create_admin:
                    try:
                        # Create admin user for this school
                        admin_user = User(
                            tenant_id=new_school.id,
                            username=admin_username,
                            email=admin_email,
                            first_name=admin_first_name or 'Admin',
                            last_name=admin_last_name or 'User',
                            role='school_admin',
                            is_active=True
                        )
                        admin_user.set_password(admin_password)
                        
                        session_db.add(admin_user)
                        session_db.commit()
                        
                        flash(f'School "{name}" and admin user "{admin_username}" created successfully!', 'success')
                    except Exception as e:
                        logger.error(f"Error creating admin user: {e}")
                        flash(f'School "{name}" created successfully, but failed to create admin user: {str(e)}', 'warning')
                else:
                    flash(f'School "{name}" created successfully!', 'success')
                
                return redirect(url_for('admin.manage_schools'))
                
            except Exception as e:
                session_db.rollback()
                logger.error(f"Error adding school: {e}")
                flash('Error adding school. Please try again.', 'error')
            finally:
                session_db.close()
        
        return render_template('add_school.html')
    
    @admin_bp.route('/schools/<slug>/users')
    @login_required
    def school_users(slug):
        """Manage users for a specific school"""
        if current_user.role != 'portal_admin':
            flash('Access denied', 'error')
            return redirect(url_for('admin.login'))
        
        session_db = get_session()
        try:
            # Get school info
            school = session_db.query(Tenant).filter_by(slug=slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.manage_schools'))
            
            # Get all users for this school
            users = session_db.query(User).filter_by(tenant_id=school.id).order_by(User.created_at.desc()).all()
            
            return render_template('school_users.html', school=school, users=users)
            
        except Exception as e:
            logger.error(f"Error loading school users: {e}")
            flash('Error loading users', 'error')
            return redirect(url_for('admin.manage_schools'))
        finally:
            session_db.close()
    
    @admin_bp.route('/schools/<slug>/users/add', methods=['GET', 'POST'])
    @login_required
    def add_school_user(slug):
        """Add user to a specific school"""
        if current_user.role != 'portal_admin':
            flash('Access denied', 'error')
            return redirect(url_for('admin.login'))
        
        session_db = get_session()
        try:
            # Get school info
            school = session_db.query(Tenant).filter_by(slug=slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.manage_schools'))
            
            if request.method == 'POST':
                username = request.form.get('username', '').strip()
                email = request.form.get('email', '').strip()
                password = request.form.get('password', '').strip()
                first_name = request.form.get('first_name', '').strip()
                last_name = request.form.get('last_name', '').strip()
                role = request.form.get('role', '').strip()
                
                if not all([username, email, password, first_name, last_name, role]):
                    flash('All fields are required', 'error')
                    return render_template('add_school_user.html', school=school)
                
                if role not in ['school_admin', 'teacher']:
                    flash('Invalid role selected', 'error')
                    return render_template('add_school_user.html', school=school)
                
                # Check if username or email already exists in this school
                existing_user = session_db.query(User).filter(
                    User.tenant_id == school.id,
                    (User.username == username) | (User.email == email)
                ).first()
                
                if existing_user:
                    flash('Username or email already exists in this school', 'error')
                    return render_template('add_school_user.html', school=school)
                
                # Create new user
                new_user = User(
                    username=username,
                    email=email,
                    password_hash=generate_password_hash(password),
                    first_name=first_name,
                    last_name=last_name,
                    role=role,
                    tenant_id=school.id
                )
                
                session_db.add(new_user)
                session_db.commit()
                
                flash(f'{role.replace("_", " ").title()} "{username}" added successfully!', 'success')
                return redirect(url_for('admin.school_users', slug=slug))
            
            return render_template('add_school_user.html', school=school)
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Error adding school user: {e}")
            flash('Error adding user. Please try again.', 'error')
            return redirect(url_for('admin.school_users', slug=slug))
        finally:
            session_db.close()
    
    @admin_bp.route('/schools/<slug>/toggle-status', methods=['POST'])
    @login_required
    def toggle_school_status(slug):
        """Toggle school active/inactive status"""
        if current_user.role != 'portal_admin':
            flash('Access denied', 'error')
            return redirect(url_for('admin.login'))
        
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.manage_schools'))
            
            school.is_active = not school.is_active
            session_db.commit()
            
            status = 'activated' if school.is_active else 'deactivated'
            flash(f'School "{school.name}" has been {status}', 'success')
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Error toggling school status: {e}")
            flash('Error updating school status', 'error')
        finally:
            session_db.close()
        
        return redirect(url_for('admin.manage_schools'))
    
    @admin_bp.route('/debug')
    @login_required
    def debug_info():
        """Debug information for development"""
        if current_user.role != 'portal_admin':
            flash('Access denied', 'error')
            return redirect(url_for('admin.login'))
        
        session_db = get_session()
        try:
            # Get database statistics
            stats = {}
            stats['tenants'] = session_db.query(Tenant).count()
            stats['total_users'] = session_db.query(User).count()
            stats['portal_admins'] = session_db.query(User).filter_by(role='portal_admin').count()
            stats['school_admins'] = session_db.query(User).filter_by(role='school_admin').count()
            stats['teachers'] = session_db.query(User).filter_by(role='teacher').count()
            stats['students'] = session_db.query(Student).count()
            
            # Get recent activity
            recent_schools = session_db.query(Tenant).order_by(Tenant.created_at.desc()).limit(5).all()
            recent_users = session_db.query(User).filter(User.tenant_id.isnot(None)).order_by(User.created_at.desc()).limit(10).all()
            
            return render_template_string("""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Debug Info - EduSaint</title>
                    <style>
                        body { font-family: Arial, sans-serif; margin: 40px; }
                        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }
                        .stat-card { background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }
                        .stat-number { font-size: 2em; font-weight: bold; color: #007bff; }
                        .recent { margin: 20px 0; }
                        .list-item { background: #fff; padding: 10px; margin: 5px 0; border-left: 4px solid #007bff; }
                    </style>
                </head>
                <body>
                    <h1>🔧 Debug Information</h1>
                    <p><a href="{{ url_for('admin.dashboard') }}">&larr; Back to Dashboard</a></p>
                    
                    <h2>📊 Database Statistics</h2>
                    <div class="stats">
                        <div class="stat-card">
                            <div class="stat-number">{{ stats.tenants }}</div>
                            <div>Schools</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{{ stats.total_users }}</div>
                            <div>Total Users</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{{ stats.portal_admins }}</div>
                            <div>Portal Admins</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{{ stats.school_admins }}</div>
                            <div>School Admins</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{{ stats.teachers }}</div>
                            <div>Teachers</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">{{ stats.students }}</div>
                            <div>Students</div>
                        </div>
                    </div>
                    
                    <h2>🏫 Recent Schools</h2>
                    <div class="recent">
                        {% for school in recent_schools %}
                        <div class="list-item">
                            <strong>{{ school.name }}</strong> ({{ school.slug }}) - 
                            {% if school.is_active %}✅ Active{% else %}❌ Inactive{% endif %} - 
                            {{ school.created_at.strftime('%Y-%m-%d %H:%M') }}
                        </div>
                        {% endfor %}
                    </div>
                    
                    <h2>👥 Recent Users</h2>
                    <div class="recent">
                        {% for user in recent_users %}
                        <div class="list-item">
                            <strong>{{ user.first_name }} {{ user.last_name }}</strong> (@{{ user.username }}) - 
                            {{ user.role.replace('_', ' ').title() }} - 
                            School: {{ user.tenant_id }} - 
                            {{ user.created_at.strftime('%Y-%m-%d %H:%M') }}
                        </div>
                        {% endfor %}
                    </div>
                </body>
                </html>
            """, stats=stats, recent_schools=recent_schools, recent_users=recent_users)
            
        except Exception as e:
            logger.error(f"Error loading debug info: {e}")
            return f"<h1>Debug Error</h1><p>{str(e)}</p>"
        finally:
            session_db.close()
    
    return admin_bp
