"""
Helper functions for Teacher Attendance Management
Provides reusable functions for attendance operations across school admin and teacher portals
"""

from teacher_models import TeacherAttendance, AttendanceStatusEnum, Teacher
from sqlalchemy import extract, func, and_
from datetime import date, datetime, timedelta
from decimal import Decimal


def calculate_attendance_stats(db_session, teacher_id, month, year):
    """
    Calculate monthly attendance statistics for a teacher
    
    Args:
        db_session: SQLAlchemy session
        teacher_id: Teacher ID
        month: Month number (1-12)
        year: Year
        
    Returns:
        dict: Attendance statistics
    """
    # Get all records for the specified month
    records = db_session.query(TeacherAttendance).filter(
        TeacherAttendance.teacher_id == teacher_id,
        extract('month', TeacherAttendance.attendance_date) == month,
        extract('year', TeacherAttendance.attendance_date) == year
    ).all()
    
    if not records:
        return {
            'total_days': 0,
            'present_count': 0,
            'half_day_count': 0,
            'absent_count': 0,
            'on_leave_count': 0,
            'holiday_count': 0,
            'percentage': 0.0
        }
    
    # Count by status
    present = sum(1 for r in records if r.status == AttendanceStatusEnum.PRESENT)
    half_day = sum(1 for r in records if r.status == AttendanceStatusEnum.HALF_DAY)
    absent = sum(1 for r in records if r.status == AttendanceStatusEnum.ABSENT)
    on_leave = sum(1 for r in records if r.status == AttendanceStatusEnum.ON_LEAVE)
    holiday = sum(1 for r in records if r.status == AttendanceStatusEnum.HOLIDAY)
    week_off = sum(1 for r in records if r.status == AttendanceStatusEnum.WEEK_OFF)
    
    # Calculate total working days (exclude holidays and week-offs)
    total_working = sum(1 for r in records 
                       if r.status not in [AttendanceStatusEnum.HOLIDAY, 
                                          AttendanceStatusEnum.WEEK_OFF])
    
    # Calculate present days (full days + half of half-days)
    present_days = present + (half_day * 0.5)
    
    # Calculate percentage
    percentage = (present_days / total_working * 100) if total_working > 0 else 0
    
    return {
        'total_days': total_working,
        'present_count': present,
        'half_day_count': half_day,
        'absent_count': absent,
        'on_leave_count': on_leave,
        'holiday_count': holiday,
        'week_off_count': week_off,
        'percentage': round(percentage, 2)
    }


def mark_attendance(db_session, teacher_id, tenant_id, attendance_date, 
                   status, check_in=None, check_out=None, remarks=None, marked_by=None):
    """
    Mark or update attendance for a teacher
    
    Args:
        db_session: SQLAlchemy session
        teacher_id: Teacher ID
        tenant_id: Tenant ID
        attendance_date: Date object
        status: AttendanceStatusEnum value
        check_in: Check-in time (optional)
        check_out: Check-out time (optional)
        remarks: Additional notes (optional)
        marked_by: User ID who marked attendance (optional)
        
    Returns:
        tuple: (success: bool, message: str, record: TeacherAttendance or None)
    """
    try:
        # Validate date (cannot mark attendance for future dates)
        if attendance_date > date.today():
            return (False, "Cannot mark attendance for future dates", None)
        
        # Check for existing record
        existing = db_session.query(TeacherAttendance).filter_by(
            teacher_id=teacher_id,
            attendance_date=attendance_date
        ).first()
        
        # Calculate working hours if both times provided
        working_hours = None
        if check_in and check_out:
            # Convert to datetime for calculation
            checkin_dt = datetime.combine(attendance_date, check_in)
            checkout_dt = datetime.combine(attendance_date, check_out)
            
            # Handle overnight shifts
            if checkout_dt < checkin_dt:
                checkout_dt += timedelta(days=1)
            
            hours_diff = (checkout_dt - checkin_dt).total_seconds() / 3600
            working_hours = Decimal(str(round(hours_diff, 2)))
        
        if existing:
            # Update existing record
            existing.status = status
            existing.check_in_time = check_in
            existing.check_out_time = check_out
            existing.working_hours = working_hours
            existing.remarks = remarks
            existing.marked_by = marked_by
            existing.updated_at = datetime.utcnow()
            
            db_session.commit()
            return (True, "Attendance updated successfully", existing)
        else:
            # Create new record
            new_record = TeacherAttendance(
                tenant_id=tenant_id,
                teacher_id=teacher_id,
                attendance_date=attendance_date,
                status=status,
                check_in_time=check_in,
                check_out_time=check_out,
                working_hours=working_hours,
                remarks=remarks,
                marked_by=marked_by
            )
            db_session.add(new_record)
            db_session.commit()
            
            return (True, "Attendance marked successfully", new_record)
            
    except Exception as e:
        db_session.rollback()
        return (False, f"Error marking attendance: {str(e)}", None)


def bulk_mark_attendance(db_session, attendance_records, tenant_id, marked_by=None):
    """
    Mark attendance for multiple teachers at once
    
    Args:
        db_session: SQLAlchemy session
        attendance_records: List of dicts with keys: teacher_id, attendance_date, status, check_in, check_out, remarks
        tenant_id: Tenant ID
        marked_by: User ID who marked attendance
        
    Returns:
        tuple: (success_count: int, errors: list)
    """
    success_count = 0
    errors = []
    
    for record_data in attendance_records:
        try:
            teacher_id = record_data['teacher_id']
            attendance_date = record_data['attendance_date']
            status = record_data['status']
            check_in = record_data.get('check_in')
            check_out = record_data.get('check_out')
            remarks = record_data.get('remarks')
            
            success, message, _ = mark_attendance(
                db_session, teacher_id, tenant_id, attendance_date,
                status, check_in, check_out, remarks, marked_by
            )
            
            if success:
                success_count += 1
            else:
                errors.append({
                    'teacher_id': teacher_id,
                    'date': attendance_date,
                    'error': message
                })
                
        except Exception as e:
            errors.append({
                'teacher_id': record_data.get('teacher_id'),
                'error': str(e)
            })
    
    return (success_count, errors)


def get_monthly_attendance(db_session, teacher_id, month, year):
    """
    Get all attendance records for a teacher for a specific month
    
    Args:
        db_session: SQLAlchemy session
        teacher_id: Teacher ID
        month: Month number (1-12)
        year: Year
        
    Returns:
        list: List of TeacherAttendance records
    """
    records = db_session.query(TeacherAttendance).filter(
        TeacherAttendance.teacher_id == teacher_id,
        extract('month', TeacherAttendance.attendance_date) == month,
        extract('year', TeacherAttendance.attendance_date) == year
    ).order_by(TeacherAttendance.attendance_date).all()
    
    return records


def get_attendance_for_date(db_session, tenant_id, attendance_date):
    """
    Get all teachers' attendance for a specific date
    
    Args:
        db_session: SQLAlchemy session
        tenant_id: Tenant ID
        attendance_date: Date object
        
    Returns:
        dict: Mapping of teacher_id to TeacherAttendance record
    """
    records = db_session.query(TeacherAttendance).filter_by(
        tenant_id=tenant_id,
        attendance_date=attendance_date
    ).all()
    
    return {record.teacher_id: record for record in records}


def get_attendance_summary(db_session, tenant_id, start_date, end_date, 
                          teacher_id=None, department_id=None):
    """
    Generate attendance summary report with filters
    
    Args:
        db_session: SQLAlchemy session
        tenant_id: Tenant ID
        start_date: Start date for report
        end_date: End date for report
        teacher_id: Optional teacher filter
        department_id: Optional department filter
        
    Returns:
        dict: Summary statistics
    """
    # Build base query
    query = db_session.query(TeacherAttendance).filter(
        TeacherAttendance.tenant_id == tenant_id,
        TeacherAttendance.attendance_date >= start_date,
        TeacherAttendance.attendance_date <= end_date
    )
    
    # Apply filters
    if teacher_id:
        query = query.filter(TeacherAttendance.teacher_id == teacher_id)
    
    records = query.all()
    
    if not records:
        return {
            'total_records': 0,
            'present': 0,
            'absent': 0,
            'half_day': 0,
            'on_leave': 0,
            'percentage': 0.0
        }
    
    # Count by status
    present = sum(1 for r in records if r.status == AttendanceStatusEnum.PRESENT)
    half_day = sum(1 for r in records if r.status == AttendanceStatusEnum.HALF_DAY)
    absent = sum(1 for r in records if r.status == AttendanceStatusEnum.ABSENT)
    on_leave = sum(1 for r in records if r.status == AttendanceStatusEnum.ON_LEAVE)
    
    # Calculate working days
    total_working = sum(1 for r in records 
                       if r.status not in [AttendanceStatusEnum.HOLIDAY, 
                                          AttendanceStatusEnum.WEEK_OFF])
    
    present_days = present + (half_day * 0.5)
    percentage = (present_days / total_working * 100) if total_working > 0 else 0
    
    return {
        'total_records': len(records),
        'total_working_days': total_working,
        'present': present,
        'absent': absent,
        'half_day': half_day,
        'on_leave': on_leave,
        'percentage': round(percentage, 2)
    }


def get_teacher_attendance_calendar(db_session, teacher_id, month, year):
    """
    Get calendar-formatted attendance data for a teacher
    
    Args:
        db_session: SQLAlchemy session
        teacher_id: Teacher ID
        month: Month number (1-12)
        year: Year
        
    Returns:
        list: List of dicts with date, status, and CSS class
    """
    records = get_monthly_attendance(db_session, teacher_id, month, year)
    
    # Map status to CSS classes
    status_class_map = {
        AttendanceStatusEnum.PRESENT: 'present',
        AttendanceStatusEnum.ABSENT: 'absent',
        AttendanceStatusEnum.HALF_DAY: 'half-day',
        AttendanceStatusEnum.ON_LEAVE: 'on-leave',
        AttendanceStatusEnum.HOLIDAY: 'holiday',
        AttendanceStatusEnum.WEEK_OFF: 'week-off'
    }
    
    calendar_data = []
    for record in records:
        calendar_data.append({
            'attendance_date': record.attendance_date,
            'status': record.status.value,
            'status_class': status_class_map.get(record.status, ''),
            'check_in': record.check_in_time,
            'check_out': record.check_out_time,
            'working_hours': float(record.working_hours) if record.working_hours else 0,
            'remarks': record.remarks
        })
    
    return calendar_data


def check_leave_and_automark(db_session, tenant_id, attendance_date):
    """
    Check for approved leaves on given date and auto-mark attendance as "On Leave"
    
    Args:
        db_session: SQLAlchemy session
        tenant_id: Tenant ID
        attendance_date: Date to check
        
    Returns:
        int: Number of teachers marked on leave
    """
    from teacher_models import TeacherLeave, LeaveStatusEnum
    
    # Get all approved leaves that include this date
    leaves = db_session.query(TeacherLeave).filter(
        TeacherLeave.tenant_id == tenant_id,
        TeacherLeave.status == LeaveStatusEnum.APPROVED,
        TeacherLeave.from_date <= attendance_date,
        TeacherLeave.to_date >= attendance_date
    ).all()
    
    marked_count = 0
    for leave in leaves:
        # Check if attendance already marked
        existing = db_session.query(TeacherAttendance).filter_by(
            teacher_id=leave.teacher_id,
            attendance_date=attendance_date
        ).first()
        
        if not existing:
            # Auto-mark as on leave
            success, _, _ = mark_attendance(
                db_session,
                leave.teacher_id,
                tenant_id,
                attendance_date,
                AttendanceStatusEnum.ON_LEAVE,
                remarks=f"Auto-marked: {leave.leave_type.value} leave"
            )
            if success:
                marked_count += 1
    
    return marked_count
