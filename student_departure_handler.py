"""
Student Departure Handler
Handles all cleanup actions when a student's status changes from ACTIVE
(transfer, withdrawal, graduation)
"""

from datetime import datetime, date
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


def handle_student_departure(session: Session, student_id: int, tenant_id: int, 
                             departure_type: str, departure_date=None):
    """
    Perform comprehensive cleanup when a student leaves (transfer, withdrawal, graduation).
    
    Args:
        session: Database session
        student_id: ID of the student
        tenant_id: Tenant ID  
        departure_type: One of 'TRANSFERRED', 'LEFT', 'GRADUATED'
        departure_date: Optional departure date, defaults to today
        
    Returns:
        dict with success status and cleanup summary
    """
    from models import Student, StudentStatusEnum
    from student_models import StudentAuth
    
    if departure_date is None:
        departure_date = date.today()
    
    cleanup_summary = {
        'student_id': student_id,
        'departure_type': departure_type,
        'departure_date': str(departure_date),
        'auth_deactivated': False,
        'transport_ended': False,
        'leaves_cancelled': 0,
        'library_flagged': 0,
        'pending_fees_count': 0
    }
    
    try:
        # 1. Get and update student status
        student = session.query(Student).filter_by(
            id=student_id,
            tenant_id=tenant_id
        ).first()
        
        if not student:
            return {
                'success': False,
                'message': f'Student with ID {student_id} not found',
                'cleanup_summary': cleanup_summary
            }
        
        old_status = student.status
        cleanup_summary['student_name'] = student.full_name
        
        # Update student status
        if departure_type == 'TRANSFERRED':
            student.status = StudentStatusEnum.TRANSFERRED
        elif departure_type == 'LEFT':
            student.status = StudentStatusEnum.LEFT
        elif departure_type == 'GRADUATED':
            student.status = StudentStatusEnum.GRADUATED
        else:
            return {
                'success': False,
                'message': f'Invalid departure type: {departure_type}',
                'cleanup_summary': cleanup_summary
            }
        
        logger.info(f"Student {student_id} status changed from {old_status} to {student.status}")
        
        # 2. Deactivate StudentAuth
        try:
            student_auth = session.query(StudentAuth).filter_by(
                student_id=student_id,
                tenant_id=tenant_id
            ).first()
            
            if student_auth and student_auth.is_active:
                student_auth.is_active = False
                student_auth.updated_at = datetime.utcnow()
                cleanup_summary['auth_deactivated'] = True
                logger.info(f"StudentAuth deactivated for student {student_id}")
        except Exception as e:
            logger.warning(f"Error deactivating StudentAuth: {e}")
        
        # 3. End transport assignment
        try:
            from transport_models import TransportAssignment
            transport = session.query(TransportAssignment).filter_by(
                student_id=student_id,
                tenant_id=tenant_id,
                is_active=True
            ).first()
            
            if transport:
                transport.is_active = False
                transport.end_date = departure_date
                cleanup_summary['transport_ended'] = True
                logger.info(f"Transport assignment ended for student {student_id}")
        except ImportError:
            logger.debug("transport_models not available")
        except Exception as e:
            logger.warning(f"Error ending transport assignment: {e}")
        
        # 4. Cancel pending student leave applications
        try:
            from leave_models import StudentLeave, StudentLeaveStatusEnum
            pending_leaves = session.query(StudentLeave).filter(
                StudentLeave.student_id == student_id,
                StudentLeave.tenant_id == tenant_id,
                StudentLeave.status == StudentLeaveStatusEnum.PENDING
            ).all()
            
            for leave in pending_leaves:
                leave.status = StudentLeaveStatusEnum.CANCELLED
                leave.remarks = f"Auto-cancelled: Student {departure_type.lower()}"
                leave.updated_at = datetime.utcnow()
            
            cleanup_summary['leaves_cancelled'] = len(pending_leaves)
            if pending_leaves:
                logger.info(f"Cancelled {len(pending_leaves)} pending leaves for student {student_id}")
        except ImportError:
            logger.debug("leave_models.StudentLeave not available")
        except Exception as e:
            logger.warning(f"Error cancelling leaves: {e}")
        
        # 5. Flag library issues for return
        try:
            from library_models import LibraryIssue
            unreturned_books = session.query(LibraryIssue).filter(
                LibraryIssue.student_id == student_id,
                LibraryIssue.tenant_id == tenant_id,
                LibraryIssue.returned_date.is_(None)
            ).count()
            
            cleanup_summary['library_flagged'] = unreturned_books
            if unreturned_books > 0:
                logger.info(f"Student {student_id} has {unreturned_books} unreturned books")
        except ImportError:
            logger.debug("library_models not available")
        except Exception as e:
            logger.warning(f"Error checking library issues: {e}")
        
        # 6. Count pending fees (for clearance tracking)
        try:
            from fee_models import StudentFee, FeeStatusEnum
            pending_fees = session.query(StudentFee).filter(
                StudentFee.student_id == student_id,
                StudentFee.tenant_id == tenant_id,
                StudentFee.status.in_([FeeStatusEnum.PENDING, FeeStatusEnum.PARTIALLY_PAID, FeeStatusEnum.OVERDUE])
            ).count()
            
            cleanup_summary['pending_fees_count'] = pending_fees
            if pending_fees > 0:
                logger.info(f"Student {student_id} has {pending_fees} pending fee records")
        except ImportError:
            logger.debug("fee_models not available")
        except Exception as e:
            logger.warning(f"Error checking fees: {e}")
        
        # Commit changes
        session.flush()
        
        # Build success message
        details = []
        if cleanup_summary['auth_deactivated']:
            details.append("Login deactivated")
        if cleanup_summary['transport_ended']:
            details.append("Transport assignment ended")
        if cleanup_summary['leaves_cancelled'] > 0:
            details.append(f"{cleanup_summary['leaves_cancelled']} leave(s) cancelled")
        if cleanup_summary['library_flagged'] > 0:
            details.append(f"⚠️ {cleanup_summary['library_flagged']} book(s) need to be returned")
        if cleanup_summary['pending_fees_count'] > 0:
            details.append(f"⚠️ {cleanup_summary['pending_fees_count']} fee record(s) pending clearance")
        
        return {
            'success': True,
            'message': f'Student "{student.full_name}" marked as {departure_type}.',
            'details': details,
            'cleanup_summary': cleanup_summary
        }
        
    except Exception as e:
        logger.error(f"Error in handle_student_departure: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'success': False,
            'message': f'Error processing student departure: {str(e)}',
            'cleanup_summary': cleanup_summary
        }


def is_student_active(session: Session, student_id: int) -> bool:
    """
    Check if a student is still active.
    
    Args:
        session: Database session
        student_id: ID of the student
        
    Returns:
        True if student exists and has ACTIVE status, False otherwise
    """
    from models import Student, StudentStatusEnum
    
    try:
        student = session.query(Student).filter_by(id=student_id).first()
        return student is not None and student.status == StudentStatusEnum.ACTIVE
    except Exception as e:
        logger.error(f"Error checking student status: {e}")
        return False
