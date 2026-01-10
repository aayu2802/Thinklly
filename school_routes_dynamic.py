"""
Dynamic School Routes for Single Database Multi-Tenant System
Handles all school-specific routes with a single blueprint
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from sqlalchemy import desc, or_, extract
from datetime import datetime
import logging

from db_single import get_session
from models import User, Tenant, Student, Exam, StudentMark
from teacher_models import Teacher, EmployeeStatusEnum
from student_models import StudentAuth, StudentAuthUser
from expense_models import Expense, Budget, RecurringExpense, ExpenseCategoryEnum, PaymentMethodEnum, ExpenseStatusEnum

logger = logging.getLogger(__name__)

def create_school_blueprint():
    """Create a single blueprint that handles all school tenants dynamically"""
    
    school_bp = Blueprint('school', __name__, 
                         template_folder='akademi/templates',
                         static_folder='akademi/static')
    
    # Filter object for template context
    class FilterObj:
        def __init__(self, filters=None):
            if filters:
                for key, value in filters.items():
                    setattr(self, key, value)
    
    def require_school_auth(f):
        """Decorator to require school authentication"""
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'current_tenant'):
                return redirect('/admin/')
            
            if not current_user.is_authenticated:
                tenant_slug = g.current_tenant.slug
                return redirect(url_for('school.login', tenant_slug=tenant_slug))
            
            # Check if user belongs to current tenant
            if current_user.tenant_id != g.current_tenant.id:
                flash('Access denied - wrong school', 'error')
                tenant_slug = g.current_tenant.slug
                return redirect(url_for('school.login', tenant_slug=tenant_slug))
            
            return f(*args, **kwargs)
        
        decorated_function.__name__ = f.__name__
        return decorated_function
    
    @school_bp.route('/<tenant_slug>/')
    def index(tenant_slug):
        """School homepage - redirect to login or dashboard"""
        if current_user.is_authenticated and hasattr(g, 'current_tenant') and current_user.tenant_id == g.current_tenant.id:
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        return redirect(url_for('school.login', tenant_slug=tenant_slug))
    
    @school_bp.route('/<tenant_slug>/login', methods=['GET', 'POST'])
    def login(tenant_slug):
        """School user login"""
        session_db = get_session()
        try:
            # Get school info
            school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
            if not school:
                flash('School not found or inactive', 'error')
                return redirect('/admin/')
            
            if request.method == 'POST':
                username = request.form.get('username', '').strip()
                password = request.form.get('password', '').strip()
                
                if not username or not password:
                    flash('Please enter both username and password', 'error')
                    return render_template('akademi/school_login.html', school=school)
                
                # Find user in this school
                user = session_db.query(User).filter_by(
                    username=username,
                    tenant_id=school.id
                ).first()
                
                if user and check_password_hash(user.password_hash, password):
                    # Set custom user ID format for Flask-Login
                    user.get_id = lambda: f'school_{school.id}_{user.id}'
                    login_user(user, remember=True)
                    flash(f'Welcome back, {user.first_name}!', 'success')
                    return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
                else:
                    flash('Invalid username or password', 'error')
            
            return render_template('akademi/school_login.html', school=school)
            
        except Exception as e:
            logger.error(f"School login error for {tenant_slug}: {e}")
            flash('Login error occurred', 'error')
            return redirect('/admin/')
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/logout')
    def logout(tenant_slug):
        """Logout school user"""
        logout_user()
        flash('You have been logged out successfully', 'info')
        return redirect(url_for('school.login', tenant_slug=tenant_slug))
    
    # ===== SCHOOL ADMIN PASSWORD RESET ROUTES =====
    
    @school_bp.route('/<tenant_slug>/forgot-password', methods=['GET', 'POST'])
    def forgot_password(tenant_slug):
        """Step 1: Request password reset - enter email to receive OTP"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
            if not school:
                flash('School not found', 'error')
                return redirect('/admin/')
            
            if request.method == 'POST':
                email = request.form.get('email', '').strip().lower()
                
                if not email:
                    flash('Please enter your email address', 'error')
                    return render_template('akademi/school-admin-forgot-password.html', school=school)
                
                # Find user by email in this school
                user = session_db.query(User).filter(
                    User.tenant_id == school.id,
                    User.email == email
                ).first()
                
                if not user:
                    # Don't reveal if email exists - show same message
                    flash('If an account with this email exists, you will receive an OTP shortly.', 'info')
                    return render_template('akademi/school-admin-forgot-password.html', school=school)
                
                # Check if account is active
                if not user.is_active:
                    flash('This account has been deactivated. Please contact your administrator.', 'error')
                    return render_template('akademi/school-admin-forgot-password.html', school=school)
                
                # Get admin name
                admin_name = user.full_name or user.username
                
                # Generate OTP
                otp = user.generate_reset_otp()
                session_db.commit()
                
                # Send OTP email
                from notification_email import send_admin_otp_email
                success, msg = send_admin_otp_email(
                    to_email=email,
                    otp=otp,
                    admin_name=admin_name,
                    school_name=school.name
                )
                
                if success:
                    logger.info(f"Password reset OTP sent to {email} for school {tenant_slug}")
                    flash('OTP has been sent to your email address. Please check your inbox.', 'success')
                    # Store email in session for next step
                    from flask import session
                    session['admin_reset_email'] = email
                    return redirect(url_for('school.verify_otp', tenant_slug=tenant_slug))
                else:
                    logger.error(f"Failed to send OTP email to {email}: {msg}")
                    flash('Failed to send OTP email. Please try again later.', 'error')
                    return render_template('akademi/school-admin-forgot-password.html', school=school)
            
            # GET request
            return render_template('akademi/school-admin-forgot-password.html', school=school)
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Forgot password error for {tenant_slug}: {e}")
            import traceback
            traceback.print_exc()
            flash('An error occurred. Please try again.', 'error')
            return render_template('akademi/school-admin-forgot-password.html', 
                                 school={'name': tenant_slug, 'slug': tenant_slug})
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/verify-otp', methods=['GET', 'POST'])
    def verify_otp(tenant_slug):
        """Step 2: Verify OTP"""
        from flask import session as flask_session
        
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
            if not school:
                flash('School not found', 'error')
                return redirect('/admin/')
            
            # Check if email is in session
            reset_email = flask_session.get('admin_reset_email')
            if not reset_email:
                flash('Please start the password reset process from the beginning.', 'warning')
                return redirect(url_for('school.forgot_password', tenant_slug=tenant_slug))
            
            if request.method == 'POST':
                otp = request.form.get('otp', '').strip()
                
                if not otp or len(otp) != 6:
                    flash('Please enter a valid 6-digit OTP', 'error')
                    return render_template('akademi/school-admin-verify-otp.html', school=school, email=reset_email)
                
                # Find user
                user = session_db.query(User).filter(
                    User.tenant_id == school.id,
                    User.email == reset_email
                ).first()
                
                if not user:
                    flask_session.pop('admin_reset_email', None)
                    flash('Session expired. Please start again.', 'error')
                    return redirect(url_for('school.forgot_password', tenant_slug=tenant_slug))
                
                # Verify OTP
                if not user.verify_reset_otp(otp):
                    flash('Invalid or expired OTP. Please try again or request a new OTP.', 'error')
                    return render_template('akademi/school-admin-verify-otp.html', school=school, email=reset_email)
                
                # OTP verified - store verification flag
                flask_session['admin_otp_verified'] = True
                logger.info(f"OTP verified for {reset_email} at school {tenant_slug}")
                flash('OTP verified successfully. Please set your new password.', 'success')
                return redirect(url_for('school.reset_password', tenant_slug=tenant_slug))
            
            # GET request
            return render_template('akademi/school-admin-verify-otp.html', school=school, email=reset_email)
            
        except Exception as e:
            logger.error(f"OTP verification error for {tenant_slug}: {e}")
            import traceback
            traceback.print_exc()
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('school.forgot_password', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/reset-password', methods=['GET', 'POST'])
    def reset_password(tenant_slug):
        """Step 3: Set new password after OTP verification"""
        from flask import session as flask_session
        
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
            if not school:
                flash('School not found', 'error')
                return redirect('/admin/')
            
            # Check if OTP was verified
            reset_email = flask_session.get('admin_reset_email')
            otp_verified = flask_session.get('admin_otp_verified')
            
            if not reset_email or not otp_verified:
                flash('Please complete the OTP verification first.', 'warning')
                return redirect(url_for('school.forgot_password', tenant_slug=tenant_slug))
            
            if request.method == 'POST':
                password = request.form.get('password', '').strip()
                confirm_password = request.form.get('confirm_password', '').strip()
                
                # Validation
                if not password or not confirm_password:
                    flash('Please enter and confirm your new password', 'error')
                    return render_template('akademi/school-admin-reset-password.html', school=school)
                
                if password != confirm_password:
                    flash('Passwords do not match', 'error')
                    return render_template('akademi/school-admin-reset-password.html', school=school)
                
                if len(password) < 8:
                    flash('Password must be at least 8 characters', 'error')
                    return render_template('akademi/school-admin-reset-password.html', school=school)
                
                # Find user
                user = session_db.query(User).filter(
                    User.tenant_id == school.id,
                    User.email == reset_email
                ).first()
                
                if not user:
                    flask_session.pop('admin_reset_email', None)
                    flask_session.pop('admin_otp_verified', None)
                    flash('Session expired. Please start again.', 'error')
                    return redirect(url_for('school.forgot_password', tenant_slug=tenant_slug))
                
                # Update password
                user.set_password(password)
                user.clear_reset_otp()
                session_db.commit()
                
                # Clear session
                flask_session.pop('admin_reset_email', None)
                flask_session.pop('admin_otp_verified', None)
                
                logger.info(f"Password reset successfully for {reset_email} at school {tenant_slug}")
                flash('Password reset successfully! You can now login with your new password.', 'success')
                return redirect(url_for('school.login', tenant_slug=tenant_slug))
            
            # GET request
            return render_template('akademi/school-admin-reset-password.html', school=school)
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Password reset error for {tenant_slug}: {e}")
            import traceback
            traceback.print_exc()
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('school.forgot_password', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/resend-otp', methods=['POST'])
    def resend_otp(tenant_slug):
        """Resend OTP for password reset"""
        from flask import session as flask_session
        
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            reset_email = flask_session.get('admin_reset_email')
            if not reset_email:
                return jsonify({'success': False, 'message': 'Session expired. Please start again.'}), 400
            
            # Find user
            user = session_db.query(User).filter(
                User.tenant_id == school.id,
                User.email == reset_email
            ).first()
            
            if not user:
                return jsonify({'success': False, 'message': 'Account not found.'}), 404
            
            # Get admin name
            admin_name = user.full_name or user.username
            
            # Generate new OTP
            otp = user.generate_reset_otp()
            session_db.commit()
            
            # Send OTP email
            from notification_email import send_admin_otp_email
            success, msg = send_admin_otp_email(
                to_email=reset_email,
                otp=otp,
                admin_name=admin_name,
                school_name=school.name
            )
            
            if success:
                logger.info(f"OTP resent to {reset_email} for school {tenant_slug}")
                return jsonify({'success': True, 'message': 'New OTP sent to your email.'})
            else:
                logger.error(f"Failed to resend OTP to {reset_email}: {msg}")
                return jsonify({'success': False, 'message': 'Failed to send OTP. Please try again.'}), 500
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Resend OTP error for {tenant_slug}: {e}")
            return jsonify({'success': False, 'message': 'An error occurred.'}), 500
        finally:
            session_db.close()
    
    
    @school_bp.route('/<tenant_slug>/dashboard')
    @require_school_auth
    def dashboard(tenant_slug):
        """School dashboard - redirects to home dashboard"""
        return redirect(url_for('home.home_dashboard', tenant_slug=tenant_slug))
    
    
    
    # ===== TIMETABLE MANAGEMENT ROUTES =====
    
    

    # ===== REGISTER FEE MANAGEMENT ROUTES =====
    from fee_routes import register_fee_routes
    register_fee_routes(school_bp, require_school_auth)

    # ===== REGISTER LIBRARY MANAGEMENT ROUTES =====
    from library_routes import create_library_routes
    create_library_routes(school_bp, require_school_auth)

    # ===== REGISTER EXAMINATION ROUTES =====
    from examination_routes import register_examination_routes
    register_examination_routes(school_bp, require_school_auth)

    # ===== REGISTER QUESTION PAPER ROUTES =====
    from question_paper_routes import register_question_paper_routes, register_copy_checking_routes
    register_question_paper_routes(school_bp, require_school_auth)
    register_copy_checking_routes(school_bp, require_school_auth)

    # ===== REGISTER NOTIFICATION ROUTES =====
    from notification_routes import create_notification_routes
    create_notification_routes(school_bp, require_school_auth)

    # ===== REGISTER TRANSPORT ROUTES =====
    from transport_routes import create_transport_routes
    create_transport_routes(school_bp, require_school_auth)
    
    # ===== REGISTER FINANCE ROUTES =====
    from finance_routes import register_finance_routes
    register_finance_routes(school_bp, require_school_auth)

    # ===== REGISTER STUDENT ROUTES =====
    from student_routes import register_student_routes
    register_student_routes(school_bp, require_school_auth)
    
    # ===== REGISTER TEACHER ROUTES =====
    from teacher_routes import register_teacher_routes
    register_teacher_routes(school_bp, require_school_auth)

    # ===== REGISTER TIMETABLE ROUTES =====
    from timetable_routes import register_timetable_routes
    register_timetable_routes(school_bp, require_school_auth)

    # ===== REGISTER CHAT ROUTES =====
    from chat_routes import register_chat_routes
    register_chat_routes(school_bp, require_school_auth)
    
    return school_bp
