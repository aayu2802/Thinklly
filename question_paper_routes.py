"""
Question Paper Routes for School ERP
Routes for question paper setter/reviewer workflow
"""
from flask import render_template, request, redirect, url_for, flash, g, jsonify, send_file
from flask_login import current_user
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import joinedload
from datetime import datetime
import logging
import os

from db_single import get_session
from question_paper_models import (
    QuestionPaperAssignment, QuestionPaper, QuestionPaperReview,
    AssignmentRole, QuestionPaperStatus, ReviewAction
)
from examination_models import Examination, ExaminationSubject
from teacher_models import Teacher, Subject
from models import Class

logger = logging.getLogger(__name__)


def register_question_paper_routes(bp, require_school_auth):
    """Register question paper management routes to the school blueprint"""
    
    # ==================== QUESTION PAPER SELECT EXAM (ADMIN) ====================
    
    @bp.route('/<tenant_slug>/question-papers')
    @require_school_auth
    def question_papers_select(tenant_slug):
        """Select an exam to manage question papers"""
        session_db = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Get all examinations for this tenant
            examinations = session_db.query(Examination).filter_by(
                tenant_id=tenant_id
            ).order_by(Examination.start_date.desc()).all()
            
            # Build exam data with paper stats
            exams_data = []
            for exam in examinations:
                # Count subjects
                subjects = session_db.query(ExaminationSubject).filter_by(
                    examination_id=exam.id
                ).all()
                
                total_subjects = len(subjects)
                
                # Count papers by status
                papers_count = 0
                approved_count = 0
                for subj in subjects:
                    paper = session_db.query(QuestionPaper).filter(
                        QuestionPaper.examination_subject_id == subj.id,
                        QuestionPaper.status != QuestionPaperStatus.SUPERSEDED
                    ).order_by(QuestionPaper.version.desc()).first()
                    if paper:
                        papers_count += 1
                        if paper.status in [QuestionPaperStatus.APPROVED, QuestionPaperStatus.FINAL]:
                            approved_count += 1
                
                exams_data.append({
                    'exam': exam,
                    'total_subjects': total_subjects,
                    'papers_uploaded': papers_count,
                    'papers_approved': approved_count
                })
            
            return render_template(
                'akademi/examinations/question_papers_select.html',
                exams_data=exams_data,
                school=g.current_tenant
            )
            
        except Exception as e:
            logger.error(f"Error in question_papers_select for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error loading examinations', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    # ==================== QUESTION PAPER MANAGEMENT (ADMIN) ====================
    
    @bp.route('/<tenant_slug>/examinations/<int:exam_id>/question-papers')
    @require_school_auth
    def question_papers_list(tenant_slug, exam_id):
        """List all question papers for an examination"""
        session_db = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            examination = session_db.query(Examination).filter_by(
                id=exam_id,
                tenant_id=tenant_id
            ).first()
            
            if not examination:
                flash('Examination not found', 'error')
                return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
            
            # Get all exam subjects with their assignments and papers
            exam_subjects = session_db.query(ExaminationSubject).filter_by(
                examination_id=exam_id
            ).all()
            
            # Build data structure for template
            subjects_data = []
            for es in exam_subjects:
                # Get setters for this subject
                setters = session_db.query(QuestionPaperAssignment).filter_by(
                    examination_subject_id=es.id,
                    role=AssignmentRole.SETTER
                ).all()
                
                # Get reviewer for this subject
                reviewer = session_db.query(QuestionPaperAssignment).filter_by(
                    examination_subject_id=es.id,
                    role=AssignmentRole.REVIEWER
                ).first()
                
                # Get latest question paper (excluding superseded)
                latest_paper = session_db.query(QuestionPaper).filter(
                    QuestionPaper.examination_subject_id == es.id,
                    QuestionPaper.status != QuestionPaperStatus.SUPERSEDED
                ).order_by(QuestionPaper.version.desc()).first()
                
                subjects_data.append({
                    'exam_subject': es,
                    'subject': es.subject,
                    'class_ref': es.class_ref,
                    'setters': setters,
                    'reviewer': reviewer,
                    'latest_paper': latest_paper
                })
            
            # Calculate stats
            total_subjects = len(exam_subjects)
            papers_submitted = sum(1 for s in subjects_data if s['latest_paper'] and s['latest_paper'].status != QuestionPaperStatus.DRAFT)
            papers_approved = sum(1 for s in subjects_data if s['latest_paper'] and s['latest_paper'].status in [QuestionPaperStatus.APPROVED, QuestionPaperStatus.FINAL])
            papers_final = sum(1 for s in subjects_data if s['latest_paper'] and s['latest_paper'].status == QuestionPaperStatus.FINAL)
            
            stats = {
                'total_subjects': total_subjects,
                'papers_submitted': papers_submitted,
                'papers_approved': papers_approved,
                'papers_final': papers_final
            }
            
            return render_template(
                'akademi/examinations/question_papers_list.html',
                examination=examination,
                subjects_data=subjects_data,
                stats=stats,
                school=g.current_tenant,
                QuestionPaperStatus=QuestionPaperStatus
            )
            
        except Exception as e:
            logger.error(f"Error in question_papers_list for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error loading question papers', 'error')
            return redirect(url_for('school.examinations_detail', tenant_slug=tenant_slug, exam_id=exam_id))
        finally:
            session_db.close()
    
    
    @bp.route('/<tenant_slug>/examinations/<int:exam_id>/subjects/<int:subject_id>/assign-setters', methods=['GET', 'POST'])
    @require_school_auth
    def assign_setters_reviewers(tenant_slug, exam_id, subject_id):
        """Assign setters and reviewer for a subject"""
        session_db = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Verify examination and subject
            examination = session_db.query(Examination).filter_by(
                id=exam_id,
                tenant_id=tenant_id
            ).first()
            
            if not examination:
                flash('Examination not found', 'error')
                return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
            
            exam_subject = session_db.query(ExaminationSubject).filter_by(
                id=subject_id,
                examination_id=exam_id
            ).first()
            
            if not exam_subject:
                flash('Subject not found', 'error')
                return redirect(url_for('school.question_papers_list', tenant_slug=tenant_slug, exam_id=exam_id))
            
            if request.method == 'POST':
                # Get form data
                setter_ids = request.form.getlist('setter_ids')
                reviewer_id = request.form.get('reviewer_id', type=int)
                admin_comments = request.form.get('admin_comments', '').strip()
                setter_deadline_str = request.form.get('setter_deadline', '').strip()
                reviewer_deadline_str = request.form.get('reviewer_deadline', '').strip()
                
                # Parse deadlines
                setter_deadline = None
                reviewer_deadline = None
                if setter_deadline_str:
                    try:
                        setter_deadline = datetime.strptime(setter_deadline_str, '%Y-%m-%dT%H:%M')
                    except ValueError:
                        try:
                            setter_deadline = datetime.strptime(setter_deadline_str, '%Y-%m-%d')
                        except ValueError:
                            pass
                
                if reviewer_deadline_str:
                    try:
                        reviewer_deadline = datetime.strptime(reviewer_deadline_str, '%Y-%m-%dT%H:%M')
                    except ValueError:
                        try:
                            reviewer_deadline = datetime.strptime(reviewer_deadline_str, '%Y-%m-%d')
                        except ValueError:
                            pass
                
                # Clear existing assignments for this subject
                session_db.query(QuestionPaperAssignment).filter_by(
                    examination_subject_id=subject_id
                ).delete()
                
                new_teacher_ids = []
                
                # Add setters
                for setter_id in setter_ids:
                    if setter_id:
                        setter_id = int(setter_id)
                        assignment = QuestionPaperAssignment(
                            examination_subject_id=subject_id,
                            teacher_id=setter_id,
                            role=AssignmentRole.SETTER,
                            admin_comments=admin_comments,
                            deadline=setter_deadline,
                            created_by=current_user.id
                        )
                        session_db.add(assignment)
                        new_teacher_ids.append(setter_id)
                
                # Add reviewer (single)
                if reviewer_id:
                    assignment = QuestionPaperAssignment(
                        examination_subject_id=subject_id,
                        teacher_id=reviewer_id,
                        role=AssignmentRole.REVIEWER,
                        admin_comments=admin_comments,
                        deadline=reviewer_deadline,
                        created_by=current_user.id
                    )
                    session_db.add(assignment)
                    new_teacher_ids.append(reviewer_id)
                
                session_db.commit()
                
                # Send notifications to assigned teachers
                if new_teacher_ids:
                    try:
                        _send_assignment_notifications(
                            session_db, tenant_id, 
                            new_teacher_ids, examination, 
                            exam_subject, admin_comments,
                            setter_deadline, reviewer_deadline
                        )
                    except Exception as notif_error:
                        logger.error(f"Error sending notifications: {notif_error}")
                        # Don't fail the whole operation for notification errors
                
                flash('Setters and reviewer assigned successfully', 'success')
                return redirect(url_for('school.question_papers_list', tenant_slug=tenant_slug, exam_id=exam_id))
            
            # GET request - show form
            teachers = session_db.query(Teacher).filter_by(
                tenant_id=tenant_id
            ).filter(
                Teacher.employee_status.in_(['Active', 'ACTIVE'])
            ).order_by(Teacher.first_name).all()
            
            # Get current assignments
            current_setters = session_db.query(QuestionPaperAssignment).filter_by(
                examination_subject_id=subject_id,
                role=AssignmentRole.SETTER
            ).all()
            
            current_reviewer = session_db.query(QuestionPaperAssignment).filter_by(
                examination_subject_id=subject_id,
                role=AssignmentRole.REVIEWER
            ).first()
            
            # Get previous admin comments if any
            prev_comments = ''
            setter_deadline = None
            reviewer_deadline = None
            if current_setters:
                prev_comments = current_setters[0].admin_comments or ''
                setter_deadline = current_setters[0].deadline
            if current_reviewer:
                if not prev_comments:
                    prev_comments = current_reviewer.admin_comments or ''
                reviewer_deadline = current_reviewer.deadline
            
            return render_template(
                'akademi/examinations/assign_setters.html',
                examination=examination,
                exam_subject=exam_subject,
                teachers=teachers,
                current_setters=current_setters,
                current_reviewer=current_reviewer,
                prev_comments=prev_comments,
                setter_deadline=setter_deadline,
                reviewer_deadline=reviewer_deadline,
                school=g.current_tenant
            )
            
        except Exception as e:
            logger.error(f"Error in assign_setters_reviewers for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error assigning setters/reviewer', 'error')
            session_db.rollback()
            return redirect(url_for('school.question_papers_list', tenant_slug=tenant_slug, exam_id=exam_id))
        finally:
            session_db.close()
    
    
    @bp.route('/<tenant_slug>/question-papers/<int:paper_id>/download')
    @require_school_auth
    def download_question_paper(tenant_slug, paper_id):
        """Download a question paper (only approved/final)"""
        session_db = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            paper = session_db.query(QuestionPaper).filter_by(id=paper_id).first()
            
            if not paper:
                flash('Question paper not found', 'error')
                return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
            
            # Verify tenant ownership through examination
            exam_subject = session_db.query(ExaminationSubject).filter_by(
                id=paper.examination_subject_id
            ).first()
            
            if not exam_subject:
                flash('Invalid question paper', 'error')
                return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
            
            examination = session_db.query(Examination).filter_by(
                id=exam_subject.examination_id,
                tenant_id=tenant_id
            ).first()
            
            if not examination:
                flash('Access denied', 'error')
                return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
            
            # Check if file exists
            if not os.path.exists(paper.file_path):
                flash('File not found on server', 'error')
                return redirect(url_for('school.question_papers_list', tenant_slug=tenant_slug, exam_id=examination.id))
            
            return send_file(
                paper.file_path,
                as_attachment=True,
                download_name=paper.file_name
            )
            
        except Exception as e:
            logger.error(f"Error in download_question_paper: {e}")
            flash('Error downloading file', 'error')
            return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    
    @bp.route('/<tenant_slug>/question-papers/<int:paper_id>/finalize', methods=['POST'])
    @require_school_auth
    def finalize_question_paper(tenant_slug, paper_id):
        """Mark an approved paper as final"""
        session_db = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            paper = session_db.query(QuestionPaper).filter_by(id=paper_id).first()
            
            if not paper:
                flash('Question paper not found', 'error')
                return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
            
            # Verify tenant and status
            exam_subject = session_db.query(ExaminationSubject).filter_by(
                id=paper.examination_subject_id
            ).first()
            
            examination = session_db.query(Examination).filter_by(
                id=exam_subject.examination_id,
                tenant_id=tenant_id
            ).first()
            
            if not examination:
                flash('Access denied', 'error')
                return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
            
            if paper.status != QuestionPaperStatus.APPROVED:
                flash('Only approved papers can be finalized', 'error')
                return redirect(url_for('school.question_papers_list', tenant_slug=tenant_slug, exam_id=examination.id))
            
            paper.status = QuestionPaperStatus.FINAL
            paper.finalized_at = datetime.utcnow()
            session_db.commit()
            
            flash('Question paper finalized successfully', 'success')
            return redirect(url_for('school.question_papers_list', tenant_slug=tenant_slug, exam_id=examination.id))
            
        except Exception as e:
            logger.error(f"Error in finalize_question_paper: {e}")
            session_db.rollback()
            flash('Error finalizing paper', 'error')
            return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    
    @bp.route('/<tenant_slug>/question-papers/<int:paper_id>/preview')
    @require_school_auth
    def preview_question_paper(tenant_slug, paper_id):
        """Preview question paper (inline PDF viewing)"""
        session_db = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            paper = session_db.query(QuestionPaper).filter_by(id=paper_id).first()
            
            if not paper:
                flash('Question paper not found', 'error')
                return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
            
            # Verify tenant ownership through examination
            exam_subject = session_db.query(ExaminationSubject).filter_by(
                id=paper.examination_subject_id
            ).first()
            
            if not exam_subject:
                flash('Invalid question paper', 'error')
                return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
            
            examination = session_db.query(Examination).filter_by(
                id=exam_subject.examination_id,
                tenant_id=tenant_id
            ).first()
            
            if not examination:
                flash('Access denied', 'error')
                return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
            
            # Check if file exists
            if not os.path.exists(paper.file_path):
                flash('File not found on server', 'error')
                return redirect(url_for('school.question_papers_list', tenant_slug=tenant_slug, exam_id=examination.id))
            
            # Only allow PDF preview
            if paper.file_type.lower() != 'pdf':
                flash('Preview only available for PDF files. Please download the file.', 'info')
                return redirect(url_for('school.download_question_paper', tenant_slug=tenant_slug, paper_id=paper_id))
            
            # Serve file inline for browser viewing
            return send_file(
                paper.file_path,
                as_attachment=False,  # Inline viewing
                mimetype='application/pdf'
            )
            
        except Exception as e:
            logger.error(f"Error in preview_question_paper: {e}")
            flash('Error previewing file', 'error')
            return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    
    @bp.route('/<tenant_slug>/examinations/<int:exam_id>/subjects/<int:subject_id>/reset-question-papers', methods=['POST'])
    @require_school_auth
    def reset_subject_question_papers(tenant_slug, exam_id, subject_id):
        """Reset/Delete all question papers and assignments for a subject - start fresh"""
        session_db = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Verify examination and subject ownership
            examination = session_db.query(Examination).filter_by(
                id=exam_id,
                tenant_id=tenant_id
            ).first()
            
            if not examination:
                flash('Examination not found', 'error')
                return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
            
            exam_subject = session_db.query(ExaminationSubject).filter_by(
                id=subject_id,
                examination_id=exam_id
            ).first()
            
            if not exam_subject:
                flash('Subject not found', 'error')
                return redirect(url_for('school.question_papers_list', tenant_slug=tenant_slug, exam_id=exam_id))
            
            # Get all question papers for this subject to delete files
            papers = session_db.query(QuestionPaper).filter_by(
                examination_subject_id=subject_id
            ).all()
            
            # Delete physical files from disk
            deleted_files = 0
            for paper in papers:
                try:
                    if os.path.exists(paper.file_path):
                        os.remove(paper.file_path)
                        deleted_files += 1
                except Exception as file_error:
                    logger.warning(f"Could not delete file {paper.file_path}: {file_error}")
            
            # Delete all question paper reviews (cascade will handle this, but being explicit)
            from question_paper_models import QuestionPaperReview
            session_db.query(QuestionPaperReview).filter(
                QuestionPaperReview.question_paper_id.in_([p.id for p in papers])
            ).delete(synchronize_session=False)
            
            # Delete all question papers for this subject
            deleted_papers = session_db.query(QuestionPaper).filter_by(
                examination_subject_id=subject_id
            ).delete()
            
            # Delete all teacher assignments (setters and reviewers)
            deleted_assignments = session_db.query(QuestionPaperAssignment).filter_by(
                examination_subject_id=subject_id
            ).delete()
            
            session_db.commit()
            
            subject_name = exam_subject.subject.name if exam_subject.subject else f"Subject #{subject_id}"
            flash(f'Successfully reset {subject_name}: Deleted {deleted_papers} paper(s), {deleted_assignments} assignment(s), and {deleted_files} file(s)', 'success')
            return redirect(url_for('school.question_papers_list', tenant_slug=tenant_slug, exam_id=exam_id))
            
        except Exception as e:
            logger.error(f"Error in reset_subject_question_papers: {e}")
            import traceback
            logger.error(traceback.format_exc())
            session_db.rollback()
            flash('Error resetting question papers', 'error')
            return redirect(url_for('school.question_papers_list', tenant_slug=tenant_slug, exam_id=exam_id))
        finally:
            session_db.close()


def _send_assignment_notifications(session_db, tenant_id, teacher_ids, examination, exam_subject, admin_comments, setter_deadline=None, reviewer_deadline=None):
    """Send notifications to teachers when assigned as setter/reviewer"""
    try:
        from notification_models import Notification, NotificationRecipient, NotificationStatusEnum, RecipientStatusEnum
        
        # Create notification message
        subject_name = exam_subject.subject.name if exam_subject.subject else f"Subject #{exam_subject.subject_id}"
        class_name = f"{exam_subject.class_ref.class_name} - {exam_subject.class_ref.section}" if exam_subject.class_ref else f"Class #{exam_subject.class_id}"
        
        title = f"Question Paper Assignment - {examination.exam_name}"
        message = f"""You have been assigned to work on the question paper for:

**Examination:** {examination.exam_name}
**Subject:** {subject_name}
**Class:** {class_name}"""

        # Add deadline info
        if setter_deadline:
            message += f"\n**Setter Deadline:** {setter_deadline.strftime('%b %d, %Y at %H:%M')}"
        if reviewer_deadline:
            message += f"\n**Reviewer Deadline:** {reviewer_deadline.strftime('%b %d, %Y at %H:%M')}"

        message += "\n\nPlease login to the teacher portal to view your assignment and upload/review the question paper."

        if admin_comments:
            message += f"\n\n**Admin Instructions:**\n{admin_comments}"
        
        # Create notification
        notification = Notification(
            tenant_id=tenant_id,
            title=title,
            message=message,
            status=NotificationStatusEnum.SENT,
            sent_at=datetime.utcnow(),
            created_by=current_user.id if current_user else None
        )
        session_db.add(notification)
        session_db.flush()
        
        # Add recipients
        for teacher_id in set(teacher_ids):  # Use set to avoid duplicates
            recipient = NotificationRecipient(
                notification_id=notification.id,
                teacher_id=teacher_id,
                status=RecipientStatusEnum.SENT,
                sent_at=datetime.utcnow()
            )
            session_db.add(recipient)
        
        session_db.commit()
        logger.info(f"Sent question paper assignment notifications to {len(teacher_ids)} teachers")
        
    except Exception as e:
        logger.error(f"Error sending assignment notifications: {e}")
        # Don't re-raise - notifications are not critical


def register_copy_checking_routes(bp, require_school_auth):
    """Register copy checking (marks entry) assignment routes to the school blueprint"""
    
    # ==================== COPY CHECKING SELECT EXAM (ADMIN) ====================
    
    @bp.route('/<tenant_slug>/copy-checking')
    @require_school_auth
    def copy_checking_select(tenant_slug):
        """Select an exam to manage copy checking assignments"""
        session_db = get_session()
        try:
            from examination_models import Examination, ExaminationSubject, MarkEntryStatus
            from copy_checking_models import CopyCheckingAssignment
            
            tenant_id = g.current_tenant.id
            
            # Get all examinations for this tenant
            examinations = session_db.query(Examination).filter_by(
                tenant_id=tenant_id
            ).order_by(Examination.start_date.desc()).all()
            
            # Build exam data with checking stats
            exams_data = []
            for exam in examinations:
                subjects = session_db.query(ExaminationSubject).filter_by(
                    examination_id=exam.id
                ).all()
                
                total_subjects = len(subjects)
                assigned_count = 0
                completed_count = 0
                
                for subj in subjects:
                    # Check if teacher assigned
                    assignment = session_db.query(CopyCheckingAssignment).filter_by(
                        examination_subject_id=subj.id
                    ).first()
                    if assignment:
                        assigned_count += 1
                    
                    # Check if marks entry completed
                    if subj.mark_entry_status in [MarkEntryStatus.COMPLETED, MarkEntryStatus.VERIFIED, MarkEntryStatus.PUBLISHED]:
                        completed_count += 1
                
                exams_data.append({
                    'exam': exam,
                    'total_subjects': total_subjects,
                    'assigned_count': assigned_count,
                    'completed_count': completed_count
                })
            
            return render_template(
                'akademi/examinations/copy_checking_select.html',
                exams_data=exams_data,
                school=g.current_tenant
            )
            
        except Exception as e:
            logger.error(f"Error in copy_checking_select for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error loading examinations', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    # ==================== COPY CHECKING LIST (ADMIN) ====================
    
    @bp.route('/<tenant_slug>/examinations/<int:exam_id>/copy-checking')
    @require_school_auth
    def copy_checking_list(tenant_slug, exam_id):
        """List all subjects for copy checking assignment"""
        session_db = get_session()
        try:
            from examination_models import Examination, ExaminationSubject, MarkEntryStatus
            from copy_checking_models import CopyCheckingAssignment
            
            tenant_id = g.current_tenant.id
            
            examination = session_db.query(Examination).filter_by(
                id=exam_id,
                tenant_id=tenant_id
            ).first()
            
            if not examination:
                flash('Examination not found', 'error')
                return redirect(url_for('school.copy_checking_select', tenant_slug=tenant_slug))
            
            # Get all exam subjects with assignments
            exam_subjects = session_db.query(ExaminationSubject).filter_by(
                examination_id=exam_id
            ).all()
            
            subjects_data = []
            for es in exam_subjects:
                assignment = session_db.query(CopyCheckingAssignment).filter_by(
                    examination_subject_id=es.id
                ).first()
                
                subjects_data.append({
                    'exam_subject': es,
                    'subject': es.subject,
                    'class_ref': es.class_ref,
                    'assignment': assignment,
                    'status': es.mark_entry_status
                })
            
            # Calculate stats
            total_subjects = len(exam_subjects)
            assigned_count = sum(1 for s in subjects_data if s['assignment'])
            completed_count = sum(1 for s in subjects_data if s['status'] in [MarkEntryStatus.COMPLETED, MarkEntryStatus.VERIFIED, MarkEntryStatus.PUBLISHED])
            
            stats = {
                'total_subjects': total_subjects,
                'assigned_count': assigned_count,
                'completed_count': completed_count
            }
            
            return render_template(
                'akademi/examinations/copy_checking_list.html',
                examination=examination,
                subjects_data=subjects_data,
                stats=stats,
                MarkEntryStatus=MarkEntryStatus,
                school=g.current_tenant
            )
            
        except Exception as e:
            logger.error(f"Error in copy_checking_list for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error loading copy checking list', 'error')
            return redirect(url_for('school.copy_checking_select', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    # ==================== ASSIGN COPY CHECKER (ADMIN) ====================
    
    @bp.route('/<tenant_slug>/examinations/<int:exam_id>/copy-checking/<int:subject_id>/assign', methods=['GET', 'POST'])
    @require_school_auth
    def assign_copy_checker(tenant_slug, exam_id, subject_id):
        """Assign a teacher as copy checker for a subject"""
        session_db = get_session()
        try:
            from examination_models import Examination, ExaminationSubject
            from copy_checking_models import CopyCheckingAssignment
            from teacher_models import Teacher, EmployeeStatusEnum
            
            tenant_id = g.current_tenant.id
            
            examination = session_db.query(Examination).filter_by(
                id=exam_id,
                tenant_id=tenant_id
            ).first()
            
            if not examination:
                flash('Examination not found', 'error')
                return redirect(url_for('school.copy_checking_select', tenant_slug=tenant_slug))
            
            exam_subject = session_db.query(ExaminationSubject).filter_by(
                id=subject_id,
                examination_id=exam_id
            ).first()
            
            if not exam_subject:
                flash('Subject not found', 'error')
                return redirect(url_for('school.copy_checking_list', tenant_slug=tenant_slug, exam_id=exam_id))
            
            if request.method == 'POST':
                teacher_id = request.form.get('teacher_id', type=int)
                deadline_str = request.form.get('deadline', '').strip()
                admin_comments = request.form.get('admin_comments', '').strip()
                
                # Parse deadline
                deadline = None
                if deadline_str:
                    try:
                        deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
                    except ValueError:
                        try:
                            deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
                        except ValueError:
                            pass
                
                # Clear existing assignment
                session_db.query(CopyCheckingAssignment).filter_by(
                    examination_subject_id=subject_id
                ).delete()
                
                # Create new assignment if teacher selected
                if teacher_id:
                    assignment = CopyCheckingAssignment(
                        examination_subject_id=subject_id,
                        teacher_id=teacher_id,
                        deadline=deadline,
                        admin_comments=admin_comments,
                        assigned_by=current_user.id
                    )
                    session_db.add(assignment)
                    
                    # Send notification
                    try:
                        _send_copy_checking_notification(
                            session_db, tenant_id, teacher_id,
                            examination, exam_subject, deadline, admin_comments
                        )
                    except Exception as notif_error:
                        logger.error(f"Error sending notification: {notif_error}")
                
                session_db.commit()
                flash('Copy checker assigned successfully', 'success')
                return redirect(url_for('school.copy_checking_list', tenant_slug=tenant_slug, exam_id=exam_id))
            
            # GET request - show form
            teachers = session_db.query(Teacher).filter_by(
                tenant_id=tenant_id
            ).filter(
                Teacher.employee_status.in_(['Active', 'ACTIVE'])
            ).order_by(Teacher.first_name).all()
            
            # Get current assignment
            current_assignment = session_db.query(CopyCheckingAssignment).filter_by(
                examination_subject_id=subject_id
            ).first()
            
            return render_template(
                'akademi/examinations/assign_checker.html',
                examination=examination,
                exam_subject=exam_subject,
                teachers=teachers,
                current_assignment=current_assignment,
                school=g.current_tenant
            )
            
        except Exception as e:
            logger.error(f"Error in assign_copy_checker for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error assigning copy checker', 'error')
            session_db.rollback()
            return redirect(url_for('school.copy_checking_list', tenant_slug=tenant_slug, exam_id=exam_id))
        finally:
            session_db.close()


def _send_copy_checking_notification(session_db, tenant_id, teacher_id, examination, exam_subject, deadline, admin_comments):
    """Send notification to teacher when assigned for copy checking"""
    try:
        from notification_models import Notification, NotificationRecipient, NotificationStatusEnum, RecipientStatusEnum, RecipientTypeEnum
        
        subject_name = exam_subject.subject.name if exam_subject.subject else f"Subject #{exam_subject.subject_id}"
        class_name = f"{exam_subject.class_ref.class_name} - {exam_subject.class_ref.section}" if exam_subject.class_ref else f"Class #{exam_subject.class_id}"
        
        title = f"Copy Checking Assignment - {examination.exam_name}"
        message = f"""You have been assigned for copy checking (marks entry):

**Examination:** {examination.exam_name}
**Subject:** {subject_name}
**Class:** {class_name}"""

        if deadline:
            message += f"\n**Deadline:** {deadline.strftime('%b %d, %Y at %H:%M')}"

        message += "\n\nPlease login to the teacher portal to enter marks."

        if admin_comments:
            message += f"\n\n**Admin Instructions:**\n{admin_comments}"
        
        notification = Notification(
            tenant_id=tenant_id,
            title=title,
            message=message,
            recipient_type=RecipientTypeEnum.SPECIFIC_TEACHERS,
            status=NotificationStatusEnum.SENT,
            sent_at=datetime.utcnow(),
            created_by=current_user.id if current_user else None
        )
        session_db.add(notification)
        session_db.flush()
        
        recipient = NotificationRecipient(
            tenant_id=tenant_id,
            notification_id=notification.id,
            teacher_id=teacher_id,
            status=RecipientStatusEnum.SENT,
            sent_at=datetime.utcnow()
        )
        session_db.add(recipient)
        
        session_db.commit()
        logger.info(f"Sent copy checking notification to teacher {teacher_id}")
        
    except Exception as e:
        logger.error(f"Error sending copy checking notification: {e}")
