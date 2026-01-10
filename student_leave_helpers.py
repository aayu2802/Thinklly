"""
Helper functions for Student Leave Management
Provides reusable functions for leave operations
"""

from leave_models import StudentLeave, StudentLeaveStatusEnum, StudentLeaveTypeEnum
from datetime import datetime, date
import os
import json
import uuid
from werkzeug.utils import secure_filename


def apply_student_leave(db_session, tenant_id, student_id, class_id, leave_data, files=None):
    """
    Apply for student leave
    
    Args:
        db_session: SQLAlchemy session
        tenant_id: Tenant ID
        student_id: Student ID
        class_id: Class ID
        leave_data: Dict with leave_type, from_date, to_date, is_half_day, half_day_period, reason
        files: List of FileStorage objects
        
    Returns:
        tuple: (success: bool, message: str, leave: StudentLeave or None)
    """
    try:
        # Validate dates
        from_date = leave_data['from_date']
        to_date = leave_data['to_date']
        
        if from_date > to_date:
            return (False, "From date cannot be after to date", None)
        
        # Validate half-day
        is_half_day = leave_data.get('is_half_day', False)
        if is_half_day and from_date != to_date:
            return (False, "Half-day leave must be for a single day", None)
        
        # Check for overlapping leaves
        existing = db_session.query(StudentLeave).filter(
            StudentLeave.student_id == student_id,
            StudentLeave.status != StudentLeaveStatusEnum.REJECTED,
            StudentLeave.from_date <= to_date,
            StudentLeave.to_date >= from_date
        ).first()
        
        if existing:
            return (False, "You already have a leave application for these dates", None)
        
        # Create leave record
        leave = StudentLeave(
            tenant_id=tenant_id,
            student_id=student_id,
            class_id=class_id,
            leave_type=StudentLeaveTypeEnum(leave_data['leave_type']),
            from_date=from_date,
            to_date=to_date,
            is_half_day=is_half_day,
            half_day_period=leave_data.get('half_day_period'),
            reason=leave_data['reason'],
            status=StudentLeaveStatusEnum.PENDING
        )
        
        db_session.add(leave)
        db_session.flush()  # Get leave.id
        
        # Handle document uploads
        if files:
            from models import Student
            student = db_session.query(Student).filter_by(id=student_id).first()
            if student:
                doc_paths = save_leave_documents(files, tenant_id, student.admission_number, leave.id)
                leave.set_documents(doc_paths)
        
        db_session.commit()
        return (True, "Leave application submitted successfully", leave)
        
    except Exception as e:
        db_session.rollback()
        return (False, f"Error applying for leave: {str(e)}", None)


def save_leave_documents(files, tenant_id, student_admission_number, leave_id):
    """
    Save uploaded documents and return list of file paths
    
    Args:
        files: List of FileStorage objects
        tenant_id: Tenant ID
        student_admission_number: Student admission number
        leave_id: Leave ID
    
    Returns:
        list: List of saved file paths
    """
    saved_paths = []
    allowed_extensions = {'pdf', 'jpg', 'jpeg', 'png'}
    max_size = 5 * 1024 * 1024  # 5MB
    
    base_path = f"static/uploads/documents/{tenant_id}/students/{student_admission_number}/leaves/{leave_id}/"
    os.makedirs(base_path, exist_ok=True)
    
    for file in files:
        if file and file.filename:
            # Validate extension
            ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            if ext not in allowed_extensions:
                continue
            
            # Validate size
            file.seek(0, 2)
            size = file.tell()
            file.seek(0)
            if size > max_size:
                continue
            
            # Generate unique filename
            filename = secure_filename(file.filename)
            unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"
            file_path = os.path.join(base_path, unique_name)
            
            # Save file
            file.save(file_path)
            saved_paths.append(file_path)
    
    return saved_paths


def delete_leave_documents(document_paths):
    """Delete all documents associated with a leave"""
    for path in document_paths:
        if os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass


def get_student_leaves(db_session, student_id, status=None):
    """
    Get leaves for a student
    
    Args:
        db_session: SQLAlchemy session
        student_id: Student ID
        status: Optional LeaveStatusEnum filter
        
    Returns:
        list: List of StudentLeave records
    """
    query = db_session.query(StudentLeave).filter_by(student_id=student_id)
    
    if status:
        query = query.filter_by(status=status)
    
    return query.order_by(StudentLeave.applied_date.desc()).all()


def get_pending_leaves_for_admin(db_session, tenant_id, class_id=None):
    """
    Get pending leaves for admin review
    
    Args:
        db_session: SQLAlchemy session
        tenant_id: Tenant ID
        class_id: Optional class filter
        
    Returns:
        list: List of pending StudentLeave records
    """
    from sqlalchemy.orm import joinedload
    
    query = db_session.query(StudentLeave).options(
        joinedload(StudentLeave.student),
        joinedload(StudentLeave.student_class)
    ).filter(
        StudentLeave.tenant_id == tenant_id,
        StudentLeave.status == StudentLeaveStatusEnum.PENDING
    )
    
    if class_id:
        query = query.filter(StudentLeave.class_id == class_id)
    
    return query.order_by(StudentLeave.applied_date.desc()).all()


def get_pending_leaves_for_teacher(db_session, teacher_id, tenant_id):
    """
    Get pending leaves for teacher's assigned classes
    
    Args:
        db_session: SQLAlchemy session
        teacher_id: Teacher ID
        tenant_id: Tenant ID
        
    Returns:
        list: List of pending StudentLeave records
    """
    from sqlalchemy.orm import joinedload
    from timetable_models import ClassTeacherAssignment
    
    # Get classes where teacher is class teacher
    assignments = db_session.query(ClassTeacherAssignment).filter(
        ClassTeacherAssignment.teacher_id == teacher_id,
        ClassTeacherAssignment.tenant_id == tenant_id,
        ClassTeacherAssignment.is_class_teacher == True,
        ClassTeacherAssignment.removed_date.is_(None)
    ).all()
    
    class_ids = [a.class_id for a in assignments]
    
    if not class_ids:
        return []
    
    query = db_session.query(StudentLeave).options(
        joinedload(StudentLeave.student),
        joinedload(StudentLeave.student_class)
    ).filter(
        StudentLeave.tenant_id == tenant_id,
        StudentLeave.class_id.in_(class_ids),
        StudentLeave.status == StudentLeaveStatusEnum.PENDING
    )
    
    return query.order_by(StudentLeave.applied_date.desc()).all()


def approve_leave(db_session, leave_id, reviewer_id, reviewer_type, remarks=None):
    """
    Approve a leave request
    
    Args:
        db_session: SQLAlchemy session
        leave_id: Leave ID
        reviewer_id: User ID of reviewer
        reviewer_type: 'admin' or 'teacher'
        remarks: Optional admin remarks
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        leave = db_session.query(StudentLeave).filter_by(id=leave_id).first()
        
        if not leave:
            return (False, "Leave not found")
        
        if leave.status != StudentLeaveStatusEnum.PENDING:
            return (False, f"Leave is already {leave.status.value}")
        
        leave.status = StudentLeaveStatusEnum.APPROVED
        leave.reviewed_by = reviewer_id
        leave.reviewed_by_type = reviewer_type
        leave.reviewed_date = datetime.utcnow()
        leave.admin_remarks = remarks
        
        db_session.commit()
        
        # Mark attendance as "On Leave" for approved dates
        mark_attendance_for_approved_leave(db_session, leave)
        
        return (True, "Leave approved successfully")
        
    except Exception as e:
        db_session.rollback()
        return (False, f"Error approving leave: {str(e)}")


def reject_leave(db_session, leave_id, reviewer_id, reviewer_type, remarks=None):
    """
    Reject a leave request
    
    Args:
        db_session: SQLAlchemy session
        leave_id: Leave ID
        reviewer_id: User ID of reviewer
        reviewer_type: 'admin' or 'teacher'
        remarks: Optional admin remarks
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        leave = db_session.query(StudentLeave).filter_by(id=leave_id).first()
        
        if not leave:
            return (False, "Leave not found")
        
        if leave.status != StudentLeaveStatusEnum.PENDING:
            return (False, f"Leave is already {leave.status.value}")
        
        leave.status = StudentLeaveStatusEnum.REJECTED
        leave.reviewed_by = reviewer_id
        leave.reviewed_by_type = reviewer_type
        leave.reviewed_date = datetime.utcnow()
        leave.admin_remarks = remarks
        
        db_session.commit()
        return (True, "Leave rejected successfully")
        
    except Exception as e:
        db_session.rollback()
        return (False, f"Error rejecting leave: {str(e)}")


def cancel_student_leave(db_session, leave_id, student_id):
    """
    Cancel pending leave and delete documents
    
    Args:
        db_session: SQLAlchemy session
        leave_id: Leave ID
        student_id: Student ID (for verification)
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        leave = db_session.query(StudentLeave).filter(
            StudentLeave.id == leave_id,
            StudentLeave.student_id == student_id,
            StudentLeave.status == StudentLeaveStatusEnum.PENDING
        ).first()
        
        if not leave:
            return (False, "Leave not found or cannot be cancelled")
        
        # Delete documents
        if leave.documents:
            delete_leave_documents(leave.documents)
        
        # Delete leave record
        db_session.delete(leave)
        db_session.commit()
        
        return (True, "Leave cancelled successfully")
        
    except Exception as e:
        db_session.rollback()
        return (False, f"Error cancelling leave: {str(e)}")


def mark_attendance_for_approved_leave(db_session, leave):
    """
    Mark attendance as 'On Leave' for approved leave dates
    
    Args:
        db_session: SQLAlchemy session
        leave: StudentLeave object
    """
    from student_attendance_helpers import mark_student_attendance
    from models import StudentAttendanceStatusEnum
    from datetime import timedelta
    
    try:
        current_date = leave.from_date
        while current_date <= leave.to_date:
            # Mark attendance as On Leave
            mark_student_attendance(
                db_session,
                student_id=leave.student_id,
                class_id=leave.class_id,
                tenant_id=leave.tenant_id,
                attendance_date=current_date,
                status=StudentAttendanceStatusEnum.ON_LEAVE,
                remarks=f"Approved leave: {leave.leave_type.value}"
            )
            current_date += timedelta(days=1)
        
        db_session.commit()
    except Exception as e:
        print(f"Error marking attendance for leave: {e}")
