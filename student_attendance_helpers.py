"""
Helper functions for Student Attendance Management
Provides reusable functions for attendance operations across school admin portal
"""

from models import StudentAttendance, StudentAttendanceSummary, StudentHoliday, StudentAttendanceStatusEnum, Student
from sqlalchemy import extract, func, and_, or_
from datetime import date, datetime, timedelta
from decimal import Decimal


def calculate_student_attendance_stats(db_session, student_id, month, year):
    """
    Calculate monthly attendance statistics for a student
    
    Args:
        db_session: SQLAlchemy session
        student_id: Student ID
        month: Month number (1-12)
        year: Year
        
    Returns:
        dict: Attendance statistics
    """
    # Get all records for the specified month
    records = db_session.query(StudentAttendance).filter(
        StudentAttendance.student_id == student_id,
        extract('month', StudentAttendance.attendance_date) == month,
        extract('year', StudentAttendance.attendance_date) == year
    ).all()
    
    if not records:
        return {
            'total_days': 0,
            'present_count': 0,
            'half_day_count': 0,
            'absent_count': 0,
            'on_leave_count': 0,
            'holiday_count': 0,
            'weekoff_count': 0,
            'percentage': 0.0
        }
    
    # Count by status
    present = sum(1 for r in records if r.status == StudentAttendanceStatusEnum.PRESENT)
    half_day = sum(1 for r in records if r.status == StudentAttendanceStatusEnum.HALF_DAY)
    absent = sum(1 for r in records if r.status == StudentAttendanceStatusEnum.ABSENT)
    on_leave = sum(1 for r in records if r.status == StudentAttendanceStatusEnum.ON_LEAVE)
    holiday = sum(1 for r in records if r.status == StudentAttendanceStatusEnum.HOLIDAY)
    week_off = sum(1 for r in records if r.status == StudentAttendanceStatusEnum.WEEK_OFF)
    
    # Calculate total working days (exclude holidays and week-offs)
    total_working = sum(1 for r in records 
                       if r.status not in [StudentAttendanceStatusEnum.HOLIDAY, 
                                          StudentAttendanceStatusEnum.WEEK_OFF])
    
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
        'weekoff_count': week_off,
        'percentage': round(percentage, 2)
    }


def mark_student_attendance(db_session, student_id, class_id, tenant_id, attendance_date, 
                           status, check_in=None, check_out=None, remarks=None, marked_by=None):
    """
    Mark or update attendance for a student
    
    Args:
        db_session: SQLAlchemy session
        student_id: Student ID
        class_id: Class ID
        tenant_id: Tenant ID
        attendance_date: Date object
        status: StudentAttendanceStatusEnum value
        check_in: Check-in datetime (optional)
        check_out: Check-out datetime (optional)
        remarks: Additional notes (optional)
        marked_by: User ID who marked attendance (optional)
        
    Returns:
        tuple: (success: bool, message: str, record: StudentAttendance or None)
    """
    try:
        # Validate date (cannot mark attendance for future dates)
        if attendance_date > date.today():
            return (False, "Cannot mark attendance for future dates", None)
        
        # Check for existing record
        existing = db_session.query(StudentAttendance).filter_by(
            student_id=student_id,
            attendance_date=attendance_date
        ).first()
        
        if existing:
            # Update existing record
            existing.status = status
            existing.check_in_time = check_in
            existing.check_out_time = check_out
            existing.remarks = remarks
            existing.marked_by = marked_by
            existing.updated_at = datetime.utcnow()
            
            db_session.commit()
            
            # Update summary
            update_student_attendance_summary(db_session, student_id, class_id, tenant_id,
                                            attendance_date.month, attendance_date.year)
            
            return (True, "Attendance updated successfully", existing)
        else:
            # Create new record
            new_record = StudentAttendance(
                tenant_id=tenant_id,
                student_id=student_id,
                class_id=class_id,
                attendance_date=attendance_date,
                status=status,
                check_in_time=check_in,
                check_out_time=check_out,
                remarks=remarks,
                marked_by=marked_by
            )
            db_session.add(new_record)
            db_session.commit()
            
            # Update summary
            update_student_attendance_summary(db_session, student_id, class_id, tenant_id,
                                            attendance_date.month, attendance_date.year)
            
            return (True, "Attendance marked successfully", new_record)
            
    except Exception as e:
        db_session.rollback()
        return (False, f"Error marking attendance: {str(e)}", None)


def get_student_attendance_for_date(db_session, tenant_id, class_id, attendance_date):
    """
    Get attendance records for all students in a class for a specific date
    
    Args:
        db_session: SQLAlchemy session
        tenant_id: Tenant ID
        class_id: Class ID (optional, if None returns all students)
        attendance_date: Date object
        
    Returns:
        dict: {student_id: StudentAttendance record}
    """
    query = db_session.query(StudentAttendance).filter(
        StudentAttendance.tenant_id == tenant_id,
        StudentAttendance.attendance_date == attendance_date
    )
    
    if class_id:
        query = query.filter(StudentAttendance.class_id == class_id)
    
    records = query.all()
    
    return {record.student_id: record for record in records}


def check_holidays_and_automark(db_session, tenant_id, class_id, attendance_date):
    """
    Check if a date is a holiday and auto-mark students if needed
    
    Args:
        db_session: SQLAlchemy session
        tenant_id: Tenant ID
        class_id: Class ID (optional)
        attendance_date: Date object
        
    Returns:
        bool: True if it's a holiday
    """
    # Check for holidays (class-specific or school-wide) that include this date
    holiday = db_session.query(StudentHoliday).filter(
        StudentHoliday.tenant_id == tenant_id,
        or_(
            StudentHoliday.class_id == class_id,
            StudentHoliday.class_id.is_(None)  # School-wide holiday
        ),
        StudentHoliday.start_date <= attendance_date,
        StudentHoliday.end_date >= attendance_date
    ).first()
    
    return holiday is not None


def update_student_attendance_summary(db_session, student_id, class_id, tenant_id, month, year):
    """
    Recalculate and update monthly summary for a student
    
    Args:
        db_session: SQLAlchemy session
        student_id: Student ID
        class_id: Class ID
        tenant_id: Tenant ID
        month: Month (1-12)
        year: Year
    """
    try:
        # Calculate stats
        stats = calculate_student_attendance_stats(db_session, student_id, month, year)
        
        # Check if summary exists
        summary = db_session.query(StudentAttendanceSummary).filter_by(
            student_id=student_id,
            month=month,
            year=year
        ).first()
        
        if summary:
            # Update existing
            summary.total_working_days = stats['total_days']
            summary.present_days = Decimal(str(stats['present_count'] + stats['half_day_count'] * 0.5))
            summary.absent_days = stats['absent_count']
            summary.half_days = stats['half_day_count']
            summary.leave_days = stats['on_leave_count']
            summary.holiday_days = stats['holiday_count']
            summary.weekoff_days = stats['weekoff_count']
            summary.attendance_percentage = Decimal(str(stats['percentage']))
            summary.updated_at = datetime.utcnow()
        else:
            # Create new
            summary = StudentAttendanceSummary(
                tenant_id=tenant_id,
                student_id=student_id,
                class_id=class_id,
                month=month,
                year=year,
                total_working_days=stats['total_days'],
                present_days=Decimal(str(stats['present_count'] + stats['half_day_count'] * 0.5)),
                absent_days=stats['absent_count'],
                half_days=stats['half_day_count'],
                leave_days=stats['on_leave_count'],
                holiday_days=stats['holiday_count'],
                weekoff_days=stats['weekoff_count'],
                attendance_percentage=Decimal(str(stats['percentage']))
            )
            db_session.add(summary)
        
        db_session.commit()
        return summary
        
    except Exception as e:
        db_session.rollback()
        print(f"Error updating summary: {e}")
        return None


def get_student_monthly_calendar(db_session, student_id, month, year):
    """
    Get attendance calendar for a student for a specific month
    
    Args:
        db_session: SQLAlchemy session
        student_id: Student ID
        month: Month (1-12)
        year: Year
        
    Returns:
        dict: {date_string: {status, check_in, check_out, remarks}}
    """
    from datetime import date as date_class
    from calendar import monthrange
    
    # Get student info for tenant_id and class_id
    student = db_session.query(Student).filter_by(id=student_id).first()
    if not student:
        return {}
    
    # Get attendance records
    records = db_session.query(StudentAttendance).filter(
        StudentAttendance.student_id == student_id,
        extract('month', StudentAttendance.attendance_date) == month,
        extract('year', StudentAttendance.attendance_date) == year
    ).all()
    
    calendar_data = {}
    for record in records:
        date_str = record.attendance_date.strftime('%Y-%m-%d')
        calendar_data[date_str] = {
            'id': record.id,
            'status': record.status.value,
            'check_in': record.check_in_time.strftime('%I:%M %p') if record.check_in_time else None,
            'check_out': record.check_out_time.strftime('%I:%M %p') if record.check_out_time else None,
            'remarks': record.remarks
        }
    
    # Get holidays for the month (class-specific and school-wide)
    first_day = date_class(year, month, 1)
    last_day = date_class(year, month, monthrange(year, month)[1])
    
    holidays = db_session.query(StudentHoliday).filter(
        StudentHoliday.tenant_id == student.tenant_id,
        or_(
            StudentHoliday.class_id == student.class_id,
            StudentHoliday.class_id.is_(None)  # School-wide holidays
        ),
        StudentHoliday.start_date <= last_day,
        StudentHoliday.end_date >= first_day
    ).all()
    
    # Add holidays to calendar (only if no attendance record exists)
    for holiday in holidays:
        # Generate all dates in the holiday range that fall in this month
        current_date = max(holiday.start_date, first_day)
        end_date = min(holiday.end_date, last_day)
        
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            # Only add holiday if no attendance record exists for this date
            if date_str not in calendar_data:
                calendar_data[date_str] = {
                    'id': None,  # No attendance record ID for holidays
                    'status': 'Holiday',
                    'check_in': None,
                    'check_out': None,
                    'remarks': holiday.description
                }
            current_date += timedelta(days=1)
    
    return calendar_data


def get_class_attendance_report(db_session, class_id, month, year):
    """
    Get attendance report for entire class
    
    Args:
        db_session: SQLAlchemy session
        class_id: Class ID
        month: Month (1-12)
        year: Year
        
    Returns:
        list: List of summaries with student info
    """
    from sqlalchemy.orm import joinedload
    
    summaries = db_session.query(StudentAttendanceSummary).options(
        joinedload(StudentAttendanceSummary.student)
    ).filter(
        StudentAttendanceSummary.class_id == class_id,
        StudentAttendanceSummary.month == month,
        StudentAttendanceSummary.year == year
    ).all()
    
    return summaries


def bulk_mark_attendance(db_session, attendance_data, tenant_id, marked_by=None):
    """
    Mark attendance for multiple students at once
    
    Args:
        db_session: SQLAlchemy session
        attendance_data: List of dicts with student_id, class_id, date, status, etc.
        tenant_id: Tenant ID
        marked_by: User ID who marked
        
    Returns:
        tuple: (success_count, error_list)
    """
    success_count = 0
    errors = []
    
    for data in attendance_data:
        try:
            success, message, _ = mark_student_attendance(
                db_session,
                student_id=data['student_id'],
                class_id=data['class_id'],
                tenant_id=tenant_id,
                attendance_date=data['attendance_date'],
                status=data['status'],
                check_in=data.get('check_in'),
                check_out=data.get('check_out'),
                remarks=data.get('remarks'),
                marked_by=marked_by
            )
            
            if success:
                success_count += 1
            else:
                errors.append(f"Student {data['student_id']}: {message}")
                
        except Exception as e:
            errors.append(f"Student {data['student_id']}: {str(e)}")
    
    return (success_count, errors)
