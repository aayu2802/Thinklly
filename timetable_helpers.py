"""
Timetable Helper Functions
Provides utility functions for timetable management, conflict detection, and schedule retrieval
"""

from datetime import datetime, date, time
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload
import logging

logger = logging.getLogger(__name__)


def get_current_academic_year():
    """Get current academic year based on date (April to March)"""
    today = date.today()
    if today.month >= 4:  # April onwards
        return f"{today.year}-{str(today.year + 1)[-2:]}"
    else:
        return f"{today.year - 1}-{str(today.year)[-2:]}"


def get_teacher_schedule(session, teacher_id, tenant_id, academic_year=None):
    """
    Get complete weekly schedule for a teacher
    Only shows time slots where the teacher has assigned classes or slots available to all classes
    
    Args:
        session: Database session
        teacher_id: Teacher ID
        tenant_id: Tenant ID
        academic_year: Academic year (defaults to current)
    
    Returns:
        Dictionary organized by day and time
    """
    from timetable_models import TimetableSchedule, TimeSlot, DayOfWeekEnum, TimeSlotClass
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    try:
        # Get all classes where this teacher teaches
        teacher_class_ids = session.query(TimetableSchedule.class_id).filter(
            TimetableSchedule.teacher_id == teacher_id,
            TimetableSchedule.tenant_id == tenant_id,
            TimetableSchedule.academic_year == academic_year,
            TimetableSchedule.is_active == True
        ).distinct().all()
        
        teacher_class_ids = [cls_id[0] for cls_id in teacher_class_ids]
        
        # Query all schedules for the teacher
        schedules = session.query(TimetableSchedule).filter(
            TimetableSchedule.teacher_id == teacher_id,
            TimetableSchedule.tenant_id == tenant_id,
            TimetableSchedule.academic_year == academic_year,
            TimetableSchedule.is_active == True
        ).options(
            joinedload(TimetableSchedule.time_slot),
            joinedload(TimetableSchedule.class_ref),
            joinedload(TimetableSchedule.subject)
        ).all()
        
        # Get all time slot IDs that are restricted to specific classes
        restricted_slot_ids = {}
        if teacher_class_ids:
            # Get slot restrictions
            slot_class_assignments = session.query(TimeSlotClass).filter(
                TimeSlotClass.tenant_id == tenant_id,
                TimeSlotClass.is_active == True
            ).all()
            
            # Build map of slot_id -> list of allowed class_ids
            for assignment in slot_class_assignments:
                if assignment.time_slot_id not in restricted_slot_ids:
                    restricted_slot_ids[assignment.time_slot_id] = []
                restricted_slot_ids[assignment.time_slot_id].append(assignment.class_id)
        
        # Organize by day
        weekly_schedule = {}
        for day in DayOfWeekEnum:
            weekly_schedule[day.value] = []
        
        for schedule in schedules:
            if schedule.time_slot and schedule.day_of_week:
                # Check if this time slot is restricted
                slot_id = schedule.time_slot.id
                
                # If slot is restricted, check if teacher's class is allowed
                if slot_id in restricted_slot_ids:
                    allowed_class_ids = restricted_slot_ids[slot_id]
                    if schedule.class_id not in allowed_class_ids:
                        # Skip this slot - teacher's class not allowed
                        continue
                
                # Slot is either unrestricted or teacher's class is allowed
                day = schedule.day_of_week.value
                weekly_schedule[day].append({
                    'time': f"{schedule.time_slot.start_time.strftime('%H:%M')}-{schedule.time_slot.end_time.strftime('%H:%M')}",
                    'start_time': schedule.time_slot.start_time.strftime('%H:%M'),
                    'end_time': schedule.time_slot.end_time.strftime('%H:%M'),
                    'class': f"{schedule.class_ref.class_name}-{schedule.class_ref.section}" if schedule.class_ref else 'N/A',
                    'subject': schedule.subject.name if schedule.subject else 'N/A',
                    'room': schedule.room_number or 'TBA',
                    'slot_order': schedule.time_slot.slot_order or 0,
                    'slot_type': schedule.time_slot.slot_type.value if schedule.time_slot.slot_type else 'Regular'
                })
        
        # Sort each day's schedule by slot_order
        for day in weekly_schedule:
            weekly_schedule[day].sort(key=lambda x: x['slot_order'])
        
        return weekly_schedule
    
    except Exception as e:
        logger.error(f"Error getting teacher schedule: {e}")
        import traceback
        traceback.print_exc()
        return {}


def get_today_schedule(session, teacher_id, tenant_id, academic_year=None):
    """
    Get today's schedule for a teacher
    Only shows time slots where the teacher has assigned classes or slots available to all classes
    
    Args:
        session: Database session
        teacher_id: Teacher ID
        tenant_id: Tenant ID
        academic_year: Academic year (defaults to current)
    
    Returns:
        List of today's classes
    """
    from timetable_models import TimetableSchedule, DayOfWeekEnum, TimeSlotClass
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    try:
        # Get current day
        today = datetime.now()
        day_name = today.strftime('%A')  # Monday, Tuesday, etc.
        
        # Map to enum
        day_enum = None
        for day in DayOfWeekEnum:
            if day.value == day_name:
                day_enum = day
                break
        
        if not day_enum:
            return []
        
        # Get all classes where this teacher teaches
        teacher_class_ids = session.query(TimetableSchedule.class_id).filter(
            TimetableSchedule.teacher_id == teacher_id,
            TimetableSchedule.tenant_id == tenant_id,
            TimetableSchedule.academic_year == academic_year,
            TimetableSchedule.is_active == True
        ).distinct().all()
        
        teacher_class_ids = [cls_id[0] for cls_id in teacher_class_ids]
        
        # Query today's schedules
        schedules = session.query(TimetableSchedule).filter(
            TimetableSchedule.teacher_id == teacher_id,
            TimetableSchedule.tenant_id == tenant_id,
            TimetableSchedule.day_of_week == day_enum,
            TimetableSchedule.academic_year == academic_year,
            TimetableSchedule.is_active == True
        ).options(
            joinedload(TimetableSchedule.time_slot),
            joinedload(TimetableSchedule.class_ref),
            joinedload(TimetableSchedule.subject)
        ).all()
        
        # Get all time slot IDs that are restricted to specific classes
        restricted_slot_ids = {}
        if teacher_class_ids:
            slot_class_assignments = session.query(TimeSlotClass).filter(
                TimeSlotClass.tenant_id == tenant_id,
                TimeSlotClass.is_active == True
            ).all()
            
            for assignment in slot_class_assignments:
                if assignment.time_slot_id not in restricted_slot_ids:
                    restricted_slot_ids[assignment.time_slot_id] = []
                restricted_slot_ids[assignment.time_slot_id].append(assignment.class_id)
        
        today_schedule = []
        for schedule in schedules:
            if schedule.time_slot and schedule.time_slot.slot_type.value == 'Regular':
                # Check if this time slot is restricted
                slot_id = schedule.time_slot.id
                
                # If slot is restricted, check if teacher's class is allowed
                if slot_id in restricted_slot_ids:
                    allowed_class_ids = restricted_slot_ids[slot_id]
                    if schedule.class_id not in allowed_class_ids:
                        # Skip this slot - teacher's class not allowed
                        continue
                
                today_schedule.append({
                    'time': f"{schedule.time_slot.start_time.strftime('%H:%M')}-{schedule.time_slot.end_time.strftime('%H:%M')}",
                    'class': f"{schedule.class_ref.class_name}-{schedule.class_ref.section}" if schedule.class_ref else 'N/A',
                    'subject': schedule.subject.name if schedule.subject else 'N/A',
                    'room': schedule.room_number or 'TBA',
                    'slot_order': schedule.time_slot.slot_order or 0
                })
        
        # Sort by time
        today_schedule.sort(key=lambda x: x['slot_order'])
        
        return today_schedule
    
    except Exception as e:
        logger.error(f"Error getting today's schedule: {e}")
        import traceback
        traceback.print_exc()
        return []


def check_scheduling_conflicts(session, tenant_id, class_id, day_of_week, time_slot_id, teacher_id=None, room_number=None, exclude_id=None, academic_year=None):
    """
    Check for scheduling conflicts
    
    Args:
        session: Database session
        tenant_id: Tenant ID
        class_id: Class ID
        day_of_week: Day of week enum
        time_slot_id: Time slot ID
        teacher_id: Teacher ID (optional)
        room_number: Room number (optional)
        exclude_id: Schedule ID to exclude (for updates)
        academic_year: Academic year (defaults to current)
    
    Returns:
        Tuple (has_conflict, conflict_messages)
    """
    from timetable_models import TimetableSchedule
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    conflicts = []
    
    try:
        # Check class conflict
        class_conflict = session.query(TimetableSchedule).filter(
            TimetableSchedule.tenant_id == tenant_id,
            TimetableSchedule.class_id == class_id,
            TimetableSchedule.day_of_week == day_of_week,
            TimetableSchedule.time_slot_id == time_slot_id,
            TimetableSchedule.academic_year == academic_year,
            TimetableSchedule.is_active == True
        )
        if exclude_id:
            class_conflict = class_conflict.filter(TimetableSchedule.id != exclude_id)
        
        if class_conflict.first():
            conflicts.append("This class already has a subject scheduled at this time")
        
        # Check teacher conflict
        if teacher_id:
            teacher_conflict = session.query(TimetableSchedule).filter(
                TimetableSchedule.tenant_id == tenant_id,
                TimetableSchedule.teacher_id == teacher_id,
                TimetableSchedule.day_of_week == day_of_week,
                TimetableSchedule.time_slot_id == time_slot_id,
                TimetableSchedule.academic_year == academic_year,
                TimetableSchedule.is_active == True
            )
            if exclude_id:
                teacher_conflict = teacher_conflict.filter(TimetableSchedule.id != exclude_id)
            
            if teacher_conflict.first():
                conflicts.append("This teacher is already assigned to another class at this time")
        
        # Check room conflict
        if room_number:
            room_conflict = session.query(TimetableSchedule).filter(
                TimetableSchedule.tenant_id == tenant_id,
                TimetableSchedule.room_number == room_number,
                TimetableSchedule.day_of_week == day_of_week,
                TimetableSchedule.time_slot_id == time_slot_id,
                TimetableSchedule.academic_year == academic_year,
                TimetableSchedule.is_active == True
            )
            if exclude_id:
                room_conflict = room_conflict.filter(TimetableSchedule.id != exclude_id)
            
            if room_conflict.first():
                conflicts.append(f"Room {room_number} is already assigned to another class at this time")
        
        return len(conflicts) > 0, conflicts
    
    except Exception as e:
        logger.error(f"Error checking conflicts: {e}")
        return True, [f"Error checking conflicts: {str(e)}"]


def get_class_schedule(session, class_id, tenant_id, academic_year=None):
    """
    Get complete weekly schedule for a class
    
    Args:
        session: Database session
        class_id: Class ID
        tenant_id: Tenant ID
        academic_year: Academic year (defaults to current)
    
    Returns:
        Dictionary organized by day and time
    """
    from timetable_models import TimetableSchedule, TimeSlot, DayOfWeekEnum
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    try:
        schedules = session.query(TimetableSchedule).filter(
            TimetableSchedule.class_id == class_id,
            TimetableSchedule.tenant_id == tenant_id,
            TimetableSchedule.academic_year == academic_year,
            TimetableSchedule.is_active == True
        ).options(
            joinedload(TimetableSchedule.time_slot),
            joinedload(TimetableSchedule.teacher),
            joinedload(TimetableSchedule.subject)
        ).all()
        
        weekly_schedule = {}
        for day in DayOfWeekEnum:
            weekly_schedule[day.value] = []
        
        for schedule in schedules:
            if schedule.time_slot and schedule.day_of_week:
                day = schedule.day_of_week.value
                weekly_schedule[day].append({
                    'id': schedule.id,
                    'time': f"{schedule.time_slot.start_time.strftime('%H:%M')}-{schedule.time_slot.end_time.strftime('%H:%M')}",
                    'teacher': f"{schedule.teacher.first_name} {schedule.teacher.last_name}" if schedule.teacher else 'N/A',
                    'subject': schedule.subject.name if schedule.subject else 'N/A',
                    'room': schedule.room_number or 'TBA',
                    'slot_type': schedule.time_slot.slot_type.value if schedule.time_slot.slot_type else 'Regular',
                    'slot_name': schedule.time_slot.slot_name or '',
                    'slot_order': schedule.time_slot.slot_order or 0
                })
        
        for day in weekly_schedule:
            weekly_schedule[day].sort(key=lambda x: x['slot_order'])
        
        return weekly_schedule
    
    except Exception as e:
        logger.error(f"Error getting class schedule: {e}")
        return {}


def get_teacher_workload(session, teacher_id, tenant_id, academic_year=None):
    """
    Calculate teacher's weekly workload (number of periods)
    
    Args:
        session: Database session
        teacher_id: Teacher ID
        tenant_id: Tenant ID
        academic_year: Academic year (defaults to current)
    
    Returns:
        Dictionary with workload statistics
    """
    from timetable_models import TimetableSchedule
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    try:
        total_periods = session.query(TimetableSchedule).filter(
            TimetableSchedule.teacher_id == teacher_id,
            TimetableSchedule.tenant_id == tenant_id,
            TimetableSchedule.academic_year == academic_year,
            TimetableSchedule.is_active == True
        ).count()
        
        return {
            'total_periods': total_periods,
            'avg_per_day': round(total_periods / 6, 2) if total_periods > 0 else 0
        }
    
    except Exception as e:
        logger.error(f"Error calculating workload: {e}")
        return {'total_periods': 0, 'avg_per_day': 0}


# ==========================================
# WORKLOAD REPORT FUNCTIONS
# ==========================================

def get_or_create_workload_settings(session, tenant_id):
    """
    Get or create workload settings for a tenant
    
    Args:
        session: Database session
        tenant_id: Tenant ID
    
    Returns:
        WorkloadSettings object
    """
    from timetable_models import WorkloadSettings
    
    try:
        settings = session.query(WorkloadSettings).filter_by(tenant_id=tenant_id).first()
        
        if not settings:
            settings = WorkloadSettings(
                tenant_id=tenant_id,
                max_periods_per_week=35,
                max_consecutive_periods=4,
                optimal_min_percent=60,
                optimal_max_percent=85
            )
            session.add(settings)
            session.commit()
            logger.info(f"Created default workload settings for tenant {tenant_id}")
        
        return settings
    
    except Exception as e:
        logger.error(f"Error getting workload settings: {e}")
        # Return default settings object without saving
        from timetable_models import WorkloadSettings
        return WorkloadSettings(
            tenant_id=tenant_id,
            max_periods_per_week=35,
            max_consecutive_periods=4,
            optimal_min_percent=60,
            optimal_max_percent=85
        )


def calculate_detailed_teacher_workload(session, teacher_id, tenant_id, settings=None, academic_year=None):
    """
    Calculate comprehensive workload metrics for a teacher
    
    Args:
        session: Database session
        teacher_id: Teacher ID
        tenant_id: Tenant ID
        settings: WorkloadSettings object (optional, will fetch if not provided)
        academic_year: Academic year (defaults to current)
    
    Returns:
        Dictionary with detailed workload data
    """
    from timetable_models import TimetableSchedule, TimeSlot, SlotTypeEnum, DayOfWeekEnum
    from teacher_models import Teacher, TeacherDepartment
    from sqlalchemy import func
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    if not settings:
        settings = get_or_create_workload_settings(session, tenant_id)
    
    try:
        # Get teacher info
        teacher = session.query(Teacher).filter_by(id=teacher_id).first()
        if not teacher:
            return None
        
        # Get teacher's department for department-specific max periods
        department_name = None
        dept_assoc = session.query(TeacherDepartment).filter_by(
            teacher_id=teacher_id, is_primary=True
        ).first()
        if dept_assoc and dept_assoc.department:
            department_name = dept_assoc.department.name
        
        max_periods = settings.get_max_periods_for_department(department_name) if department_name else settings.max_periods_per_week
        
        # Get schedules (only REGULAR slot types count as teaching)
        schedules = session.query(TimetableSchedule).join(TimeSlot).filter(
            TimetableSchedule.teacher_id == teacher_id,
            TimetableSchedule.tenant_id == tenant_id,
            TimetableSchedule.academic_year == academic_year,
            TimetableSchedule.is_active == True,
            TimeSlot.slot_type == SlotTypeEnum.REGULAR
        ).options(
            joinedload(TimetableSchedule.time_slot),
            joinedload(TimetableSchedule.class_ref),
            joinedload(TimetableSchedule.subject)
        ).all()
        
        periods_per_week = len(schedules)
        
        # Day-wise breakdown
        day_wise = {}
        for day in DayOfWeekEnum:
            day_wise[day.value] = 0
        
        # Classes and subjects
        classes_set = set()
        subjects_set = set()
        
        # For consecutive period detection
        day_slots = {}  # {day: [(slot_order, time_slot_id)]}
        
        for schedule in schedules:
            if schedule.day_of_week:
                day = schedule.day_of_week.value
                day_wise[day] = day_wise.get(day, 0) + 1
                
                # Track slots per day for consecutive detection
                if day not in day_slots:
                    day_slots[day] = []
                if schedule.time_slot:
                    day_slots[day].append(schedule.time_slot.slot_order or 0)
            
            if schedule.class_ref:
                classes_set.add(f"{schedule.class_ref.class_name}-{schedule.class_ref.section}")
            
            if schedule.subject:
                subjects_set.add(schedule.subject.name)
        
        # Calculate max consecutive periods
        max_consecutive = 0
        for day, slots in day_slots.items():
            if len(slots) > 1:
                sorted_slots = sorted(slots)
                current_consecutive = 1
                for i in range(1, len(sorted_slots)):
                    if sorted_slots[i] == sorted_slots[i-1] + 1:
                        current_consecutive += 1
                    else:
                        max_consecutive = max(max_consecutive, current_consecutive)
                        current_consecutive = 1
                max_consecutive = max(max_consecutive, current_consecutive)
        
        # Calculate free periods (REGULAR slots where teacher has no assignment)
        total_regular_slots = session.query(TimeSlot).filter(
            TimeSlot.tenant_id == tenant_id,
            TimeSlot.slot_type == SlotTypeEnum.REGULAR,
            TimeSlot.is_active == True
        ).count()
        
        free_periods = total_regular_slots - periods_per_week
        
        # Calculate workload percentage
        workload_percent = round((periods_per_week / max_periods) * 100, 1) if max_periods > 0 else 0
        
        # Determine status
        if workload_percent > 100:
            status = 'overloaded'
            status_badge = 'danger'
        elif workload_percent < settings.optimal_min_percent:
            status = 'underutilized'
            status_badge = 'info'
        elif workload_percent > settings.optimal_max_percent:
            status = 'high'
            status_badge = 'warning'
        else:
            status = 'optimal'
            status_badge = 'success'
        
        # Get workload class for progress bar
        if workload_percent > 100:
            workload_class = 'high'
        elif workload_percent > settings.optimal_max_percent:
            workload_class = 'medium'
        else:
            workload_class = 'low'
        
        return {
            'teacher_id': teacher_id,
            'teacher_name': teacher.full_name,
            'initials': ''.join([n[0].upper() for n in teacher.full_name.split()[:2]]),
            'gender': teacher.gender.value if teacher.gender else 'Male',
            'department': department_name or 'General',
            'subjects': list(subjects_set),
            'classes': list(classes_set),
            'periods_per_week': periods_per_week,
            'max_periods': max_periods,
            'workload_percent': min(workload_percent, 120),  # Cap at 120% for display
            'workload_class': workload_class,
            'day_wise': day_wise,
            'free_periods': max(0, free_periods),
            'consecutive_max': max_consecutive,
            'status': status,
            'status_badge': status_badge
        }
    
    except Exception as e:
        logger.error(f"Error calculating detailed workload for teacher {teacher_id}: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_all_teachers_workload(session, tenant_id, filters=None, academic_year=None):
    """
    Get workload data for all teachers with optional filtering
    
    Args:
        session: Database session
        tenant_id: Tenant ID
        filters: Dictionary with filter options (department, status)
        academic_year: Academic year (defaults to current)
    
    Returns:
        List of teacher workload dictionaries
    """
    from teacher_models import Teacher, EmployeeStatusEnum
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    if not filters:
        filters = {}
    
    try:
        settings = get_or_create_workload_settings(session, tenant_id)
        
        # Get all active teachers
        teachers = session.query(Teacher).filter(
            Teacher.tenant_id == tenant_id,
            Teacher.employee_status == EmployeeStatusEnum.ACTIVE
        ).all()
        
        workload_data = []
        
        for teacher in teachers:
            workload = calculate_detailed_teacher_workload(
                session, teacher.id, tenant_id, settings, academic_year
            )
            if workload:
                # Apply filters
                if filters.get('department') and filters['department'] != 'all':
                    if workload['department'] != filters['department']:
                        continue
                
                if filters.get('status') and filters['status'] != 'all':
                    if workload['status'] != filters['status']:
                        continue
                
                workload_data.append(workload)
        
        # Sort by workload percentage (highest first)
        workload_data.sort(key=lambda x: x['workload_percent'], reverse=True)
        
        return workload_data
    
    except Exception as e:
        logger.error(f"Error getting all teachers workload: {e}")
        return []


def identify_workload_issues(workload_data, settings):
    """
    Analyze workload data and return list of issues/alerts
    
    Args:
        workload_data: List of teacher workload dictionaries
        settings: WorkloadSettings object
    
    Returns:
        List of alert dictionaries
    """
    alerts = []
    
    for teacher in workload_data:
        # Check for overload
        if teacher['workload_percent'] > 100:
            excess = teacher['periods_per_week'] - teacher['max_periods']
            alerts.append({
                'type': 'overload',
                'severity': 'danger',
                'teacher_id': teacher['teacher_id'],
                'title': f"{teacher['teacher_name']} is overloaded!",
                'message': f"Has {teacher['periods_per_week']} periods/week (max: {teacher['max_periods']}). Consider redistributing {excess} periods."
            })
        
        # Check for consecutive periods
        if teacher['consecutive_max'] > settings.max_consecutive_periods:
            alerts.append({
                'type': 'consecutive',
                'severity': 'warning',
                'teacher_id': teacher['teacher_id'],
                'title': f"{teacher['teacher_name']} has {teacher['consecutive_max']} consecutive periods",
                'message': f"Exceeds recommended limit of {settings.max_consecutive_periods}. Consider adding breaks."
            })
    
    # Check for underutilized teachers
    underutilized = [t for t in workload_data if t['status'] == 'underutilized']
    if len(underutilized) > 1:
        names = [t['teacher_name'] for t in underutilized[:3]]
        alerts.append({
            'type': 'underutilized',
            'severity': 'info',
            'teacher_id': None,
            'title': f"{', '.join(names)} {'and more ' if len(underutilized) > 3 else ''}are underutilized",
            'message': f"These teachers have less than {settings.optimal_min_percent}% workload. Can take additional classes."
        })
    
    return alerts


def get_subject_distribution(session, tenant_id, academic_year=None):
    """
    Get total periods per subject
    
    Args:
        session: Database session
        tenant_id: Tenant ID
        academic_year: Academic year (defaults to current)
    
    Returns:
        List of dictionaries with subject name and period count
    """
    from timetable_models import TimetableSchedule, TimeSlot, SlotTypeEnum
    from teacher_models import Subject
    from sqlalchemy import func
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    try:
        results = session.query(
            Subject.name,
            func.count(TimetableSchedule.id).label('period_count')
        ).join(
            TimetableSchedule, TimetableSchedule.subject_id == Subject.id
        ).join(
            TimeSlot, TimetableSchedule.time_slot_id == TimeSlot.id
        ).filter(
            TimetableSchedule.tenant_id == tenant_id,
            TimetableSchedule.academic_year == academic_year,
            TimetableSchedule.is_active == True,
            TimeSlot.slot_type == SlotTypeEnum.REGULAR
        ).group_by(Subject.name).order_by(func.count(TimetableSchedule.id).desc()).all()
        
        # Color mapping for subjects
        subject_colors = {
            'Mathematics': '#3b82f6',
            'Science': '#10b981',
            'English': '#f59e0b',
            'Hindi': '#ef4444',
            'Social Studies': '#8b5cf6',
            'Computer': '#06b6d4',
            'Physical Education': '#ec4899',
            'Art': '#f97316'
        }
        
        return [
            {
                'name': result[0],
                'count': result[1],
                'color': subject_colors.get(result[0], '#6b7280')
            }
            for result in results
        ]
    
    except Exception as e:
        logger.error(f"Error getting subject distribution: {e}")
        return []


def get_class_distribution(session, tenant_id, academic_year=None):
    """
    Get total periods per class
    
    Args:
        session: Database session
        tenant_id: Tenant ID
        academic_year: Academic year (defaults to current)
    
    Returns:
        List of dictionaries with class name and period count
    """
    from timetable_models import TimetableSchedule, TimeSlot, SlotTypeEnum
    from models import Class
    from sqlalchemy import func
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    try:
        results = session.query(
            Class.class_name,
            Class.section,
            func.count(TimetableSchedule.id).label('period_count')
        ).join(
            TimetableSchedule, TimetableSchedule.class_id == Class.id
        ).join(
            TimeSlot, TimetableSchedule.time_slot_id == TimeSlot.id
        ).filter(
            TimetableSchedule.tenant_id == tenant_id,
            TimetableSchedule.academic_year == academic_year,
            TimetableSchedule.is_active == True,
            TimeSlot.slot_type == SlotTypeEnum.REGULAR
        ).group_by(Class.class_name, Class.section).order_by(Class.class_name, Class.section).all()
        
        return [
            {
                'name': f"{result[0]}-{result[1]}",
                'count': result[2]
            }
            for result in results
        ]
    
    except Exception as e:
        logger.error(f"Error getting class distribution: {e}")
        return []


def get_workload_stats(workload_data):
    """
    Calculate summary statistics from workload data
    
    Args:
        workload_data: List of teacher workload dictionaries
    
    Returns:
        Dictionary with summary stats
    """
    total_teachers = len(workload_data)
    optimal = sum(1 for t in workload_data if t['status'] == 'optimal')
    overloaded = sum(1 for t in workload_data if t['status'] == 'overloaded')
    high = sum(1 for t in workload_data if t['status'] == 'high')
    underutilized = sum(1 for t in workload_data if t['status'] == 'underutilized')
    total_periods = sum(t['periods_per_week'] for t in workload_data)
    
    return {
        'total_teachers': total_teachers,
        'optimal': optimal,
        'overloaded': overloaded + high,  # Combine overloaded and high for display
        'underutilized': underutilized,
        'total_periods': total_periods
    }


# ==========================================
# AUTO TIMETABLE GENERATION FUNCTIONS
# ==========================================

def get_class_teacher(session, class_id, tenant_id, academic_year=None):
    """
    Get the class teacher (homeroom teacher) for a class
    
    Args:
        session: Database session
        class_id: Class ID
        tenant_id: Tenant ID
        academic_year: Academic year (defaults to current)
    
    Returns:
        ClassTeacherAssignment object or None
    """
    from timetable_models import ClassTeacherAssignment
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    try:
        assignment = session.query(ClassTeacherAssignment).filter(
            ClassTeacherAssignment.tenant_id == tenant_id,
            ClassTeacherAssignment.class_id == class_id,
            ClassTeacherAssignment.is_class_teacher == True,
            ClassTeacherAssignment.removed_date.is_(None)
        ).first()
        
        return assignment
    except Exception as e:
        logger.error(f"Error getting class teacher: {e}")
        return None


def get_class_available_slots(session, class_id, tenant_id):
    """
    Get all available time slots for a class, considering slot restrictions
    
    Args:
        session: Database session
        class_id: Class ID
        tenant_id: Tenant ID
    
    Returns:
        List of TimeSlot objects organized by day
    """
    from timetable_models import TimeSlot, TimeSlotClass, DayOfWeekEnum, SlotTypeEnum
    
    try:
        # Get all active time slots for the tenant
        all_slots = session.query(TimeSlot).filter(
            TimeSlot.tenant_id == tenant_id,
            TimeSlot.is_active == True
        ).all()
        
        available_slots = []
        
        for slot in all_slots:
            # Check if slot has class restrictions
            restrictions = session.query(TimeSlotClass).filter(
                TimeSlotClass.time_slot_id == slot.id
            ).count()
            
            if restrictions == 0:
                # No restrictions - available to all classes
                available_slots.append(slot)
            else:
                # Has restrictions - check if this class is included
                is_assigned = session.query(TimeSlotClass).filter(
                    TimeSlotClass.time_slot_id == slot.id,
                    TimeSlotClass.class_id == class_id
                ).first()
                if is_assigned:
                    available_slots.append(slot)
        
        # Sort by day, then slot_order, then start_time
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        available_slots.sort(key=lambda x: (
            day_order.index(x.day_of_week.value) if x.day_of_week.value in day_order else 7,
            x.slot_order or 0,
            x.start_time
        ))
        
        return available_slots
        
    except Exception as e:
        logger.error(f"Error getting class available slots: {e}")
        import traceback
        traceback.print_exc()
        return []


def check_teacher_slot_conflict(session, teacher_id, day_of_week, time_slot_id, tenant_id, academic_year=None):
    """
    Check if a teacher is already scheduled at a given time slot
    
    Args:
        session: Database session
        teacher_id: Teacher ID
        day_of_week: DayOfWeekEnum value
        time_slot_id: Time slot ID
        tenant_id: Tenant ID
        academic_year: Academic year (defaults to current)
    
    Returns:
        True if conflict exists, False otherwise
    """
    from timetable_models import TimetableSchedule
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    try:
        conflict = session.query(TimetableSchedule).filter(
            TimetableSchedule.tenant_id == tenant_id,
            TimetableSchedule.teacher_id == teacher_id,
            TimetableSchedule.day_of_week == day_of_week,
            TimetableSchedule.time_slot_id == time_slot_id,
            TimetableSchedule.academic_year == academic_year,
            TimetableSchedule.is_active == True
        ).first()
        
        return conflict is not None
    except Exception as e:
        logger.error(f"Error checking teacher slot conflict: {e}")
        return True  # Assume conflict on error to be safe


def auto_generate_timetable(session, class_id, tenant_id, period_config, class_teacher_first_slot=False, academic_year=None):
    """
    Auto-generate timetable for a class
    
    Args:
        session: Database session
        class_id: Class ID
        tenant_id: Tenant ID
        period_config: Dict mapping teacher_id -> {subject_id: periods_per_week}
                      Example: {1: {10: 5, 11: 3}, 2: {12: 4}}
        class_teacher_first_slot: If True, assign class teacher to slot 1 of each day
        academic_year: Academic year (defaults to current)
    
    Returns:
        Dictionary with:
        - success: bool
        - schedules: List of proposed schedule dicts (not saved to DB)
        - warnings: List of warning messages
        - errors: List of error messages
    """
    from timetable_models import TimeSlot, SlotTypeEnum, DayOfWeekEnum
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    result = {
        'success': False,
        'schedules': [],
        'warnings': [],
        'errors': []
    }
    
    try:
        # Get all available time slots for this class
        available_slots = get_class_available_slots(session, class_id, tenant_id)
        
        if not available_slots:
            result['errors'].append("No time slots available for this class")
            return result
        
        # Filter to only REGULAR slots (not breaks, lunch, etc.)
        regular_slots = [s for s in available_slots if s.slot_type == SlotTypeEnum.REGULAR]
        
        if not regular_slots:
            result['errors'].append("No regular teaching periods available for this class")
            return result
        
        # Build requirements list: [(teacher_id, subject_id, remaining_periods, room), ...]
        requirements = []
        for teacher_id, subjects in period_config.items():
            for subject_id, config in subjects.items():
                # Handle both old format (just periods int) and new format (dict with periods and room)
                if isinstance(config, dict):
                    periods = config.get('periods', 0)
                    room = config.get('room', '')
                else:
                    periods = int(config)
                    room = ''
                    
                if periods > 0:
                    requirements.append({
                        'teacher_id': int(teacher_id),
                        'subject_id': int(subject_id),
                        'remaining': int(periods),
                        'room': room,
                        'assigned_days': []  # Track which days already have this subject
                    })
        
        if not requirements:
            result['errors'].append("No period requirements specified")
            return result
        
        # Calculate total periods needed vs available
        total_required = sum(r['remaining'] for r in requirements)
        total_available = len(regular_slots)
        
        if total_required > total_available:
            result['warnings'].append(
                f"Warning: Requested {total_required} periods but only {total_available} slots available. "
                f"Some subjects may not be fully scheduled."
            )
        
        # Organize slots by day
        slots_by_day = {}
        for slot in regular_slots:
            day = slot.day_of_week.value
            if day not in slots_by_day:
                slots_by_day[day] = []
            slots_by_day[day].append(slot)
        
        # Sort slots within each day by slot_order
        for day in slots_by_day:
            slots_by_day[day].sort(key=lambda x: (x.slot_order or 0, x.start_time))
        
        # Track scheduled slots
        scheduled = []  # List of generated schedule dicts
        used_slots = set()  # Set of (day, time_slot_id) tuples
        
        # Handle class teacher first slot if enabled
        if class_teacher_first_slot:
            class_teacher = get_class_teacher(session, class_id, tenant_id, academic_year)
            if class_teacher:
                # Find the class teacher's subject
                ct_requirement = None
                for req in requirements:
                    if req['teacher_id'] == class_teacher.teacher_id:
                        ct_requirement = req
                        break
                
                if ct_requirement:
                    # Assign first slot of each day to class teacher
                    for day, day_slots in slots_by_day.items():
                        if day_slots and ct_requirement['remaining'] > 0:
                            first_slot = day_slots[0]
                            
                            # Check if class teacher has conflict
                            has_conflict = check_teacher_slot_conflict(
                                session, ct_requirement['teacher_id'],
                                first_slot.day_of_week, first_slot.id,
                                tenant_id, academic_year
                            )
                            
                            if not has_conflict:
                                scheduled.append({
                                    'class_id': class_id,
                                    'time_slot_id': first_slot.id,
                                    'day_of_week': first_slot.day_of_week.value,
                                    'teacher_id': ct_requirement['teacher_id'],
                                    'subject_id': ct_requirement['subject_id'],
                                    'room_number': ct_requirement.get('room', ''),
                                    'academic_year': academic_year,
                                    'slot_info': {
                                        'start_time': first_slot.start_time.strftime('%H:%M'),
                                        'end_time': first_slot.end_time.strftime('%H:%M'),
                                        'slot_name': first_slot.slot_name or f"Period {first_slot.slot_order or 1}",
                                        'slot_order': first_slot.slot_order or 1
                                    }
                                })
                                used_slots.add((day, first_slot.id))
                                ct_requirement['remaining'] -= 1
                                ct_requirement['assigned_days'].append(day)
                else:
                    result['warnings'].append(
                        "Class teacher first slot enabled but class teacher not found in assignments"
                    )
        
        # Shuffle requirements first for variety on regeneration, then sort by remaining
        import random
        random.shuffle(requirements)
        
        # Sort requirements by remaining periods (highest first) for better distribution
        # Using stable sort so shuffled order is preserved for equal values
        requirements.sort(key=lambda x: x['remaining'], reverse=True)
        
        # Fill remaining slots
        for day, day_slots in slots_by_day.items():
            for slot in day_slots:
                if (day, slot.id) in used_slots:
                    continue  # Already scheduled
                
                # Find best teacher/subject for this slot
                best_req = None
                best_score = -1
                
                for req in requirements:
                    if req['remaining'] <= 0:
                        continue
                    
                    # Check if teacher is available at this slot
                    # First check within our generated schedules
                    teacher_busy_in_generated = any(
                        s['day_of_week'] == day and 
                        s['time_slot_id'] == slot.id and 
                        s['teacher_id'] == req['teacher_id']
                        for s in scheduled
                    )
                    
                    if teacher_busy_in_generated:
                        continue
                    
                    # Then check existing database schedules
                    has_db_conflict = check_teacher_slot_conflict(
                        session, req['teacher_id'],
                        slot.day_of_week, slot.id,
                        tenant_id, academic_year
                    )
                    
                    if has_db_conflict:
                        continue
                    
                    # Calculate score (prefer even distribution)
                    score = req['remaining'] * 10  # Prioritize subjects needing more periods
                    
                    # Penalize if already scheduled on this day (for distribution)
                    if day in req['assigned_days']:
                        score -= 5
                    
                    if score > best_score:
                        best_score = score
                        best_req = req
                
                # Assign the best match
                if best_req:
                    scheduled.append({
                        'class_id': class_id,
                        'time_slot_id': slot.id,
                        'day_of_week': day,
                        'teacher_id': best_req['teacher_id'],
                        'subject_id': best_req['subject_id'],
                        'room_number': best_req.get('room', ''),
                        'academic_year': academic_year,
                        'slot_info': {
                            'start_time': slot.start_time.strftime('%H:%M'),
                            'end_time': slot.end_time.strftime('%H:%M'),
                            'slot_name': slot.slot_name or f"Period {slot.slot_order or 1}",
                            'slot_order': slot.slot_order or 1
                        }
                    })
                    used_slots.add((day, slot.id))
                    best_req['remaining'] -= 1
                    best_req['assigned_days'].append(day)
        
        # Check for unfulfilled requirements
        for req in requirements:
            if req['remaining'] > 0:
                result['warnings'].append(
                    f"Could not schedule {req['remaining']} period(s) for teacher {req['teacher_id']}, "
                    f"subject {req['subject_id']} (insufficient slots or conflicts)"
                )
        
        result['success'] = True
        result['schedules'] = scheduled
        
        return result
        
    except Exception as e:
        logger.error(f"Error in auto_generate_timetable: {e}")
        import traceback
        traceback.print_exc()
        result['errors'].append(f"Generation failed: {str(e)}")
        return result


def apply_generated_timetable(session, class_id, tenant_id, schedules, academic_year=None, clear_existing=True):
    """
    Apply generated timetable schedules to the database
    
    Args:
        session: Database session
        class_id: Class ID
        tenant_id: Tenant ID
        schedules: List of schedule dicts from auto_generate_timetable
        academic_year: Academic year (defaults to current)
        clear_existing: If True, delete existing schedules for this class first
    
    Returns:
        Dictionary with success status and count of created schedules
    """
    from timetable_models import TimetableSchedule, DayOfWeekEnum
    from datetime import datetime
    
    if not academic_year:
        academic_year = get_current_academic_year()
    
    result = {
        'success': False,
        'created': 0,
        'errors': []
    }
    
    try:
        # Optionally clear existing schedules
        if clear_existing:
            deleted = session.query(TimetableSchedule).filter(
                TimetableSchedule.tenant_id == tenant_id,
                TimetableSchedule.class_id == class_id,
                TimetableSchedule.academic_year == academic_year
            ).delete(synchronize_session=False)
            logger.info(f"Deleted {deleted} existing schedules for class {class_id}")
        
        # Create new schedules
        for sched in schedules:
            # Convert day string to enum
            day_enum = None
            for day in DayOfWeekEnum:
                if day.value == sched['day_of_week']:
                    day_enum = day
                    break
            
            if not day_enum:
                result['errors'].append(f"Invalid day: {sched['day_of_week']}")
                continue
            
            new_schedule = TimetableSchedule(
                tenant_id=tenant_id,
                class_id=class_id,
                time_slot_id=sched['time_slot_id'],
                day_of_week=day_enum,
                teacher_id=sched['teacher_id'],
                subject_id=sched['subject_id'],
                room_number=sched.get('room_number', ''),
                academic_year=academic_year,
                effective_from=datetime.now().date(),
                is_active=True
            )
            session.add(new_schedule)
            result['created'] += 1
        
        session.commit()
        result['success'] = True
        
        return result
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error applying generated timetable: {e}")
        import traceback
        traceback.print_exc()
        result['errors'].append(f"Failed to save: {str(e)}")
        return result
