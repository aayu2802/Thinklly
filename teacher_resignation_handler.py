"""
Teacher Resignation Handler
Comprehensive cleanup when a teacher's status changes to RESIGNED
"""

from datetime import date
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


def handle_teacher_resignation(session: Session, teacher_id: int, tenant_id: int, resignation_date=None):
    """
    Handle all cleanup tasks when a teacher resigns.
    
    This function is called when:
    1. A teacher is soft-deleted via delete_teacher route
    2. A teacher's employee_status is manually changed to RESIGNED via profile edit
    
    Args:
        session: Database session
        teacher_id: ID of the resigning teacher
        tenant_id: ID of the tenant/school
        resignation_date: Date of resignation (defaults to today)
    
    Returns:
        dict with success status and cleanup details
    """
    from teacher_models import Teacher, TeacherAuth, TeacherSalary, EmployeeStatusEnum
    from timetable_models import TimetableSchedule, ClassTeacherAssignment
    from leave_models import TeacherLeaveApplication, LeaveStatusEnum
    from question_paper_models import QuestionPaperAssignment
    from copy_checking_models import CopyCheckingAssignment
    
    resignation_date = resignation_date or date.today()
    
    try:
        teacher = session.query(Teacher).filter_by(id=teacher_id, tenant_id=tenant_id).first()
        if not teacher:
            return {'success': False, 'error': 'Teacher not found'}
        
        teacher_name = teacher.full_name
        cleanup_summary = {
            'teacher_name': teacher_name,
            'auth_deactivated': False,
            'timetable_schedules_deactivated': 0,
            'class_assignments_ended': 0,
            'leave_applications_cancelled': 0,
            'salary_deactivated': False,
            'pending_question_paper_assignments': 0,
            'pending_copy_checking_assignments': 0
        }
        
        # 1. Update teacher status to RESIGNED (if not already)
        if teacher.employee_status != EmployeeStatusEnum.RESIGNED:
            teacher.employee_status = EmployeeStatusEnum.RESIGNED
            logger.info(f"Teacher {teacher_id} status updated to RESIGNED")
        
        # 2. Deactivate TeacherAuth (prevent login)
        auth = session.query(TeacherAuth).filter_by(teacher_id=teacher_id).first()
        if auth and auth.is_active:
            auth.is_active = False
            cleanup_summary['auth_deactivated'] = True
            logger.info(f"Teacher {teacher_id} auth deactivated")
        
        # 3. End class teacher assignments (set removed_date)
        class_assignments = session.query(ClassTeacherAssignment).filter(
            ClassTeacherAssignment.teacher_id == teacher_id,
            ClassTeacherAssignment.tenant_id == tenant_id,
            ClassTeacherAssignment.removed_date == None
        ).all()
        
        for assignment in class_assignments:
            assignment.removed_date = resignation_date
        cleanup_summary['class_assignments_ended'] = len(class_assignments)
        logger.info(f"Ended {len(class_assignments)} class assignments for teacher {teacher_id}")
        
        # 4. Deactivate timetable schedules
        timetable_schedules = session.query(TimetableSchedule).filter(
            TimetableSchedule.teacher_id == teacher_id,
            TimetableSchedule.tenant_id == tenant_id,
            TimetableSchedule.is_active == True
        ).all()
        
        for schedule in timetable_schedules:
            schedule.is_active = False
            schedule.effective_to = resignation_date
        cleanup_summary['timetable_schedules_deactivated'] = len(timetable_schedules)
        logger.info(f"Deactivated {len(timetable_schedules)} timetable schedules for teacher {teacher_id}")
        
        # 5. Cancel pending leave applications
        pending_leaves = session.query(TeacherLeaveApplication).filter(
            TeacherLeaveApplication.teacher_id == teacher_id,
            TeacherLeaveApplication.tenant_id == tenant_id,
            TeacherLeaveApplication.status == LeaveStatusEnum.PENDING
        ).all()
        
        for leave in pending_leaves:
            leave.status = LeaveStatusEnum.CANCELLED
            leave.admin_notes = (leave.admin_notes or '') + '\n[Auto-cancelled: Teacher resigned on ' + str(resignation_date) + ']'
        cleanup_summary['leave_applications_cancelled'] = len(pending_leaves)
        logger.info(f"Cancelled {len(pending_leaves)} pending leave applications for teacher {teacher_id}")
        
        # 6. Deactivate salary record
        salary = session.query(TeacherSalary).filter_by(
            teacher_id=teacher_id, 
            is_active=True
        ).first()
        if salary:
            salary.is_active = False
            salary.effective_to = resignation_date
            cleanup_summary['salary_deactivated'] = True
            logger.info(f"Deactivated salary for teacher {teacher_id}")
        
        # 7. Count pending question paper assignments (for notification)
        pending_qp_count = session.query(QuestionPaperAssignment).filter_by(
            teacher_id=teacher_id
        ).count()
        cleanup_summary['pending_question_paper_assignments'] = pending_qp_count
        
        # 8. Count pending copy checking assignments (for notification)
        pending_cc_count = session.query(CopyCheckingAssignment).filter_by(
            teacher_id=teacher_id
        ).count()
        cleanup_summary['pending_copy_checking_assignments'] = pending_cc_count
        
        if pending_qp_count > 0 or pending_cc_count > 0:
            logger.warning(f"Teacher {teacher_id} has {pending_qp_count} QP assignments and {pending_cc_count} copy checking assignments that need reassignment")
        
        return {
            'success': True,
            **cleanup_summary,
            'message': f'Teacher "{teacher_name}" resignation processed successfully.'
        }
        
    except Exception as e:
        logger.error(f"Error processing teacher resignation for teacher_id={teacher_id}: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def is_teacher_resigned(session: Session, teacher_id: int) -> bool:
    """
    Check if a teacher has resigned status.
    
    Args:
        session: Database session
        teacher_id: ID of the teacher
    
    Returns:
        True if teacher is resigned, False otherwise
    """
    from teacher_models import Teacher, EmployeeStatusEnum
    
    teacher = session.query(Teacher).filter_by(id=teacher_id).first()
    if not teacher:
        return True  # If teacher doesn't exist, treat as resigned
    
    return teacher.employee_status == EmployeeStatusEnum.RESIGNED


def get_teacher_resignation_warning(session: Session, teacher_id: int, tenant_id: int) -> dict:
    """
    Get warning information about what will be affected when teacher resigns.
    Call this before resignation to inform admin.
    
    Args:
        session: Database session
        teacher_id: ID of the teacher
        tenant_id: ID of the tenant
    
    Returns:
        dict with counts of affected records
    """
    from teacher_models import Teacher
    from timetable_models import TimetableSchedule, ClassTeacherAssignment
    from leave_models import TeacherLeaveApplication, LeaveStatusEnum
    from question_paper_models import QuestionPaperAssignment
    from copy_checking_models import CopyCheckingAssignment
    
    teacher = session.query(Teacher).filter_by(id=teacher_id, tenant_id=tenant_id).first()
    if not teacher:
        return {'error': 'Teacher not found'}
    
    active_schedules = session.query(TimetableSchedule).filter(
        TimetableSchedule.teacher_id == teacher_id,
        TimetableSchedule.is_active == True
    ).count()
    
    active_class_assignments = session.query(ClassTeacherAssignment).filter(
        ClassTeacherAssignment.teacher_id == teacher_id,
        ClassTeacherAssignment.removed_date == None
    ).count()
    
    pending_leaves = session.query(TeacherLeaveApplication).filter(
        TeacherLeaveApplication.teacher_id == teacher_id,
        TeacherLeaveApplication.status == LeaveStatusEnum.PENDING
    ).count()
    
    qp_assignments = session.query(QuestionPaperAssignment).filter_by(
        teacher_id=teacher_id
    ).count()
    
    cc_assignments = session.query(CopyCheckingAssignment).filter_by(
        teacher_id=teacher_id
    ).count()
    
    return {
        'teacher_name': teacher.full_name,
        'active_timetable_schedules': active_schedules,
        'active_class_assignments': active_class_assignments,
        'pending_leave_applications': pending_leaves,
        'question_paper_assignments': qp_assignments,
        'copy_checking_assignments': cc_assignments,
        'total_affected': active_schedules + active_class_assignments + pending_leaves + qp_assignments + cc_assignments
    }
