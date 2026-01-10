"""
Leave Management Helper Functions
"""

from datetime import datetime, date
from decimal import Decimal
from dateutil.relativedelta import relativedelta
import logging

logger = logging.getLogger(__name__)


def get_current_academic_year():
    """
    Calculate current academic year based on current date
    Academic year starts on April 1st
    
    Returns:
        str: Academic year in format "2024-25"
    """
    today = date.today()
    
    # If month is Jan-Mar, academic year is previous year
    if today.month < 4:
        start_year = today.year - 1
        end_year = today.year
    else:
        start_year = today.year
        end_year = today.year + 1
    
    return f"{start_year}-{str(end_year)[-2:]}"


def get_or_create_quota_settings(session, tenant_id, academic_year=None):
    """
    Get existing quota settings or create default ones
    
    Args:
        session: Database session
        tenant_id: School tenant ID
        academic_year: Academic year string (e.g., "2024-25")
    
    Returns:
        LeaveQuotaSettings: Quota settings object
    """
    from leave_models import LeaveQuotaSettings
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    settings = session.query(LeaveQuotaSettings).filter_by(
        tenant_id=tenant_id,
        academic_year=academic_year
    ).first()
    
    if not settings:
        # Create default settings
        settings = LeaveQuotaSettings(
            tenant_id=tenant_id,
            academic_year=academic_year,
            cl_quota=12.0,
            sl_quota=12.0,
            el_quota=15.0,
            maternity_quota=180.0,
            paternity_quota=15.0,
            allow_half_day=True,
            allow_lop=True,
            duty_leave_unlimited=True,
            max_continuous_days=30,
            min_advance_days=1,
            weekend_counted=False,
            is_active=True
        )
        session.add(settings)
        session.flush()
        logger.info(f"Created default quota settings for tenant {tenant_id}, year {academic_year}")
    
    return settings


def initialize_teacher_balance(session, teacher_id, tenant_id, quota_settings, academic_year=None):
    """
    Initialize leave balance for a single teacher based on quota settings
    
    Args:
        session: Database session
        teacher_id: Teacher ID
        tenant_id: School tenant ID
        quota_settings: LeaveQuotaSettings object
        academic_year: Academic year string
    
    Returns:
        TeacherLeaveBalance: Created balance object
    """
    from leave_models import TeacherLeaveBalance
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    # Check if balance already exists
    existing = session.query(TeacherLeaveBalance).filter_by(
        teacher_id=teacher_id,
        academic_year=academic_year
    ).first()
    
    if existing:
        logger.warning(f"Balance already exists for teacher {teacher_id}, year {academic_year}")
        return existing
    
    # Create new balance
    balance = TeacherLeaveBalance(
        tenant_id=tenant_id,
        teacher_id=teacher_id,
        academic_year=academic_year,
        cl_total=quota_settings.cl_quota,
        cl_taken=0,
        cl_pending=0,
        sl_total=quota_settings.sl_quota,
        sl_taken=0,
        sl_pending=0,
        el_total=quota_settings.el_quota,
        el_taken=0,
        el_pending=0,
        maternity_total=quota_settings.maternity_quota,
        maternity_taken=0,
        maternity_pending=0,
        paternity_total=quota_settings.paternity_quota,
        paternity_taken=0,
        paternity_pending=0,
        lop_taken=0,
        duty_leave_taken=0,
        el_carried_forward=0,
        last_reset_date=date.today()
    )
    
    session.add(balance)
    logger.info(f"Initialized balance for teacher {teacher_id}, year {academic_year}")
    
    return balance


def initialize_all_teacher_balances(session, tenant_id, academic_year=None, force_reset=False):
    """
    Initialize leave balances for all active teachers in a school
    
    Args:
        session: Database session
        tenant_id: School tenant ID
        academic_year: Academic year string
        force_reset: If True, reset existing balances to quota values
    
    Returns:
        dict: Statistics about initialization
    """
    from teacher_models import Teacher, EmployeeStatusEnum
    from leave_models import TeacherLeaveBalance
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    # Get quota settings
    quota_settings = get_or_create_quota_settings(session, tenant_id, academic_year)
    
    # Get all active teachers
    teachers = session.query(Teacher).filter_by(
        tenant_id=tenant_id,
        employee_status=EmployeeStatusEnum.ACTIVE
    ).all()
    
    stats = {
        'total_teachers': len(teachers),
        'initialized': 0,
        'already_exists': 0,
        'reset': 0,
        'errors': 0
    }
    
    for teacher in teachers:
        try:
            existing = session.query(TeacherLeaveBalance).filter_by(
                teacher_id=teacher.id,
                academic_year=academic_year
            ).first()
            
            if existing:
                if force_reset:
                    # Reset totals to quota values, preserve taken/pending
                    existing.cl_total = quota_settings.cl_quota
                    existing.sl_total = quota_settings.sl_quota
                    existing.el_total = quota_settings.el_quota
                    existing.maternity_total = quota_settings.maternity_quota
                    existing.paternity_total = quota_settings.paternity_quota
                    existing.last_reset_date = date.today()
                    stats['reset'] += 1
                    logger.info(f"Reset balance for teacher {teacher.id}")
                else:
                    stats['already_exists'] += 1
            else:
                # Create new balance
                initialize_teacher_balance(
                    session, teacher.id, tenant_id, quota_settings, academic_year
                )
                stats['initialized'] += 1
        
        except Exception as e:
            logger.error(f"Error initializing balance for teacher {teacher.id}: {e}")
            stats['errors'] += 1
            continue
    
    try:
        session.commit()
        logger.info(f"Batch balance initialization complete: {stats}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error committing balance initialization: {e}")
        raise
    
    return stats


def update_teacher_balance(session, teacher_id, academic_year, balance_updates):
    """
    Update individual teacher's leave balance
    
    Args:
        session: Database session
        teacher_id: Teacher ID
        academic_year: Academic year string
        balance_updates: Dict with keys like 'cl_total', 'sl_total', etc.
    
    Returns:
        TeacherLeaveBalance: Updated balance object
    """
    from leave_models import TeacherLeaveBalance
    
    balance = session.query(TeacherLeaveBalance).filter_by(
        teacher_id=teacher_id,
        academic_year=academic_year
    ).first()
    
    if not balance:
        raise ValueError(f"Balance not found for teacher {teacher_id}, year {academic_year}")
    
    # Update allowed fields
    allowed_fields = [
        'cl_total', 'sl_total', 'el_total',
        'maternity_total', 'paternity_total',
        'el_carried_forward', 'notes'
    ]
    
    for field, value in balance_updates.items():
        if field in allowed_fields:
            setattr(balance, field, value)
    
    balance.updated_at = datetime.utcnow()
    session.commit()
    
    logger.info(f"Updated balance for teacher {teacher_id}: {balance_updates}")
    return balance


def get_teacher_balance(session, teacher_id, academic_year=None):
    """
    Get teacher's leave balance for specified academic year
    
    Args:
        session: Database session
        teacher_id: Teacher ID
        academic_year: Academic year string (defaults to current)
    
    Returns:
        TeacherLeaveBalance or None
    """
    from leave_models import TeacherLeaveBalance
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    return session.query(TeacherLeaveBalance).filter_by(
        teacher_id=teacher_id,
        academic_year=academic_year
    ).first()


def get_all_teacher_balances(session, tenant_id, academic_year=None):
    """
    Get all teacher leave balances for a school
    
    Args:
        session: Database session
        tenant_id: School tenant ID
        academic_year: Academic year string
    
    Returns:
        List of TeacherLeaveBalance objects
    """
    from leave_models import TeacherLeaveBalance
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    return session.query(TeacherLeaveBalance).filter_by(
        tenant_id=tenant_id,
        academic_year=academic_year
    ).all()


def calculate_leave_days(start_date, end_date, is_half_day=False, count_weekends=False):
    """
    Calculate number of leave days between start and end date
    
    Args:
        start_date: Start date (date object)
        end_date: End date (date object)
        is_half_day: Whether it's a half-day leave
        count_weekends: Whether to count weekends
    
    Returns:
        float: Number of days (0.5 for half-day)
    """
    if is_half_day:
        return 0.5
    
    if start_date > end_date:
        raise ValueError("Start date cannot be after end date")
    
    days = (end_date - start_date).days + 1
    
    if not count_weekends:
        # Count only weekdays
        total_days = 0
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # Monday = 0, Friday = 4
                total_days += 1
            current += relativedelta(days=1)
        return float(total_days)
    
    return float(days)


def validate_leave_dates(start_date, end_date, is_half_day=False, min_advance_days=1):
    """
    Validate leave application dates
    
    Args:
        start_date: Start date
        end_date: End date
        is_half_day: Whether it's half-day
        min_advance_days: Minimum advance notice required
    
    Returns:
        tuple: (is_valid, error_message)
    """
    today = date.today()
    
    # Check if dates are in the past
    if start_date < today:
        return (False, "Leave cannot be applied for past dates")
    
    # Check advance notice
    days_ahead = (start_date - today).days
    if days_ahead < min_advance_days:
        return (False, f"Minimum {min_advance_days} day(s) advance notice required")
    
    # Check end date is not before start date
    if end_date < start_date:
        return (False, "End date cannot be before start date")
    
    # For half-day, start and end should be same
    if is_half_day and start_date != end_date:
        return (False, "Half-day leave must have same start and end date")
    
    return (True, None)


def check_balance_availability(session, teacher_id, leave_type, total_days, academic_year=None):
    """
    Check if teacher has sufficient balance for leave type
    
    Args:
        session: Database session
        teacher_id: Teacher ID
        leave_type: Leave type string (CL, SL, EL, etc.)
        total_days: Number of days requested
        academic_year: Academic year
    
    Returns:
        tuple: (has_balance, available_balance, message)
    """
    from leave_models import TeacherLeaveBalance
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    # LOP and Duty Leave don't need balance check
    if leave_type in ['LOP', 'Duty Leave']:
        return (True, None, "No quota limit for this leave type")
    
    balance = session.query(TeacherLeaveBalance).filter_by(
        teacher_id=teacher_id,
        academic_year=academic_year
    ).first()
    
    if not balance:
        return (False, 0, "Leave balance not initialized. Contact admin.")
    
    # Check balance based on leave type
    balance_map = {
        'CL': balance.cl_balance,
        'SL': balance.sl_balance,
        'EL': balance.el_balance,
        'Half-day': balance.cl_balance,  # Half-day uses CL balance
        'Maternity': balance.maternity_balance,
        'Paternity': balance.paternity_balance
    }
    
    available = balance_map.get(leave_type, 0)
    
    if available < total_days:
        return (False, available, f"Insufficient balance. Available: {available} days")
    
    return (True, available, f"Sufficient balance. Available: {available} days")


def apply_leave(session, teacher_id, tenant_id, leave_data, academic_year=None):
    """
    Submit a leave application
    
    Args:
        session: Database session
        teacher_id: Teacher ID
        tenant_id: School tenant ID
        leave_data: Dict with keys: leave_type, start_date, end_date, reason, etc.
        academic_year: Academic year
    
    Returns:
        tuple: (success, leave_application_or_error_message)
    """
    from leave_models import TeacherLeaveApplication, LeaveTypeEnum, HalfDayPeriodEnum
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    try:
        # Parse dates
        start_date = leave_data['start_date']
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        end_date = leave_data['end_date']
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        is_half_day = leave_data.get('is_half_day', False)
        leave_type = leave_data['leave_type']
        
        # Get quota settings for validation
        quota_settings = get_or_create_quota_settings(session, tenant_id, academic_year)
        
        # Validate dates
        is_valid, error_msg = validate_leave_dates(
            start_date, end_date, is_half_day, quota_settings.min_advance_days
        )
        if not is_valid:
            return (False, error_msg)
        
        # Calculate total days
        total_days = calculate_leave_days(
            start_date, end_date, is_half_day, quota_settings.weekend_counted
        )
        
        # Check max continuous days
        if total_days > quota_settings.max_continuous_days:
            return (False, f"Maximum {quota_settings.max_continuous_days} continuous days allowed")
        
        # Check balance availability (except for LOP and Duty Leave)
        has_balance, available, balance_msg = check_balance_availability(
            session, teacher_id, leave_type, total_days, academic_year
        )
        if not has_balance:
            return (False, balance_msg)
        
        # Create leave application
        half_day_period = None
        if is_half_day and 'half_day_period' in leave_data:
            period_str = leave_data['half_day_period']
            half_day_period = HalfDayPeriodEnum.FIRST_HALF if period_str == 'First Half' else HalfDayPeriodEnum.SECOND_HALF
        
        leave_app = TeacherLeaveApplication(
            tenant_id=tenant_id,
            teacher_id=teacher_id,
            leave_type=LeaveTypeEnum(leave_type),
            start_date=start_date,
            end_date=end_date,
            is_half_day=is_half_day,
            half_day_period=half_day_period,
            total_days=total_days,
            reason=leave_data['reason'],
            contact_during_leave=leave_data.get('contact_during_leave'),
            address_during_leave=leave_data.get('address_during_leave'),
            academic_year=academic_year
        )
        
        session.add(leave_app)
        
        # Update pending balance
        from leave_models import TeacherLeaveBalance
        balance = session.query(TeacherLeaveBalance).filter_by(
            teacher_id=teacher_id,
            academic_year=academic_year
        ).first()
        
        if balance and leave_type not in ['LOP', 'Duty Leave']:
            # Convert to Decimal before updating DECIMAL columns to avoid Decimal+float errors
            td = Decimal(str(total_days))
            if leave_type == 'CL' or leave_type == 'Half-day':
                current = balance.cl_pending if balance.cl_pending is not None else Decimal('0')
                balance.cl_pending = current + td
            elif leave_type == 'SL':
                current = balance.sl_pending if balance.sl_pending is not None else Decimal('0')
                balance.sl_pending = current + td
            elif leave_type == 'EL':
                current = balance.el_pending if balance.el_pending is not None else Decimal('0')
                balance.el_pending = current + td
            elif leave_type == 'Maternity':
                current = balance.maternity_pending if balance.maternity_pending is not None else Decimal('0')
                balance.maternity_pending = current + td
            elif leave_type == 'Paternity':
                current = balance.paternity_pending if balance.paternity_pending is not None else Decimal('0')
                balance.paternity_pending = current + td
        
        session.commit()
        logger.info(f"Leave applied successfully: teacher_id={teacher_id}, type={leave_type}, days={total_days}")
        
        return (True, leave_app)
    
    except Exception as e:
        session.rollback()
        logger.error(f"Error applying leave: {e}")
        import traceback
        traceback.print_exc()
        return (False, f"Error applying leave: {str(e)}")


def cancel_leave_application(session, leave_id, teacher_id):
    """
    Cancel a pending leave application
    
    Args:
        session: Database session
        leave_id: Leave application ID
        teacher_id: Teacher ID (for security check)
    
    Returns:
        tuple: (success, message)
    """
    from leave_models import TeacherLeaveApplication, LeaveStatusEnum, TeacherLeaveBalance
    
    leave_app = session.query(TeacherLeaveApplication).filter_by(
        id=leave_id,
        teacher_id=teacher_id
    ).first()
    
    if not leave_app:
        return (False, "Leave application not found")
    
    if leave_app.status != LeaveStatusEnum.PENDING:
        return (False, "Only pending applications can be cancelled")
    
    try:
        # Update status
        leave_app.status = LeaveStatusEnum.CANCELLED
        leave_app.updated_at = datetime.utcnow()
        
        # Restore pending balance
        leave_type = leave_app.leave_type.value
        # Use Decimal for arithmetic with DECIMAL columns
        total_days = Decimal(str(float(leave_app.total_days)))

        if leave_type not in ['LOP', 'Duty Leave']:
            balance = session.query(TeacherLeaveBalance).filter_by(
                teacher_id=teacher_id,
                academic_year=leave_app.academic_year
            ).first()

            if balance:
                if leave_type == 'CL' or leave_type == 'Half-day':
                    current = balance.cl_pending if balance.cl_pending is not None else Decimal('0')
                    balance.cl_pending = current - total_days
                elif leave_type == 'SL':
                    current = balance.sl_pending if balance.sl_pending is not None else Decimal('0')
                    balance.sl_pending = current - total_days
                elif leave_type == 'EL':
                    current = balance.el_pending if balance.el_pending is not None else Decimal('0')
                    balance.el_pending = current - total_days
                elif leave_type == 'Maternity':
                    current = balance.maternity_pending if balance.maternity_pending is not None else Decimal('0')
                    balance.maternity_pending = current - total_days
                elif leave_type == 'Paternity':
                    current = balance.paternity_pending if balance.paternity_pending is not None else Decimal('0')
                    balance.paternity_pending = current - total_days
        
        session.commit()
        logger.info(f"Leave cancelled: leave_id={leave_id}")
        return (True, "Leave application cancelled successfully")
    
    except Exception as e:
        session.rollback()
        logger.error(f"Error cancelling leave: {e}")
        return (False, f"Error cancelling leave: {str(e)}")


def approve_leave_application(session, leave_id, admin_user_id, admin_notes=None):
    """
    Approve a leave application
    
    Args:
        session: Database session
        leave_id: Leave application ID
        admin_user_id: Admin user ID who is approving
        admin_notes: Optional admin notes
    
    Returns:
        tuple: (success, message)
    """
    from leave_models import TeacherLeaveApplication, LeaveStatusEnum, TeacherLeaveBalance
    
    leave_app = session.query(TeacherLeaveApplication).get(leave_id)
    
    if not leave_app:
        return (False, "Leave application not found")
    
    if leave_app.status != LeaveStatusEnum.PENDING:
        return (False, f"Leave is already {leave_app.status.value}")
    
    try:
        # Update application status
        leave_app.status = LeaveStatusEnum.APPROVED
        leave_app.approved_by = admin_user_id
        leave_app.approved_date = datetime.utcnow()
        leave_app.admin_notes = admin_notes
        leave_app.updated_at = datetime.utcnow()
        
        # Update balance: move from pending to taken
        leave_type = leave_app.leave_type.value
        # Use Decimal for arithmetic with DECIMAL columns
        total_days = Decimal(str(float(leave_app.total_days)))

        balance = session.query(TeacherLeaveBalance).filter_by(
            teacher_id=leave_app.teacher_id,
            academic_year=leave_app.academic_year
        ).first()

        if balance:
            if leave_type == 'CL' or leave_type == 'Half-day':
                current_pending = balance.cl_pending if balance.cl_pending is not None else Decimal('0')
                current_taken = balance.cl_taken if balance.cl_taken is not None else Decimal('0')
                balance.cl_pending = current_pending - total_days
                balance.cl_taken = current_taken + total_days
            elif leave_type == 'SL':
                current_pending = balance.sl_pending if balance.sl_pending is not None else Decimal('0')
                current_taken = balance.sl_taken if balance.sl_taken is not None else Decimal('0')
                balance.sl_pending = current_pending - total_days
                balance.sl_taken = current_taken + total_days
            elif leave_type == 'EL':
                current_pending = balance.el_pending if balance.el_pending is not None else Decimal('0')
                current_taken = balance.el_taken if balance.el_taken is not None else Decimal('0')
                balance.el_pending = current_pending - total_days
                balance.el_taken = current_taken + total_days
            elif leave_type == 'Maternity':
                current_pending = balance.maternity_pending if balance.maternity_pending is not None else Decimal('0')
                current_taken = balance.maternity_taken if balance.maternity_taken is not None else Decimal('0')
                balance.maternity_pending = current_pending - total_days
                balance.maternity_taken = current_taken + total_days
            elif leave_type == 'Paternity':
                current_pending = balance.paternity_pending if balance.paternity_pending is not None else Decimal('0')
                current_taken = balance.paternity_taken if balance.paternity_taken is not None else Decimal('0')
                balance.paternity_pending = current_pending - total_days
                balance.paternity_taken = current_taken + total_days
            elif leave_type == 'LOP':
                current = balance.lop_taken if balance.lop_taken is not None else Decimal('0')
                balance.lop_taken = current + total_days
            elif leave_type == 'Duty Leave':
                current = balance.duty_leave_taken if balance.duty_leave_taken is not None else Decimal('0')
                balance.duty_leave_taken = current + total_days
        
        session.commit()
        logger.info(f"Leave approved: leave_id={leave_id} by admin={admin_user_id}")
        return (True, "Leave approved successfully")
    
    except Exception as e:
        session.rollback()
        logger.error(f"Error approving leave: {e}")
        return (False, f"Error approving leave: {str(e)}")


def reject_leave_application(session, leave_id, admin_user_id, rejection_reason):
    """
    Reject a leave application
    
    Args:
        session: Database session
        leave_id: Leave application ID
        admin_user_id: Admin user ID who is rejecting
        rejection_reason: Reason for rejection
    
    Returns:
        tuple: (success, message)
    """
    from leave_models import TeacherLeaveApplication, LeaveStatusEnum, TeacherLeaveBalance
    
    leave_app = session.query(TeacherLeaveApplication).get(leave_id)
    
    if not leave_app:
        return (False, "Leave application not found")
    
    if leave_app.status != LeaveStatusEnum.PENDING:
        return (False, f"Leave is already {leave_app.status.value}")
    
    try:
        # Update application status
        leave_app.status = LeaveStatusEnum.REJECTED
        leave_app.approved_by = admin_user_id
        leave_app.approved_date = datetime.utcnow()
        leave_app.rejection_reason = rejection_reason
        leave_app.updated_at = datetime.utcnow()
        
        # Restore pending balance
        leave_type = leave_app.leave_type.value
        # Use Decimal for arithmetic with DECIMAL columns
        total_days = Decimal(str(float(leave_app.total_days)))

        if leave_type not in ['LOP', 'Duty Leave']:
            balance = session.query(TeacherLeaveBalance).filter_by(
                teacher_id=leave_app.teacher_id,
                academic_year=leave_app.academic_year
            ).first()

            if balance:
                if leave_type == 'CL' or leave_type == 'Half-day':
                    current = balance.cl_pending if balance.cl_pending is not None else Decimal('0')
                    balance.cl_pending = current - total_days
                elif leave_type == 'SL':
                    current = balance.sl_pending if balance.sl_pending is not None else Decimal('0')
                    balance.sl_pending = current - total_days
                elif leave_type == 'EL':
                    current = balance.el_pending if balance.el_pending is not None else Decimal('0')
                    balance.el_pending = current - total_days
                elif leave_type == 'Maternity':
                    current = balance.maternity_pending if balance.maternity_pending is not None else Decimal('0')
                    balance.maternity_pending = current - total_days
                elif leave_type == 'Paternity':
                    current = balance.paternity_pending if balance.paternity_pending is not None else Decimal('0')
                    balance.paternity_pending = current - total_days
        
        session.commit()
        logger.info(f"Leave rejected: leave_id={leave_id} by admin={admin_user_id}")
        return (True, "Leave rejected successfully")
    
    except Exception as e:
        session.rollback()
        logger.error(f"Error rejecting leave: {e}")
        return (False, f"Error rejecting leave: {str(e)}")
