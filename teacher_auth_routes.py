"""
Teacher Authentication Routes
Simple registration and login system for teachers (No 2FA)
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import logging

from db_single import get_session
from models import Tenant
from teacher_models import Teacher, TeacherAuth

logger = logging.getLogger(__name__)

# Create blueprint
teacher_auth_bp = Blueprint('teacher_auth', __name__)


# ===== HELPER CLASSES =====

class TeacherAuthUser:
    """Wrapper for Flask-Login integration"""
    def __init__(self, teacher_auth, teacher=None):
        self.id = teacher_auth.id
        self.teacher_id = teacher_auth.teacher_id
        self.tenant_id = teacher_auth.tenant_id
        self.email = teacher_auth.email
        self._is_active = teacher_auth.is_active
        self.teacher = teacher  # Store teacher object for easy access
        self.role = 'teacher'  # Add role attribute for compatibility
    
    def get_id(self):
        """Return user ID for Flask-Login"""
        return f"teacher_{self.tenant_id}_{self.id}"
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_active(self):
        return self._is_active
    
    @property
    def is_anonymous(self):
        return False


# ===== DECORATORS =====

def require_teacher_auth(f):
    """Decorator to require teacher authentication"""
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            tenant_slug = kwargs.get('tenant_slug') or g.current_tenant.slug
            flash('Please login to access this page', 'warning')
            return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
        
        # Check if this is a teacher user
        if not hasattr(current_user, 'teacher_id'):
            tenant_slug = kwargs.get('tenant_slug') or g.current_tenant.slug
            flash('Access denied - teachers only', 'error')
            return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
        
        # Check if user belongs to current tenant
        if hasattr(g, 'current_tenant') and current_user.tenant_id != g.current_tenant.id:
            tenant_slug = g.current_tenant.slug
            flash('Access denied - wrong school', 'error')
            return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
        
        # Check if teacher has resigned (real-time check)
        from teacher_resignation_handler import is_teacher_resigned
        session_db = get_session()
        try:
            if is_teacher_resigned(session_db, current_user.teacher_id):
                tenant_slug = kwargs.get('tenant_slug') or g.current_tenant.slug
                logout_user()
                flash('Your account has been deactivated. Please contact your school administration.', 'error')
                return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
        finally:
            session_db.close()
        
        return f(*args, **kwargs)
    
    decorated_function.__name__ = f.__name__
    return decorated_function


# ===== ROUTES =====

@teacher_auth_bp.route('/<tenant_slug>/teacher/register', methods=['GET', 'POST'])
def register(tenant_slug):
    """Teacher registration - create account"""
    session_db = get_session()
    try:
        # Get school
        school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
        if not school:
            flash('School not found', 'error')
            return redirect('/admin/')
        
        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            mobile = request.form.get('mobile', '').strip()
            password = request.form.get('password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()
            
            # Validation
            if not email or not password:
                flash('Email and password are required', 'error')
                return render_template('teacher_dashboard_new/register.html', school=school, form_data=request.form)
            
            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return render_template('teacher_dashboard_new/register.html', school=school, form_data=request.form)
            
            if len(password) < 8:
                flash('Password must be at least 8 characters', 'error')
                return render_template('teacher_dashboard_new/register.html', school=school, form_data=request.form)
            
            # Check if email exists in teachers table
            teacher = session_db.query(Teacher).filter_by(
                email=email,
                tenant_id=school.id
            ).first()
            
            if not teacher:
                flash('Email not found in teacher records. Please contact your school administration.', 'error')
                return render_template('teacher_dashboard_new/register.html', school=school, form_data=request.form)
            
            # Check if teacher already has an account
            existing_auth = session_db.query(TeacherAuth).filter_by(
                teacher_id=teacher.id
            ).first()
            
            if existing_auth:
                flash('Account already exists for this email. Please login instead.', 'warning')
                return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
            
            # Create teacher auth record
            teacher_auth = TeacherAuth(
                tenant_id=school.id,
                teacher_id=teacher.id,
                email=email,
                mobile=mobile if mobile else None,
                is_active=True
            )
            teacher_auth.set_password(password)
            
            session_db.add(teacher_auth)
            session_db.commit()
            
            # Auto-login after registration
            teacher_user = TeacherAuthUser(teacher_auth, teacher)
            login_user(teacher_user, remember=True)
            
            logger.info(f"New teacher registered: {email} for school {tenant_slug}")
            flash(f'Welcome {teacher.full_name}! Your account has been created successfully.', 'success')
            return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
        
        # GET request
        return render_template('teacher_dashboard_new/register.html', school=school, form_data={})
        
    except Exception as e:
        session_db.rollback()
        logger.error(f"Registration error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        flash('Registration error occurred. Please try again.', 'error')
        return render_template('teacher_dashboard_new/register.html', 
                             school={'name': tenant_slug, 'slug': tenant_slug},
                             form_data=request.form if request.method == 'POST' else {})
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/login', methods=['GET', 'POST'])
def login(tenant_slug):
    """Teacher login"""
    session_db = get_session()
    try:
        # Get school
        school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
        if not school:
            flash('School not found', 'error')
            return redirect('/admin/')
        
        # If already logged in as teacher, redirect to dashboard
        if current_user.is_authenticated and hasattr(current_user, 'teacher_id'):
            if current_user.tenant_id == school.id:
                return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
        
        if request.method == 'POST':
            email_or_mobile = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '').strip()
            remember = request.form.get('remember', False) == 'on'
            
            if not email_or_mobile or not password:
                flash('Email/Mobile and password are required', 'error')
                return render_template('teacher_dashboard_new/login.html', school=school)
            
            # Find teacher auth by email or mobile
            teacher_auth = session_db.query(TeacherAuth).filter(
                TeacherAuth.tenant_id == school.id,
                ((TeacherAuth.email == email_or_mobile) | (TeacherAuth.mobile == email_or_mobile))
            ).first()
            
            if not teacher_auth:
                flash('Invalid email/mobile or password', 'error')
                return render_template('teacher_dashboard_new/login.html', school=school)
            
            # Check password
            if not teacher_auth.check_password(password):
                flash('Invalid email/mobile or password', 'error')
                return render_template('teacher_dashboard_new/login.html', school=school)
            
            # Check if account is active
            if not teacher_auth.is_active:
                flash('Your account has been deactivated. Please contact your school administration.', 'error')
                return render_template('teacher_dashboard_new/login.html', school=school)
            
            # Get teacher details
            teacher = session_db.query(Teacher).filter_by(id=teacher_auth.teacher_id).first()
            
            # Check if teacher has resigned - prevent login
            from teacher_models import EmployeeStatusEnum
            if teacher and teacher.employee_status == EmployeeStatusEnum.RESIGNED:
                flash('Your account has been deactivated due to resignation. Please contact your school administration.', 'error')
                return render_template('teacher_dashboard_new/login.html', school=school)
            
            # Update last login
            teacher_auth.last_login = datetime.utcnow()
            session_db.commit()
            
            # Login user
            teacher_user = TeacherAuthUser(teacher_auth, teacher)
            login_user(teacher_user, remember=remember)
            
            logger.info(f"Teacher logged in: {email_or_mobile} for school {tenant_slug}")
            flash(f'Welcome back, {teacher.full_name}!', 'success')
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if next_page and next_page.startswith(f'/{tenant_slug}/'):
                return redirect(next_page)
            return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
        
        # GET request
        return render_template('teacher_dashboard_new/login.html', school=school)
        
    except Exception as e:
        logger.error(f"Login error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        flash('Login error occurred. Please try again.', 'error')
        return render_template('teacher_dashboard_new/login.html', 
                             school={'name': tenant_slug, 'slug': tenant_slug})
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/logout')
@require_teacher_auth
def logout(tenant_slug):
    """Teacher logout"""
    logger.info(f"Teacher logged out from school {tenant_slug}")
    logout_user()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))


# ===== PASSWORD RESET ROUTES =====

@teacher_auth_bp.route('/<tenant_slug>/teacher/forgot-password', methods=['GET', 'POST'])
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
                return render_template('teacher_dashboard_new/forgot_password.html', school=school)
            
            # Find teacher auth by email
            teacher_auth = session_db.query(TeacherAuth).filter(
                TeacherAuth.tenant_id == school.id,
                TeacherAuth.email == email
            ).first()
            
            if not teacher_auth:
                # Don't reveal if email exists - show same message
                flash('If an account with this email exists, you will receive an OTP shortly.', 'info')
                return render_template('teacher_dashboard_new/forgot_password.html', school=school)
            
            # Check if account is active
            if not teacher_auth.is_active:
                flash('This account has been deactivated. Please contact your school administration.', 'error')
                return render_template('teacher_dashboard_new/forgot_password.html', school=school)
            
            # Get teacher name
            teacher = session_db.query(Teacher).filter_by(id=teacher_auth.teacher_id).first()
            teacher_name = teacher.full_name if teacher else "Teacher"
            
            # Generate OTP
            otp = teacher_auth.generate_reset_otp()
            session_db.commit()
            
            # Send OTP email
            from notification_email import send_otp_email
            success, msg = send_otp_email(
                to_email=email,
                otp=otp,
                teacher_name=teacher_name,
                school_name=school.name
            )
            
            if success:
                logger.info(f"Password reset OTP sent to {email} for school {tenant_slug}")
                flash('OTP has been sent to your email address. Please check your inbox.', 'success')
                # Store email in session for next step
                from flask import session
                session['reset_email'] = email
                return redirect(url_for('teacher_auth.verify_otp', tenant_slug=tenant_slug))
            else:
                logger.error(f"Failed to send OTP email to {email}: {msg}")
                flash('Failed to send OTP email. Please try again later.', 'error')
                return render_template('teacher_dashboard_new/forgot_password.html', school=school)
        
        # GET request
        return render_template('teacher_dashboard_new/forgot_password.html', school=school)
        
    except Exception as e:
        session_db.rollback()
        logger.error(f"Forgot password error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        flash('An error occurred. Please try again.', 'error')
        return render_template('teacher_dashboard_new/forgot_password.html', 
                             school={'name': tenant_slug, 'slug': tenant_slug})
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/verify-otp', methods=['GET', 'POST'])
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
        reset_email = flask_session.get('reset_email')
        if not reset_email:
            flash('Please start the password reset process from the beginning.', 'warning')
            return redirect(url_for('teacher_auth.forgot_password', tenant_slug=tenant_slug))
        
        if request.method == 'POST':
            otp = request.form.get('otp', '').strip()
            
            if not otp or len(otp) != 6:
                flash('Please enter a valid 6-digit OTP', 'error')
                return render_template('teacher_dashboard_new/verify_otp.html', school=school, email=reset_email)
            
            # Find teacher auth
            teacher_auth = session_db.query(TeacherAuth).filter(
                TeacherAuth.tenant_id == school.id,
                TeacherAuth.email == reset_email
            ).first()
            
            if not teacher_auth:
                flask_session.pop('reset_email', None)
                flash('Session expired. Please start again.', 'error')
                return redirect(url_for('teacher_auth.forgot_password', tenant_slug=tenant_slug))
            
            # Verify OTP
            if not teacher_auth.verify_reset_otp(otp):
                flash('Invalid or expired OTP. Please try again or request a new OTP.', 'error')
                return render_template('teacher_dashboard_new/verify_otp.html', school=school, email=reset_email)
            
            # OTP verified - store verification flag
            flask_session['otp_verified'] = True
            logger.info(f"OTP verified for {reset_email} at school {tenant_slug}")
            flash('OTP verified successfully. Please set your new password.', 'success')
            return redirect(url_for('teacher_auth.reset_password', tenant_slug=tenant_slug))
        
        # GET request
        return render_template('teacher_dashboard_new/verify_otp.html', school=school, email=reset_email)
        
    except Exception as e:
        logger.error(f"OTP verification error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('teacher_auth.forgot_password', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/reset-password', methods=['GET', 'POST'])
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
        reset_email = flask_session.get('reset_email')
        otp_verified = flask_session.get('otp_verified')
        
        if not reset_email or not otp_verified:
            flash('Please complete the OTP verification first.', 'warning')
            return redirect(url_for('teacher_auth.forgot_password', tenant_slug=tenant_slug))
        
        if request.method == 'POST':
            password = request.form.get('password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()
            
            # Validation
            if not password or not confirm_password:
                flash('Please enter and confirm your new password', 'error')
                return render_template('teacher_dashboard_new/reset_password.html', school=school)
            
            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return render_template('teacher_dashboard_new/reset_password.html', school=school)
            
            if len(password) < 8:
                flash('Password must be at least 8 characters', 'error')
                return render_template('teacher_dashboard_new/reset_password.html', school=school)
            
            # Find teacher auth
            teacher_auth = session_db.query(TeacherAuth).filter(
                TeacherAuth.tenant_id == school.id,
                TeacherAuth.email == reset_email
            ).first()
            
            if not teacher_auth:
                flask_session.pop('reset_email', None)
                flask_session.pop('otp_verified', None)
                flash('Session expired. Please start again.', 'error')
                return redirect(url_for('teacher_auth.forgot_password', tenant_slug=tenant_slug))
            
            # Update password
            teacher_auth.set_password(password)
            teacher_auth.clear_reset_otp()
            session_db.commit()
            
            # Clear session
            flask_session.pop('reset_email', None)
            flask_session.pop('otp_verified', None)
            
            logger.info(f"Password reset successfully for {reset_email} at school {tenant_slug}")
            flash('Password reset successfully! You can now login with your new password.', 'success')
            return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
        
        # GET request
        return render_template('teacher_dashboard_new/reset_password.html', school=school)
        
    except Exception as e:
        session_db.rollback()
        logger.error(f"Password reset error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('teacher_auth.forgot_password', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/resend-otp', methods=['POST'])
def resend_otp(tenant_slug):
    """Resend OTP for password reset"""
    from flask import session as flask_session
    
    session_db = get_session()
    try:
        school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
        if not school:
            return jsonify({'success': False, 'message': 'School not found'}), 404
        
        reset_email = flask_session.get('reset_email')
        if not reset_email:
            return jsonify({'success': False, 'message': 'Session expired. Please start again.'}), 400
        
        # Find teacher auth
        teacher_auth = session_db.query(TeacherAuth).filter(
            TeacherAuth.tenant_id == school.id,
            TeacherAuth.email == reset_email
        ).first()
        
        if not teacher_auth:
            return jsonify({'success': False, 'message': 'Account not found.'}), 404
        
        # Get teacher name
        teacher = session_db.query(Teacher).filter_by(id=teacher_auth.teacher_id).first()
        teacher_name = teacher.full_name if teacher else "Teacher"
        
        # Generate new OTP
        otp = teacher_auth.generate_reset_otp()
        session_db.commit()
        
        # Send OTP email
        from notification_email import send_otp_email
        success, msg = send_otp_email(
            to_email=reset_email,
            otp=otp,
            teacher_name=teacher_name,
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


@teacher_auth_bp.route('/<tenant_slug>/teacher/dashboard')
@require_teacher_auth
def dashboard(tenant_slug):
    """Teacher dashboard - displays teacher-login-portal.html"""
    session_db = get_session()
    try:
        from attendance_helpers import get_monthly_attendance, calculate_attendance_stats, get_teacher_attendance_calendar
        from teacher_models import TeacherSalary
        from timetable_helpers import get_teacher_schedule, get_today_schedule, get_current_academic_year
        from timetable_models import ClassTeacherAssignment
        from leave_helpers import get_teacher_balance, get_current_academic_year as get_leave_academic_year
        from teacher_models import TeacherLeave, LeaveStatusEnum
        from datetime import datetime
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get teacher info
        teacher = session_db.query(Teacher).filter_by(
            id=current_user.teacher_id
        ).first()
        
        if not teacher:
            flash('Teacher record not found', 'error')
            return redirect(url_for('teacher_auth.logout', tenant_slug=tenant_slug))
        
        # Get attendance data for current month
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        # Fetch monthly attendance records
        monthly_attendance = get_teacher_attendance_calendar(
            session_db, teacher.id, current_month, current_year
        )
        
        # Calculate attendance statistics
        attendance_stats = calculate_attendance_stats(
            session_db, teacher.id, current_month, current_year
        )
        
        # Get salary data
        salary_data = session_db.query(TeacherSalary).filter_by(
            teacher_id=teacher.id,
            tenant_id=school.id
        ).first()
        
        # Get timetable data
        academic_year = get_current_academic_year()
        weekly_schedule = get_teacher_schedule(session_db, teacher.id, school.id, academic_year)
        today_schedule = get_today_schedule(session_db, teacher.id, school.id, academic_year)
        
        # Get class teacher assignments
        class_teacher_assignments = session_db.query(ClassTeacherAssignment).filter_by(
            teacher_id=teacher.id,
            tenant_id=school.id,
            is_class_teacher=True
        ).filter(
            ClassTeacherAssignment.removed_date.is_(None)
        ).all()
        
        # Get leave balance for current academic year
        leave_academic_year = get_leave_academic_year()
        leave_balance = get_teacher_balance(session_db, teacher.id, leave_academic_year)
        
        # Calculate total leaves taken (approved only)
        total_leaves_taken = 0
        total_leaves_quota = 0
        if leave_balance:
            total_leaves_taken = (
                (leave_balance.cl_taken or 0) + 
                (leave_balance.sl_taken or 0) + 
                (leave_balance.el_taken or 0)
            )
            total_leaves_quota = (
                (leave_balance.cl_total or 0) + 
                (leave_balance.sl_total or 0) + 
                (leave_balance.el_total or 0)
            )
        
        # Count today's classes
        classes_today = len(today_schedule) if today_schedule else 0
        
        # Get unread notification count
        from notification_models import NotificationRecipient, RecipientStatusEnum
        unread_count = session_db.query(NotificationRecipient).filter(
            NotificationRecipient.teacher_id == teacher.id,
            NotificationRecipient.tenant_id == school.id,
            NotificationRecipient.status != RecipientStatusEnum.READ
        ).count()
        
        # Render the modular dashboard template
        return render_template('teacher_dashboard_new/dashboard.html',
                             school=school,
                             teacher=teacher,
                             current_user=current_user,
                             monthly_attendance=monthly_attendance,
                             attendance_stats=attendance_stats,
                             salary_data=salary_data,
                             weekly_schedule=weekly_schedule,
                             today_schedule=today_schedule,
                             academic_year=academic_year,
                             class_teacher_assignments=class_teacher_assignments,
                             leave_balance=leave_balance,
                             total_leaves_taken=total_leaves_taken,
                             total_leaves_quota=total_leaves_quota,
                             classes_today=classes_today,
                             unread_count=unread_count,
                             page_title="Dashboard")
        
    except Exception as e:
        logger.error(f"Dashboard error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading dashboard', 'error')
        return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/attendance/json')
@require_teacher_auth
def attendance_json(tenant_slug):
    """Return attendance data for a specific month/year as JSON with summary stats"""
    session_db = get_session()
    try:
        from attendance_helpers import get_teacher_attendance_calendar
        from datetime import datetime
        from flask import jsonify
        
        # Get month and year from query params
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int)
        
        # Default to current month/year if not provided
        if not month or not year:
            now = datetime.now()
            month = month or now.month
            year = year or now.year
        
        # Validate month and year
        if not (1 <= month <= 12):
            return jsonify({'error': 'Invalid month'}), 400
        if not (2000 <= year <= 2100):
            return jsonify({'error': 'Invalid year'}), 400
        
        # Get teacher info
        teacher = session_db.query(Teacher).filter_by(
            id=current_user.teacher_id
        ).first()
        
        if not teacher:
            return jsonify({'error': 'Teacher not found'}), 404
        
        # Fetch monthly attendance records (helpers may return list of dicts or ORM objects)
        monthly_attendance = get_teacher_attendance_calendar(
            session_db, teacher.id, month, year
        )

        # Normalize to JSON-serializable format
        attendance_list = []
        present_count = 0
        absent_count = 0
        total_working_days = 0
        
        for rec in monthly_attendance:
            # rec can be a dict produced by attendance_helpers or an ORM object
            try:
                if isinstance(rec, dict):
                    att_date = rec.get('attendance_date')
                    # attendance_date could be a date object or ISO string
                    if hasattr(att_date, 'strftime'):
                        date_str = att_date.strftime('%Y-%m-%d')
                    else:
                        date_str = str(att_date) if att_date is not None else None

                    status = rec.get('status')
                    status_class = rec.get('status_class')
                    check_in = rec.get('check_in')
                    check_out = rec.get('check_out')
                    working_hours = rec.get('working_hours')
                    remarks = rec.get('remarks')
                else:
                    # ORM object
                    att_date = getattr(rec, 'attendance_date', None)
                    date_str = att_date.strftime('%Y-%m-%d') if hasattr(att_date, 'strftime') else str(att_date)

                    # status may be Enum or string
                    st = getattr(rec, 'status', None)
                    if hasattr(st, 'value'):
                        status = st.value
                    else:
                        status = str(st) if st is not None else None

                    status_class = getattr(rec, 'status_class', None)
                    check_in = getattr(rec, 'check_in', None) or getattr(rec, 'check_in_time', None)
                    check_out = getattr(rec, 'check_out', None) or getattr(rec, 'check_out_time', None)
                    working_hours = getattr(rec, 'working_hours', None)
                    remarks = getattr(rec, 'remarks', None)

                # Format times if they are time objects
                if hasattr(check_in, 'strftime'):
                    check_in = check_in.strftime('%H:%M')
                if hasattr(check_out, 'strftime'):
                    check_out = check_out.strftime('%H:%M')

                # Ensure working_hours is numeric or null
                if working_hours is not None:
                    try:
                        working_hours = float('%.2f' % float(working_hours))
                    except Exception:
                        working_hours = None

                # Count for summary (only count working days - exclude holidays/week off)
                if status and status not in ['Holiday', 'Week Off']:
                    total_working_days += 1
                    if status == 'Present' or status == 'Half-Day':
                        present_count += 1
                    elif status == 'Absent':
                        absent_count += 1

                attendance_list.append({
                    'attendance_date': date_str,
                    'status': status,
                    'status_class': status_class,
                    'check_in': check_in if check_in else None,
                    'check_out': check_out if check_out else None,
                    'working_hours': working_hours,
                    'remarks': remarks if remarks else None
                })
            except Exception:
                # Skip malformed record but continue processing others
                logger.exception('Failed to normalize attendance record')
                continue

        # Calculate attendance percentage
        attendance_percent = round((present_count / total_working_days * 100), 1) if total_working_days > 0 else 0.0

        # Return new format with summary + records
        return jsonify({
            'summary': {
                'working_days': total_working_days,
                'present': present_count,
                'absent': absent_count,
                'attendance_percent': attendance_percent
            },
            'records': attendance_list
        })
        
    except Exception as e:
        logger.error(f"Attendance JSON error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch attendance data'}), 500
    finally:
        session_db.close()


# Optional: Index route that redirects to login
@teacher_auth_bp.route('/<tenant_slug>/teacher')
def index(tenant_slug):
    """Teacher portal index - redirect to login or dashboard"""
    if current_user.is_authenticated and hasattr(current_user, 'teacher_id'):
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))


# ===== STUDENT ATTENDANCE MANAGEMENT (For Class Teachers) =====

@teacher_auth_bp.route('/<tenant_slug>/teacher/students/classes')
@require_teacher_auth
def get_teacher_classes(tenant_slug):
    """Get classes where teacher is class teacher - JSON endpoint"""
    session_db = get_session()
    try:
        from timetable_models import ClassTeacherAssignment
        from models import Class
        from sqlalchemy.orm import joinedload
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get class teacher assignments
        assignments = session_db.query(ClassTeacherAssignment).options(
            joinedload(ClassTeacherAssignment.class_ref)
        ).filter_by(
            teacher_id=current_user.teacher_id,
            tenant_id=school.id,
            is_class_teacher=True
        ).filter(
            ClassTeacherAssignment.removed_date.is_(None)
        ).all()
        
        classes = []
        for assignment in assignments:
            if assignment.class_ref:
                classes.append({
                    'id': assignment.class_id,
                    'name': f"{assignment.class_ref.class_name}-{assignment.class_ref.section}",
                    'class_name': assignment.class_ref.class_name,
                    'section': assignment.class_ref.section
                })
        
        return jsonify({
            'success': True,
            'classes': classes
        })
        
    except Exception as e:
        logger.error(f"Error fetching teacher classes: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/students/list')
@require_teacher_auth
def student_list(tenant_slug):
    """Get students for a class - JSON endpoint"""
    session_db = get_session()
    try:
        from models import Student, StudentAttendanceSummary
        from timetable_models import ClassTeacherAssignment
        from datetime import datetime
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        class_id = request.args.get('class_id', type=int)
        
        if not class_id:
            return jsonify({
                'success': False,
                'error': 'Class ID required'
            }), 400
        
        # Verify teacher is class teacher for this class
        is_class_teacher = session_db.query(ClassTeacherAssignment).filter_by(
            teacher_id=current_user.teacher_id,
            tenant_id=school.id,
            class_id=class_id,
            is_class_teacher=True
        ).filter(
            ClassTeacherAssignment.removed_date.is_(None)
        ).first()
        
        if not is_class_teacher:
            return jsonify({
                'success': False,
                'error': 'Access denied - not class teacher for this class'
            }), 403
        
        # Fetch students
        students = session_db.query(Student).filter_by(
            tenant_id=school.id,
            class_id=class_id
        ).order_by(Student.roll_number, Student.full_name).all()
        
        # Get current month and year for attendance percentage
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        student_list = []
        for student in students:
            # Get attendance summary for current month
            summary = session_db.query(StudentAttendanceSummary).filter_by(
                student_id=student.id,
                month=current_month,
                year=current_year
            ).first()
            
            attendance_percentage = float(summary.attendance_percentage) if summary and summary.attendance_percentage else 0.0
            
            student_list.append({
                'id': student.id,
                'name': student.full_name,
                'roll_number': student.roll_number,
                'admission_number': student.admission_number,
                'class_id': student.class_id,
                'attendance_percentage': attendance_percentage
            })
        
        return jsonify({
            'success': True,
            'students': student_list
        })
        
    except Exception as e:
        logger.error(f"Error fetching students: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/students')
@require_teacher_auth
def student_management(tenant_slug):
    """Student management dashboard for class teachers"""
    session_db = get_session()
    try:
        from timetable_models import ClassTeacherAssignment
        from sqlalchemy.orm import joinedload
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        teacher = session_db.query(Teacher).filter_by(id=current_user.teacher_id).first()
        
        # Get class teacher assignments
        class_teacher_assignments = session_db.query(ClassTeacherAssignment).options(
            joinedload(ClassTeacherAssignment.class_ref)
        ).filter_by(
            teacher_id=current_user.teacher_id,
            tenant_id=school.id,
            is_class_teacher=True
        ).filter(
            ClassTeacherAssignment.removed_date.is_(None)
        ).all()
        
        return render_template('teacher_dashboard_new/students/student_list.html',
                             school=school,
                             teacher=teacher,
                             current_user=current_user,
                             class_teacher_assignments=class_teacher_assignments,
                             page_title="Student Management")
    
    except Exception as e:
        logger.error(f"Student management error: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading student management', 'error')
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/students/attendance/mark', methods=['GET', 'POST'])
@require_teacher_auth
def mark_student_attendance(tenant_slug):
    """Mark student attendance for class teacher's class"""
    session_db = get_session()
    try:
        from models import Student, StudentAttendance, StudentAttendanceStatusEnum
        from timetable_models import ClassTeacherAssignment
        from student_attendance_helpers import mark_student_attendance as mark_attendance_helper, check_holidays_and_automark
        from datetime import datetime as dt, date
        from sqlalchemy.orm import joinedload
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get class teacher assignments
        class_assignments = session_db.query(ClassTeacherAssignment).options(
            joinedload(ClassTeacherAssignment.class_ref)
        ).filter_by(
            teacher_id=current_user.teacher_id,
            tenant_id=school.id,
            is_class_teacher=True
        ).filter(
            ClassTeacherAssignment.removed_date.is_(None)
        ).all()
        
        # If not a class teacher, show page with message instead of redirecting
        teacher = session_db.query(Teacher).filter_by(id=current_user.teacher_id).first()
        
        if not class_assignments:
            return render_template('teacher_dashboard_new/students/mark_attendance.html',
                                 school=school,
                                 teacher=teacher,
                                 current_user=current_user,
                                 class_assignments=[],
                                 selected_class_id=None,
                                 students=[],
                                 selected_date=date.today(),
                                 attendance_dict={},
                                 status_enum=StudentAttendanceStatusEnum,
                                 today=date.today(),
                                 is_holiday=False,
                                 page_title="Mark Attendance")
        
        # Get selected date and class
        selected_date_str = request.values.get('date', date.today().strftime('%Y-%m-%d'))
        class_id = request.values.get('class_id', type=int)
        
        # Default to first assigned class if not specified
        if not class_id and class_assignments:
            class_id = class_assignments[0].class_id
        
        try:
            selected_date = dt.strptime(selected_date_str, '%Y-%m-%d').date()
        except:
            selected_date = date.today()
        
        if request.method == 'POST':
            # Check if date is a holiday
            if class_id and check_holidays_and_automark(session_db, school.id, class_id, selected_date):
                flash('Cannot mark attendance on a holiday', 'error')
                return redirect(url_for('teacher_auth.mark_student_attendance', 
                                      tenant_slug=tenant_slug,
                                      date=selected_date_str, 
                                      class_id=class_id))
            
            # Handle bulk attendance marking
            try:
                marked_count = 0
                errors = []
                
                for key in request.form:
                    if key.startswith('status_'):
                        student_id = int(key.split('_')[1])
                        status_value = request.form[key]
                        
                        if not status_value:
                            continue
                        
                        # Get check-in, check-out, remarks
                        check_in_str = request.form.get(f'check_in_{student_id}', '').strip()
                        check_out_str = request.form.get(f'check_out_{student_id}', '').strip()
                        remarks = request.form.get(f'remarks_{student_id}', '').strip()
                        
                        check_in = None
                        check_out = None
                        
                        if check_in_str:
                            try:
                                check_in = dt.strptime(f"{selected_date} {check_in_str}", '%Y-%m-%d %H:%M')
                            except:
                                pass
                        
                        if check_out_str:
                            try:
                                check_out = dt.strptime(f"{selected_date} {check_out_str}", '%Y-%m-%d %H:%M')
                            except:
                                pass
                        
                        status = StudentAttendanceStatusEnum(status_value)
                        
                        success, message, _ = mark_attendance_helper(
                            session_db, student_id, class_id, school.id, selected_date,
                            status, check_in, check_out, remarks, current_user.teacher_id
                        )
                        
                        if success:
                            marked_count += 1
                        else:
                            errors.append(f"Student ID {student_id}: {message}")
                
                if marked_count > 0:
                    flash(f'Attendance marked for {marked_count} student(s)', 'success')
                
                if errors:
                    for error in errors[:5]:
                        flash(error, 'error')
                
                return redirect(url_for('teacher_auth.mark_student_attendance',
                                      tenant_slug=tenant_slug,
                                      date=selected_date_str,
                                      class_id=class_id))
            
            except Exception as e:
                logger.error(f"Error marking attendance: {e}")
                flash(f'Error marking attendance: {str(e)}', 'error')
        
        # GET request - show form
        students = []
        attendance_dict = {}
        is_holiday = False
        
        if class_id:
            # Fetch students
            students = session_db.query(Student).filter_by(
                tenant_id=school.id,
                class_id=class_id
            ).order_by(Student.roll_number, Student.full_name).all()
            
            # Fetch existing attendance
            existing_records = session_db.query(StudentAttendance).filter_by(
                tenant_id=school.id,
                class_id=class_id,
                attendance_date=selected_date
            ).all()
            
            attendance_dict = {record.student_id: record for record in existing_records}
            
            # Check holidays
            is_holiday = check_holidays_and_automark(session_db, school.id, class_id, selected_date)
        
        # Get teacher info
        teacher = session_db.query(Teacher).get(current_user.teacher_id)
        
        return render_template('teacher_dashboard_new/students/mark_attendance.html',
                             school=school,
                             teacher=teacher,
                             current_user=current_user,
                             class_assignments=class_assignments,
                             selected_class_id=class_id,
                             students=students,
                             selected_date=selected_date,
                             attendance_dict=attendance_dict,
                             status_enum=StudentAttendanceStatusEnum,
                             today=date.today(),
                             is_holiday=is_holiday,
                             page_title="Mark Attendance")
    
    except Exception as e:
        logger.error(f"Error in student attendance: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading attendance page', 'error')
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/students/attendance/history/<int:student_id>')
@require_teacher_auth
def student_attendance_history(tenant_slug, student_id):
    """View individual student attendance history"""
    session_db = get_session()
    try:
        from models import Student
        from timetable_models import ClassTeacherAssignment
        from student_attendance_helpers import calculate_student_attendance_stats, get_student_monthly_calendar
        from datetime import datetime as dt
        from sqlalchemy.orm import joinedload
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Fetch student
        student = session_db.query(Student).options(
            joinedload(Student.student_class)
        ).filter_by(
            id=student_id,
            tenant_id=school.id
        ).first()
        
        if not student:
            flash('Student not found', 'error')
            return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
        
        # Verify teacher is class teacher for this student's class
        is_class_teacher = session_db.query(ClassTeacherAssignment).filter_by(
            teacher_id=current_user.teacher_id,
            tenant_id=school.id,
            class_id=student.class_id,
            is_class_teacher=True
        ).filter(
            ClassTeacherAssignment.removed_date.is_(None)
        ).first()
        
        if not is_class_teacher:
            flash('Access denied - not class teacher for this student', 'error')
            return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
        
        # Get month and year
        month = request.args.get('month', dt.now().month, type=int)
        year = request.args.get('year', dt.now().year, type=int)
        
        # Get monthly records
        calendar_data = get_student_monthly_calendar(session_db, student_id, month, year)
        
        # Calculate stats
        stats = calculate_student_attendance_stats(session_db, student_id, month, year)
        
        # Get teacher info
        teacher = session_db.query(Teacher).get(current_user.teacher_id)
        
        return render_template('teacher_dashboard_new/students/attendance_history.html',
                             school=school,
                             teacher=teacher,
                             student=student,
                             calendar_data=calendar_data,
                             stats=stats,
                             month=month,
                             year=year,
                             month_name=dt(year, month, 1).strftime('%B'))
    
    except Exception as e:
        logger.error(f"Error viewing student history: {e}")
        flash('Error loading attendance history', 'error')
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()

# ===== ASSIGNMENT, DOCUMENTS & SETTINGS ROUTES =====

@teacher_auth_bp.route('/<tenant_slug>/teacher/assignments')
@require_teacher_auth
def assignments(tenant_slug):
    """Assignment Management page"""
    session_db = get_session()
    try:
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        teacher = session_db.query(Teacher).filter_by(id=current_user.teacher_id).first()
        
        return render_template('teacher_dashboard_new/assignments.html',
                             school=school,
                             teacher=teacher,
                             current_user=current_user,
                             page_title="Assignment Management")
    except Exception as e:
        logger.error(f"Assignments error: {e}")
        flash('Error loading assignments page', 'error')
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/documents')
@require_teacher_auth
def documents(tenant_slug):
    """My Documents page"""
    session_db = get_session()
    try:
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        teacher = session_db.query(Teacher).filter_by(id=current_user.teacher_id).first()
        
        return render_template('teacher_dashboard_new/documents.html',
                             school=school,
                             teacher=teacher,
                             current_user=current_user,
                             page_title="My Documents")
    except Exception as e:
        logger.error(f"Documents error: {e}")
        flash('Error loading documents page', 'error')
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/settings')
@require_teacher_auth
def settings(tenant_slug):
    """Settings page"""
    session_db = get_session()
    try:
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        teacher = session_db.query(Teacher).filter_by(id=current_user.teacher_id).first()
        
        return render_template('teacher_dashboard_new/settings.html',
                             school=school,
                             teacher=teacher,
                             current_user=current_user,
                             page_title="Settings")
    except Exception as e:
        logger.error(f"Settings error: {e}")
        flash('Error loading settings page', 'error')
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


# ===== ATTENDANCE ROUTES =====

@teacher_auth_bp.route('/<tenant_slug>/teacher/attendance')
@require_teacher_auth
def teacher_attendance(tenant_slug):
    """Teacher attendance dashboard - view monthly attendance"""
    session_db = get_session()
    try:
        from attendance_helpers import get_teacher_attendance_calendar, calculate_attendance_stats
        from datetime import datetime
        from teacher_models import Teacher
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        teacher = session_db.query(Teacher).filter_by(id=current_user.teacher_id).first()
        
        # Get month/year from query or default to current
        now = datetime.now()
        month = request.args.get('month', now.month, type=int)
        year = request.args.get('year', now.year, type=int)
        
        # Get calendar data
        calendar_data = get_teacher_attendance_calendar(session_db, current_user.teacher_id, month, year)
        
        # Get stats
        stats = calculate_attendance_stats(session_db, current_user.teacher_id, month, year)
        
        # Helper for month name in template
        def get_month_name(m):
            return datetime(year, m, 1).strftime('%B')
            
        return render_template('teacher_dashboard_new/attendance/my_attendance.html',
                             school=school,
                             teacher=teacher,
                             current_user=current_user,
                             calendar_data=calendar_data,
                             stats=stats,
                             month=month,
                             year=year,
                             current_year=now.year,
                             month_name=get_month_name,
                             page_title="My Attendance")
                             
    except Exception as e:
        logger.error(f"Teacher attendance error: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading attendance', 'error')
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


# ===== TEACHING SCHEDULE ROUTES =====

@teacher_auth_bp.route('/<tenant_slug>/teacher/schedule')
@require_teacher_auth
def teaching_schedule(tenant_slug):
    """Teacher teaching schedule - view weekly timetable"""
    session_db = get_session()
    try:
        from timetable_helpers import get_teacher_schedule, get_today_schedule, get_current_academic_year
        from datetime import datetime
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        teacher = session_db.query(Teacher).filter_by(id=current_user.teacher_id).first()
        
        # Get academic year and schedule
        academic_year = get_current_academic_year()
        weekly_schedule = get_teacher_schedule(session_db, teacher.id, school.id, academic_year)
        today_schedule = get_today_schedule(session_db, teacher.id, school.id, academic_year)
        
        # Get today's day name
        today_name = datetime.now().strftime('%A')
        
        # Days of the week
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        
        # Calculate stats
        total_periods = 0
        unique_classes = set()
        unique_subjects = set()
        all_time_slots = set()
        
        for day, periods in weekly_schedule.items():
            total_periods += len(periods)
            for period in periods:
                if period.get('class'):
                    unique_classes.add(period['class'])
                if period.get('subject'):
                    unique_subjects.add(period['subject'])
                if period.get('time'):
                    all_time_slots.add(period['time'])
        
        # Sort time slots for grid display
        time_slots = sorted([{'time': t} for t in all_time_slots], key=lambda x: x['time'])
        
        # Check if there's any schedule
        has_schedule = total_periods > 0
        
        return render_template('teacher_dashboard_new/schedule.html',
                             school=school,
                             teacher=teacher,
                             current_user=current_user,
                             weekly_schedule=weekly_schedule,
                             today_schedule=today_schedule,
                             academic_year=academic_year,
                             today_name=today_name,
                             days=days,
                             time_slots=time_slots,
                             total_periods=total_periods,
                             unique_classes=unique_classes,
                             unique_subjects=unique_subjects,
                             has_schedule=has_schedule,
                             page_title="Teaching Schedule")
                             
    except Exception as e:
        logger.error(f"Teaching schedule error: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading schedule', 'error')
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


# ===== LEAVE MANAGEMENT ROUTES =====

@teacher_auth_bp.route('/<tenant_slug>/teacher/leaves')
@login_required
def leave_dashboard(tenant_slug):
    """
    Teacher leave dashboard - view balance and recent applications
    """
    if not hasattr(current_user, 'teacher_id'):
        flash('Access denied', 'error')
        return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
    
    session_db = get_session()
    try:
        from leave_helpers import get_teacher_balance, get_current_academic_year
        from leave_models import TeacherLeaveApplication, LeaveStatusEnum
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        if not school or school.id != current_user.tenant_id:
            flash('Invalid school', 'error')
            return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
        
        teacher = session_db.query(Teacher).get(current_user.teacher_id)
        academic_year = get_current_academic_year()
        
        # Get leave balance
        balance = get_teacher_balance(session_db, current_user.teacher_id, academic_year)
        
        # Get recent leave applications (last 5)
        recent_leaves = session_db.query(TeacherLeaveApplication).filter_by(
            teacher_id=current_user.teacher_id
        ).order_by(TeacherLeaveApplication.applied_date.desc()).limit(5).all()
        
        # Get pending count
        pending_count = session_db.query(TeacherLeaveApplication).filter_by(
            teacher_id=current_user.teacher_id,
            status=LeaveStatusEnum.PENDING
        ).count()
        
        return render_template('teacher_dashboard_new/leaves/my_leaves.html',
                             school=school,
                             teacher=teacher,
                             balance=balance,
                             recent_leaves=recent_leaves,
                             pending_count=pending_count,
                             academic_year=academic_year,
                             current_user=current_user,
                             page_title="My Leaves")
    
    except Exception as e:
        logger.error(f"Leave dashboard error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading leave dashboard', 'error')
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/leaves/apply', methods=['GET', 'POST'])
@login_required
def apply_leave(tenant_slug):
    """
    Apply for leave
    """
    if not hasattr(current_user, 'teacher_id'):
        flash('Access denied', 'error')
        return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
    
    session_db = get_session()
    try:
        from leave_helpers import (get_teacher_balance, get_current_academic_year, 
                                   apply_leave as apply_leave_helper, get_or_create_quota_settings)
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        if not school or school.id != current_user.tenant_id:
            flash('Invalid school', 'error')
            return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
        
        teacher = session_db.query(Teacher).get(current_user.teacher_id)
        academic_year = get_current_academic_year()
        
        if request.method == 'POST':
            try:
                # Collect form data
                leave_data = {
                    'leave_type': (request.form.get('leave_type') or (request.json.get('leave_type') if request.is_json else None)),
                    'start_date': (request.form.get('start_date') or (request.json.get('start_date') if request.is_json else None)),
                    'end_date': (request.form.get('end_date') or (request.json.get('end_date') if request.is_json else None)),
                    'is_half_day': (('is_half_day' in request.form) if not request.is_json else bool(request.json.get('is_half_day'))),
                    'half_day_period': (request.form.get('half_day_period') or (request.json.get('half_day_period') if request.is_json else None)),
                    'reason': (request.form.get('reason') or (request.json.get('reason') if request.is_json else None)),
                    'contact_during_leave': (request.form.get('contact_during_leave') or (request.json.get('contact_during_leave') if request.is_json else None)),
                    'address_during_leave': (request.form.get('address_during_leave') or (request.json.get('address_during_leave') if request.is_json else None))
                }
                
                # Apply leave using helper
                success, result = apply_leave_helper(
                    session_db,
                    current_user.teacher_id,
                    school.id,
                    leave_data,
                    academic_year
                )
                
                wants_json = request.is_json or 'application/json' in request.headers.get('Accept', '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'

                if success:
                    # Save uploaded supporting document (if any) into tenant/teacher uploads and record as TeacherDocument
                    try:
                        if 'leave_document' in request.files:
                            doc = request.files['leave_document']
                            if doc and doc.filename:
                                from werkzeug.utils import secure_filename
                                import os
                                from teacher_models import TeacherDocument
                                from datetime import datetime

                                filename = secure_filename(doc.filename)
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                filename = f"{current_user.teacher_id}_{timestamp}_{filename}"

                                upload_folder = os.path.join('akademi', 'static', 'uploads', 'documents', str(school.id), 'teachers', str(current_user.teacher_id))
                                os.makedirs(upload_folder, exist_ok=True)
                                doc_path = os.path.join(upload_folder, filename)
                                doc.save(doc_path)

                                file_size = os.path.getsize(doc_path) // 1024
                                rel_path = f"uploads/documents/{school.id}/teachers/{current_user.teacher_id}/{filename}"

                                td = TeacherDocument(
                                    tenant_id=school.id,
                                    teacher_id=current_user.teacher_id,
                                    doc_type='OTHER' if not getattr(doc, 'content_type', None) else 'OTHER',
                                    file_name=doc.filename,
                                    file_path=rel_path,
                                    file_size_kb=file_size,
                                    mime_type=getattr(doc, 'content_type', None),
                                    uploaded_at=datetime.now()
                                )
                                session_db.add(td)
                                session_db.commit()
                    except Exception as e:
                        # Log but don't fail the main leave submission
                        logger.error(f"Error saving leave attachment: {e}")
                    if wants_json:
                        return jsonify({
                            'success': True,
                            'message': 'Leave application submitted successfully',
                            'data': result.to_dict() if hasattr(result, 'to_dict') else None
                        })
                    flash('Leave application submitted successfully! Waiting for approval.', 'success')
                    return redirect(url_for('teacher_auth.leave_history', tenant_slug=tenant_slug))
                else:
                    if wants_json:
                        return jsonify({'success': False, 'message': result}), 400
                    flash(f'Error: {result}', 'error')
            
            except Exception as e:
                logger.error(f"Leave application error: {e}")
                import traceback
                traceback.print_exc()
                wants_json = request.is_json or 'application/json' in request.headers.get('Accept', '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                if wants_json:
                    return jsonify({'success': False, 'message': f'Error submitting leave application: {str(e)}'}), 500
                flash(f'Error submitting leave application: {str(e)}', 'error')
        
        # GET request - show form
        balance = get_teacher_balance(session_db, current_user.teacher_id, academic_year)
        quota_settings = get_or_create_quota_settings(session_db, school.id, academic_year)
        
        return render_template('teacher_dashboard_new/leaves/apply.html',
                             school=school,
                             teacher=teacher,
                             balance=balance,
                             quota_settings=quota_settings,
                             academic_year=academic_year,
                             current_user=current_user,
                             page_title="Apply Leave")
    
    except Exception as e:
        logger.error(f"Apply leave error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading application form', 'error')
        return redirect(url_for('teacher_auth.leave_dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/leaves/balance.json', methods=['GET'])
@login_required
def leave_balance_json(tenant_slug):
    """Return current teacher's leave balance as JSON"""
    if not hasattr(current_user, 'teacher_id'):
        return jsonify({'error': 'Unauthorized'}), 401

    session_db = get_session()
    try:
        from leave_helpers import get_current_academic_year, get_teacher_balance
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        if not school or school.id != current_user.tenant_id:
            return jsonify({'error': 'Invalid school'}), 400

        academic_year = get_current_academic_year()
        balance = get_teacher_balance(session_db, current_user.teacher_id, academic_year)
        return jsonify({'success': True, 'academic_year': academic_year, 'balance': (balance.to_dict() if balance else None)})
    except Exception as e:
        logger.exception("leave_balance_json error")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/leaves/history.json', methods=['GET'])
@login_required
def leave_history_json(tenant_slug):
    """Return teacher leave history list for an academic year as JSON"""
    if not hasattr(current_user, 'teacher_id'):
        return jsonify({'error': 'Unauthorized'}), 401

    session_db = get_session()
    try:
        from leave_models import TeacherLeaveApplication
        from leave_helpers import get_current_academic_year
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        if not school or school.id != current_user.tenant_id:
            return jsonify({'error': 'Invalid school'}), 400

        year = request.args.get('year') or get_current_academic_year()
        apps = session_db.query(TeacherLeaveApplication).filter_by(
            teacher_id=current_user.teacher_id,
            academic_year=year
        ).order_by(TeacherLeaveApplication.applied_date.desc()).all()

        return jsonify({'success': True, 'academic_year': year, 'applications': [a.to_dict() for a in apps]})
    except Exception as e:
        logger.exception("leave_history_json error")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session_db.close()

@teacher_auth_bp.route('/<tenant_slug>/teacher/leaves/history')
@login_required
def leave_history(tenant_slug):
    """
    View leave application history
    """
    if not hasattr(current_user, 'teacher_id'):
        flash('Access denied', 'error')
        return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
    
    session_db = get_session()
    try:
        from leave_models import TeacherLeaveApplication
        from leave_helpers import get_current_academic_year
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        if not school or school.id != current_user.tenant_id:
            flash('Invalid school', 'error')
            return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
        
        teacher = session_db.query(Teacher).get(current_user.teacher_id)
        academic_year = request.args.get('year', get_current_academic_year())
        
        # Get all leave applications for the academic year
        leave_applications = session_db.query(TeacherLeaveApplication).filter_by(
            teacher_id=current_user.teacher_id,
            academic_year=academic_year
        ).order_by(TeacherLeaveApplication.applied_date.desc()).all()
        
        # Get available academic years for filter
        all_years = session_db.query(TeacherLeaveApplication.academic_year).filter_by(
            teacher_id=current_user.teacher_id
        ).distinct().all()
        academic_years = sorted([y[0] for y in all_years], reverse=True)
        if academic_year not in academic_years and leave_applications:
            academic_years.append(academic_year)
        
        return render_template('teacher_dashboard_new/leaves/history.html',
                             school=school,
                             teacher=teacher,
                             leave_applications=leave_applications,
                             academic_year=academic_year,
                             academic_years=academic_years,
                             current_user=current_user,
                             page_title="Leave History")
    
    except Exception as e:
        logger.error(f"Leave history error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading leave history', 'error')
        return redirect(url_for('teacher_auth.leave_dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/leaves/<int:leave_id>')
@login_required
def leave_details(tenant_slug, leave_id):
    """
    View details of a specific leave application
    """
    if not hasattr(current_user, 'teacher_id'):
        flash('Access denied', 'error')
        return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
    
    session_db = get_session()
    try:
        from leave_models import TeacherLeaveApplication
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        if not school or school.id != current_user.tenant_id:
            flash('Invalid school', 'error')
            return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
        
        teacher = session_db.query(Teacher).get(current_user.teacher_id)
        
        # Get the leave application
        leave = session_db.query(TeacherLeaveApplication).filter_by(
            id=leave_id,
            teacher_id=current_user.teacher_id
        ).first()
        
        if not leave:
            flash('Leave application not found', 'error')
            return redirect(url_for('teacher_auth.leave_dashboard', tenant_slug=tenant_slug))
        
        return render_template('teacher_dashboard_new/leaves/leave_details.html',
                             school=school,
                             teacher=teacher,
                             leave=leave,
                             current_user=current_user,
                             page_title="Leave Details")
    
    except Exception as e:
        logger.error(f"Leave details error: {e}")
        flash('Error loading leave details', 'error')
        return redirect(url_for('teacher_auth.leave_dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/leaves/cancel/<int:leave_id>', methods=['POST'])
@login_required
def cancel_leave(tenant_slug, leave_id):
    """
    Cancel a pending leave application
    """
    if not hasattr(current_user, 'teacher_id'):
        flash('Access denied', 'error')
        return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
    
    session_db = get_session()
    try:
        from leave_helpers import cancel_leave_application
        
        success, message = cancel_leave_application(session_db, leave_id, current_user.teacher_id)

        # Detect if caller expects JSON (XHR / fetch)
        wants_json = request.is_json or 'application/json' in request.headers.get('Accept', '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if wants_json:
            # Return JSON response for client-side callers
            status_code = 200 if success else 400
            return jsonify({'success': bool(success), 'message': message}), status_code

        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
    
    except Exception as e:
        logger.error(f"Cancel leave error: {e}")
        flash('Error cancelling leave application', 'error')
    finally:
        session_db.close()
    
    return redirect(url_for('teacher_auth.leave_history', tenant_slug=tenant_slug))


# ===== STUDENT LEAVE MANAGEMENT (TEACHER) ROUTES =====

@teacher_auth_bp.route('/<tenant_slug>/teacher/student-leaves')
@login_required
def student_leaves(tenant_slug):
    """Teacher view for student leave management - only for their assigned classes"""
    if not hasattr(current_user, 'teacher_id'):
        flash('Access denied', 'error')
        return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
    
    session_db = get_session()
    try:
        from leave_models import StudentLeave, StudentLeaveStatusEnum
        from models import Class
        from timetable_models import ClassTeacherAssignment
        from sqlalchemy.orm import joinedload
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        if not school:
            flash('School not found', 'error')
            return redirect('/')
        
        teacher = session_db.query(Teacher).filter_by(id=current_user.teacher_id).first()
        if not teacher:
            flash('Teacher record not found', 'error')
            return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
        
        # Get classes where this teacher is class teacher
        class_assignments = session_db.query(ClassTeacherAssignment).filter_by(
            teacher_id=teacher.id,
            is_class_teacher=True
        ).all()
        
        assigned_class_ids = [assignment.class_id for assignment in class_assignments]
        
        if not assigned_class_ids:
            # Teacher is not a class teacher for any class
            return render_template('teacher_dashboard_new/leaves/student_leaves.html',
                                 school=school,
                                 teacher=teacher,
                                 leaves=[],
                                 classes=[],
                                 stats={'pending': 0, 'approved': 0, 'rejected': 0},
                                 current_user=current_user,
                                 page_title="Student Leaves")
        
        # Get filter parameters
        status_filter = request.args.get('status')
        class_id = request.args.get('class_id', type=int)
        
        # Base query - only leaves from assigned classes
        query = session_db.query(StudentLeave).filter(
            StudentLeave.tenant_id == school.id,
            StudentLeave.class_id.in_(assigned_class_ids)
        ).options(
            joinedload(StudentLeave.student),
            joinedload(StudentLeave.student_class),
            joinedload(StudentLeave.reviewer)
        )
        
        # Apply filters
        if status_filter:
            query = query.filter(StudentLeave.status == StudentLeaveStatusEnum(status_filter))
        
        if class_id and class_id in assigned_class_ids:
            query = query.filter(StudentLeave.class_id == class_id)
        
        # Order by latest first
        leaves = query.order_by(StudentLeave.applied_date.desc()).all()
        
        # Get assigned classes for filter dropdown
        classes = session_db.query(Class).filter(
            Class.id.in_(assigned_class_ids)
        ).order_by(Class.class_name, Class.section).all()
        
        # Calculate statistics for assigned classes only
        stats = {
            'pending': session_db.query(StudentLeave).filter(
                StudentLeave.tenant_id == school.id,
                StudentLeave.class_id.in_(assigned_class_ids),
                StudentLeave.status == StudentLeaveStatusEnum.PENDING
            ).count(),
            'approved': session_db.query(StudentLeave).filter(
                StudentLeave.tenant_id == school.id,
                StudentLeave.class_id.in_(assigned_class_ids),
                StudentLeave.status == StudentLeaveStatusEnum.APPROVED
            ).count(),
            'rejected': session_db.query(StudentLeave).filter(
                StudentLeave.tenant_id == school.id,
                StudentLeave.class_id.in_(assigned_class_ids),
                StudentLeave.status == StudentLeaveStatusEnum.REJECTED
            ).count()
        }
        
        return render_template('teacher_dashboard_new/leaves/student_leaves.html',
                             school=school,
                             teacher=teacher,
                             leaves=leaves,
                             classes=classes,
                             stats=stats,
                             current_user=current_user,
                             page_title="Student Leaves")
                             
    except Exception as e:
        logger.error(f"Student leaves error for {tenant_slug}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash('Error loading student leaves', 'error')
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/student-leaves/<int:leave_id>')
@login_required
def student_leave_details(tenant_slug, leave_id):
    """View detailed information about a student leave application"""
    if not hasattr(current_user, 'teacher_id'):
        return '<div class="alert alert-danger">Access denied</div>', 403
    
    session_db = get_session()
    try:
        from leave_models import StudentLeave
        from timetable_models import ClassTeacherAssignment
        from sqlalchemy.orm import joinedload
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        teacher = session_db.query(Teacher).filter_by(id=current_user.teacher_id).first()
        
        # Get classes where this teacher is class teacher
        class_assignments = session_db.query(ClassTeacherAssignment).filter_by(
            teacher_id=teacher.id,
            is_class_teacher=True
        ).all()
        
        assigned_class_ids = [assignment.class_id for assignment in class_assignments]
        
        # Get leave and verify it's from an assigned class
        leave = session_db.query(StudentLeave).filter_by(
            id=leave_id,
            tenant_id=school.id
        ).options(
            joinedload(StudentLeave.student),
            joinedload(StudentLeave.student_class),
            joinedload(StudentLeave.reviewer)
        ).first()
        
        if not leave or leave.class_id not in assigned_class_ids:
            return '<div class="alert alert-danger">Leave application not found or access denied</div>', 404
        
        return render_template('teacher_dashboard_new/leaves/student_leave_details.html',
                             school=school,
                             teacher=teacher,
                             leave=leave,
                             current_user=current_user)
                             
    except Exception as e:
        logger.error(f"Student leave details error for {tenant_slug}: {e}")
        return '<div class="alert alert-danger">Error loading leave details</div>', 500
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/student-leaves/<int:leave_id>/approve', methods=['POST'])
@login_required
def student_leave_approve(tenant_slug, leave_id):
    """Approve a student leave application"""
    if not hasattr(current_user, 'teacher_id'):
        flash('Access denied', 'error')
        return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
    
    session_db = get_session()
    try:
        from student_leave_helpers import approve_leave
        from timetable_models import ClassTeacherAssignment
        from leave_models import StudentLeave
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        teacher = session_db.query(Teacher).filter_by(id=current_user.teacher_id).first()
        
        # Verify teacher is class teacher for this leave's class
        leave = session_db.query(StudentLeave).filter_by(id=leave_id).first()
        if leave:
            assignment = session_db.query(ClassTeacherAssignment).filter_by(
                teacher_id=teacher.id,
                class_id=leave.class_id,
                is_class_teacher=True
            ).first()
            
            if not assignment:
                flash('You can only approve leaves for your assigned classes', 'error')
                return redirect(url_for('teacher_auth.student_leaves', tenant_slug=tenant_slug))
        
        # Approve leave using helper function
        success, message = approve_leave(
            db_session=session_db,
            leave_id=leave_id,
            reviewer_id=current_user.id,
            reviewer_type='Class Teacher',
            remarks=None
        )
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
    except Exception as e:
        logger.error(f"Error approving leave for {tenant_slug}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash('Error approving leave', 'error')
        session_db.rollback()
    finally:
        session_db.close()
    
    return redirect(url_for('teacher_auth.student_leaves', tenant_slug=tenant_slug))


@teacher_auth_bp.route('/<tenant_slug>/teacher/student-leaves/<int:leave_id>/reject', methods=['POST'])
@login_required
def student_leave_reject(tenant_slug, leave_id):
    """Reject a student leave application"""
    if not hasattr(current_user, 'teacher_id'):
        flash('Access denied', 'error')
        return redirect(url_for('teacher_auth.login', tenant_slug=tenant_slug))
    
    session_db = get_session()
    try:
        from student_leave_helpers import reject_leave
        from timetable_models import ClassTeacherAssignment
        from leave_models import StudentLeave
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        teacher = session_db.query(Teacher).filter_by(id=current_user.teacher_id).first()
        remarks = request.form.get('remarks', '')
        
        if not remarks:
            flash('Rejection reason is required', 'error')
            return redirect(url_for('teacher_auth.student_leaves', tenant_slug=tenant_slug))
        
        # Verify teacher is class teacher for this leave's class
        leave = session_db.query(StudentLeave).filter_by(id=leave_id).first()
        if leave:
            assignment = session_db.query(ClassTeacherAssignment).filter_by(
                teacher_id=teacher.id,
                class_id=leave.class_id,
                is_class_teacher=True
            ).first()
            
            if not assignment:
                flash('You can only reject leaves for your assigned classes', 'error')
                return redirect(url_for('teacher_auth.student_leaves', tenant_slug=tenant_slug))
        
        # Reject leave using helper function
        success, message = reject_leave(
            db_session=session_db,
            leave_id=leave_id,
            reviewer_id=current_user.id,
            reviewer_type='Class Teacher',
            remarks=remarks
        )
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
    except Exception as e:
        logger.error(f"Error rejecting leave for {tenant_slug}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash('Error rejecting leave', 'error')
        session_db.rollback()
    finally:
        session_db.close()
    
    return redirect(url_for('teacher_auth.student_leaves', tenant_slug=tenant_slug))


@teacher_auth_bp.route('/<tenant_slug>/teacher/profile')
@require_teacher_auth
def profile(tenant_slug):
    """Teacher profile page"""
    session_db = get_session()
    try:
        from teacher_models import TeacherBankingDetails, TeacherExperience, TeacherDesignation, Qualification
        from sqlalchemy.orm import joinedload
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Fetch detailed teacher info including relationships
        teacher = session_db.query(Teacher).filter_by(id=current_user.teacher_id).options(
            joinedload(Teacher.experiences),
            joinedload(Teacher.banking_details),
            joinedload(Teacher.designations).joinedload(TeacherDesignation.designation),
            joinedload(Teacher.qualifications)
        ).first()

        return render_template('teacher_dashboard_new/profile.html',
                             school=school,
                             teacher=teacher,
                             current_user=current_user,
                             page_title="My Profile")
    except Exception as e:
        logger.error(f"Profile error: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading profile', 'error')
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()

@teacher_auth_bp.route('/<tenant_slug>/teacher/notifications')
@require_teacher_auth
def notifications(tenant_slug):
    """Teacher notifications page"""
    session_db = get_session()
    try:
        from notification_models import NotificationRecipient, Notification, RecipientStatusEnum
        from sqlalchemy import desc
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Fetch notifications for this teacher
        notifications_query = session_db.query(NotificationRecipient).join(
            Notification
        ).filter(
            NotificationRecipient.teacher_id == current_user.teacher_id,
            NotificationRecipient.tenant_id == school.id
        ).order_by(desc(Notification.created_at))
        
        notifications_all = notifications_query.all()
        
        # Serialize for template
        notifications_list = []
        for recipient in notifications_all:
             notif_obj = recipient.notification
             if not notif_obj:
                 continue
                 
             # Process documents
             docs_data = []
             if notif_obj.documents:
                 for doc in notif_obj.documents:
                     docs_data.append({
                         'file_name': doc.file_name,
                         'file_path': doc.file_path,
                         'file_size_kb': doc.file_size_kb,
                         'mime_type': doc.mime_type
                     })
             
             notifications_list.append({
                'id': notif_obj.id,
                'title': notif_obj.title,
                'message': notif_obj.message,
                'priority': notif_obj.priority.value if hasattr(notif_obj.priority, 'value') else notif_obj.priority,
                'sent_at': notif_obj.created_at,
                'is_read': recipient.status == RecipientStatusEnum.READ,
                'documents': docs_data
             })

        return render_template('teacher_dashboard_new/notifications.html',
                             school=school,
                             current_user=current_user,
                             notifications=notifications_list,
                             page_title="Notifications")
    except Exception as e:
        logger.error(f"Notifications error: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading notifications', 'error')
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


# ===== NOTIFICATION ROUTES FOR TEACHERS =====

@teacher_auth_bp.route('/<tenant_slug>/teacher/salary')
@require_teacher_auth
def salary(tenant_slug):
    """Teacher salary and payslips page"""
    session_db = get_session()
    try:
        from teacher_models import TeacherSalary, TeacherBankingDetails
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get active salary record
        salary_data = session_db.query(TeacherSalary).filter_by(
            teacher_id=current_user.teacher_id,
            tenant_id=school.id,
            is_active=True
        ).first()
        
        # Get banking details
        banking_details = session_db.query(TeacherBankingDetails).filter_by(
            teacher_id=current_user.teacher_id,
            tenant_id=school.id
        ).first()
        
        return render_template('teacher_dashboard_new/salary.html',
                             school=school,
                             current_user=current_user,
                             salary_data=salary_data,
                             banking_details=banking_details,
                             page_title="Salary & Payslips")
    except Exception as e:
        logger.error(f"Salary error: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading salary details', 'error')
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/notifications/count.json')
@require_teacher_auth
def teacher_notifications_count(tenant_slug):
    """Get unread notification count for the navbar badge - JSON endpoint"""
    session_db = get_session()
    try:
        from notification_models import NotificationRecipient, Notification, RecipientStatusEnum, NotificationStatusEnum
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Count unread (SENT status) notifications for this teacher
        unread_count = session_db.query(NotificationRecipient).join(
            Notification, NotificationRecipient.notification_id == Notification.id
        ).filter(
            NotificationRecipient.teacher_id == current_user.teacher_id,
            NotificationRecipient.tenant_id == school.id,
            NotificationRecipient.status == RecipientStatusEnum.SENT,
            Notification.status == NotificationStatusEnum.SENT
        ).count()
        
        return jsonify({
            'success': True,
            'count': unread_count
        })
        
    except Exception as e:
        logger.error(f"Notification count error: {e}")
        return jsonify({'success': False, 'count': 0, 'error': str(e)}), 500
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/notifications/recent.json')
@require_teacher_auth
def teacher_notifications_recent(tenant_slug):
    """Get recent notifications for navbar dropdown - JSON endpoint"""
    session_db = get_session()
    try:
        from notification_models import NotificationRecipient, Notification, NotificationDocument, RecipientStatusEnum, NotificationStatusEnum
        from sqlalchemy.orm import joinedload, subqueryload
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get recent notifications (last 5)
        # Get limit from query param or default to 50 for full list
        limit = request.args.get('limit', 5, type=int)
        
        recent = session_db.query(NotificationRecipient).join(
            Notification, NotificationRecipient.notification_id == Notification.id
        ).filter(
            NotificationRecipient.teacher_id == current_user.teacher_id,
            NotificationRecipient.tenant_id == school.id,
            Notification.status == NotificationStatusEnum.SENT
        ).options(
            joinedload(NotificationRecipient.notification).subqueryload(Notification.documents)
        ).order_by(NotificationRecipient.sent_at.desc()).limit(limit).all()
        
        notifications = []
        for nr in recent:
            # Get documents for this notification
            docs = []
            for doc in nr.notification.documents:
                docs.append({
                    'file_name': doc.file_name,
                    'file_path': doc.file_path,
                    'file_size_kb': doc.file_size_kb,
                    'mime_type': doc.mime_type
                })
            
            notifications.append({
                'id': nr.id,
                'notification_id': nr.notification_id,
                'title': nr.notification.title,
                'message': nr.notification.message,
                'priority': nr.notification.priority.value if nr.notification.priority else 'Normal',
                'sent_at': nr.sent_at.strftime('%b %d, %Y %H:%M') if nr.sent_at else None,
                'is_read': nr.status == RecipientStatusEnum.READ,
                'has_attachments': len(docs) > 0,
                'documents': docs
            })
        
        # Get unread count
        unread_count = session_db.query(NotificationRecipient).join(
            Notification, NotificationRecipient.notification_id == Notification.id
        ).filter(
            NotificationRecipient.teacher_id == current_user.teacher_id,
            NotificationRecipient.tenant_id == school.id,
            NotificationRecipient.status == RecipientStatusEnum.SENT,
            Notification.status == NotificationStatusEnum.SENT
        ).count()
        
        return jsonify({
            'success': True,
            'notifications': notifications,
            'unread_count': unread_count
        })
        
    except Exception as e:
        logger.error(f"Recent notifications error: {e}")
        return jsonify({'success': False, 'notifications': [], 'error': str(e)}), 500
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/notifications/<int:recipient_id>/read', methods=['POST'])
@require_teacher_auth
def teacher_notification_mark_read(tenant_slug, recipient_id):
    """Mark a notification as read"""
    session_db = get_session()
    try:
        from notification_models import NotificationRecipient, RecipientStatusEnum
        from datetime import datetime
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Find and update the notification recipient record
        nr = session_db.query(NotificationRecipient).filter_by(
            id=recipient_id,
            teacher_id=current_user.teacher_id,
            tenant_id=school.id
        ).first()
        
        if nr:
            nr.status = RecipientStatusEnum.READ
            nr.read_at = datetime.now()
            session_db.commit()
            return jsonify({'success': True, 'message': 'Notification marked as read'})
        else:
            return jsonify({'success': False, 'error': 'Notification not found'}), 404
        
    except Exception as e:
        logger.error(f"Mark read error: {e}")
        session_db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/notifications/mark-all-read', methods=['POST'])
@require_teacher_auth
def teacher_notifications_mark_all_read(tenant_slug):
    """Mark all notifications as read"""
    session_db = get_session()
    try:
        from notification_models import NotificationRecipient, RecipientStatusEnum
        from datetime import datetime
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Update all unread notifications for this teacher
        session_db.query(NotificationRecipient).filter_by(
            teacher_id=current_user.teacher_id,
            tenant_id=school.id,
            status=RecipientStatusEnum.SENT
        ).update({
            'status': RecipientStatusEnum.READ,
            'read_at': datetime.now()
        })
        
        session_db.commit()
        return jsonify({'success': True, 'message': 'All notifications marked as read'})
        
    except Exception as e:
        logger.error(f"Mark all read error: {e}")
        session_db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/activities/recent.json')
@require_teacher_auth
def teacher_recent_activities(tenant_slug):
    """Get recent activities for teacher dashboard - JSON endpoint"""
    session_db = get_session()
    try:
        from notification_models import NotificationRecipient, Notification, RecipientStatusEnum
        from teacher_models import TeacherLeave, TeacherAttendance
        from datetime import datetime, timedelta
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        if not school:
            return jsonify({'success': False, 'activities': []}), 404
        
        activities = []
        
        # Get recent notifications (last 7 days)
        recent_notifications = session_db.query(NotificationRecipient).join(
            Notification
        ).filter(
            NotificationRecipient.teacher_id == current_user.teacher_id,
            NotificationRecipient.tenant_id == school.id,
            NotificationRecipient.sent_at >= datetime.now() - timedelta(days=7)
        ).order_by(NotificationRecipient.sent_at.desc()).limit(3).all()
        
        for notif in recent_notifications:
            time_diff = datetime.now() - notif.sent_at
            if time_diff.days > 0:
                time_ago = f"{time_diff.days} day{'s' if time_diff.days > 1 else ''} ago"
            elif time_diff.seconds >= 3600:
                hours = time_diff.seconds // 3600
                time_ago = f"{hours} hour{'s' if hours > 1 else ''} ago"
            else:
                minutes = max(1, time_diff.seconds // 60)
                time_ago = f"{minutes} min ago"
            
            activities.append({
                'action': notif.notification.title if notif.notification else 'New notification',
                'time': time_ago,
                'type': 'notification'
            })
        
        # Get recent leaves (last 30 days)
        recent_leaves = session_db.query(TeacherLeave).filter(
            TeacherLeave.teacher_id == current_user.teacher_id,
            TeacherLeave.tenant_id == school.id,
            TeacherLeave.created_at >= datetime.now() - timedelta(days=30)
        ).order_by(TeacherLeave.created_at.desc()).limit(2).all()
        
        for leave in recent_leaves:
            time_diff = datetime.now() - leave.created_at
            if time_diff.days > 0:
                time_ago = f"{time_diff.days} day{'s' if time_diff.days > 1 else ''} ago"
            else:
                hours = time_diff.seconds // 3600
                time_ago = f"{hours} hour{'s' if hours > 1 else ''} ago" if hours > 0 else "Today"
            
            activities.append({
                'action': f"{leave.leave_type.value} application {leave.status.value.lower()}",
                'time': time_ago,
                'type': 'leave'
            })
        
        # Get recent attendance records (last 7 days)
        recent_attendance = session_db.query(TeacherAttendance).filter(
            TeacherAttendance.teacher_id == current_user.teacher_id,
            TeacherAttendance.tenant_id == school.id,
            TeacherAttendance.attendance_date >= datetime.now().date() - timedelta(days=7)
        ).order_by(TeacherAttendance.attendance_date.desc()).limit(2).all()
        
        for att in recent_attendance:
            time_diff = datetime.now().date() - att.attendance_date
            if time_diff.days == 0:
                time_ago = "Today"
            elif time_diff.days == 1:
                time_ago = "Yesterday"
            else:
                time_ago = f"{time_diff.days} days ago"
            
            activities.append({
                'action': f"Attendance marked as {att.status.value}",
                'time': time_ago,
                'type': 'attendance'
            })
        
        # Sort all activities by recency (this is a simplified sort, ideally would sort by actual timestamps)
        # Return top 5 most recent
        return jsonify({
            'success': True,
            'activities': activities[:5]
        })
        
    except Exception as e:
        logger.error(f"Recent activities error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'activities': []}), 500
    finally:
        session_db.close()


# ===== QUESTION PAPER ROUTES FOR TEACHERS =====

@teacher_auth_bp.route('/<tenant_slug>/teacher/question-papers')
@require_teacher_auth
def question_paper_assignments(tenant_slug):
    """View question paper assignments for the teacher (setter role)"""
    session_db = get_session()
    try:
        from question_paper_models import QuestionPaperAssignment, QuestionPaper, AssignmentRole, QuestionPaperStatus
        from examination_models import Examination, ExaminationSubject
        from teacher_models import Subject
        from models import Class
        from sqlalchemy.orm import joinedload
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        teacher = session_db.query(Teacher).filter_by(id=current_user.teacher_id).first()
        
        # Get setter assignments for this teacher
        assignments = session_db.query(QuestionPaperAssignment).filter_by(
            teacher_id=current_user.teacher_id,
            role=AssignmentRole.SETTER
        ).all()
        
        # Build assignment data with exam/subject details
        assignments_data = []
        for assignment in assignments:
            exam_subject = session_db.query(ExaminationSubject).filter_by(
                id=assignment.examination_subject_id
            ).first()
            
            if not exam_subject:
                continue
            
            examination = session_db.query(Examination).filter_by(
                id=exam_subject.examination_id
            ).first()
            
            if not examination or examination.tenant_id != school.id:
                continue
            
            # Get latest paper by this setter
            latest_paper = session_db.query(QuestionPaper).filter_by(
                examination_subject_id=assignment.examination_subject_id,
                setter_id=current_user.teacher_id
            ).order_by(QuestionPaper.version.desc()).first()
            
            # Check if overdue
            is_overdue = False
            if assignment.deadline and assignment.deadline < datetime.utcnow():
                is_overdue = True
            
            assignments_data.append({
                'assignment': assignment,
                'examination': examination,
                'exam_subject': exam_subject,
                'subject': exam_subject.subject,
                'class_ref': exam_subject.class_ref,
                'latest_paper': latest_paper,
                'is_overdue': is_overdue
            })
        
        return render_template('teacher_dashboard_new/question_papers/my_assignments.html',
                             school=school,
                             teacher=teacher,
                             assignments_data=assignments_data,
                             current_user=current_user,
                             QuestionPaperStatus=QuestionPaperStatus,
                             page_title="Question Paper Assignments")
    
    except Exception as e:
        logger.error(f"Question paper assignments error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading question paper assignments', 'error')
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/question-papers/<int:assignment_id>/upload', methods=['GET', 'POST'])
@require_teacher_auth
def upload_question_paper(tenant_slug, assignment_id):
    """Upload question paper for an assignment"""
    session_db = get_session()
    try:
        from question_paper_models import QuestionPaperAssignment, QuestionPaper, QuestionPaperReview, AssignmentRole, QuestionPaperStatus
        from examination_models import Examination, ExaminationSubject
        from werkzeug.utils import secure_filename
        import os
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        teacher = session_db.query(Teacher).filter_by(id=current_user.teacher_id).first()
        
        # Get assignment
        assignment = session_db.query(QuestionPaperAssignment).filter_by(
            id=assignment_id,
            teacher_id=current_user.teacher_id,
            role=AssignmentRole.SETTER
        ).first()
        
        if not assignment:
            flash('Assignment not found or access denied', 'error')
            return redirect(url_for('teacher_auth.question_paper_assignments', tenant_slug=tenant_slug))
        
        exam_subject = session_db.query(ExaminationSubject).filter_by(
            id=assignment.examination_subject_id
        ).first()
        
        examination = session_db.query(Examination).filter_by(
            id=exam_subject.examination_id,
            tenant_id=school.id
        ).first()
        
        if not examination:
            flash('Invalid assignment', 'error')
            return redirect(url_for('teacher_auth.question_paper_assignments', tenant_slug=tenant_slug))
        
        # Get existing papers
        existing_papers = session_db.query(QuestionPaper).filter_by(
            examination_subject_id=assignment.examination_subject_id,
            setter_id=current_user.teacher_id
        ).order_by(QuestionPaper.version.desc()).all()
        
        latest_paper = existing_papers[0] if existing_papers else None
        
        # Check if paper is locked (approved or finalized)
        paper_locked = False
        if latest_paper and latest_paper.status in [QuestionPaperStatus.APPROVED, QuestionPaperStatus.FINAL]:
            paper_locked = True
        
        # Get latest review comments (especially for revision requests)
        latest_review = None
        if latest_paper:
            latest_review = session_db.query(QuestionPaperReview).filter_by(
                question_paper_id=latest_paper.id
            ).order_by(QuestionPaperReview.reviewed_at.desc()).first()
        
        if request.method == 'POST':
            # Check if paper is locked
            if paper_locked:
                flash('Cannot upload - question paper has already been approved', 'error')
                return redirect(url_for('teacher_auth.question_paper_assignments', tenant_slug=tenant_slug))
            
            if 'file' not in request.files:
                flash('No file selected', 'error')
                return redirect(request.url)
            
            file = request.files['file']
            if file.filename == '':
                flash('No file selected', 'error')
                return redirect(request.url)
            
            # Validate file type
            allowed_extensions = {'pdf', 'doc', 'docx'}
            file_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            if file_ext not in allowed_extensions:
                flash('Only PDF, DOC, and DOCX files are allowed', 'error')
                return redirect(request.url)
            
            # Check file size (10MB max)
            file.seek(0, 2)  # Seek to end
            file_size = file.tell()
            file.seek(0)  # Reset
            
            if file_size > 10 * 1024 * 1024:  # 10MB
                flash('File size must be less than 10MB', 'error')
                return redirect(request.url)
            
            # Determine version
            new_version = (latest_paper.version + 1) if latest_paper else 1
            
            # Create upload directory
            upload_dir = os.path.join('uploads', 'question_papers', str(school.id), str(examination.id), str(exam_subject.id))
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save file with version
            safe_filename = secure_filename(file.filename)
            base_name = safe_filename.rsplit('.', 1)[0] if '.' in safe_filename else safe_filename
            file_name = f"{base_name}_v{new_version}.{file_ext}"
            file_path = os.path.join(upload_dir, file_name)
            file.save(file_path)
            
            # Create or update paper record
            submit_action = request.form.get('action') == 'submit'
            
            paper = QuestionPaper(
                examination_subject_id=assignment.examination_subject_id,
                setter_id=current_user.teacher_id,
                file_path=file_path,
                file_name=file_name,
                file_size=file_size,
                file_type=file_ext,
                version=new_version,
                status=QuestionPaperStatus.SUBMITTED if submit_action else QuestionPaperStatus.DRAFT,
                submitted_at=datetime.utcnow() if submit_action else None
            )
            session_db.add(paper)
            session_db.commit()
            
            if submit_action:
                flash('Question paper uploaded and submitted for review', 'success')
            else:
                flash('Question paper saved as draft', 'success')
            
            return redirect(url_for('teacher_auth.question_paper_assignments', tenant_slug=tenant_slug))
        
        # GET request
        is_overdue = False
        if assignment.deadline and assignment.deadline < datetime.utcnow():
            is_overdue = True
        
        return render_template('teacher_dashboard_new/question_papers/upload.html',
                             school=school,
                             teacher=teacher,
                             assignment=assignment,
                             examination=examination,
                             exam_subject=exam_subject,
                             existing_papers=existing_papers,
                             latest_paper=latest_paper,
                             latest_review=latest_review,
                             paper_locked=paper_locked,
                             deadline=assignment.deadline,
                             is_overdue=is_overdue,
                             current_user=current_user,
                             QuestionPaperStatus=QuestionPaperStatus,
                             page_title="Upload Question Paper")
    
    except Exception as e:
        logger.error(f"Upload question paper error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        flash('Error uploading question paper', 'error')
        session_db.rollback()
        return redirect(url_for('teacher_auth.question_paper_assignments', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/question-papers/reviews')
@require_teacher_auth
def question_paper_reviews(tenant_slug):
    """View papers pending review (reviewer role) - grouped by subject for comparative review"""
    session_db = get_session()
    try:
        from question_paper_models import QuestionPaperAssignment, QuestionPaper, AssignmentRole, QuestionPaperStatus
        from examination_models import Examination, ExaminationSubject
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        teacher = session_db.query(Teacher).filter_by(id=current_user.teacher_id).first()
        
        # Get reviewer assignments for this teacher
        reviewer_assignments = session_db.query(QuestionPaperAssignment).filter_by(
            teacher_id=current_user.teacher_id,
            role=AssignmentRole.REVIEWER
        ).all()
        
        # Build review data grouped by subject
        subjects_with_papers = []
        for assignment in reviewer_assignments:
            exam_subject = session_db.query(ExaminationSubject).filter_by(
                id=assignment.examination_subject_id
            ).first()
            
            if not exam_subject:
                continue
            
            examination = session_db.query(Examination).filter_by(
                id=exam_subject.examination_id,
                tenant_id=school.id
            ).first()
            
            if not examination:
                continue
            
            # Get ALL submitted papers for this subject (from all setters)
            papers = session_db.query(QuestionPaper).filter(
                QuestionPaper.examination_subject_id == assignment.examination_subject_id,
                QuestionPaper.status.in_([QuestionPaperStatus.SUBMITTED, QuestionPaperStatus.UNDER_REVIEW])
            ).order_by(QuestionPaper.submitted_at.desc()).all()
            
            if not papers:
                continue
            
            # Build papers list with setter info
            papers_data = []
            for paper in papers:
                setter = session_db.query(Teacher).filter_by(id=paper.setter_id).first()
                papers_data.append({
                    'paper': paper,
                    'setter': setter
                })
            
            subjects_with_papers.append({
                'assignment': assignment,
                'examination': examination,
                'exam_subject': exam_subject,
                'subject': exam_subject.subject,
                'class_ref': exam_subject.class_ref,
                'papers': papers_data,
                'paper_count': len(papers_data)
            })
        
        return render_template('teacher_dashboard_new/question_papers/reviews.html',
                             school=school,
                             teacher=teacher,
                             subjects_with_papers=subjects_with_papers,
                             current_user=current_user,
                             QuestionPaperStatus=QuestionPaperStatus,
                             page_title="Review Question Papers")
    
    except Exception as e:
        logger.error(f"Question paper reviews error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading review queue', 'error')
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/question-papers/<int:paper_id>/review', methods=['GET', 'POST'])
@require_teacher_auth
def review_question_paper(tenant_slug, paper_id):
    """Review a specific question paper"""
    session_db = get_session()
    try:
        from question_paper_models import QuestionPaperAssignment, QuestionPaper, QuestionPaperReview, AssignmentRole, QuestionPaperStatus, ReviewAction
        from examination_models import Examination, ExaminationSubject
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        teacher = session_db.query(Teacher).filter_by(id=current_user.teacher_id).first()
        
        # Get paper
        paper = session_db.query(QuestionPaper).filter_by(id=paper_id).first()
        
        if not paper:
            flash('Paper not found', 'error')
            return redirect(url_for('teacher_auth.question_paper_reviews', tenant_slug=tenant_slug))
        
        # Verify reviewer assignment
        reviewer_assignment = session_db.query(QuestionPaperAssignment).filter_by(
            examination_subject_id=paper.examination_subject_id,
            teacher_id=current_user.teacher_id,
            role=AssignmentRole.REVIEWER
        ).first()
        
        if not reviewer_assignment:
            flash('You are not the reviewer for this paper', 'error')
            return redirect(url_for('teacher_auth.question_paper_reviews', tenant_slug=tenant_slug))
        
        exam_subject = session_db.query(ExaminationSubject).filter_by(
            id=paper.examination_subject_id
        ).first()
        
        examination = session_db.query(Examination).filter_by(
            id=exam_subject.examination_id,
            tenant_id=school.id
        ).first()
        
        setter = session_db.query(Teacher).filter_by(id=paper.setter_id).first()
        
        # Get previous reviews for this paper
        previous_reviews = session_db.query(QuestionPaperReview).filter_by(
            question_paper_id=paper_id
        ).order_by(QuestionPaperReview.reviewed_at.desc()).all()
        
        if request.method == 'POST':
            action = request.form.get('action')
            comments = request.form.get('comments', '').strip()
            
            if action not in ['approve', 'revision']:
                flash('Invalid action', 'error')
                return redirect(request.url)
            
            if action == 'revision' and not comments:
                flash('Comments are required when requesting revision', 'error')
                return redirect(request.url)
            
            # Create review record
            review = QuestionPaperReview(
                question_paper_id=paper_id,
                reviewer_id=current_user.teacher_id,
                action=ReviewAction.APPROVED if action == 'approve' else ReviewAction.REVISION_REQUESTED,
                comments=comments,
                reviewed_at=datetime.utcnow()
            )
            session_db.add(review)
            
            # Update paper status
            if action == 'approve':
                paper.status = QuestionPaperStatus.APPROVED
                paper.approved_at = datetime.utcnow()
                
                # SINGLE SELECTION: Mark all other papers for this subject as SUPERSEDED
                other_papers = session_db.query(QuestionPaper).filter(
                    QuestionPaper.examination_subject_id == paper.examination_subject_id,
                    QuestionPaper.id != paper.id,
                    QuestionPaper.status.in_([
                        QuestionPaperStatus.SUBMITTED, 
                        QuestionPaperStatus.UNDER_REVIEW,
                        QuestionPaperStatus.DRAFT,
                        QuestionPaperStatus.REVISION_REQUESTED
                    ])
                ).all()
                
                superseded_count = 0
                for other_paper in other_papers:
                    other_paper.status = QuestionPaperStatus.SUPERSEDED
                    superseded_count += 1
                
                if superseded_count > 0:
                    flash(f'Paper approved! {superseded_count} other paper(s) marked as superseded.', 'success')
                else:
                    flash('Paper approved successfully', 'success')
            else:
                paper.status = QuestionPaperStatus.REVISION_REQUESTED
                flash('Revision requested. Setter will be notified.', 'success')
            
            session_db.commit()
            return redirect(url_for('teacher_auth.question_paper_reviews', tenant_slug=tenant_slug))
        
        # GET request
        return render_template('teacher_dashboard_new/question_papers/review_paper.html',
                             school=school,
                             teacher=teacher,
                             paper=paper,
                             setter=setter,
                             examination=examination,
                             exam_subject=exam_subject,
                             previous_reviews=previous_reviews,
                             current_user=current_user,
                             QuestionPaperStatus=QuestionPaperStatus,
                             page_title="Review Question Paper")
    
    except Exception as e:
        logger.error(f"Review question paper error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        flash('Error reviewing paper', 'error')
        session_db.rollback()
        return redirect(url_for('teacher_auth.question_paper_reviews', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/question-papers/<int:paper_id>/download')
@require_teacher_auth
def download_teacher_question_paper(tenant_slug, paper_id):
    """Download question paper file"""
    session_db = get_session()
    try:
        from question_paper_models import QuestionPaperAssignment, QuestionPaper, AssignmentRole
        from flask import send_file
        import os
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        paper = session_db.query(QuestionPaper).filter_by(id=paper_id).first()
        
        if not paper:
            flash('Paper not found', 'error')
            return redirect(url_for('teacher_auth.question_paper_assignments', tenant_slug=tenant_slug))
        
        # Check access - must be setter or reviewer
        is_setter = paper.setter_id == current_user.teacher_id
        is_reviewer = session_db.query(QuestionPaperAssignment).filter_by(
            examination_subject_id=paper.examination_subject_id,
            teacher_id=current_user.teacher_id,
            role=AssignmentRole.REVIEWER
        ).first() is not None
        
        if not is_setter and not is_reviewer:
            flash('Access denied', 'error')
            return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
        
        if not os.path.exists(paper.file_path):
            flash('File not found on server', 'error')
            return redirect(url_for('teacher_auth.question_paper_assignments', tenant_slug=tenant_slug))
        
        return send_file(
            paper.file_path,
            as_attachment=True,
            download_name=paper.file_name
        )
    
    except Exception as e:
        logger.error(f"Download question paper error: {e}")
        flash('Error downloading file', 'error')
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/question-papers/<int:paper_id>/preview')
@require_teacher_auth
def preview_question_paper(tenant_slug, paper_id):
    """Preview question paper (inline PDF viewing)"""
    session_db = get_session()
    try:
        from question_paper_models import QuestionPaperAssignment, QuestionPaper, AssignmentRole
        from flask import send_file
        import os
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        paper = session_db.query(QuestionPaper).filter_by(id=paper_id).first()
        
        if not paper:
            flash('Paper not found', 'error')
            return redirect(url_for('teacher_auth.question_paper_assignments', tenant_slug=tenant_slug))
        
        # Check access - must be setter or reviewer
        is_setter = paper.setter_id == current_user.teacher_id
        is_reviewer = session_db.query(QuestionPaperAssignment).filter_by(
            examination_subject_id=paper.examination_subject_id,
            teacher_id=current_user.teacher_id,
            role=AssignmentRole.REVIEWER
        ).first() is not None
        
        if not is_setter and not is_reviewer:
            flash('Access denied', 'error')
            return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
        
        if not os.path.exists(paper.file_path):
            flash('File not found on server', 'error')
            return redirect(url_for('teacher_auth.question_paper_assignments', tenant_slug=tenant_slug))
        # Only allow PDF preview
        if paper.file_type.lower() != 'pdf':
            flash('Preview only available for PDF files. Please download the file.', 'info')
            return redirect(url_for('teacher_auth.download_teacher_question_paper', tenant_slug=tenant_slug, paper_id=paper_id))
        
        # Serve file inline for browser viewing
        return send_file(
            paper.file_path,
            as_attachment=False,  # Inline viewing
            mimetype='application/pdf'
        )
    
    except Exception as e:
        logger.error(f"Preview question paper error: {e}")
        flash('Error previewing file', 'error')
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


# ===== COPY CHECKING (MARKS ENTRY) ROUTES FOR TEACHERS =====

@teacher_auth_bp.route('/<tenant_slug>/teacher/copy-checking')
@require_teacher_auth
def copy_checking_assignments(tenant_slug):
    """View copy checking (marks entry) assignments for the teacher"""
    session_db = get_session()
    try:
        from copy_checking_models import CopyCheckingAssignment
        from examination_models import Examination, ExaminationSubject, MarkEntryStatus
        from models import Student
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        teacher = session_db.query(Teacher).filter_by(id=current_user.teacher_id).first()
        
        # Get copy checking assignments for this teacher
        assignments = session_db.query(CopyCheckingAssignment).filter_by(
            teacher_id=current_user.teacher_id
        ).all()
        
        # Initialize statistics
        total_copies = 0
        checked_copies = 0
        assigned_tasks = len(assignments)
        
        # Build assignment data with exam/subject details
        assignments_data = []
        for assignment in assignments:
            exam_subject = session_db.query(ExaminationSubject).filter_by(
                id=assignment.examination_subject_id
            ).first()
            
            if not exam_subject:
                continue
            
            examination = session_db.query(Examination).filter_by(
                id=exam_subject.examination_id
            ).first()
            
            if not examination or examination.tenant_id != school.id:
                continue
            
            # Count students in this class
            student_count = session_db.query(Student).filter_by(
                class_id=exam_subject.class_id,
                tenant_id=school.id
            ).count()
            
            # Calculate progress based on mark entry status
            if exam_subject.mark_entry_status in [MarkEntryStatus.COMPLETED, MarkEntryStatus.VERIFIED, MarkEntryStatus.PUBLISHED]:
                progress_percent = 100
                student_checked = student_count
            elif exam_subject.mark_entry_status == MarkEntryStatus.IN_PROGRESS:
                # For now, assume 50% if in progress (you could enhance this by counting actual marks entered)
                progress_percent = 50
                student_checked = student_count // 2
            else:
                progress_percent = 0
                student_checked = 0
            
            total_copies += student_count
            checked_copies += student_checked
            
            # Check if overdue - only if not completed and deadline has passed
            is_overdue = False
            is_completed = exam_subject.mark_entry_status in [MarkEntryStatus.COMPLETED, MarkEntryStatus.VERIFIED, MarkEntryStatus.PUBLISHED]
            if assignment.deadline and assignment.deadline < datetime.utcnow() and not is_completed:
                is_overdue = True
            
            assignments_data.append({
                'assignment': assignment,
                'examination': examination,
                'exam_subject': exam_subject,
                'subject': exam_subject.subject,
                'class_ref': exam_subject.class_ref,
                'status': exam_subject.mark_entry_status,
                'is_overdue': is_overdue,
                'student_count': student_count,
                'student_checked': student_checked,
                'progress_percent': progress_percent
            })
        
        # Calculate overall statistics
        overall_progress = (checked_copies / total_copies * 100) if total_copies > 0 else 0
        checked_completed = sum(1 for item in assignments_data if item['status'] in [MarkEntryStatus.COMPLETED, MarkEntryStatus.VERIFIED, MarkEntryStatus.PUBLISHED])
        completion_percentage = (checked_completed / assigned_tasks * 100) if assigned_tasks > 0 else 0
        
        stats = {
            'assigned_tasks': assigned_tasks,
            'total_copies': total_copies,
            'checked_copies': checked_copies,
            'checked_completed': checked_completed,
            'overall_progress': round(overall_progress, 1),
            'completion_percentage': round(completion_percentage)
        }
        
        return render_template('teacher_dashboard_new/copy_checking/my_assignments.html',
                             school=school,
                             teacher=teacher,
                             assignments_data=assignments_data,
                             stats=stats,
                             MarkEntryStatus=MarkEntryStatus,
                             current_user=current_user,
                             page_title="Copy Checking Assignments")
    
    except Exception as e:
        logger.error(f"Copy checking assignments error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading copy checking assignments', 'error')
        return redirect(url_for('teacher_auth.dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()


@teacher_auth_bp.route('/<tenant_slug>/teacher/copy-checking/<int:assignment_id>/marks', methods=['GET', 'POST'])
@require_teacher_auth
def enter_marks(tenant_slug, assignment_id):
    """Enter marks for a copy checking assignment"""
    session_db = get_session()
    try:
        from copy_checking_models import CopyCheckingAssignment
        from examination_models import Examination, ExaminationSubject, ExaminationMark, MarkEntryStatus
        from models import Student, StudentStatusEnum
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        teacher = session_db.query(Teacher).filter_by(id=current_user.teacher_id).first()
        
        # Get assignment
        assignment = session_db.query(CopyCheckingAssignment).filter_by(
            id=assignment_id,
            teacher_id=current_user.teacher_id
        ).first()
        
        if not assignment:
            flash('Assignment not found or access denied', 'error')
            return redirect(url_for('teacher_auth.copy_checking_assignments', tenant_slug=tenant_slug))
        
        exam_subject = session_db.query(ExaminationSubject).filter_by(
            id=assignment.examination_subject_id
        ).first()
        
        examination = session_db.query(Examination).filter_by(
            id=exam_subject.examination_id,
            tenant_id=school.id
        ).first()
        
        if not examination:
            flash('Invalid assignment', 'error')
            return redirect(url_for('teacher_auth.copy_checking_assignments', tenant_slug=tenant_slug))
        
        # Get students for this class
        students = session_db.query(Student).filter_by(
            class_id=exam_subject.class_id,
            status=StudentStatusEnum.ACTIVE
        ).order_by(Student.roll_number, Student.first_name).all()
        
        # Get existing marks
        marks_dict = {}
        existing_marks = session_db.query(ExaminationMark).filter_by(
            examination_id=examination.id,
            examination_subject_id=exam_subject.id
        ).all()
        
        for mark in existing_marks:
            marks_dict[mark.student_id] = {
                'theory_marks_obtained': mark.theory_marks_obtained,
                'practical_marks_obtained': mark.practical_marks_obtained,
                'is_absent': mark.is_absent
            }
        
        if request.method == 'POST':
            # Handle AJAX marks save
            if request.is_json:
                data = request.get_json()
                marks_data_list = data.get('marks_data', [])
                
                for mark_data in marks_data_list:
                    student_id = int(mark_data['student_id'])
                    theory = mark_data.get('theory_marks')
                    practical = mark_data.get('practical_marks')
                    is_absent = mark_data.get('is_absent', False)
                    
                    theory = float(theory) if theory is not None else None
                    practical = float(practical) if practical is not None else None
                    
                    mark_entry = session_db.query(ExaminationMark).filter_by(
                        examination_id=examination.id,
                        examination_subject_id=exam_subject.id,
                        student_id=student_id
                    ).first()
                    
                    if mark_entry:
                        mark_entry.theory_marks_obtained = theory
                        mark_entry.practical_marks_obtained = practical
                        mark_entry.internal_marks_obtained = 0
                        mark_entry.is_absent = is_absent
                        mark_entry.updated_at = datetime.utcnow()
                    else:
                        mark_entry = ExaminationMark(
                            examination_id=examination.id,
                            examination_subject_id=exam_subject.id,
                            student_id=student_id,
                            theory_marks_obtained=theory,
                            practical_marks_obtained=practical,
                            internal_marks_obtained=0,
                            is_absent=is_absent,
                            entered_by=current_user.teacher_id,
                            entered_at=datetime.utcnow()
                        )
                        session_db.add(mark_entry)
                    
                    # Calculate total and pass status
                    mark_entry.calculate_total()
                    mark_entry.check_pass_status(exam_subject.passing_marks)
                
                session_db.flush()
                
                # Update status
                students_with_marks = session_db.query(ExaminationMark).filter_by(
                    examination_subject_id=exam_subject.id
                ).count()
                
                total_students = session_db.query(Student).filter(
                    Student.class_id == exam_subject.class_id,
                    Student.status == StudentStatusEnum.ACTIVE
                ).count()
                
                if students_with_marks >= total_students:
                    exam_subject.mark_entry_status = MarkEntryStatus.COMPLETED
                elif students_with_marks > 0:
                    exam_subject.mark_entry_status = MarkEntryStatus.IN_PROGRESS
                
                session_db.commit()
                
                return jsonify({'success': True, 'message': 'Marks saved successfully'})
        
        # Check deadline
        is_overdue = False
        if assignment.deadline and assignment.deadline < datetime.utcnow():
            is_overdue = True
        
        return render_template('teacher_dashboard_new/copy_checking/enter_marks.html',
                             school=school,
                             teacher=teacher,
                             assignment=assignment,
                             examination=examination,
                             exam_subject=exam_subject,
                             students=students,
                             marks_dict=marks_dict,
                             is_overdue=is_overdue,
                             current_user=current_user,
                             page_title="Enter Marks")
    
    except Exception as e:
        logger.error(f"Enter marks error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)})
        flash('Error loading marks entry', 'error')
        return redirect(url_for('teacher_auth.copy_checking_assignments', tenant_slug=tenant_slug))
    finally:
        session_db.close()
