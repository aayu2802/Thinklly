"""
Student Authentication and Dashboard Routes
Registration, login, password reset, and student portal routes
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify
from flask_login import login_user, logout_user, current_user
from datetime import datetime
import logging
from sqlalchemy import desc

from db_single import get_session
from models import Tenant, Student
from student_models import StudentAuth, StudentAuthUser

logger = logging.getLogger(__name__)

# Create blueprint
student_auth_bp = Blueprint('student_auth', __name__)


# ===== DECORATORS =====

def require_student_auth(f):
    """Decorator to require student authentication"""
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            tenant_slug = kwargs.get('tenant_slug') or g.current_tenant.slug
            flash('Please login to access this page', 'warning')
            return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
        
        # Check if this is a student user
        if not hasattr(current_user, 'student_id'):
            tenant_slug = kwargs.get('tenant_slug') or g.current_tenant.slug
            flash('Access denied - students only', 'error')
            return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
        
        # Check if user belongs to current tenant
        if hasattr(g, 'current_tenant') and current_user.tenant_id != g.current_tenant.id:
            tenant_slug = g.current_tenant.slug
            flash('Access denied - wrong school', 'error')
            return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
        
        # NEW: Real-time check if student is still active
        try:
            from student_departure_handler import is_student_active
            session_db = get_session()
            try:
                if not is_student_active(session_db, current_user.student_id):
                    logout_user()
                    tenant_slug = kwargs.get('tenant_slug') or g.current_tenant.slug
                    flash('Your student account is no longer active. Please contact administration.', 'warning')
                    return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
            finally:
                session_db.close()
        except Exception as e:
            logger.warning(f"Error checking student status in decorator: {e}")
        
        return f(*args, **kwargs)
    
    decorated_function.__name__ = f.__name__
    return decorated_function


# ===== ROUTES =====
# Paste your routes below this line
# Remember to:
# 1. Change @student_auth_bp.route(...) to @student_auth_bp.route(...)
# 2. Change @require_student_auth to @require_student_auth (for protected routes)
# 3. Change url_for('student_auth.student_xxx') to url_for('student_auth.xxx')


# ===== STUDENT DASHBOARD ROUTES =====

@student_auth_bp.route('/<tenant_slug>/student/register', methods=['GET', 'POST'])
def student_register(tenant_slug):
    """Student registration page"""
    session_db = get_session()
    try:
        school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
        if not school:
            flash('School not found or inactive', 'error')
            return redirect('/admin/')
        
        if request.method == 'POST':
            admission_number = request.form.get('admission_number', '').strip()
            date_of_birth = request.form.get('date_of_birth', '').strip()
            password = request.form.get('password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()
            
            if not all([admission_number, date_of_birth, password, confirm_password]):
                flash('All fields are required', 'error')
                return render_template('student_dashboard_new/register.html', school=school)
            
            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return render_template('student_dashboard_new/register.html', school=school)
            
            if len(password) < 6:
                flash('Password must be at least 6 characters long', 'error')
                return render_template('student_dashboard_new/register.html', school=school)
            
            # Verify student exists with matching admission number and DOB
            try:
                dob = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format', 'error')
                return render_template('student_dashboard_new/register.html', school=school)
            
            student = session_db.query(Student).filter_by(
                tenant_id=school.id,
                admission_number=admission_number,
                date_of_birth=dob
            ).first()
            
            if not student:
                flash('Invalid admission number or date of birth', 'error')
                return render_template('student_dashboard_new/register.html', school=school)
            
            # Optional: Warn if student record doesn't have email/phone
            if not student.email and not student.phone:
                flash('Warning: Your student record does not have email or phone number. Please contact administrator.', 'warning')
            
            # Check if student_auth account already exists
            existing_auth = session_db.query(StudentAuth).filter_by(
                tenant_id=school.id,
                student_id=student.id
            ).first()
            
            if existing_auth:
                flash('Account already exists. Please login.', 'info')
                return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
            
            # Create student_auth record
            student_auth = StudentAuth(
                tenant_id=school.id,
                student_id=student.id,
                admission_number=student.admission_number,
                email=student.email,
                mobile=student.phone  # Student model uses 'phone' not 'mobile'
            )
            student_auth.set_password(password)
            
            session_db.add(student_auth)
            session_db.commit()
            
            # Auto-login after registration
            student_auth_user = StudentAuthUser(student_auth)
            login_user(student_auth_user, remember=False)
            
            flash(f'Registration successful! Welcome, {student.first_name}!', 'success')
            return redirect(url_for('student_auth.student_dashboard', tenant_slug=tenant_slug))
        
        return render_template('student_dashboard_new/register.html', school=school)
        
    except Exception as e:
        session_db.rollback()
        logger.error(f"Student registration error for {tenant_slug}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash('Registration error occurred', 'error')
        return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/login', methods=['GET', 'POST'])
def student_login(tenant_slug):
    """Student login page"""
    session_db = get_session()
    try:
        school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
        if not school:
            flash('School not found or inactive', 'error')
            return redirect('/admin/')
        
        if request.method == 'POST':
            admission_number = request.form.get('admission_number', '').strip()
            password = request.form.get('password', '').strip()
            remember_me = request.form.get('remember_me') == 'on'
            
            if not admission_number or not password:
                flash('Please enter both admission number and password', 'error')
                return render_template('student_dashboard_new/login.html', school=school)
            
            # Find student_auth record by admission number
            student_auth = session_db.query(StudentAuth).filter_by(
                tenant_id=school.id,
                admission_number=admission_number,
                is_active=True
            ).first()
            
            if student_auth and student_auth.check_password(password):
                # Check if the student is still active
                from models import StudentStatusEnum
                student = session_db.query(Student).filter_by(id=student_auth.student_id).first()
                if student and student.status != StudentStatusEnum.ACTIVE:
                    flash(f'Your student account is marked as {student.status.value}. Please contact administration.', 'error')
                    return render_template('student_dashboard_new/login.html', school=school)
                
                # Update last login timestamp
                student_auth.last_login = datetime.utcnow()
                session_db.commit()
                
                # Create wrapper user object and login
                student_auth_user = StudentAuthUser(student_auth)
                login_user(student_auth_user, remember=remember_me)
                
                flash(f'Welcome back, {student_auth_user.first_name}!', 'success')
                return redirect(url_for('student_auth.student_dashboard', tenant_slug=tenant_slug))
            else:
                flash('Invalid admission number or password', 'error')
        
        return render_template('student_dashboard_new/login.html', school=school)
        
    except Exception as e:
        logger.error(f"Student login error for {tenant_slug}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash('Login error occurred', 'error')
        return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/logout')
@require_student_auth
def student_logout(tenant_slug):
    """Student logout"""
    logout_user()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))

# ===== STUDENT PASSWORD RESET ROUTES =====

@student_auth_bp.route('/<tenant_slug>/student/forgot-password', methods=['GET', 'POST'])
def student_forgot_password(tenant_slug):
    """Step 1: Request password reset - enter admission number to find email"""
    session_db = get_session()
    try:
        school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
        if not school:
            flash('School not found', 'error')
            return redirect('/admin/')
        
        if request.method == 'POST':
            admission_number = request.form.get('admission_number', '').strip()
            
            if not admission_number:
                flash('Please enter your admission number', 'error')
                return render_template('student_dashboard_new/forgot_password.html', school=school)
            
            # Find student auth by admission number
            student_auth = session_db.query(StudentAuth).filter(
                StudentAuth.tenant_id == school.id,
                StudentAuth.admission_number == admission_number
            ).first()
            
            if not student_auth:
                # Don't reveal if account exists
                flash('If an account with this admission number exists, we will check for available email addresses.', 'info')
                return render_template('student_dashboard_new/forgot_password.html', school=school)
            
            # Check if account is active
            if not student_auth.is_active:
                flash('This account has been deactivated. Please contact your school administration.', 'error')
                return render_template('student_dashboard_new/forgot_password.html', school=school)
            
            # Get student record to find available emails
            student = session_db.query(Student).filter_by(id=student_auth.student_id).first()
            if not student:
                flash('Student record not found. Please contact administrator.', 'error')
                return render_template('student_dashboard_new/forgot_password.html', school=school)
            
            # Check for available emails (student's own email or parent's email)
            student_email = student.email
            parent_email = student.guardian_email
            
            if not student_email and not parent_email:
                flash('No email address found for your account. Please contact your school administration for password reset.', 'error')
                return render_template('student_dashboard_new/forgot_password.html', school=school)
            
            # Store admission number in session for next step
            from flask import session
            session['student_reset_admission'] = admission_number
            session['student_reset_student_email'] = student_email
            session['student_reset_parent_email'] = parent_email
            session['student_reset_student_name'] = student.full_name
            
            # Redirect to email selection page
            return redirect(url_for('student_auth.student_select_email', tenant_slug=tenant_slug))
        
        # GET request
        return render_template('student_dashboard_new/forgot_password.html', school=school)
        
    except Exception as e:
        session_db.rollback()
        logger.error(f"Student forgot password error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        flash('An error occurred. Please try again.', 'error')
        return render_template('student_dashboard_new/forgot_password.html', 
                                school={'name': tenant_slug, 'slug': tenant_slug})
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/select-email', methods=['GET', 'POST'])
def student_select_email(tenant_slug):
    """Step 2: Select which email to receive OTP (student's own or parent's)"""
    from flask import session as flask_session
    
    session_db = get_session()
    try:
        school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
        if not school:
            flash('School not found', 'error')
            return redirect('/admin/')
        
        # Check if admission number is in session
        admission_number = flask_session.get('student_reset_admission')
        if not admission_number:
            flash('Please start the password reset process from the beginning.', 'warning')
            return redirect(url_for('student_auth.student_forgot_password', tenant_slug=tenant_slug))
        
        student_email = flask_session.get('student_reset_student_email')
        parent_email = flask_session.get('student_reset_parent_email')
        student_name = flask_session.get('student_reset_student_name', 'Student')
        
        if request.method == 'POST':
            selected_email = request.form.get('selected_email', '').strip()
            
            # Validate selected email
            valid_emails = []
            if student_email:
                valid_emails.append(student_email)
            if parent_email:
                valid_emails.append(parent_email)
            
            if selected_email not in valid_emails:
                flash('Please select a valid email address', 'error')
                return render_template('student_dashboard_new/select_email.html', 
                                        school=school,
                                        student_email=student_email,
                                        parent_email=parent_email,
                                        student_name=student_name)
            
            # Find student auth
            student_auth = session_db.query(StudentAuth).filter(
                StudentAuth.tenant_id == school.id,
                StudentAuth.admission_number == admission_number
            ).first()
            
            if not student_auth:
                flask_session.pop('student_reset_admission', None)
                flash('Session expired. Please start again.', 'error')
                return redirect(url_for('student_auth.student_forgot_password', tenant_slug=tenant_slug))
            
            # Generate OTP
            otp = student_auth.generate_reset_otp()
            session_db.commit()
            
            # Send OTP email
            from notification_email import send_student_otp_email
            success, msg = send_student_otp_email(
                to_email=selected_email,
                otp=otp,
                student_name=student_name,
                school_name=school.name
            )
            
            if success:
                logger.info(f"Student password reset OTP sent to {selected_email} for school {tenant_slug}")
                flash('OTP has been sent to the selected email address. Please check your inbox.', 'success')
                # Store selected email in session for next step
                flask_session['student_reset_email'] = selected_email
                return redirect(url_for('student_auth.student_verify_otp', tenant_slug=tenant_slug))
            else:
                logger.error(f"Failed to send student OTP email to {selected_email}: {msg}")
                flash('Failed to send OTP email. Please try again later.', 'error')
                return render_template('student_dashboard_new/select_email.html',
                                        school=school,
                                        student_email=student_email,
                                        parent_email=parent_email,
                                        student_name=student_name)
        
        # GET request
        return render_template('student_dashboard_new/select_email.html',
                                school=school,
                                student_email=student_email,
                                parent_email=parent_email,
                                student_name=student_name)
        
    except Exception as e:
        session_db.rollback()
        logger.error(f"Student select email error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('student_auth.student_forgot_password', tenant_slug=tenant_slug))
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/verify-otp', methods=['GET', 'POST'])
def student_verify_otp(tenant_slug):
    """Step 3: Verify OTP"""
    from flask import session as flask_session
    
    session_db = get_session()
    try:
        school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
        if not school:
            flash('School not found', 'error')
            return redirect('/admin/')
        
        # Check if email is in session
        admission_number = flask_session.get('student_reset_admission')
        reset_email = flask_session.get('student_reset_email')
        if not admission_number or not reset_email:
            flash('Please start the password reset process from the beginning.', 'warning')
            return redirect(url_for('student_auth.student_forgot_password', tenant_slug=tenant_slug))
        
        if request.method == 'POST':
            otp = request.form.get('otp', '').strip()
            
            if not otp or len(otp) != 6:
                flash('Please enter a valid 6-digit OTP', 'error')
                return render_template('student_dashboard_new/verify_otp.html', school=school, email=reset_email)
            
            # Find student auth
            student_auth = session_db.query(StudentAuth).filter(
                StudentAuth.tenant_id == school.id,
                StudentAuth.admission_number == admission_number
            ).first()
            
            if not student_auth:
                flask_session.pop('student_reset_admission', None)
                flask_session.pop('student_reset_email', None)
                flash('Session expired. Please start again.', 'error')
                return redirect(url_for('student_auth.student_forgot_password', tenant_slug=tenant_slug))
            
            # Verify OTP
            if not student_auth.verify_reset_otp(otp):
                flash('Invalid or expired OTP. Please try again or request a new OTP.', 'error')
                return render_template('student_dashboard_new/verify_otp.html', school=school, email=reset_email)
            
            # OTP verified - store verification flag
            flask_session['student_otp_verified'] = True
            logger.info(f"Student OTP verified for admission {admission_number} at school {tenant_slug}")
            flash('OTP verified successfully. Please set your new password.', 'success')
            return redirect(url_for('student_auth.student_reset_password', tenant_slug=tenant_slug))
        
        # GET request
        return render_template('student_dashboard_new/verify_otp.html', school=school, email=reset_email)
        
    except Exception as e:
        logger.error(f"Student OTP verification error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('student_auth.student_forgot_password', tenant_slug=tenant_slug))
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/reset-password', methods=['GET', 'POST'])
def student_reset_password(tenant_slug):
    """Step 4: Set new password after OTP verification"""
    from flask import session as flask_session
    
    session_db = get_session()
    try:
        school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
        if not school:
            flash('School not found', 'error')
            return redirect('/admin/')
        
        # Check if OTP was verified
        admission_number = flask_session.get('student_reset_admission')
        otp_verified = flask_session.get('student_otp_verified')
        
        if not admission_number or not otp_verified:
            flash('Please complete the OTP verification first.', 'warning')
            return redirect(url_for('student_auth.student_forgot_password', tenant_slug=tenant_slug))
        
        if request.method == 'POST':
            password = request.form.get('password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()
            
            # Validation
            if not password or not confirm_password:
                flash('Please enter and confirm your new password', 'error')
                return render_template('student_dashboard_new/reset_password.html', school=school)
            
            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return render_template('student_dashboard_new/reset_password.html', school=school)
            
            if len(password) < 8:
                flash('Password must be at least 8 characters', 'error')
                return render_template('student_dashboard_new/reset_password.html', school=school)
            
            # Find student auth
            student_auth = session_db.query(StudentAuth).filter(
                StudentAuth.tenant_id == school.id,
                StudentAuth.admission_number == admission_number
            ).first()
            
            if not student_auth:
                # Clear all session data
                flask_session.pop('student_reset_admission', None)
                flask_session.pop('student_reset_email', None)
                flask_session.pop('student_otp_verified', None)
                flask_session.pop('student_reset_student_email', None)
                flask_session.pop('student_reset_parent_email', None)
                flask_session.pop('student_reset_student_name', None)
                flash('Session expired. Please start again.', 'error')
                return redirect(url_for('student_auth.student_forgot_password', tenant_slug=tenant_slug))
            
            # Update password
            student_auth.set_password(password)
            student_auth.clear_reset_otp()
            session_db.commit()
            
            # Clear all session data
            flask_session.pop('student_reset_admission', None)
            flask_session.pop('student_reset_email', None)
            flask_session.pop('student_otp_verified', None)
            flask_session.pop('student_reset_student_email', None)
            flask_session.pop('student_reset_parent_email', None)
            flask_session.pop('student_reset_student_name', None)
            
            logger.info(f"Student password reset successfully for admission {admission_number} at school {tenant_slug}")
            flash('Password reset successfully! You can now login with your new password.', 'success')
            return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
        
        # GET request
        return render_template('student_dashboard_new/reset_password.html', school=school)
        
    except Exception as e:
        session_db.rollback()
        logger.error(f"Student password reset error for {tenant_slug}: {e}")
        import traceback
        traceback.print_exc()
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('student_auth.student_forgot_password', tenant_slug=tenant_slug))
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/resend-otp', methods=['POST'])
def student_resend_otp(tenant_slug):
    """Resend OTP for student password reset"""
    from flask import session as flask_session
    
    session_db = get_session()
    try:
        school = session_db.query(Tenant).filter_by(slug=tenant_slug, is_active=True).first()
        if not school:
            return jsonify({'success': False, 'message': 'School not found'}), 404
        
        admission_number = flask_session.get('student_reset_admission')
        reset_email = flask_session.get('student_reset_email')
        student_name = flask_session.get('student_reset_student_name', 'Student')
        
        if not admission_number or not reset_email:
            return jsonify({'success': False, 'message': 'Session expired. Please start again.'}), 400
        
        # Find student auth
        student_auth = session_db.query(StudentAuth).filter(
            StudentAuth.tenant_id == school.id,
            StudentAuth.admission_number == admission_number
        ).first()
        
        if not student_auth:
            return jsonify({'success': False, 'message': 'Account not found.'}), 404
        
        # Generate new OTP
        otp = student_auth.generate_reset_otp()
        session_db.commit()
        
        # Send OTP email
        from notification_email import send_student_otp_email
        success, msg = send_student_otp_email(
            to_email=reset_email,
            otp=otp,
            student_name=student_name,
            school_name=school.name
        )
        
        if success:
            logger.info(f"Student OTP resent to {reset_email} for school {tenant_slug}")
            return jsonify({'success': True, 'message': 'OTP has been resent to your email.'})
        else:
            logger.error(f"Failed to resend student OTP to {reset_email}: {msg}")
            return jsonify({'success': False, 'message': 'Failed to send OTP. Please try again.'}), 500
            
    except Exception as e:
        session_db.rollback()
        logger.error(f"Student resend OTP error for {tenant_slug}: {e}")
        return jsonify({'success': False, 'message': 'An error occurred.'}), 500
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/dashboard')
@require_student_auth
def student_dashboard(tenant_slug):
    """Student dashboard - bulletproof with safe fallbacks"""
    session_db = get_session()
    
    # Initialize all variables with safe defaults
    school = None
    student = None
    attendance_percent = 0
    average_score = 0
    pending_assignments = 0
    fee_status = "N/A"
    today_schedule = []
    upcoming_events_list = []
    recent_grades_list = []
    announcements_list = []
    unread_count = 0
    
    try:
        from sqlalchemy.orm import joinedload
        from sqlalchemy import func
        
        # Safe imports with fallbacks
        try:
            from student_attendance_helpers import calculate_student_attendance_stats
        except ImportError:
            logger.warning("student_attendance_helpers not available")
            calculate_student_attendance_stats = None
        
        try:
            from examination_models import ExaminationSubject, StudentResult, ExamSchedule
        except ImportError:
            logger.warning("examination_models not available")
            StudentResult = None
            ExamSchedule = None
        
        try:
            from fee_models import StudentFee, PaymentStatusEnum
        except ImportError:
            logger.warning("fee_models not available")
            StudentFee = None
            PaymentStatusEnum = None
        
        try:
            from timetable_models import TimetableSchedule, TimeSlot, DayOfWeekEnum, TimeSlotClass
        except ImportError:
            logger.warning("timetable_models not available")
            TimetableSchedule = None
            DayOfWeekEnum = None
        
        try:
            from notification_models import NotificationRecipient, Notification, RecipientStatusEnum
        except ImportError:
            logger.warning("notification_models not available")
            NotificationRecipient = None
            RecipientStatusEnum = None
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        if not school:
            logger.error(f"School not found: {tenant_slug}")
            flash('School not found', 'error')
            return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
        
        # Get student record with safe fallbacks
        try:
            if hasattr(current_user, 'student_id'):
                student = session_db.query(Student).options(
                    joinedload(Student.student_class),
                    joinedload(Student.academic_session)
                ).filter_by(id=current_user.student_id, tenant_id=school.id).first()
            else:
                # Fallback for legacy User model
                student = session_db.query(Student).options(
                    joinedload(Student.student_class),
                    joinedload(Student.academic_session)
                ).filter_by(
                    tenant_id=school.id,
                    admission_number=current_user.username
                ).first()
        except Exception as e:
            logger.error(f"Error fetching student record: {e}")
            student = None
        
        if not student:
            logger.error(f"Student record not found for user: {current_user}")
            flash('Student record not found. Please contact administrator.', 'warning')
            # Don't redirect - render dashboard with minimal data
        
        # 1. Calculate attendance percentage (safe)
        if student and calculate_student_attendance_stats:
            try:
                current_month = datetime.now().month
                current_year = datetime.now().year
                attendance_stats = calculate_student_attendance_stats(session_db, student.id, current_month, current_year)
                attendance_percent = attendance_stats.get('percentage', 0) if attendance_stats else 0
            except Exception as e:
                logger.warning(f"Attendance calculation failed: {e}")
                attendance_percent = 0
        
        # 2. Calculate average score (safe)
        if student and StudentResult:
            try:
                recent_results = session_db.query(StudentResult).filter_by(
                    student_id=student.id,
                    tenant_id=school.id
                ).order_by(desc(StudentResult.created_at)).limit(5).all()
                
                if recent_results:
                    total_marks = sum([r.marks_obtained for r in recent_results if r.marks_obtained])
                    total_max = sum([r.total_marks for r in recent_results if r.total_marks])
                    average_score = round((total_marks / total_max * 100), 1) if total_max > 0 else 0
            except Exception as e:
                logger.warning(f"Average score calculation failed: {e}")
                average_score = 0
        
        # 3. Count pending assignments (safe)
        if student and ExamSchedule:
            try:
                today = datetime.now().date()
                pending_assignments = session_db.query(ExamSchedule).filter(
                    ExamSchedule.class_id == student.class_id,
                    ExamSchedule.tenant_id == school.id,
                    ExamSchedule.exam_date >= today
                ).count()
            except Exception as e:
                logger.warning(f"Pending assignments count failed: {e}")
                pending_assignments = 0
        
        # 4. Get fee status (safe)
        if student and StudentFee and PaymentStatusEnum:
            try:
                student_fees = session_db.query(StudentFee).filter_by(
                    student_id=student.id,
                    tenant_id=school.id
                ).all()
                
                if student_fees:
                    has_due = any(fee.payment_status == PaymentStatusEnum.PENDING for fee in student_fees)
                    fee_status = "Due" if has_due else "Paid"
                else:
                    fee_status = "No Fee Records"
            except Exception as e:
                logger.warning(f"Fee status check failed: {e}")
                fee_status = "N/A"
        
        # 5. Get today's timetable (safe)
        if student and TimetableSchedule and DayOfWeekEnum:
            try:
                today_day = datetime.now().weekday()
                day_mapping = {
                    0: DayOfWeekEnum.MONDAY,
                    1: DayOfWeekEnum.TUESDAY,
                    2: DayOfWeekEnum.WEDNESDAY,
                    3: DayOfWeekEnum.THURSDAY,
                    4: DayOfWeekEnum.FRIDAY,
                    5: DayOfWeekEnum.SATURDAY,
                    6: DayOfWeekEnum.SUNDAY
                }
                
                if student.class_id and today_day in day_mapping:
                    schedules = session_db.query(TimetableSchedule).join(
                        TimeSlot
                    ).join(
                        TimeSlotClass
                    ).filter(
                        TimeSlotClass.class_id == student.class_id,
                        TimetableSchedule.day_of_week == day_mapping[today_day],
                        TimetableSchedule.tenant_id == school.id
                    ).order_by(TimeSlot.start_time).all()
                    
                    # Check for substitutes for today
                    from timetable_models import SubstituteAssignment
                    today = datetime.now().date()
                    
                    today_schedule = []
                    for schedule in schedules:
                        # Check if there's a substitute for this schedule today
                        substitute_assignment = session_db.query(SubstituteAssignment).filter_by(
                            schedule_id=schedule.id,
                            date=today
                        ).first()
                        
                        # Use substitute teacher if assigned
                        if substitute_assignment and substitute_assignment.substitute_teacher:
                            teacher_name = f"{substitute_assignment.substitute_teacher.first_name} {substitute_assignment.substitute_teacher.last_name} (Substitute)"
                        else:
                            teacher_name = f"{schedule.teacher.first_name} {schedule.teacher.last_name}" if schedule.teacher else 'N/A'
                        
                        today_schedule.append({
                            'subject': schedule.subject.subject_name if schedule.subject else 'N/A',
                            'teacher': teacher_name,
                            'time': f"{schedule.time_slot.start_time.strftime('%H:%M')} - {schedule.time_slot.end_time.strftime('%H:%M')}" if schedule.time_slot else 'N/A',
                            'room': schedule.room_number or 'N/A'
                        })
            except Exception as e:
                logger.warning(f"Today's schedule fetch failed: {e}")
                today_schedule = []
        
        # 6. Get upcoming events (safe)
        if student and ExamSchedule:
            try:
                today = datetime.now().date()
                upcoming_events = session_db.query(ExamSchedule).filter(
                    ExamSchedule.class_id == student.class_id,
                    ExamSchedule.tenant_id == school.id,
                    ExamSchedule.exam_date >= today
                ).order_by(ExamSchedule.exam_date).limit(5).all()
                
                upcoming_events_list = [{
                    'title': f"{schedule.exam_subject.subject.subject_name if schedule.exam_subject and schedule.exam_subject.subject else 'Exam'} Exam",
                    'date': schedule.exam_date,
                    'time': schedule.start_time.strftime('%H:%M') if schedule.start_time else 'TBD',
                    'type': 'exam'
                } for schedule in upcoming_events]
            except Exception as e:
                logger.warning(f"Upcoming events fetch failed: {e}")
                upcoming_events_list = []
        
        # 7. Get recent grades (safe)
        if student and StudentResult:
            try:
                recent_grades = session_db.query(StudentResult).filter_by(
                    student_id=student.id,
                    tenant_id=school.id
                ).order_by(desc(StudentResult.created_at)).limit(5).all()
                
                recent_grades_list = [{
                    'subject': result.exam_subject.subject.subject_name if result.exam_subject and result.exam_subject.subject else 'N/A',
                    'marks': f"{result.marks_obtained}/{result.total_marks}" if result.marks_obtained is not None else 'N/A',
                    'grade': result.grade or 'N/A',
                    'date': result.created_at.strftime('%Y-%m-%d') if result.created_at else 'N/A'
                } for result in recent_grades]
            except Exception as e:
                logger.warning(f"Recent grades fetch failed: {e}")
                recent_grades_list = []
        
        # 8. Get announcements (safe)
        if student and NotificationRecipient and RecipientStatusEnum:
            try:
                announcements = session_db.query(NotificationRecipient).join(
                    Notification
                ).filter(
                    NotificationRecipient.student_id == student.id,
                    NotificationRecipient.tenant_id == school.id
                ).order_by(desc(Notification.created_at)).limit(5).all()
                
                announcements_list = [{
                    'title': recipient.notification.title if recipient.notification else 'Announcement',
                    'message': recipient.notification.message if recipient.notification else '',
                    'date': recipient.notification.created_at.strftime('%Y-%m-%d') if recipient.notification and recipient.notification.created_at else 'N/A',
                    'is_read': recipient.status == RecipientStatusEnum.READ
                } for recipient in announcements]
            except Exception as e:
                logger.warning(f"Announcements fetch failed: {e}")
                announcements_list = []
        
        # Get unread count (safe)
        if student and NotificationRecipient and RecipientStatusEnum:
            try:
                unread_count = session_db.query(NotificationRecipient).join(
                    Notification
                ).filter(
                    NotificationRecipient.student_id == student.id,
                    NotificationRecipient.tenant_id == school.id,
                    NotificationRecipient.status == RecipientStatusEnum.SENT
                ).count()
            except Exception as e:
                logger.warning(f"Unread count failed: {e}")
                unread_count = 0
        
        # Always render dashboard - NEVER redirect to login
        return render_template('student_dashboard_new/dashboard.html',
                                school=school,
                                student=student,
                                active_menu='dashboard',
                                current_year=datetime.now().year,
                                current_user=current_user,
                                attendance_percent=attendance_percent,
                                average_score=average_score,
                                pending_assignments=pending_assignments,
                                fee_status=fee_status,
                                today_schedule=today_schedule,
                                upcoming_events=upcoming_events_list,
                                recent_grades=recent_grades_list,
                                announcements=announcements_list,
                                unread_count=unread_count)
                                
    except Exception as e:
        logger.error(f"Critical dashboard error for {tenant_slug}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # NEVER redirect authenticated user - render minimal dashboard
        return render_template('student_dashboard_new/dashboard.html',
                                school=school if school else {'name': tenant_slug, 'slug': tenant_slug},
                                student=student,
                                active_menu='dashboard',
                                current_year=datetime.now().year,
                                current_user=current_user,
                                attendance_percent=0,
                                average_score=0,
                                pending_assignments=0,
                                fee_status="N/A",
                                today_schedule=[],
                                upcoming_events=[],
                                recent_grades=[],
                                announcements=[],
                                unread_count=0)
    finally:
        if session_db:
            session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/profile')
@require_student_auth
def student_profile(tenant_slug):
    """Student profile page"""
    session_db = get_session()
    try:
        from sqlalchemy.orm import joinedload
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get student record with all related data - current_user is StudentAuthUser with student_id
        if hasattr(current_user, 'student_id'):
            student = session_db.query(Student).options(
                joinedload(Student.student_class),
                joinedload(Student.academic_session),
                joinedload(Student.guardians),
                joinedload(Student.medical_info)
            ).filter_by(id=current_user.student_id).first()
        else:
            # Fallback for legacy User model
            student = session_db.query(Student).options(
                joinedload(Student.student_class),
                joinedload(Student.academic_session),
                joinedload(Student.guardians),
                joinedload(Student.medical_info)
            ).filter_by(
                tenant_id=school.id,
                admission_number=current_user.username
            ).first()
        
        if not student:
            flash('Student record not found', 'error')
            return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
        
        # Get unread message count for badge
        from notification_models import NotificationRecipient, Notification, RecipientStatusEnum
        unread_count = session_db.query(NotificationRecipient).join(
            Notification
        ).filter(
            NotificationRecipient.student_id == student.id,
            NotificationRecipient.tenant_id == school.id,
            NotificationRecipient.status == RecipientStatusEnum.SENT
        ).count()
        
        return render_template('student_dashboard_new/profile.html',
                                school=school,
                                student=student,
                                active_menu='profile',
                                current_year=datetime.now().year,
                                current_user=current_user,
                                unread_count=unread_count)
                                
    except Exception as e:
        logger.error(f"Student profile error for {tenant_slug}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash('Error loading profile', 'error')
        return redirect(url_for('student_auth.student_dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/attendance')
@require_student_auth
def student_attendance(tenant_slug):
    """Student attendance page"""
    session_db = get_session()
    try:
        from student_attendance_helpers import calculate_student_attendance_stats, get_student_monthly_calendar
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get student record - current_user is StudentAuthUser with student_id
        if hasattr(current_user, 'student_id'):
            student = session_db.query(Student).filter_by(id=current_user.student_id).first()
        else:
            # Fallback for legacy User model
            student = session_db.query(Student).filter_by(
                tenant_id=school.id,
                admission_number=current_user.username
            ).first()
        
        if not student:
            flash('Student record not found', 'error')
            return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
        
        # Get month and year from query params or use current
        current_month = int(request.args.get('month', datetime.now().month))
        current_year = int(request.args.get('year', datetime.now().year))
        
        # Calculate attendance statistics
        stats = calculate_student_attendance_stats(session_db, student.id, current_month, current_year)
        
        # Get monthly calendar data
        calendar_data = get_student_monthly_calendar(session_db, student.id, current_month, current_year)
        
        # Get unread message count for badge
        from notification_models import NotificationRecipient, Notification, RecipientStatusEnum
        unread_count = session_db.query(NotificationRecipient).join(
            Notification
        ).filter(
            NotificationRecipient.student_id == student.id,
            NotificationRecipient.tenant_id == school.id,
            NotificationRecipient.status == RecipientStatusEnum.SENT
        ).count()
        
        return render_template('student_dashboard_new/attendance.html',
                                school=school,
                                student=student,
                                active_menu='attendance',
                                current_year=current_year,
                                current_month=current_month,
                                attendance_stats=stats,
                                calendar_data=calendar_data,
                                current_user=current_user,
                                unread_count=unread_count)
                                
    except Exception as e:
        logger.error(f"Student attendance error for {tenant_slug}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash('Error loading attendance', 'error')
        return redirect(url_for('student_auth.student_dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/timetable')
@require_student_auth
def student_timetable(tenant_slug):
    """Student timetable page"""
    session_db = get_session()
    try:
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get student record - current_user is StudentAuthUser with student_id
        if hasattr(current_user, 'student_id'):
            student = session_db.query(Student).filter_by(id=current_user.student_id).first()
        else:
            # Fallback for legacy User model
            student = session_db.query(Student).filter_by(
                tenant_id=school.id,
                admission_number=current_user.username
            ).first()
        
        if not student:
            flash('Student record not found', 'error')
            return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
        
        # Get class timetable using the same logic as view_class_timetable
        from timetable_models import TimetableSchedule, TimeSlot, DayOfWeekEnum, TimeSlotClass
        from teacher_models import Subject, Teacher
        from timetable_helpers import get_current_academic_year
        
        timetable_data = None
        if student.class_id:
            academic_year = get_current_academic_year()
            
            # Fetch all time slots for this tenant
            all_time_slots = session_db.query(TimeSlot).filter_by(
                tenant_id=school.id,
                is_active=True
            ).order_by(TimeSlot.day_of_week, TimeSlot.slot_order, TimeSlot.start_time).all()
            
            # Filter time slots based on class assignments
            # Get all TimeSlotClass restrictions for this tenant
            slot_class_restrictions = session_db.query(TimeSlotClass).filter_by(
                tenant_id=school.id,
                is_active=True
            ).all()
            
            # Build a map of restricted slot IDs to their allowed class IDs
            restricted_slot_ids = {}
            for restriction in slot_class_restrictions:
                if restriction.time_slot_id not in restricted_slot_ids:
                    restricted_slot_ids[restriction.time_slot_id] = []
                restricted_slot_ids[restriction.time_slot_id].append(restriction.class_id)
            
            # Filter time slots: include if unrestricted OR student's class is in allowed list
            time_slots = []
            for slot in all_time_slots:
                if slot.id in restricted_slot_ids:
                    # Slot is restricted - only include if student's class is allowed
                    if student.class_id in restricted_slot_ids[slot.id]:
                        time_slots.append(slot)
                else:
                    # Slot is unrestricted - include it
                    time_slots.append(slot)
            
            # Fetch all timetable schedules for this class
            schedules = session_db.query(TimetableSchedule).filter_by(
                tenant_id=school.id,
                class_id=student.class_id,
                is_active=True,
                academic_year=academic_year
            ).all()
            
            # Create a mapping of (day, time_slot_id) -> schedule
            schedule_map = {}
            for schedule in schedules:
                key = (schedule.day_of_week.value, schedule.time_slot_id)
                
                # Get teacher and subject details
                teacher = session_db.query(Teacher).get(schedule.teacher_id)
                subject = session_db.query(Subject).get(schedule.subject_id)
                
                # Check for substitute teacher for TODAY
                from timetable_models import SubstituteAssignment
                from datetime import date
                today = date.today()
                
                substitute_assignment = session_db.query(SubstituteAssignment).filter_by(
                    schedule_id=schedule.id,
                    date=today
                ).first()
                
                # Use substitute teacher if assigned for today
                if substitute_assignment:
                    substitute_teacher = session_db.query(Teacher).get(substitute_assignment.substitute_teacher_id)
                    teacher_name = f"{substitute_teacher.first_name} {substitute_teacher.last_name} (Substitute)" if substitute_teacher else 'N/A'
                else:
                    teacher_name = f"{teacher.first_name} {teacher.last_name}" if teacher else 'N/A'
                
                schedule_map[key] = {
                    'id': schedule.id,
                    'subject': subject.name if subject else 'N/A',
                    'teacher': teacher_name,
                    'room': schedule.room_number or '-'
                }
            
            # Organize time slots by day
            days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            time_slots_by_day = {}
            for day in days_order:
                time_slots_by_day[day] = []
            
            for slot in time_slots:
                day = slot.day_of_week.value
                if day in time_slots_by_day:
                    time_slots_by_day[day].append(slot)
            
            # Get all unique time slots (unique by time, not by day)
            unique_slots = {}
            for slot in time_slots:
                key = (slot.start_time, slot.end_time, slot.slot_name or '', slot.slot_type.value)
                if key not in unique_slots:
                    unique_slots[key] = {
                        'start_time': slot.start_time.strftime('%H:%M'),
                        'end_time': slot.end_time.strftime('%H:%M'),
                        'slot_name': slot.slot_name or 'Period',
                        'slot_type': slot.slot_type.value,
                        'slot_order': slot.slot_order or 0
                    }
            
            # Sort unique slots by slot_order and start_time
            sorted_slots = sorted(unique_slots.values(), key=lambda x: (x['slot_order'], x['start_time']))
            
            # Build the timetable grid
            timetable_grid = []
            for slot_info in sorted_slots:
                row = {
                    'time': f"{slot_info['start_time']} - {slot_info['end_time']}",
                    'slot_name': slot_info['slot_name'],
                    'slot_type': slot_info['slot_type'],
                    'periods': {}
                }
                
                # For each day, find the schedule for this time slot
                for day in days_order:
                    # Find the time slot ID for this day and time
                    matching_slot = None
                    for slot in time_slots_by_day.get(day, []):
                        if (slot.start_time.strftime('%H:%M') == slot_info['start_time'] and
                            slot.end_time.strftime('%H:%M') == slot_info['end_time']):
                            matching_slot = slot
                            break
                    
                    if matching_slot:
                        key = (day, matching_slot.id)
                        if key in schedule_map:
                            row['periods'][day] = schedule_map[key]
                        elif matching_slot.slot_type.value in ['Break', 'Lunch', 'Assembly']:
                            row['periods'][day] = {
                                'subject': matching_slot.slot_type.value,
                                'teacher': '-',
                                'room': '-',
                                'is_break': True
                            }
                        else:
                            # Empty but has time slot - can be assigned
                            row['periods'][day] = {
                                'is_empty': True,
                                'time_slot_id': matching_slot.id
                            }
                    else:
                        # No time slot for this day/time - truly empty
                        row['periods'][day] = None
                
                timetable_grid.append(row)
            
            timetable_data = {
                'grid': timetable_grid,
                'days': days_order
            }
        
        # Get unread message count for badge
        from notification_models import NotificationRecipient, Notification, RecipientStatusEnum
        unread_count = session_db.query(NotificationRecipient).join(
            Notification
        ).filter(
            NotificationRecipient.student_id == student.id,
            NotificationRecipient.tenant_id == school.id,
            NotificationRecipient.status == RecipientStatusEnum.SENT
        ).count()
        
        return render_template('student_dashboard_new/timetable.html',
                                school=school,
                                student=student,
                                timetable_data=timetable_data,
                                active_menu='timetable',
                                current_year=datetime.now().year,
                                current_user=current_user,
                                unread_count=unread_count)
                                
    except Exception as e:
        logger.error(f"Student timetable error for {tenant_slug}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash('Error loading timetable', 'error')
        return redirect(url_for('student_auth.student_dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/exams')
@require_student_auth
def student_exams(tenant_slug):
    """Student examinations page with real backend data"""
    session_db = get_session()
    try:
        from examination_models import ExamSchedule, StudentResult, ExaminationSubject
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get student record - current_user is StudentAuthUser with student_id
        if hasattr(current_user, 'student_id'):
            student = session_db.query(Student).filter_by(
                id=current_user.student_id,
                tenant_id=school.id
            ).first()
        else:
            # Fallback for legacy User model
            student = session_db.query(Student).filter_by(
                tenant_id=school.id,
                admission_number=current_user.username
            ).first()
        
        if not student:
            flash('Student record not found', 'error')
            return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
        
        # Fetch real exam data
        today = datetime.now().date()
        
        # Upcoming exams
        upcoming_exams = session_db.query(ExamSchedule).filter(
            ExamSchedule.class_id == student.class_id,
            ExamSchedule.tenant_id == school.id,
            ExamSchedule.exam_date >= today
        ).order_by(ExamSchedule.exam_date).limit(10).all()
        
        # Previous results
        previous_results = session_db.query(StudentResult).filter_by(
            student_id=student.id,
            tenant_id=school.id
        ).order_by(desc(StudentResult.created_at)).limit(10).all()
        
        # Calculate statistics
        if previous_results:
            total_marks = sum([r.marks_obtained for r in previous_results if r.marks_obtained])
            total_max = sum([r.total_marks for r in previous_results if r.total_marks])
            overall_average = round((total_marks / total_max * 100), 1) if total_max > 0 else 0
        else:
            overall_average = 0
        
        total_exams = len(previous_results)
        
        return render_template('student_dashboard_new/exams.html',
                                school=school,
                                student=student,
                                active_menu='exams',
                                current_year=datetime.now().year,
                                current_user=current_user,
                                upcoming_exams=upcoming_exams,
                                previous_results=previous_results,
                                overall_average=overall_average,
                                total_exams=total_exams)
                                
    except Exception as e:
        logger.error(f"Student exams error for {tenant_slug}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash('Error loading examinations', 'error')
        return redirect(url_for('student_auth.student_dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/fees')
@require_student_auth
def student_fees(tenant_slug):
    """Student fees and payments page"""
    session_db = get_session()
    try:
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get student record - current_user is StudentAuthUser with student_id
        if hasattr(current_user, 'student_id'):
            student = session_db.query(Student).filter_by(id=current_user.student_id).first()
        else:
            # Fallback for legacy User model
            student = session_db.query(Student).filter_by(
                tenant_id=school.id,
                admission_number=current_user.username
            ).first()
        
        if not student:
            flash('Student record not found', 'error')
            return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
        
        # Get active academic session
        from models import AcademicSession
        from fee_models import StudentFee, FeeReceipt, FeeInstallment, FeeStructureDetail, FeeStructure, FeeCategory, PaymentStatusEnum
        from fee_helpers import calculate_student_fee_total
        from sqlalchemy.orm import joinedload
        
        active_session = session_db.query(AcademicSession).filter_by(
            tenant_id=school.id,
            is_active=True
        ).first()
        
        # Get all student fees for current session
        student_fees = []
        total_amount = 0
        total_paid = 0
        total_outstanding = 0
        next_due_date = None
        
        if active_session:
            fees_query = session_db.query(StudentFee).options(
                joinedload(StudentFee.fee_structure)
            ).filter_by(
                student_id=student.id,
                session_id=active_session.id
            ).all()
            
            for fee in fees_query:
                fee_calc = calculate_student_fee_total(session_db, fee.id)
                
                # Get fee structure details for breakdown
                structure_details = session_db.query(FeeStructureDetail).options(
                    joinedload(FeeStructureDetail.category)
                ).filter_by(
                    fee_structure_id=fee.fee_structure_id
                ).order_by(FeeStructureDetail.installment_number).all()
                
                # Get installments
                installments = session_db.query(FeeInstallment).filter_by(
                    student_fee_id=fee.id
                ).order_by(FeeInstallment.installment_number).all()
                
                # Get receipts
                receipts = session_db.query(FeeReceipt).options(
                    joinedload(FeeReceipt.student_fee).joinedload(StudentFee.fee_structure)
                ).filter_by(
                    student_fee_id=fee.id,
                    status=PaymentStatusEnum.VERIFIED
                ).order_by(FeeReceipt.payment_date.desc()).all()
                
                student_fees.append({
                    'fee': fee,
                    'structure_details': structure_details,
                    'installments': installments,
                    'receipts': receipts,
                    'total_amount': fee_calc['total_amount'],
                    'paid_amount': fee_calc['paid_amount'],
                    'balance_amount': fee_calc['balance_amount'],
                    'discount_amount': fee_calc['discount_amount'],
                    'fine_amount': fee_calc['fine_amount'],
                    'net_amount': fee_calc['net_amount'],
                    'status': fee_calc['status']
                })
                
                total_amount += fee_calc['net_amount']
                total_paid += fee_calc['paid_amount']
                total_outstanding += fee_calc['balance_amount']
                
                # Track nearest due date
                if fee.due_date:
                    if not next_due_date or fee.due_date < next_due_date:
                        if fee_calc['balance_amount'] > 0:
                            next_due_date = fee.due_date
        
        # Calculate payment percentage
        payment_percentage = (total_paid / total_amount * 100) if total_amount > 0 else 0
        
        # Get unread message count for badge
        from notification_models import NotificationRecipient, Notification, RecipientStatusEnum
        unread_count = session_db.query(NotificationRecipient).join(
            Notification
        ).filter(
            NotificationRecipient.student_id == student.id,
            NotificationRecipient.tenant_id == school.id,
            NotificationRecipient.status == RecipientStatusEnum.SENT
        ).count()
        
        return render_template('student_dashboard_new/fees.html',
                                school=school,
                                student=student,
                                active_menu='fees',
                                current_year=datetime.now().year,
                                current_user=current_user,
                                active_session=active_session,
                                student_fees=student_fees,
                                total_amount=total_amount,
                                total_paid=total_paid,
                                total_outstanding=total_outstanding,
                                payment_percentage=payment_percentage,
                                next_due_date=next_due_date,
                                unread_count=unread_count)
                                
    except Exception as e:
        logger.error(f"Student fees error for {tenant_slug}: {e}")
        flash('Error loading fees', 'error')
        return redirect(url_for('student_auth.student_dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/messages')
@require_student_auth
def student_messages(tenant_slug):
    """Student messages page - using notifications as messages"""
    session_db = get_session()
    try:
        from notification_models import NotificationRecipient, Notification, RecipientStatusEnum
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get student record - current_user is StudentAuthUser with student_id
        if hasattr(current_user, 'student_id'):
            student = session_db.query(Student).filter_by(
                id=current_user.student_id,
                tenant_id=school.id
            ).first()
        else:
            # Fallback for legacy User model
            student = session_db.query(Student).filter_by(
                tenant_id=school.id,
                admission_number=current_user.username
            ).first()
        
        if not student:
            flash('Student record not found', 'error')
            return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
        
        # Fetch messages (using notifications as messages)
        messages = session_db.query(NotificationRecipient).join(
            Notification
        ).filter(
            NotificationRecipient.student_id == student.id,
            NotificationRecipient.tenant_id == school.id
        ).order_by(desc(Notification.created_at)).limit(20).all()
        
        # Count unread messages
        unread_count = sum(1 for m in messages if m.status != RecipientStatusEnum.READ)
        
        return render_template('student_dashboard_new/messages.html',
                                school=school,
                                student=student,
                                active_menu='messages',
                                current_year=datetime.now().year,
                                current_user=current_user,
                                messages=messages,
                                unread_count=unread_count)
                                
    except Exception as e:
        logger.error(f"Student messages error for {tenant_slug}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash('Error loading messages', 'error')
        return redirect(url_for('student_auth.student_dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/messages/count.json')
@require_student_auth
def student_messages_count(tenant_slug):
    """Get unread message count for student messages badge - bulletproof"""
    session_db = get_session()
    try:
        # Safe import
        try:
            from notification_models import NotificationRecipient, Notification, RecipientStatusEnum
        except ImportError:
            logger.warning("notification_models not available")
            return jsonify({'success': False, 'count': 0, 'error': 'Notifications module unavailable'})
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        if not school:
            return jsonify({'success': False, 'count': 0, 'error': 'School not found'})
        
        # Get student record with safe fallback
        student_id = None
        try:
            if hasattr(current_user, 'student_id'):
                student_id = current_user.student_id
            else:
                student = session_db.query(Student).filter_by(
                    tenant_id=school.id,
                    admission_number=current_user.username
                ).first()
                student_id = student.id if student else None
        except Exception as e:
            logger.warning(f"Error fetching student ID: {e}")
            student_id = None
        
        if not student_id:
            return jsonify({'success': False, 'count': 0, 'error': 'Student not found'})
        
        # Count unread messages with error handling
        try:
            unread_count = session_db.query(NotificationRecipient).join(
                Notification
            ).filter(
                NotificationRecipient.student_id == student_id,
                NotificationRecipient.tenant_id == school.id,
                NotificationRecipient.status != RecipientStatusEnum.READ
            ).count()
        except Exception as e:
            logger.warning(f"Error counting unread messages: {e}")
            unread_count = 0
        
        return jsonify({
            'success': True,
            'count': unread_count
        })
        
    except Exception as e:
        logger.error(f"Student messages count error: {e}")
        return jsonify({'success': False, 'count': 0, 'error': str(e)}), 500
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/messages/recent.json')
@require_student_auth
def student_messages_recent(tenant_slug):
    """Get recent messages for student messages dropdown"""
    session_db = get_session()
    try:
        from notification_models import NotificationRecipient, Notification, RecipientStatusEnum
        from sqlalchemy.orm import joinedload
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get student record
        if hasattr(current_user, 'student_id'):
            student_id = current_user.student_id
        else:
            student = session_db.query(Student).filter_by(
                tenant_id=school.id,
                admission_number=current_user.username
            ).first()
            student_id = student.id if student else None
        
        if not student_id:
            return jsonify({'success': False, 'messages': [], 'error': 'Student not found'})
        
        # Get limit from query param or default to 5
        limit = request.args.get('limit', 5, type=int)
        
        # Fetch recent messages
        recent = session_db.query(NotificationRecipient).join(
            Notification
        ).options(
            joinedload(NotificationRecipient.notification)
        ).filter(
            NotificationRecipient.student_id == student_id,
            NotificationRecipient.tenant_id == school.id
        ).order_by(desc(Notification.created_at)).limit(limit).all()
        
        # Format messages for JSON response
        messages_data = []
        for recipient in recent:
            notif = recipient.notification
            if notif:
                # Calculate time ago
                time_diff = datetime.now() - notif.created_at if notif.created_at else None
                if time_diff:
                    if time_diff.days > 0:
                        time_ago = f"{time_diff.days} day{'s' if time_diff.days > 1 else ''} ago"
                    elif time_diff.seconds >= 3600:
                        hours = time_diff.seconds // 3600
                        time_ago = f"{hours} hour{'s' if hours > 1 else ''} ago"
                    elif time_diff.seconds >= 60:
                        minutes = time_diff.seconds // 60
                        time_ago = f"{minutes} min ago"
                    else:
                        time_ago = "Just now"
                else:
                    time_ago = "Unknown"
                
                messages_data.append({
                    'id': recipient.id,
                    'sender': notif.title or 'System',
                    'message': notif.message[:60] + '...' if len(notif.message) > 60 else notif.message,
                    'time_ago': time_ago,
                    'is_unread': recipient.status != RecipientStatusEnum.READ,
                    'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M:%S') if notif.created_at else None
                })
        
        # Count unread
        unread_count = sum(1 for msg in messages_data if msg['is_unread'])
        
        return jsonify({
            'success': True,
            'messages': messages_data,
            'unread_count': unread_count
        })
        
    except Exception as e:
        logger.error(f"Student messages recent error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'messages': [], 'unread_count': 0, 'error': str(e)}), 500
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/documents')
@require_student_auth
def student_documents(tenant_slug):
    """Student documents page with real backend data"""
    session_db = get_session()
    try:
        from student_models import StudentDocument, StudentDocumentTypeEnum
        from sqlalchemy import func
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get student record - current_user is StudentAuthUser with student_id
        if hasattr(current_user, 'student_id'):
            student = session_db.query(Student).filter_by(
                id=current_user.student_id,
                tenant_id=school.id
            ).first()
        else:
            # Fallback for legacy User model
            student = session_db.query(Student).filter_by(
                tenant_id=school.id,
                admission_number=current_user.username
            ).first()
        
        if not student:
            flash('Student record not found', 'error')
            return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
        
        # Fetch real documents data
        documents = session_db.query(StudentDocument).filter_by(
            student_id=student.id,
            tenant_id=school.id
        ).order_by(desc(StudentDocument.uploaded_at)).all()
        
        # Calculate statistics
        total_documents = len(documents)
        
        # Count by type (simulating file types) - safely handle missing attributes
        pdf_count = 0
        image_count = 0
        for d in documents:
            if hasattr(d, 'file_name') and d.file_name:
                if d.file_name.lower().endswith('.pdf'):
                    pdf_count += 1
                elif d.file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    image_count += 1
            elif hasattr(d, 'file_path') and d.file_path:
                if d.file_path.lower().endswith('.pdf'):
                    pdf_count += 1
                elif d.file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    image_count += 1
        other_count = total_documents - pdf_count - image_count
        
        # Category-wise grouping - safely handle missing doc_type
        category_counts = {}
        for doc in documents:
            try:
                if hasattr(doc, 'doc_type') and doc.doc_type:
                    doc_type = doc.doc_type.value if hasattr(doc.doc_type, 'value') else str(doc.doc_type)
                elif hasattr(doc, 'document_type') and doc.document_type:
                    doc_type = doc.document_type.value if hasattr(doc.document_type, 'value') else str(doc.document_type)
                else:
                    doc_type = 'other'
                category_counts[doc_type] = category_counts.get(doc_type, 0) + 1
            except:
                category_counts['other'] = category_counts.get('other', 0) + 1
        
        # Get unread message count for badge
        from notification_models import NotificationRecipient, Notification, RecipientStatusEnum
        unread_count = session_db.query(NotificationRecipient).join(
            Notification
        ).filter(
            NotificationRecipient.student_id == student.id,
            NotificationRecipient.tenant_id == school.id,
            NotificationRecipient.status == RecipientStatusEnum.SENT
        ).count()
        
        return render_template('student_dashboard_new/documents.html',
                                school=school,
                                student=student,
                                active_menu='documents',
                                current_year=datetime.now().year,
                                current_user=current_user,
                                documents=documents,
                                total_documents=total_documents,
                                pdf_count=pdf_count,
                                image_count=image_count,
                                other_count=other_count,
                                category_counts=category_counts,
                                unread_count=unread_count)
                                
    except Exception as e:
        logger.error(f"Student documents error for {tenant_slug}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash('Error loading documents', 'error')
        return redirect(url_for('student_auth.student_dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/leaves', methods=['GET', 'POST'])
@require_student_auth
def student_leaves(tenant_slug):
    """Student leave management page"""
    session_db = get_session()
    try:
        from student_leave_helpers import get_student_leaves, apply_student_leave
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get student record - current_user is StudentAuthUser with student_id
        if hasattr(current_user, 'student_id'):
            student = session_db.query(Student).filter_by(id=current_user.student_id).first()
        else:
            # Fallback for legacy User model
            student = session_db.query(Student).filter_by(
                tenant_id=school.id,
                admission_number=current_user.username
            ).first()
        
        if not student:
            flash('Student record not found', 'error')
            return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
        
        # Handle leave application submission
        if request.method == 'POST':
            return redirect(url_for('student_auth.student_apply_leave', tenant_slug=tenant_slug))
        
        # Get all leaves for this student
        leaves = get_student_leaves(session_db, student.id)
        
        # Get unread message count for badge
        from notification_models import NotificationRecipient, Notification, RecipientStatusEnum
        unread_count = session_db.query(NotificationRecipient).join(
            Notification
        ).filter(
            NotificationRecipient.student_id == student.id,
            NotificationRecipient.tenant_id == school.id,
            NotificationRecipient.status == RecipientStatusEnum.SENT
        ).count()
        
        return render_template('student_dashboard_new/leaves.html',
                                school=school,
                                student=student,
                                leaves=leaves,
                                active_menu='leaves',
                                current_year=datetime.now().year,
                                current_user=current_user,
                                unread_count=unread_count)
                                
    except Exception as e:
        logger.error(f"Student leaves error for {tenant_slug}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash('Error loading leaves', 'error')
        return redirect(url_for('student_auth.student_dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/leaves/apply', methods=['POST'])
@require_student_auth
def student_apply_leave(tenant_slug):
    """Apply for a leave"""
    session_db = get_session()
    try:
        from student_leave_helpers import apply_student_leave
        from leave_models import StudentLeaveTypeEnum
        from datetime import date
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get student record - current_user is StudentAuthUser with student_id
        if hasattr(current_user, 'student_id'):
            student = session_db.query(Student).filter_by(id=current_user.student_id).first()
        else:
            # Fallback for legacy User model
            student = session_db.query(Student).filter_by(
                tenant_id=school.id,
                admission_number=current_user.username
            ).first()
        
        if not student:
            flash('Student record not found', 'error')
            return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
        
        # Parse form data
        leave_type_str = request.form.get('leave_type')
        from_date_str = request.form.get('from_date')
        to_date_str = request.form.get('to_date')
        is_half_day = request.form.get('is_half_day') == 'on'
        half_day_period = request.form.get('half_day_period') if is_half_day else None
        reason = request.form.get('reason')
        
        # Parse dates
        from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
        to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
        
        # Prepare leave data
        leave_data = {
            'leave_type': leave_type_str,
            'from_date': from_date,
            'to_date': to_date,
            'is_half_day': is_half_day,
            'half_day_period': half_day_period,
            'reason': reason
        }
        
        # Get uploaded documents
        files = request.files.getlist('documents')
        # Filter out empty files
        files = [f for f in files if f.filename]
        
        # Apply leave using helper function
        success, message, leave = apply_student_leave(
            db_session=session_db,
            tenant_id=school.id,
            student_id=student.id,
            class_id=student.class_id,
            leave_data=leave_data,
            files=files if files else None
        )
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('student_auth.student_leaves', tenant_slug=tenant_slug))
        
    except Exception as e:
        logger.error(f"Error applying leave for {tenant_slug}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash('Error submitting leave application', 'error')
        session_db.rollback()
        return redirect(url_for('student_auth.student_leaves', tenant_slug=tenant_slug))
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/leaves/<int:leave_id>/cancel', methods=['POST'])
@require_student_auth
def student_cancel_leave(tenant_slug, leave_id):
    """Cancel a pending leave"""
    session_db = get_session()
    try:
        from student_leave_helpers import cancel_student_leave
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get student record - current_user is StudentAuthUser with student_id
        if hasattr(current_user, 'student_id'):
            student = session_db.query(Student).filter_by(id=current_user.student_id).first()
        else:
            # Fallback for legacy User model
            student = session_db.query(Student).filter_by(
                tenant_id=school.id,
                admission_number=current_user.username
            ).first()
        
        if not student:
            flash('Student record not found', 'error')
            return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
        
        # Cancel leave using helper function
        success, message = cancel_student_leave(session_db, leave_id, student.id)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
    except Exception as e:
        logger.error(f"Error cancelling leave for {tenant_slug}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash('Error cancelling leave', 'error')
        session_db.rollback()
    finally:
        session_db.close()
    
    return redirect(url_for('student_auth.student_leaves', tenant_slug=tenant_slug))

# ===== STUDENT NOTIFICATION ROUTES =====

@student_auth_bp.route('/<tenant_slug>/student/notifications')
@require_student_auth
def student_notifications(tenant_slug):
    """Student notifications page"""
    session_db = get_session()
    try:
        from notification_models import NotificationRecipient, Notification, RecipientStatusEnum
        from sqlalchemy.orm import joinedload
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get student record
        if hasattr(current_user, 'student_id'):
            student = session_db.query(Student).filter_by(id=current_user.student_id).first()
        else:
            student = session_db.query(Student).filter_by(
                tenant_id=school.id,
                admission_number=current_user.username
            ).first()
        
        if not student:
            flash('Student record not found', 'error')
            return redirect(url_for('student_auth.student_login', tenant_slug=tenant_slug))
        
        # Get notifications for this student
        notifications = session_db.query(NotificationRecipient).filter_by(
            student_id=student.id,
            tenant_id=school.id
        ).options(
            joinedload(NotificationRecipient.notification)
        ).order_by(NotificationRecipient.sent_at.desc()).all()
        
        unread_count = 0
        notification_list = []
        
        for nr in notifications:
            if nr.notification and nr.notification.status.value == 'Sent':
                is_unread = nr.status == RecipientStatusEnum.SENT
                if is_unread:
                    unread_count += 1
                
                notification_list.append({
                    'id': nr.id,
                    'notification_id': nr.notification_id,
                    'title': nr.notification.title,
                    'message': nr.notification.message,
                    'priority': nr.notification.priority.value if nr.notification.priority else 'Normal',
                    'sent_at': nr.sent_at,
                    'read_at': nr.read_at,
                    'is_read': nr.status == RecipientStatusEnum.READ,
                    'documents': [{'file_name': d.file_name, 'file_path': d.file_path, 'file_size_kb': d.file_size_kb, 'mime_type': d.mime_type} for d in nr.notification.documents]
                })
        
        return render_template('student_dashboard_new/notifications.html',
                                school=school,
                                student=student,
                                notifications=notification_list,
                                unread_count=unread_count,
                                active_menu='notifications',
                                current_year=datetime.now().year,
                                current_user=current_user)
                                
    except Exception as e:
        logger.error(f"Student notifications error for {tenant_slug}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash('Error loading notifications', 'error')
        return redirect(url_for('student_auth.student_dashboard', tenant_slug=tenant_slug))
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/notifications/count.json')
@require_student_auth
def student_notifications_count(tenant_slug):
    """Get unread notification count for the student navbar badge - bulletproof"""
    session_db = get_session()
    try:
        # Safe import
        try:
            from notification_models import NotificationRecipient, Notification, RecipientStatusEnum, NotificationStatusEnum
        except ImportError:
            logger.warning("notification_models not available")
            return jsonify({'success': False, 'count': 0, 'error': 'Notifications module unavailable'})
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        if not school:
            return jsonify({'success': False, 'count': 0, 'error': 'School not found'})
        
        # Get student record with safe fallback
        student_id = None
        try:
            if hasattr(current_user, 'student_id'):
                student_id = current_user.student_id
            else:
                student = session_db.query(Student).filter_by(
                    tenant_id=school.id,
                    admission_number=current_user.username
                ).first()
                student_id = student.id if student else None
        except Exception as e:
            logger.warning(f"Error fetching student ID: {e}")
            student_id = None
        
        if not student_id:
            return jsonify({'success': False, 'count': 0, 'error': 'Student not found'})
        
        # Count unread notifications with error handling
        try:
            unread_count = session_db.query(NotificationRecipient).join(
                Notification, NotificationRecipient.notification_id == Notification.id
            ).filter(
                NotificationRecipient.student_id == student_id,
                NotificationRecipient.tenant_id == school.id,
                NotificationRecipient.status == RecipientStatusEnum.SENT,
                Notification.status == NotificationStatusEnum.SENT
            ).count()
        except Exception as e:
            logger.warning(f"Error counting unread notifications: {e}")
            unread_count = 0
        
        return jsonify({
            'success': True,
            'count': unread_count
        })
        
    except Exception as e:
        logger.error(f"Student notification count error: {e}")
        return jsonify({'success': False, 'count': 0, 'error': str(e)}), 500
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/notifications/recent.json')
@require_student_auth
def student_notifications_recent(tenant_slug):
    """Get recent notifications for student navbar dropdown"""
    session_db = get_session()
    try:
        from notification_models import NotificationRecipient, Notification, NotificationDocument, RecipientStatusEnum, NotificationStatusEnum
        from sqlalchemy.orm import joinedload, subqueryload
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get student record
        if hasattr(current_user, 'student_id'):
            student_id = current_user.student_id
        else:
            student = session_db.query(Student).filter_by(
                tenant_id=school.id,
                admission_number=current_user.username
            ).first()
            student_id = student.id if student else None
        
        if not student_id:
            return jsonify({'success': False, 'notifications': [], 'error': 'Student not found'})
        
        # Get limit from query param or default to 50
        limit = request.args.get('limit', 5, type=int)
        
        recent = session_db.query(NotificationRecipient).join(
            Notification, NotificationRecipient.notification_id == Notification.id
        ).filter(
            NotificationRecipient.student_id == student_id,
            NotificationRecipient.tenant_id == school.id,
            Notification.status == NotificationStatusEnum.SENT
        ).options(
            joinedload(NotificationRecipient.notification).subqueryload(Notification.documents)
        ).order_by(NotificationRecipient.sent_at.desc()).limit(limit).all()
        
        notifications = []
        for nr in recent:
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
            NotificationRecipient.student_id == student_id,
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
        logger.error(f"Student recent notifications error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'notifications': [], 'error': str(e)}), 500
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/notifications/<int:recipient_id>/read', methods=['POST'])
@require_student_auth
def student_notification_mark_read(tenant_slug, recipient_id):
    """Mark a notification as read for student"""
    session_db = get_session()
    try:
        from notification_models import NotificationRecipient, RecipientStatusEnum
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get student record
        if hasattr(current_user, 'student_id'):
            student_id = current_user.student_id
        else:
            student = session_db.query(Student).filter_by(
                tenant_id=school.id,
                admission_number=current_user.username
            ).first()
            student_id = student.id if student else None
        
        if not student_id:
            return jsonify({'success': False, 'error': 'Student not found'}), 404
        
        # Find and update the notification recipient record
        nr = session_db.query(NotificationRecipient).filter_by(
            id=recipient_id,
            student_id=student_id,
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
        logger.error(f"Student mark notification read error: {e}")
        session_db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session_db.close()

@student_auth_bp.route('/<tenant_slug>/student/notifications/mark-all-read', methods=['POST'])
@require_student_auth
def student_notifications_mark_all_read(tenant_slug):
    """Mark all notifications as read for student"""
    session_db = get_session()
    try:
        from notification_models import NotificationRecipient, Notification, RecipientStatusEnum, NotificationStatusEnum
        
        school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
        
        # Get student record
        if hasattr(current_user, 'student_id'):
            student_id = current_user.student_id
        else:
            student = session_db.query(Student).filter_by(
                tenant_id=school.id,
                admission_number=current_user.username
            ).first()
            student_id = student.id if student else None
        
        if not student_id:
            return jsonify({'success': False, 'error': 'Student not found'}), 404
        
        # Find recipient ids to update (avoid update() on joined query)
        recipient_ids = [r.id for r in session_db.query(NotificationRecipient.id).join(
            Notification, NotificationRecipient.notification_id == Notification.id
        ).filter(
            NotificationRecipient.student_id == student_id,
            NotificationRecipient.tenant_id == school.id,
            NotificationRecipient.status == RecipientStatusEnum.SENT,
            Notification.status == NotificationStatusEnum.SENT
        ).all()]

        updated = 0
        if recipient_ids:
            updated = session_db.query(NotificationRecipient).filter(
                NotificationRecipient.id.in_(recipient_ids)
            ).update({
                'status': RecipientStatusEnum.READ,
                'read_at': datetime.now()
            }, synchronize_session=False)
            session_db.commit()

        logger.info(f"Student mark all read: tenant={tenant_slug} student_id={student_id} recipients_found={len(recipient_ids)} updated={updated}")

        return jsonify({
            'success': True,
            'message': f'Marked {updated} notifications as read'
        })
        
    except Exception as e:
        logger.error(f"Student mark all notifications read error: {e}")
        session_db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        session_db.close()
