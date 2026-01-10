"""
Examination Routes for School ERP
Integrated into school blueprint
"""
from flask import render_template, request, redirect, url_for, flash, g, jsonify
from flask_login import current_user
from sqlalchemy import and_, or_, func, desc
from datetime import datetime, date
import logging

from db_single import get_session
from examination_models import (
    Examination, ExaminationSubject, ExaminationSchedule,
    ExaminationMark, ExaminationResult,
    ExaminationType, ExaminationStatus, MarkEntryStatus
)
from models import Class, AcademicSession
from teacher_models import Subject

logger = logging.getLogger(__name__)


def register_examination_routes(bp, require_school_auth):
    """Register all examination routes to the school blueprint"""
    
    # ==================== EXAMINATION LIST ====================
    @bp.route('/<tenant_slug>/examinations')
    @require_school_auth
    def examinations_list(tenant_slug):
        """List all examinations"""
        session_db = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Get filter parameters
            status_filter = request.args.get('status', 'all')
            class_filter = request.args.get('class_id', type=int)
            session_filter = request.args.get('session_id', type=int)
            search = request.args.get('search', '').strip()
            
            # Base query
            query = session_db.query(Examination).filter_by(tenant_id=tenant_id)
            
            # Apply filters
            if status_filter != 'all':
                try:
                    status_enum = ExaminationStatus[status_filter.upper()]
                    query = query.filter_by(status=status_enum)
                except KeyError:
                    pass
            
            if class_filter:
                # Filter examinations that have subjects for this class
                query = query.join(ExaminationSubject).filter(ExaminationSubject.class_id == class_filter)
            
            if session_filter:
                query = query.filter_by(academic_session_id=session_filter)
            
            if search:
                query = query.filter(
                    or_(
                        Examination.exam_name.ilike(f'%{search}%'),
                        Examination.exam_code.ilike(f'%{search}%')
                    )
                )
            
            # Get examinations
            examinations = query.order_by(desc(Examination.start_date)).all()
            
            # Get classes and sessions for filters
            classes = session_db.query(Class).filter_by(tenant_id=tenant_id).order_by(Class.class_name).all()
            sessions = session_db.query(AcademicSession).filter_by(tenant_id=tenant_id).order_by(desc(AcademicSession.session_name)).all()
            
            # Calculate statistics
            total_exams = len(examinations)
            upcoming = sum(1 for e in examinations if e.status == ExaminationStatus.SCHEDULED)
            ongoing = sum(1 for e in examinations if e.status == ExaminationStatus.ONGOING)
            completed = sum(1 for e in examinations if e.status == ExaminationStatus.COMPLETED)
            
            stats = {
                'total': total_exams,
                'upcoming': upcoming,
                'ongoing': ongoing,
                'completed': completed
            }
            
            return render_template(
                'akademi/examinations/list.html',
                school=g.current_tenant,
                examinations=examinations,
                classes=classes,
                sessions=sessions,
                stats=stats,
                status_filter=status_filter,
                class_filter=class_filter,
                session_filter=session_filter,
                search=search,
                ExaminationStatus=ExaminationStatus,
                current_date=date.today()
            )
            
        except Exception as e:
            logger.error(f"Error in examinations_list for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error loading examinations', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    
    # ==================== ADD EXAMINATION ====================
    @bp.route('/<tenant_slug>/examinations/add', methods=['GET', 'POST'])
    @require_school_auth
    def examinations_add(tenant_slug):
        """Add new examination"""
        session_db = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            if request.method == 'POST':
                # Get form data
                exam_name = request.form.get('exam_name')
                exam_code = request.form.get('exam_code')
                exam_type = request.form.get('exam_type')
                academic_session_id = request.form.get('academic_session_id', type=int)
                start_date = request.form.get('start_date')
                end_date = request.form.get('end_date')
                result_date = request.form.get('result_date')
                total_marks = request.form.get('total_marks', type=int)
                passing_marks = request.form.get('passing_marks', type=int)
                status = request.form.get('status', 'DRAFT')
                description = request.form.get('description')
                instructions = request.form.get('instructions')
                
                # Validation
                if not all([exam_name, exam_type, academic_session_id, start_date, end_date]):
                    flash('Please fill all required fields', 'error')
                    return redirect(request.url)
                
                # Parse dates for validation
                try:
                    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                    result_date_obj = datetime.strptime(result_date, '%Y-%m-%d').date() if result_date else None
                except ValueError:
                    flash('Invalid date format', 'error')
                    return redirect(request.url)
                
                # Validate date logic
                if end_date_obj < start_date_obj:
                    flash('End date cannot be before start date', 'error')
                    return redirect(request.url)
                
                if result_date_obj and result_date_obj < end_date_obj:
                    flash('Result date should be after or equal to end date', 'error')
                    return redirect(request.url)
                
                # Create examination
                examination = Examination(
                    tenant_id=tenant_id,
                    academic_session_id=academic_session_id,
                    exam_name=exam_name,
                    exam_code=exam_code,
                    exam_type=ExaminationType[exam_type],
                    start_date=start_date_obj,
                    end_date=end_date_obj,
                    result_date=result_date_obj,
                    total_marks=total_marks or 100,
                    passing_marks=passing_marks or 35,
                    description=description,
                    instructions=instructions,
                    status=ExaminationStatus[status],
                    created_by=current_user.id
                )
                
                session_db.add(examination)
                session_db.commit()
                
                flash(f'Examination "{exam_name}" created successfully', 'success')
                return redirect(url_for('school.examinations_detail', tenant_slug=tenant_slug, exam_id=examination.id))
            
            # GET request - show form
            sessions = session_db.query(AcademicSession).filter_by(
                tenant_id=tenant_id
            ).order_by(desc(AcademicSession.session_name)).all()
            
            classes = session_db.query(Class).filter_by(
                tenant_id=tenant_id
            ).order_by(Class.class_name).all()
            
            return render_template(
                'akademi/examinations/add.html',
                school=g.current_tenant,
                sessions=sessions,
                academic_sessions=sessions,
                classes=classes,
                ExaminationType=ExaminationType
            )
            
        except Exception as e:
            logger.error(f"Error in examinations_add for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error creating examination', 'error')
            session_db.rollback()
            return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    
    # ==================== EXAMINATION DETAIL ====================
    @bp.route('/<tenant_slug>/examinations/<int:exam_id>')
    @require_school_auth
    def examinations_detail(tenant_slug, exam_id):
        """View examination details"""
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
            
            # Get subjects with their details
            exam_subjects = session_db.query(ExaminationSubject).filter_by(
                examination_id=exam_id
            ).all()
            
            # Get schedules
            schedules = session_db.query(ExaminationSchedule).filter_by(
                examination_id=exam_id
            ).order_by(ExaminationSchedule.exam_date, ExaminationSchedule.start_time).all()
            
            # Calculate statistics
            total_subjects = len(exam_subjects)
            marks_completed = sum(1 for es in exam_subjects if es.mark_entry_status == MarkEntryStatus.COMPLETED)
            marks_verified = sum(1 for es in exam_subjects if es.mark_entry_status == MarkEntryStatus.VERIFIED)
            
            stats = {
                'total_subjects': total_subjects,
                'marks_completed': marks_completed,
                'marks_verified': marks_verified,
                'schedules_count': len(schedules)
            }
            
            return render_template(
                'akademi/examinations/detail.html',
                examination=examination,
                exam_subjects=exam_subjects,
                schedules=schedules,
                stats=stats,
                ExaminationStatus=ExaminationStatus,
                MarkEntryStatus=MarkEntryStatus,
                school=g.current_tenant
            )
            
        except Exception as e:
            logger.error(f"Error in examinations_detail for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error loading examination details', 'error')
            return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    
    # ==================== EDIT EXAMINATION ====================
    @bp.route('/<tenant_slug>/examinations/<int:exam_id>/edit', methods=['GET', 'POST'])
    @require_school_auth
    def examinations_edit(tenant_slug, exam_id):
        """Edit examination"""
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
            
            if request.method == 'POST':
                # Update examination
                examination.exam_name = request.form.get('exam_name')
                examination.exam_code = request.form.get('exam_code')
                examination.exam_type = ExaminationType[request.form.get('exam_type')]
                examination.academic_session_id = request.form.get('academic_session_id', type=int)
                
                start_date = request.form.get('start_date')
                end_date = request.form.get('end_date')
                result_date = request.form.get('result_date')
                
                # Parse and validate dates
                try:
                    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                    result_date_obj = datetime.strptime(result_date, '%Y-%m-%d').date() if result_date else None
                except ValueError:
                    flash('Invalid date format', 'error')
                    return redirect(request.url)
                
                # Validate date logic
                if end_date_obj < start_date_obj:
                    flash('End date cannot be before start date', 'error')
                    return redirect(request.url)
                
                if result_date_obj and result_date_obj < end_date_obj:
                    flash('Result date should be after or equal to end date', 'error')
                    return redirect(request.url)
                
                examination.start_date = start_date_obj
                examination.end_date = end_date_obj
                examination.result_date = result_date_obj
                
                examination.total_marks = request.form.get('total_marks', type=int)
                examination.passing_marks = request.form.get('passing_marks', type=int)
                examination.description = request.form.get('description')
                examination.instructions = request.form.get('instructions')
                
                # Update status if provided
                status = request.form.get('status')
                if status:
                    examination.status = ExaminationStatus[status]
                
                examination.updated_at = datetime.utcnow()
                
                session_db.commit()
                
                flash('Examination updated successfully', 'success')
                return redirect(url_for('school.examinations_detail', tenant_slug=tenant_slug, exam_id=exam_id))
            
            # GET request
            academic_sessions = session_db.query(AcademicSession).filter_by(
                tenant_id=tenant_id
            ).order_by(desc(AcademicSession.session_name)).all()
            
            return render_template(
                'akademi/examinations/edit.html',
                school=g.current_tenant,
                examination=examination,
                academic_sessions=academic_sessions,
                ExaminationType=ExaminationType
            )
            
        except Exception as e:
            logger.error(f"Error in examinations_edit for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error updating examination', 'error')
            session_db.rollback()
            return redirect(url_for('school.examinations_detail', tenant_slug=tenant_slug, exam_id=exam_id))
        finally:
            session_db.close()
    
    
    # ==================== DELETE EXAMINATION ====================
    @bp.route('/<tenant_slug>/examinations/<int:exam_id>/delete', methods=['POST'])
    @require_school_auth
    def examinations_delete(tenant_slug, exam_id):
        """Delete examination"""
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
            
            exam_name = examination.exam_name
            session_db.delete(examination)
            session_db.commit()
            
            flash(f'Examination "{exam_name}" deleted successfully', 'success')
            
        except Exception as e:
            logger.error(f"Error in examinations_delete for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error deleting examination', 'error')
            session_db.rollback()
        finally:
            session_db.close()
        
        return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
    
    
    # ==================== BULK ADD SUBJECTS ====================
    @bp.route('/<tenant_slug>/examinations/<int:exam_id>/subjects/bulk-add', methods=['GET', 'POST'])
    @require_school_auth
    def examinations_bulk_add_subjects(tenant_slug, exam_id):
        """Bulk add subjects to examination for multiple classes"""
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
            
            if request.method == 'POST':
                # Process bulk add
                added_count = 0
                skipped_count = 0
                errors = []
                
                for key in request.form.keys():
                    if key.startswith('subjects_'):
                        class_id = int(key.split('_')[1])
                        subject_ids = request.form.getlist(key)
                        
                        for subject_id in subject_ids:
                            try:
                                subject_id = int(subject_id)
                                
                                # Check if already exists
                                existing = session_db.query(ExaminationSubject).filter_by(
                                    examination_id=exam_id,
                                    class_id=class_id,
                                    subject_id=subject_id
                                ).first()
                                
                                if existing:
                                    skipped_count += 1
                                    continue
                                
                                # Get marks values
                                theory_marks = request.form.get(f'theory_{class_id}_{subject_id}', type=int, default=0)
                                practical_marks = request.form.get(f'practical_{class_id}_{subject_id}', type=int, default=0)
                                total_marks = request.form.get(f'total_{class_id}_{subject_id}', type=int, default=100)
                                passing_marks = request.form.get(f'passing_{class_id}_{subject_id}', type=int, default=35)
                                
                                # Create examination subject
                                exam_subject = ExaminationSubject(
                                    examination_id=exam_id,
                                    class_id=class_id,
                                    subject_id=subject_id,
                                    theory_marks=theory_marks,
                                    practical_marks=practical_marks,
                                    internal_marks=0,
                                    total_marks=total_marks,
                                    passing_marks=passing_marks
                                )
                                
                                session_db.add(exam_subject)
                                added_count += 1
                                
                            except ValueError as e:
                                errors.append(f'Invalid subject ID format')
                                logger.error(f"ValueError in bulk add: {e}")
                            except Exception as e:
                                errors.append(f'Error adding subject to class {class_id}')
                                logger.error(f"Error in bulk add subject {subject_id}: {e}")
                
                # Commit only if there were successful additions
                if added_count > 0:
                    try:
                        session_db.commit()
                    except Exception as e:
                        session_db.rollback()
                        logger.error(f"Error committing bulk add: {e}")
                        flash('Error saving subjects to database. Please try again.', 'error')
                        return redirect(url_for('school.examinations_detail', tenant_slug=tenant_slug, exam_id=exam_id))
                
                # Build appropriate flash messages
                if added_count > 0:
                    flash(f'Successfully added {added_count} subject(s) to examination', 'success')
                if skipped_count > 0:
                    flash(f'{skipped_count} subject(s) were already added and skipped', 'info')
                if errors:
                    for error in errors[:5]:  # Show first 5 errors
                        flash(error, 'warning')
                    if len(errors) > 5:
                        flash(f'...and {len(errors) - 5} more errors', 'warning')
                
                if added_count == 0 and not errors:
                    flash('No new subjects were added', 'info')
                
                return redirect(url_for('school.examinations_detail', tenant_slug=tenant_slug, exam_id=exam_id))
            
            # GET - show form
            class_ids_str = request.args.get('classes', '')
            if class_ids_str:
                class_ids = [int(cid) for cid in class_ids_str.split(',')]
                selected_classes = session_db.query(Class).filter(
                    Class.id.in_(class_ids),
                    Class.tenant_id == tenant_id
                ).order_by(Class.class_name).all()
            else:
                selected_classes = session_db.query(Class).filter_by(
                    tenant_id=tenant_id
                ).order_by(Class.class_name).all()
            
            all_subjects = session_db.query(Subject).filter_by(tenant_id=tenant_id, is_active=True).order_by(Subject.name).all()
            
            # Show error if no subjects found - never query without tenant filter
            if not all_subjects:
                flash('No subjects found for your school. Please add subjects first before configuring examinations.', 'warning')
            
            return render_template(
                'akademi/examinations/bulk_add_subjects.html',
                examination=examination,
                selected_classes=selected_classes,
                all_subjects=all_subjects,
                school=g.current_tenant
            )
            
        except Exception as e:
            logger.error(f"Error in examinations_bulk_add_subjects for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            session_db.rollback()
            flash('Error adding subjects', 'error')
            return redirect(url_for('school.examinations_detail', tenant_slug=tenant_slug, exam_id=exam_id))
        finally:
            session_db.close()
    
    
    # ==================== ADD SUBJECT TO EXAMINATION ====================
    @bp.route('/<tenant_slug>/examinations/<int:exam_id>/subjects/add', methods=['GET', 'POST'])
    @require_school_auth
    def examinations_add_subject(tenant_slug, exam_id):
        """Add subject(s) to examination - supports multiple subject selection"""
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
            
            if request.method == 'POST':
                class_id = request.form.get('class_id', type=int)
                # Get multiple subject IDs from the form
                subject_ids = request.form.getlist('subject_ids')
                theory_marks = request.form.get('theory_marks', type=int, default=0)
                practical_marks = request.form.get('practical_marks', type=int, default=0)
                total_marks = request.form.get('total_marks', type=int)
                passing_marks = request.form.get('passing_marks', type=int)
                
                if not class_id:
                    flash('Please select a class', 'error')
                    return redirect(request.url)
                
                if not subject_ids:
                    flash('Please select at least one subject', 'error')
                    return redirect(request.url)
                
                added_count = 0
                skipped_count = 0
                
                for subject_id in subject_ids:
                    subject_id = int(subject_id)
                    
                    # Check if subject already added for this class
                    existing = session_db.query(ExaminationSubject).filter_by(
                        examination_id=exam_id,
                        subject_id=subject_id,
                        class_id=class_id
                    ).first()
                    
                    if existing:
                        skipped_count += 1
                        continue
                    
                    # Create examination subject
                    exam_subject = ExaminationSubject(
                        examination_id=exam_id,
                        subject_id=subject_id,
                        class_id=class_id,
                        theory_marks=theory_marks,
                        practical_marks=practical_marks,
                        internal_marks=0,
                        total_marks=total_marks,
                        passing_marks=passing_marks
                    )
                    
                    session_db.add(exam_subject)
                    added_count += 1
                
                session_db.commit()
                
                # Build appropriate flash message
                if added_count > 0 and skipped_count > 0:
                    flash(f'Successfully added {added_count} subject(s). {skipped_count} subject(s) were already added and skipped.', 'success')
                elif added_count > 0:
                    flash(f'Successfully added {added_count} subject(s) to the examination', 'success')
                else:
                    flash('All selected subjects were already added to this examination', 'warning')
                
                return redirect(url_for('school.examinations_detail', tenant_slug=tenant_slug, exam_id=exam_id))
            
            # GET request
            classes = session_db.query(Class).filter_by(tenant_id=tenant_id).order_by(Class.class_name).all()
            
            # Get subjects - with proper tenant isolation
            subjects = session_db.query(Subject).filter_by(tenant_id=tenant_id, is_active=True).order_by(Subject.name).all()
            
            # Show error if no subjects found - never query without tenant filter
            if not subjects:
                flash('No subjects found for your school. Please add subjects first before adding them to examinations.', 'warning')
            
            exam_subjects = session_db.query(ExaminationSubject).filter_by(examination_id=exam_id).all()
            
            # Load subject details for display
            for es in exam_subjects:
                if not hasattr(es, 'subject') or es.subject is None:
                    subject = session_db.query(Subject).filter_by(id=es.subject_id).first()
                    es.subject = subject
            
            return render_template(
                'akademi/examinations/add_subject.html',
                examination=examination,
                classes=classes,
                subjects=subjects,
                exam_subjects=exam_subjects,
                school=g.current_tenant
            )
            
        except Exception as e:
            logger.error(f"Error in examinations_add_subject for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error adding subject', 'error')
            session_db.rollback()
            return redirect(url_for('school.examinations_detail', tenant_slug=tenant_slug, exam_id=exam_id))
        finally:
            session_db.close()
    

    
    # ==================== DELETE SUBJECT FROM EXAMINATION ====================
    @bp.route('/<tenant_slug>/examinations/<int:exam_id>/subjects/<int:subject_id>/delete', methods=['POST'])
    @require_school_auth
    def delete_examination_subject(tenant_slug, exam_id, subject_id):
        """Delete a subject from examination"""
        session_db = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Verify examination belongs to tenant
            examination = session_db.query(Examination).filter_by(
                id=exam_id,
                tenant_id=tenant_id
            ).first()
            
            if not examination:
                flash('Examination not found', 'error')
                return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
            
            # Find the examination subject
            exam_subject = session_db.query(ExaminationSubject).filter_by(
                id=subject_id,
                examination_id=exam_id
            ).first()
            
            if not exam_subject:
                flash('Subject not found in this examination', 'error')
                return redirect(url_for('school.examinations_detail', tenant_slug=tenant_slug, exam_id=exam_id))
            
            # Delete associated marks first
            deleted_marks = session_db.query(ExaminationMark).filter_by(
                examination_subject_id=subject_id
            ).delete()
            
            # Delete the examination subject
            session_db.delete(exam_subject)
            session_db.commit()
            
            if deleted_marks > 0:
                flash(f'Subject removed from examination. {deleted_marks} mark entries were also deleted.', 'success')
            else:
                flash('Subject removed from examination successfully', 'success')
            
            # Redirect back to the referring page or detail page
            referer = request.referrer
            if referer and 'configure' in referer:
                return redirect(url_for('school.examination_subjects_config', tenant_slug=tenant_slug, exam_id=exam_id))
            
            return redirect(url_for('school.examinations_detail', tenant_slug=tenant_slug, exam_id=exam_id))
            
        except Exception as e:
            logger.error(f"Error in delete_examination_subject for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error deleting subject from examination', 'error')
            session_db.rollback()
            return redirect(url_for('school.examinations_detail', tenant_slug=tenant_slug, exam_id=exam_id))
        finally:
            session_db.close()
    
    
    # ==================== MARKS ENTRY ====================
    @bp.route('/<tenant_slug>/examinations/<int:exam_id>/marks', methods=['GET', 'POST'])
    @require_school_auth
    def examinations_marks(tenant_slug, exam_id):
        """Enter marks for examination"""
        logger.info(f"[EXAMINATIONS_MARKS] ========== ROUTE CALLED ==========")
        logger.info(f"[EXAMINATIONS_MARKS] tenant_slug={tenant_slug}, exam_id={exam_id}")
        logger.info(f"[EXAMINATIONS_MARKS] Query params: {dict(request.args)}")
        
        session_db = get_session()
        try:
            tenant_id = g.current_tenant.id
            logger.info(f"[EXAMINATIONS_MARKS] tenant_id={tenant_id}")
            
            examination = session_db.query(Examination).filter_by(
                id=exam_id,
                tenant_id=tenant_id
            ).first()
            
            if not examination:
                flash('Examination not found', 'error')
                return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
            
            if request.method == 'POST':
                # Check if it's JSON data (from AJAX)
                if request.is_json:
                    data = request.get_json()
                    exam_subject_id = data.get('exam_subject_id')
                    marks_data_list = data.get('marks_data', [])
                    
                    for mark_data in marks_data_list:
                        student_id = int(mark_data['student_id'])
                        theory = mark_data.get('theory_marks')
                        practical = mark_data.get('practical_marks')
                        is_absent = mark_data.get('is_absent', False)
                        
                        # Convert to float if not None, otherwise keep as None
                        theory = float(theory) if theory is not None else None
                        practical = float(practical) if practical is not None else None
                        
                        # Check if mark entry exists
                        mark_entry = session_db.query(ExaminationMark).filter_by(
                            examination_id=exam_id,
                            examination_subject_id=exam_subject_id,
                            student_id=student_id
                        ).first()
                        
                        if mark_entry:
                            # Update existing
                            mark_entry.theory_marks_obtained = theory
                            mark_entry.practical_marks_obtained = practical
                            mark_entry.internal_marks_obtained = 0
                            mark_entry.is_absent = is_absent
                            mark_entry.updated_at = datetime.utcnow()
                        else:
                            # Create new
                            mark_entry = ExaminationMark(
                                examination_id=exam_id,
                                examination_subject_id=exam_subject_id,
                                student_id=student_id,
                                theory_marks_obtained=theory,
                                practical_marks_obtained=practical,
                                internal_marks_obtained=0,
                                is_absent=is_absent,
                                entered_by=current_user.id,
                                entered_at=datetime.utcnow()
                            )
                            session_db.add(mark_entry)
                        
                        # Calculate total and pass status
                        mark_entry.calculate_total()
                        exam_subject = session_db.query(ExaminationSubject).get(exam_subject_id)
                        if exam_subject:
                            mark_entry.check_pass_status(exam_subject.passing_marks)
                    
                    # Flush to ensure marks are saved before counting
                    session_db.flush()
                    
                    # Update ExaminationSubject status based on mark completion
                    exam_subject = session_db.query(ExaminationSubject).get(exam_subject_id)
                    if exam_subject:
                        # Get the class for this exam subject
                        from models import Student, StudentStatusEnum
                        
                        # Count students with marks entered for this exam subject
                        students_with_marks = session_db.query(ExaminationMark).filter_by(
                            examination_subject_id=exam_subject_id
                        ).count()
                        
                        # Count total active students in this class
                        # Using a single query to avoid race conditions
                        total_active_students = session_db.query(Student).filter(
                            Student.class_id == exam_subject.class_id,
                            Student.status == StudentStatusEnum.ACTIVE
                        ).count()
                        
                        # Set status based on completion
                        # Only mark as COMPLETED if marks are entered for ALL active students
                        if total_active_students > 0:
                            if students_with_marks >= total_active_students:
                                exam_subject.mark_entry_status = MarkEntryStatus.COMPLETED
                                logger.info(f"Updated exam_subject {exam_subject_id} status to COMPLETED ({students_with_marks}/{total_active_students})")
                            elif students_with_marks > 0:
                                exam_subject.mark_entry_status = MarkEntryStatus.IN_PROGRESS
                                logger.info(f"Updated exam_subject {exam_subject_id} status to IN_PROGRESS ({students_with_marks}/{total_active_students})")
                        else:
                            # No active students in class - keep as PENDING
                            logger.warning(f"No active students found in class {exam_subject.class_id} for exam_subject {exam_subject_id}")
                    
                    session_db.commit()
                    return jsonify({'success': True, 'message': 'Marks saved successfully'})
                else:
                    return jsonify({'success': False, 'error': 'Invalid request format'}), 400
            
            # GET request
            # Get classes that have subjects configured for this exam
            classes = session_db.query(Class).join(
                ExaminationSubject, 
                Class.id == ExaminationSubject.class_id
            ).filter(
                ExaminationSubject.examination_id == exam_id,
                Class.tenant_id == tenant_id
            ).distinct().order_by(Class.class_name).all()
            
            # Get selected class
            selected_class_id = request.args.get('class_id', type=int)
            
            # Get exam subjects - filter by class if selected
            if selected_class_id:
                exam_subjects = session_db.query(ExaminationSubject).filter_by(
                    examination_id=exam_id,
                    class_id=selected_class_id
                ).all()
            else:
                exam_subjects = session_db.query(ExaminationSubject).filter_by(
                    examination_id=exam_id
                ).all()
            
            # Load subject details for each exam_subject (for dropdown)
            logger.info(f"[EXAMINATIONS_MARKS] Loading subjects for {len(exam_subjects)} exam_subjects")
            for es in exam_subjects:
                if not hasattr(es, 'subject') or es.subject is None:
                    subject = session_db.query(Subject).filter_by(id=es.subject_id).first()
                    es.subject = subject
                    if subject:
                        logger.info(f"[EXAMINATIONS_MARKS] Dropdown - Loaded subject: id={subject.id}, name={subject.name}")
            
            # Get selected subject
            selected_subject_id = request.args.get('subject_id', type=int)
            selected_exam_subject = None
            
            logger.info(f"[EXAMINATIONS_MARKS] selected_subject_id from query params: {selected_subject_id}")
            
            if selected_subject_id:
                selected_exam_subject = session_db.query(ExaminationSubject).get(selected_subject_id)
                logger.info(f"[EXAMINATIONS_MARKS] ExaminationSubject query result: {selected_exam_subject}")
            else:
                logger.warning(f"[EXAMINATIONS_MARKS] No subject_id in query params!")
            
            students = []
            marks_dict = {}
            
            if selected_exam_subject:
                # Load subject details if not already loaded
                logger.info(f"[EXAMINATIONS_MARKS] ========== MARKS ENTRY DEBUG ==========")
                logger.info(f"[EXAMINATIONS_MARKS] selected_exam_subject.id={selected_exam_subject.id}")
                logger.info(f"[EXAMINATIONS_MARKS] selected_exam_subject.subject_id={selected_exam_subject.subject_id}")
                logger.info(f"[EXAMINATIONS_MARKS] selected_exam_subject.class_id={selected_exam_subject.class_id}")
                logger.info(f"[EXAMINATIONS_MARKS] tenant_id={tenant_id}")
                
                subject = session_db.query(Subject).filter_by(id=selected_exam_subject.subject_id).first()
                if subject:
                    selected_exam_subject.subject = subject
                    logger.info(f"[EXAMINATIONS_MARKS] ✓ Subject loaded: id={subject.id}, name={subject.name}")
                else:
                    logger.error(f"[EXAMINATIONS_MARKS] ✗ Subject NOT FOUND for subject_id={selected_exam_subject.subject_id}")
                
                # Get students for this class
                from models import Student
                
                logger.info(f"[EXAMINATIONS_MARKS] Querying students with:")
                logger.info(f"[EXAMINATIONS_MARKS]   - tenant_id={tenant_id}")
                logger.info(f"[EXAMINATIONS_MARKS]   - class_id={selected_exam_subject.class_id}")
                
                # Get all students in the class (don't filter by status)
                students = session_db.query(Student).filter(
                    Student.tenant_id == tenant_id,
                    Student.class_id == selected_exam_subject.class_id
                ).order_by(Student.roll_number, Student.full_name).all()
                
                logger.info(f"[EXAMINATIONS_MARKS] ✓ Query executed. Found {len(students)} students")
                
                if students:
                    logger.info(f"[EXAMINATIONS_MARKS] Students found:")
                    for idx, student in enumerate(students):
                        logger.info(f"[EXAMINATIONS_MARKS]   {idx+1}. ID={student.id}, Roll={student.roll_number}, Name={student.full_name}, Class={student.class_id}, Tenant={student.tenant_id}")
                else:
                    flash(f'No students found in class {selected_exam_subject.class_ref.class_name}. Please add students to this class first.', 'warning')
                    logger.error(f"[EXAMINATIONS_MARKS] No students at all in class_id={selected_exam_subject.class_id} for tenant_id={tenant_id}")
                
                # Get existing marks
                marks_entries = session_db.query(ExaminationMark).filter_by(
                    examination_id=exam_id,
                    examination_subject_id=selected_exam_subject.id
                ).all()
                
                # Convert to dict with proper structure for template
                for mark in marks_entries:
                    marks_dict[mark.student_id] = {
                        'theory_marks_obtained': mark.theory_marks_obtained,
                        'practical_marks_obtained': mark.practical_marks_obtained,
                        'total_marks_obtained': mark.total_marks_obtained,
                        'is_absent': mark.is_absent,
                        'grade': mark.grade or ''
                    }
            
            return render_template(
                'akademi/examinations/marks.html',
                school=g.current_tenant,
                examination=examination,
                classes=classes,
                selected_class_id=selected_class_id,
                exam_subjects=exam_subjects,
                selected_subject_id=selected_subject_id,
                selected_exam_subject=selected_exam_subject,
                students=students,
                marks_dict=marks_dict
            )
            
        except Exception as e:
            logger.error(f"Error in examinations_marks for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error loading marks entry', 'error')
            session_db.rollback()
            return redirect(url_for('school.examinations_detail', tenant_slug=tenant_slug, exam_id=exam_id))
        finally:
            session_db.close()
    
    
    # ==================== EXAMINATION RESULTS ====================
    @bp.route('/<tenant_slug>/examinations/<int:exam_id>/results')
    @require_school_auth
    def examinations_results(tenant_slug, exam_id):
        """View examination results"""
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
            
            # Get results
            results = session_db.query(ExaminationResult).filter_by(
                examination_id=exam_id
            ).order_by(ExaminationResult.rank).all()
            
            # Manually load student data for each result
            from models import Student
            student_ids = [r.student_id for r in results]
            students = session_db.query(Student).filter(Student.id.in_(student_ids)).all()
            students_dict = {s.id: s for s in students}
            
            logger.info(f"Loading {len(results)} results, found {len(students)} students")
            
            # Attach student to each result
            for result in results:
                result.student = students_dict.get(result.student_id)
                if result.student:
                    logger.info(f"Result {result.id}: Student {result.student.first_name} {result.student.last_name}")
                else:
                    logger.warning(f"Result {result.id}: No student found for student_id {result.student_id}")
            
            # Get class filter
            class_filter = request.args.get('class_id', type=int)
            if class_filter:
                results = [r for r in results if r.class_id == class_filter]
            
            # Get status filter
            status_filter = request.args.get('status', '')
            if status_filter == 'passed':
                results = [r for r in results if r.is_passed]
            elif status_filter == 'failed':
                results = [r for r in results if not r.is_passed]
            
            # Calculate statistics
            total_students = len(results)
            passed = sum(1 for r in results if r.is_passed)
            failed = total_students - passed
            avg_percentage = sum(r.percentage for r in results) / total_students if total_students > 0 else 0
            
            stats = {
                'total_students': total_students,
                'passed': passed,
                'failed': failed,
                'pass_percentage': (passed / total_students * 100) if total_students > 0 else 0,
                'fail_percentage': (failed / total_students * 100) if total_students > 0 else 0,
                'average_percentage': round(avg_percentage, 2)
            }
            
            # Get classes for filter
            classes = session_db.query(Class).filter_by(tenant_id=tenant_id).order_by(Class.class_name).all()
            
            return render_template(
                'akademi/examinations/results.html',
                school=g.current_tenant,
                examination=examination,
                results=results,
                stats=stats,
                classes=classes,
                selected_class_id=class_filter,
                selected_status=status_filter
            )
            
        except Exception as e:
            logger.error(f"Error in examinations_results for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error loading results', 'error')
            return redirect(url_for('school.examinations_detail', tenant_slug=tenant_slug, exam_id=exam_id))
        finally:
            session_db.close()
    
    
    # ==================== STUDENT RESULT DETAIL ====================
    @bp.route('/<tenant_slug>/examinations/<int:exam_id>/results/student/<int:student_id>')
    @require_school_auth
    def student_result_detail(tenant_slug, exam_id, student_id):
        """View detailed subject-wise results for a student"""
        session_db = get_session()
        try:
            from models import Student
            tenant_id = g.current_tenant.id
            
            # Get examination
            examination = session_db.query(Examination).filter_by(
                id=exam_id,
                tenant_id=tenant_id
            ).first()
            
            if not examination:
                flash('Examination not found', 'error')
                return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
            
            # Get student
            student = session_db.query(Student).filter_by(
                id=student_id,
                tenant_id=tenant_id
            ).first()
            
            if not student:
                flash('Student not found', 'error')
                return redirect(url_for('school.examinations_results', tenant_slug=tenant_slug, exam_id=exam_id))
            
            # Get overall result
            overall_result = session_db.query(ExaminationResult).filter_by(
                examination_id=exam_id,
                student_id=student_id
            ).first()
            
            # Get all subject marks for this student
            subject_marks = session_db.query(ExaminationMark).filter_by(
                examination_id=exam_id,
                student_id=student_id
            ).all()
            
            # Enrich subject marks with subject and exam_subject details
            subject_details = []
            for mark in subject_marks:
                exam_subject = session_db.query(ExaminationSubject).get(mark.examination_subject_id)
                if exam_subject:
                    subject = session_db.query(Subject).get(exam_subject.subject_id)
                    subject_details.append({
                        'subject_name': subject.name if subject else 'Unknown',
                        'subject_code': subject.code if subject else '',
                        'theory_max': exam_subject.theory_marks,
                        'practical_max': exam_subject.practical_marks,
                        'total_max': exam_subject.total_marks,
                        'passing_marks': exam_subject.passing_marks,
                        'theory_obtained': mark.theory_marks_obtained or 0,
                        'practical_obtained': mark.practical_marks_obtained or 0,
                        'total_obtained': mark.total_marks_obtained or 0,
                        'grade': mark.grade or 'N/A',
                        'grade_point': mark.grade_point or 0,
                        'is_passed': mark.is_passed,
                        'is_absent': mark.is_absent,
                        'remarks': mark.remarks or ''
                    })
            
            # Sort by subject name
            subject_details.sort(key=lambda x: x['subject_name'])
            
            return render_template(
                'akademi/examinations/student_result_detail.html',
                school=g.current_tenant,
                examination=examination,
                student=student,
                overall_result=overall_result,
                subject_details=subject_details
            )
            
        except Exception as e:
            logger.error(f"Error in student_result_detail for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error loading student result details', 'error')
            return redirect(url_for('school.examinations_results', tenant_slug=tenant_slug, exam_id=exam_id))
        finally:
            session_db.close()

    
    
    # ==================== ALL RESULTS LIST ====================
    @bp.route('/<tenant_slug>/examinations/results')
    @require_school_auth
    def all_examinations_results(tenant_slug):
        """List all examinations with results"""
        session_db = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Get all examinations with their result counts
            examinations = session_db.query(Examination).filter_by(
                tenant_id=tenant_id
            ).order_by(desc(Examination.start_date)).all()
            
            # Get result counts for each examination
            exam_stats = []
            for exam in examinations:
                result_count = session_db.query(ExaminationResult).filter_by(
                    examination_id=exam.id
                ).count()
                
                if result_count > 0:
                    results = session_db.query(ExaminationResult).filter_by(
                        examination_id=exam.id
                    ).all()
                    passed = sum(1 for r in results if r.is_passed)
                    avg_percentage = sum(r.percentage for r in results) / result_count if result_count > 0 else 0
                    
                    # Check if results are published (at least one result is published)
                    is_published = any(r.is_published for r in results)
                    
                    exam_stats.append({
                        'examination': exam,
                        'total_students': result_count,
                        'passed': passed,
                        'failed': result_count - passed,
                        'pass_percentage': (passed / result_count * 100) if result_count > 0 else 0,
                        'average_percentage': round(avg_percentage, 2),
                        'has_results': True,
                        'is_published': is_published
                    })
                else:
                    exam_stats.append({
                        'examination': exam,
                        'total_students': 0,
                        'has_results': False,
                        'is_published': False
                    })
            
            return render_template(
                'akademi/examinations/all_results.html',
                school=g.current_tenant,
                exam_stats=exam_stats
            )
            
        except Exception as e:
            logger.error(f"Error in all_examinations_results for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error loading examination results', 'error')
            return redirect(url_for('school.examinations_dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    
    # ==================== GRADE SETTINGS ====================
    @bp.route('/<tenant_slug>/examinations/grade-settings', methods=['GET', 'POST'])
    @require_school_auth
    def grade_settings(tenant_slug):
        """Manage grade scales"""
        session_db = get_session()
        try:
            from examination_models import GradeScale
            tenant_id = g.current_tenant.id
            
            logger.info(f"grade_settings called: method={request.method}, form={request.form}")
            
            if request.method == 'POST':
                action = request.form.get('action')
                logger.info(f"Grade settings POST action: {action}")
                
                if action == 'create_default':
                    try:
                        # Create default grade scale
                        default_grades = [
                            {'name': 'A+', 'point': 10.0, 'min': 90, 'max': 100, 'description': 'Outstanding', 'remarks': 'Outstanding', 'passing': True},
                            {'name': 'A', 'point': 9.0, 'min': 80, 'max': 89, 'description': 'Excellent', 'remarks': 'Excellent', 'passing': True},
                            {'name': 'B+', 'point': 8.0, 'min': 70, 'max': 79, 'description': 'Very Good', 'remarks': 'Very Good', 'passing': True},
                            {'name': 'B', 'point': 7.0, 'min': 60, 'max': 69, 'description': 'Good', 'remarks': 'Good', 'passing': True},
                            {'name': 'C+', 'point': 6.0, 'min': 50, 'max': 59, 'description': 'Satisfactory', 'remarks': 'Satisfactory', 'passing': True},
                            {'name': 'C', 'point': 5.0, 'min': 40, 'max': 49, 'description': 'Acceptable', 'remarks': 'Acceptable', 'passing': True},
                            {'name': 'D', 'point': 4.0, 'min': 35, 'max': 39, 'description': 'Pass', 'remarks': 'Pass', 'passing': True},
                            {'name': 'F', 'point': 0.0, 'min': 0, 'max': 34, 'description': 'Fail', 'remarks': 'Fail', 'passing': False},
                        ]
                        
                        logger.info(f"Creating {len(default_grades)} default grades for tenant {tenant_id}")
                        
                        for grade_data in default_grades:
                            grade = GradeScale(
                                tenant_id=tenant_id,
                                grade_name=grade_data['name'],
                                grade_point=grade_data['point'],
                                min_percentage=grade_data['min'],
                                max_percentage=grade_data['max'],
                                scale_name='Default Grade Scale',
                                scale_type='letter',
                                is_default=True,
                                description=grade_data['description'],
                                remarks=grade_data['remarks'],
                                is_passing=grade_data['passing']
                            )
                            session_db.add(grade)
                            logger.info(f"Added grade: {grade_data['name']}")
                        
                        session_db.commit()
                        logger.info(f"Successfully created {len(default_grades)} default grades")
                        flash('Default grade scale created successfully!', 'success')
                        return redirect(url_for('school.grade_settings', tenant_slug=tenant_slug))
                    except Exception as create_error:
                        session_db.rollback()
                        logger.error(f"Error creating default grades: {create_error}")
                        import traceback
                        logger.error(traceback.format_exc())
                        flash(f'Error creating default grades: {str(create_error)}', 'error')
                        return redirect(url_for('school.grade_settings', tenant_slug=tenant_slug))
                
                elif action == 'delete':
                    grade_id = request.form.get('grade_id', type=int)
                    grade = session_db.query(GradeScale).filter_by(
                        id=grade_id,
                        tenant_id=tenant_id
                    ).first()
                    
                    if grade:
                        session_db.delete(grade)
                        session_db.commit()
                        flash('Grade deleted successfully', 'success')
                    return redirect(url_for('school.grade_settings', tenant_slug=tenant_slug))
                
                elif action == 'add':
                    # Handle adding a new grade from the inline form
                    grade_name = request.form.get('grade_name')
                    grade_point = float(request.form.get('grade_point', 0))
                    min_percentage = float(request.form.get('min_percentage', 0))
                    max_percentage = float(request.form.get('max_percentage', 0))
                    description = request.form.get('description', '')
                    is_passing = request.form.get('is_passing') is not None
                    
                    if not grade_name or min_percentage >= max_percentage:
                        flash('Invalid grade data. Please ensure grade name is set and max > min percentage.', 'error')
                        return redirect(url_for('school.grade_settings', tenant_slug=tenant_slug))
                    
                    # Check for overlapping grade ranges
                    existing_grades = session_db.query(GradeScale).filter_by(tenant_id=tenant_id).all()
                    for existing_grade in existing_grades:
                        # Check if ranges overlap
                        if not (max_percentage < existing_grade.min_percentage or min_percentage > existing_grade.max_percentage):
                            flash(f'Grade range {min_percentage}-{max_percentage}% overlaps with existing grade "{existing_grade.grade_name}" ({existing_grade.min_percentage}-{existing_grade.max_percentage}%). Please use non-overlapping ranges.', 'error')
                            return redirect(url_for('school.grade_settings', tenant_slug=tenant_slug))
                    
                    grade = GradeScale(
                        tenant_id=tenant_id,
                        grade_name=grade_name,
                        grade_point=grade_point,
                        min_percentage=min_percentage,
                        max_percentage=max_percentage,
                        scale_name='Custom Grade Scale',
                        scale_type='letter',
                        description=description,
                        is_passing=is_passing
                    )
                    session_db.add(grade)
                    session_db.commit()
                    flash(f'Grade "{grade_name}" added successfully', 'success')
                    return redirect(url_for('school.grade_settings', tenant_slug=tenant_slug))
            
            # GET request
            grades = session_db.query(GradeScale).filter_by(
                tenant_id=tenant_id
            ).order_by(GradeScale.min_percentage.desc()).all()
            
            return render_template(
                'akademi/examinations/grade_settings.html',
                school=g.current_tenant,
                grades=grades
            )
            
        except Exception as e:
            logger.error(f"Error in grade_settings for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error loading grade settings', 'error')
            return redirect(url_for('school.examinations_dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    
    @bp.route('/<tenant_slug>/examinations/grade-settings/add', methods=['GET', 'POST'])
    @require_school_auth
    def add_grade_scale(tenant_slug):
        """Add new grade scale"""
        session_db = get_session()
        try:
            from examination_models import GradeScale
            tenant_id = g.current_tenant.id
            
            if request.method == 'POST':
                grade_name = request.form.get('grade_name')
                min_percentage = float(request.form.get('min_percentage'))
                max_percentage = float(request.form.get('max_percentage'))
                grade_point = float(request.form.get('grade_point', 0))
                is_passing = request.form.get('is_passing') == 'on'
                remarks = request.form.get('remarks', '')
                scale_name = request.form.get('scale_name', 'Custom Grade Scale')
                
                # Validation
                if not grade_name or min_percentage < 0 or max_percentage > 100 or min_percentage >= max_percentage:
                    flash('Invalid grade scale data', 'error')
                    return redirect(url_for('school.add_grade_scale', tenant_slug=tenant_slug))
                
                # Check for overlapping grade ranges
                existing_grades = session_db.query(GradeScale).filter_by(tenant_id=tenant_id).all()
                for existing_grade in existing_grades:
                    # Check if ranges overlap
                    if not (max_percentage < existing_grade.min_percentage or min_percentage > existing_grade.max_percentage):
                        flash(f'Grade range {min_percentage}-{max_percentage}% overlaps with existing grade "{existing_grade.grade_name}" ({existing_grade.min_percentage}-{existing_grade.max_percentage}%). Please use non-overlapping ranges.', 'error')
                        return redirect(url_for('school.add_grade_scale', tenant_slug=tenant_slug))
                
                # Create new grade scale
                grade_scale = GradeScale(
                    tenant_id=tenant_id,
                    grade_name=grade_name,
                    min_percentage=min_percentage,
                    max_percentage=max_percentage,
                    grade_point=grade_point,
                    scale_name=scale_name,
                    scale_type='letter',
                    is_passing=is_passing,
                    remarks=remarks
                )
                session_db.add(grade_scale)
                session_db.commit()
                
                flash(f'Grade scale "{grade_name}" added successfully', 'success')
                return redirect(url_for('school.grade_settings', tenant_slug=tenant_slug))
            
            return render_template(
                'akademi/examinations/add_grade_scale.html',
                school=g.current_tenant
            )
            
        except Exception as e:
            logger.error(f"Error in add_grade_scale for {tenant_slug}: {e}")
            session_db.rollback()
            flash('Error adding grade scale', 'error')
            return redirect(url_for('school.grade_settings', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    
    # ==================== RESULTS PROCESSING ====================
    @bp.route('/<tenant_slug>/examinations/results-processing', methods=['GET', 'POST'])
    @require_school_auth
    def results_processing(tenant_slug):
        """Process examination results and calculate ranks"""
        session_db = get_session()
        try:
            from examination_models import GradeScale
            from models import Student
            tenant_id = g.current_tenant.id
            
            if request.method == 'POST':
                exam_id = request.form.get('exam_id', type=int)
                class_id = request.form.get('class_id', type=int)
                
                logger.info(f"Results processing POST: exam_id={exam_id}, class_id={class_id}")
                
                if not exam_id:
                    flash('Please select an examination', 'error')
                    return redirect(url_for('school.results_processing', tenant_slug=tenant_slug))
                
                if not class_id:
                    flash('Please select a class', 'error')
                    return redirect(url_for('school.results_processing', tenant_slug=tenant_slug))
                
                # Get examination
                examination = session_db.query(Examination).filter_by(
                    id=exam_id,
                    tenant_id=tenant_id
                ).first()
                
                if not examination:
                    flash('Examination not found', 'error')
                    return redirect(url_for('school.results_processing', tenant_slug=tenant_slug))
                
                # Get exam subjects for this class
                exam_subjects_query = session_db.query(ExaminationSubject).filter_by(
                    examination_id=exam_id
                )
                if class_id:
                    exam_subjects_query = exam_subjects_query.filter_by(class_id=class_id)
                
                exam_subjects = exam_subjects_query.all()
                
                # VERIFICATION: Check if subjects are configured
                if not exam_subjects:
                    flash('No subjects configured for this examination/class. Please add subjects first.', 'error')
                    return redirect(url_for('school.results_processing', tenant_slug=tenant_slug))
                
                # VERIFICATION: Check if marks have been entered for ALL subjects
                from examination_models import GradeScale
                from teacher_models import Subject
                from models import StudentStatusEnum
                
                # Get all active students for this class
                students_in_class = session_db.query(Student).filter(
                    Student.tenant_id == tenant_id,
                    Student.class_id == class_id,
                    Student.status == StudentStatusEnum.ACTIVE
                ).all()
                
                if not students_in_class:
                    flash('No active students found in this class. Please add students first.', 'error')
                    return redirect(url_for('school.results_processing', tenant_slug=tenant_slug))
                
                # Check each subject for incomplete marks
                incomplete_subjects = []
                for exam_subject in exam_subjects:
                    # Count how many students have marks entered for this subject
                    marks_count = session_db.query(ExaminationMark).filter(
                        ExaminationMark.examination_id == exam_id,
                        ExaminationMark.examination_subject_id == exam_subject.id
                    ).count()
                    
                    # Get subject name for error message
                    subject = session_db.query(Subject).filter_by(id=exam_subject.subject_id).first()
                    subject_name = subject.name if subject else f"Subject ID {exam_subject.subject_id}"
                    
                    # Check if marks are entered for all students
                    if marks_count < len(students_in_class):
                        incomplete_subjects.append({
                            'name': subject_name,
                            'entered': marks_count,
                            'total': len(students_in_class)
                        })
                
                # If any subjects have incomplete marks, show error
                if incomplete_subjects:
                    subjects_list = ", ".join([f"{s['name']} ({s['entered']}/{s['total']} students)" for s in incomplete_subjects])
                    flash(f'Cannot process results. Marks are incomplete for the following subjects: {subjects_list}. Please enter marks for all students before processing.', 'error')
                    return redirect(url_for('school.results_processing', tenant_slug=tenant_slug))
                
                # VERIFICATION: Check if grade scale exists
                grade_count = session_db.query(GradeScale).filter_by(tenant_id=tenant_id).count()
                if grade_count == 0:
                    flash('No grade scale configured. Please set up grade scale before processing results.', 'warning')
                    # Note: Continue anyway, grades will show as N/A

                
                # Get all students for these classes - FIXED: Added status filter
                class_ids = list(set([es.class_id for es in exam_subjects]))
                students_query = session_db.query(Student).filter(
                    Student.tenant_id == tenant_id,
                    Student.class_id.in_(class_ids),
                    Student.status == StudentStatusEnum.ACTIVE  # FIX #4: Filter only active students
                )
                students = students_query.all()
                
                # FIX #1: Calculate passing percentage from examination's passing_marks
                exam_passing_percentage = (examination.passing_marks / examination.total_marks * 100) if examination.total_marks > 0 else 35.0
                
                # Get all grade scales for this tenant (for subject-level grading)
                all_grade_scales = session_db.query(GradeScale).filter_by(
                    tenant_id=tenant_id
                ).order_by(GradeScale.min_percentage.desc()).all()
                
                def get_grade_for_percentage(pct):
                    """Helper to get grade for a percentage - FIX #5: Better boundary handling"""
                    for gs in all_grade_scales:
                        if gs.min_percentage <= pct <= gs.max_percentage:
                            return gs.grade_name, gs.grade_point
                    # Fallback for edge cases (0% or boundary issues)
                    if pct <= 0:
                        # Find the lowest grade (usually F)
                        lowest = min(all_grade_scales, key=lambda x: x.min_percentage, default=None)
                        if lowest:
                            return lowest.grade_name, lowest.grade_point
                    return 'N/A', 0.0
                
                # Process results for each student
                results_processed = 0
                skipped_students = []
                
                for student in students:
                    # Get marks for this student in this exam
                    marks_entries = session_db.query(ExaminationMark).filter_by(
                        examination_id=exam_id,
                        student_id=student.id
                    ).all()
                    
                    if not marks_entries:
                        # Log and track skipped students
                        skipped_students.append({
                            'id': student.id,
                            'name': student.full_name,
                            'class_id': student.class_id
                        })
                        logger.warning(f"Skipping student {student.id} ({student.full_name}) - no marks entries found")
                        continue
                    
                    # Get exam subjects for this student's class
                    student_exam_subjects = [es for es in exam_subjects if es.class_id == student.class_id]
                    
                    # Create a mapping of subject_id to marks entry for easier lookup
                    marks_by_subject = {me.examination_subject_id: me for me in marks_entries}
                    
                    # Calculate totals - only count subjects where student was NOT absent
                    total_marks = 0
                    obtained_marks = 0
                    
                    for es in student_exam_subjects:
                        mark_entry = marks_by_subject.get(es.id)
                        if mark_entry and not mark_entry.is_absent:
                            # Only include this subject's marks if student was present
                            total_marks += es.total_marks
                            obtained_marks += mark_entry.total_marks_obtained or 0
                            
                            # FIX #7: Calculate and assign grade to individual mark entry
                            subject_percentage = (mark_entry.total_marks_obtained / es.total_marks * 100) if es.total_marks > 0 else 0
                            mark_grade, mark_grade_point = get_grade_for_percentage(subject_percentage)
                            mark_entry.grade = mark_grade
                            mark_entry.grade_point = mark_grade_point
                            
                            # Also update pass status based on subject's passing marks
                            mark_entry.is_passed = (mark_entry.total_marks_obtained or 0) >= es.passing_marks
                    
                    percentage = (obtained_marks / total_marks * 100) if total_marks > 0 else 0
                    
                    # Count subjects
                    total_subjects = len(student_exam_subjects)
                    subjects_appeared = sum(1 for me in marks_entries if not me.is_absent)
                    subjects_passed = sum(1 for me in marks_entries if me.is_passed and not me.is_absent)
                    subjects_failed = subjects_appeared - subjects_passed
                    
                    # FIX #1: Use examination's passing percentage instead of hardcoded 35%
                    # Student passes if: all subjects passed AND overall percentage >= exam's passing percentage
                    is_passed = (percentage >= exam_passing_percentage and subjects_passed == subjects_appeared and subjects_appeared > 0)
                    
                    # Get overall grade based on percentage
                    grade, grade_point = get_grade_for_percentage(percentage)
                    
                    # Check if result exists
                    result = session_db.query(ExaminationResult).filter_by(
                        examination_id=exam_id,
                        student_id=student.id
                    ).first()
                    
                    if result:
                        # Update existing
                        result.total_marks = total_marks
                        result.marks_obtained = obtained_marks
                        result.percentage = round(percentage, 2)
                        result.grade = grade
                        result.grade_point = grade_point
                        result.is_passed = is_passed
                        result.total_subjects = total_subjects
                        result.subjects_appeared = subjects_appeared
                        result.subjects_passed = subjects_passed
                        result.subjects_failed = subjects_failed
                        result.generated_at = datetime.utcnow()
                        result.updated_at = datetime.utcnow()
                    else:
                        # Create new
                        result = ExaminationResult(
                            examination_id=exam_id,
                            student_id=student.id,
                            class_id=student.class_id,
                            total_marks=total_marks,
                            marks_obtained=obtained_marks,
                            percentage=round(percentage, 2),
                            grade=grade,
                            grade_point=grade_point,
                            is_passed=is_passed,
                            total_subjects=total_subjects,
                            subjects_appeared=subjects_appeared,
                            subjects_passed=subjects_passed,
                            subjects_failed=subjects_failed,
                            generated_at=datetime.utcnow()
                        )
                        session_db.add(result)
                    
                    results_processed += 1
                
                # Flush to ensure all results are saved before calculating ranks
                session_db.flush()
                
                # Calculate ranks within each class - FIX #2: Also set rank_in_class
                for result_class_id in class_ids:
                    class_results = session_db.query(ExaminationResult).filter_by(
                        examination_id=exam_id,
                        class_id=result_class_id
                    ).order_by(ExaminationResult.percentage.desc()).all()
                    
                    for rank, result in enumerate(class_results, start=1):
                        result.rank = rank
                        result.rank_in_class = rank  # FIX #2: Set rank_in_class
                
                session_db.commit()
                logger.info(f'Successfully processed results for {results_processed} students')
                
                # Build comprehensive flash message
                flash(f'Results processed successfully for {results_processed} students. Results are currently UNPUBLISHED.', 'success')
                flash('To make results visible to students, go to "All Results" and click the Publish button.', 'info')
                
                if skipped_students:
                    # Show warning about skipped students
                    skipped_count = len(skipped_students)
                    if skipped_count <= 5:
                        # Show all skipped student names if 5 or fewer
                        skipped_names = ', '.join([s['name'] for s in skipped_students])
                        flash(f'Warning: {skipped_count} student(s) were skipped due to missing marks: {skipped_names}', 'warning')
                    else:
                        # Show count and first few names if more than 5
                        skipped_names = ', '.join([s['name'] for s in skipped_students[:3]])
                        flash(f'Warning: {skipped_count} student(s) were skipped due to missing marks (showing first 3): {skipped_names}, and {skipped_count - 3} more', 'warning')
                    
                    logger.warning(f"Skipped {skipped_count} students without marks: {[s['name'] for s in skipped_students]}")
                
                return redirect(url_for('school.examinations_results', tenant_slug=tenant_slug, exam_id=exam_id))
            
            # GET request - show form
            # Get all completed examinations
            examinations = session_db.query(Examination).filter(
                Examination.tenant_id == tenant_id,
                Examination.status.in_([ExaminationStatus.COMPLETED, ExaminationStatus.ONGOING])
            ).order_by(desc(Examination.start_date)).all()
            
            # Get all classes
            classes = session_db.query(Class).filter_by(tenant_id=tenant_id).order_by(Class.class_name).all()
            
            return render_template(
                'akademi/examinations/results_processing.html',
                school=g.current_tenant,
                examinations=examinations,
                classes=classes
            )
            
        except Exception as e:
            logger.error(f"Error in results_processing for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            session_db.rollback()
            flash('Error processing results', 'error')
            return redirect(url_for('school.examinations_dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    
    # ==================== EXAMINATION DASHBOARD ====================
    @bp.route('/<tenant_slug>/examinations/dashboard')
    @require_school_auth
    def examinations_dashboard(tenant_slug):
        """Examination dashboard with overview statistics"""
        session_db = get_session()
        try:
            from examination_models import GradeScale, ExaminationPublication
            from models import Student
            
            tenant_id = g.current_tenant.id
            
            # Get current academic session
            current_session = session_db.query(AcademicSession).filter_by(
                tenant_id=tenant_id, 
                is_active=True
            ).first()
            
            # Overall Statistics
            total_exams = session_db.query(Examination).filter_by(tenant_id=tenant_id).count()
            draft_exams = session_db.query(Examination).filter_by(
                tenant_id=tenant_id, 
                status=ExaminationStatus.DRAFT
            ).count()
            scheduled_exams = session_db.query(Examination).filter_by(
                tenant_id=tenant_id,
                status=ExaminationStatus.SCHEDULED
            ).count()
            ongoing_exams = session_db.query(Examination).filter_by(
                tenant_id=tenant_id,
                status=ExaminationStatus.ONGOING
            ).count()
            completed_exams = session_db.query(Examination).filter_by(
                tenant_id=tenant_id,
                status=ExaminationStatus.COMPLETED
            ).count()
            
            # Recent Exams (last 5)
            recent_exams = session_db.query(Examination).filter_by(
                tenant_id=tenant_id
            ).order_by(desc(Examination.created_at)).limit(5).all()
            
            # Upcoming Exams (next 5)
            upcoming_exams = session_db.query(Examination).filter(
                and_(
                    Examination.tenant_id == tenant_id,
                    Examination.start_date >= date.today(),
                    Examination.status.in_([ExaminationStatus.SCHEDULED, ExaminationStatus.DRAFT])
                )
            ).order_by(Examination.start_date).limit(5).all()
            
            # Marks Entry Progress
            total_subjects = session_db.query(ExaminationSubject).join(Examination).filter(
                Examination.tenant_id == tenant_id
            ).count()
            
            completed_subjects = session_db.query(ExaminationSubject).join(Examination).filter(
                and_(
                    Examination.tenant_id == tenant_id,
                    ExaminationSubject.mark_entry_status == MarkEntryStatus.COMPLETED
                )
            ).count()
            
            # Published Results
            try:
                from examination_models import PublicationStatus
                published_results = session_db.query(ExaminationPublication).join(Examination).filter(
                    and_(
                        Examination.tenant_id == tenant_id,
                        ExaminationPublication.status == PublicationStatus.PUBLISHED
                    )
                ).count()
            except:
                published_results = 0
            
            # Total Students
            total_students = session_db.query(Student).filter_by(tenant_id=tenant_id).count()
            
            # Grade Scale Status
            try:
                has_grade_scale = session_db.query(GradeScale).filter_by(
                    tenant_id=tenant_id, 
                    is_active=True
                ).count() > 0
            except:
                has_grade_scale = False
            
            stats = {
                'total_exams': total_exams,
                'draft_exams': draft_exams,
                'scheduled_exams': scheduled_exams,
                'ongoing_exams': ongoing_exams,
                'completed_exams': completed_exams,
                'total_subjects': total_subjects,
                'completed_subjects': completed_subjects,
                'marks_entry_progress': (completed_subjects / total_subjects * 100) if total_subjects > 0 else 0,
                'published_results': published_results,
                'total_students': total_students,
                'has_grade_scale': has_grade_scale
            }
            
            return render_template(
                'akademi/examinations/dashboard.html',
                school=g.current_tenant,
                stats=stats,
                recent_exams=recent_exams,
                upcoming_exams=upcoming_exams,
                current_session=current_session,
                current_date=datetime.now().date()
            )
        except Exception as e:
            logger.error(f"Error in examinations_dashboard for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error loading dashboard', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    
    # ==================== CONFIGURE SUBJECTS ====================
    @bp.route('/<tenant_slug>/examinations/subjects/configure', methods=['GET'])
    @require_school_auth
    def examination_subjects_config(tenant_slug):
        """Configure subjects for examinations"""
        session_db = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Get all examinations
            examinations = session_db.query(Examination).filter_by(
                tenant_id=tenant_id
            ).order_by(desc(Examination.created_at)).all()
            
            # Get selected examination
            exam_id = request.args.get('exam_id', type=int)
            selected_exam = None
            exam_subjects = []
            
            if exam_id:
                selected_exam = session_db.query(Examination).filter_by(
                    id=exam_id,
                    tenant_id=tenant_id
                ).first()
                
                if selected_exam:
                    exam_subjects = session_db.query(ExaminationSubject).filter_by(
                        examination_id=exam_id
                    ).all()
            
            # Get all classes and subjects
            classes = session_db.query(Class).filter_by(tenant_id=tenant_id).order_by(Class.class_name).all()
            subjects = session_db.query(Subject).filter_by(tenant_id=tenant_id, is_active=True).order_by(Subject.name).all()
            
            return render_template(
                'akademi/examinations/configure_subjects.html',
                school=g.current_tenant,
                examinations=examinations,
                selected_exam=selected_exam,
                exam_subjects=exam_subjects,
                classes=classes,
                subjects=subjects
            )
            
        except Exception as e:
            logger.error(f"Error in examination_subjects_config for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error loading subject configuration', 'error')
            return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    
    # ==================== MARKS ENTRY SELECT ====================
    @bp.route('/<tenant_slug>/examinations/marks/select')
    @require_school_auth
    def marks_entry_select(tenant_slug):
        """Select examination, class, and subject for marks entry"""
        session_db = get_session()
        try:
            from teacher_models import Subject
            tenant_id = g.current_tenant.id
            
            # Get all active examinations
            examinations = session_db.query(Examination).filter(
                and_(
                    Examination.tenant_id == tenant_id,
                    Examination.status.in_([ExaminationStatus.ONGOING, ExaminationStatus.SCHEDULED, ExaminationStatus.COMPLETED])
                )
            ).order_by(desc(Examination.start_date)).all()
            
            # If no examinations, show message
            if not examinations:
                flash('No examinations found. Please create an examination first.', 'info')
            
            # Get all classes
            classes = session_db.query(Class).filter_by(tenant_id=tenant_id).order_by(Class.class_name).all()
            
            # Get selected filters
            exam_id = request.args.get('exam_id', type=int)
            class_id = request.args.get('class_id', type=int)
            
            exam_subjects = []
            selected_exam = None
            
            if exam_id and class_id:
                selected_exam = session_db.query(Examination).filter_by(
                    id=exam_id,
                    tenant_id=tenant_id
                ).first()
                
                if selected_exam:
                    # Get exam subjects with subject details
                    exam_subjects = session_db.query(ExaminationSubject).filter_by(
                        examination_id=exam_id,
                        class_id=class_id
                    ).all()
                    
                    logger.info(f"[MARKS_ENTRY_SELECT] Found {len(exam_subjects)} exam_subjects for exam_id={exam_id}, class_id={class_id}")
                    
                    # Load subject names for each exam_subject
                    for es in exam_subjects:
                        logger.info(f"[MARKS_ENTRY_SELECT] Processing exam_subject id={es.id}, subject_id={es.subject_id}")
                        subject = session_db.query(Subject).filter_by(id=es.subject_id).first()
                        if subject:
                            es.subject = subject
                            logger.info(f"[MARKS_ENTRY_SELECT] Loaded subject: id={subject.id}, name={subject.name}, code={subject.code}")
                        else:
                            logger.error(f"[MARKS_ENTRY_SELECT] Subject not found for subject_id={es.subject_id}")
                    
                    logger.info(f"[MARKS_ENTRY_SELECT] Completed loading {len(exam_subjects)} exam subjects")
            
            return render_template(
                'akademi/examinations/marks_entry_select.html',
                school=g.current_tenant,
                examinations=examinations,
                classes=classes,
                selected_exam=selected_exam,
                exam_subjects=exam_subjects,
                selected_exam_id=exam_id,
                selected_class_id=class_id
            )
            
        except Exception as e:
            logger.error(f"Error in marks_entry_select for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error loading marks entry', 'error')
            return redirect(url_for('school.examinations_dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    
    # ==================== ADD SCHEDULE ====================
    @bp.route('/<tenant_slug>/examinations/<int:exam_id>/schedule/add', methods=['GET', 'POST'])
    @require_school_auth
    def examinations_add_schedule(tenant_slug, exam_id):
        """Add schedule to examination"""
        session_db = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Get examination
            examination = session_db.query(Examination).filter_by(
                id=exam_id,
                tenant_id=tenant_id
            ).first()
            
            if not examination:
                flash('Examination not found', 'error')
                return redirect(url_for('school.examinations_list', tenant_slug=tenant_slug))
            
            if request.method == 'POST':
                exam_subject_id = request.form.get('exam_subject_id')
                exam_date = request.form.get('exam_date')
                start_time = request.form.get('start_time')
                end_time = request.form.get('end_time')
                duration_minutes = request.form.get('duration_minutes')
                room_number = request.form.get('room_number')
                building = request.form.get('building')
                instructions = request.form.get('instructions')
                
                # Validate
                if not all([exam_subject_id, exam_date, start_time, end_time]):
                    flash('Please fill all required fields', 'error')
                    return redirect(request.url)
                
                # Parse and validate exam date
                try:
                    exam_date_obj = datetime.strptime(exam_date, '%Y-%m-%d').date()
                except ValueError:
                    flash('Invalid date format', 'error')
                    return redirect(request.url)
                
                # Validate schedule date is within examination date range
                if not (examination.start_date <= exam_date_obj <= examination.end_date):
                    flash(f'Schedule date must be between examination start date ({examination.start_date}) and end date ({examination.end_date})', 'error')
                    return redirect(request.url)
                
                # Parse times
                try:
                    start_time_obj = datetime.strptime(start_time, '%H:%M').time()
                    end_time_obj = datetime.strptime(end_time, '%H:%M').time()
                except ValueError:
                    flash('Invalid time format', 'error')
                    return redirect(request.url)
                
                # Validate end time is after start time
                if end_time_obj <= start_time_obj:
                    flash('End time must be after start time', 'error')
                    return redirect(request.url)
                
                # Create schedule
                schedule = ExaminationSchedule(
                    examination_id=exam_id,
                    examination_subject_id=int(exam_subject_id),
                    exam_date=exam_date_obj,
                    start_time=start_time_obj,
                    end_time=end_time_obj,
                    duration_minutes=int(duration_minutes) if duration_minutes else None,
                    room_number=room_number,
                    building=building,
                    instructions=instructions
                )
                
                session_db.add(schedule)
                session_db.commit()
                
                flash('Schedule added successfully', 'success')
                return redirect(url_for('school.examinations_detail', tenant_slug=tenant_slug, exam_id=exam_id))
            
            # GET - Show form
            exam_subjects = session_db.query(ExaminationSubject).filter_by(
                examination_id=exam_id
            ).all()
            
            # Load subject details for dropdown display
            from teacher_models import Subject
            for es in exam_subjects:
                if not hasattr(es, 'subject') or es.subject is None:
                    es.subject = session_db.query(Subject).filter_by(id=es.subject_id).first()
            
            return render_template(
                'akademi/examinations/add_schedule.html',
                examination=examination,
                exam_subjects=exam_subjects,
                school=g.current_tenant
            )
            
        except Exception as e:
            logger.error(f"Error in examinations_add_schedule for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            session_db.rollback()
            flash('Error adding schedule', 'error')
            return redirect(url_for('school.examinations_detail', tenant_slug=tenant_slug, exam_id=exam_id))
        finally:
            session_db.close()
    
    
    # ==================== PUBLISH RESULTS ====================
    @bp.route('/<tenant_slug>/examinations/<int:exam_id>/publish-results', methods=['POST'])
    @require_school_auth
    def publish_results(tenant_slug, exam_id):
        """Publish examination results"""
        session_db = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Get examination
            examination = session_db.query(Examination).filter_by(
                id=exam_id,
                tenant_id=tenant_id
            ).first()
            
            if not examination:
                flash('Examination not found', 'error')
                return redirect(url_for('school.all_examinations_results', tenant_slug=tenant_slug))
            
            # Get class_id from form if provided (for class-specific publishing)
            class_id = request.form.get('class_id', type=int)
            
            # Update all results for this examination (or specific class) to published
            results_query = session_db.query(ExaminationResult).filter_by(
                examination_id=exam_id
            )
            
            if class_id:
                results_query = results_query.filter_by(class_id=class_id)
            
            results = results_query.all()
            
            if not results:
                flash('No results found to publish', 'warning')
                return redirect(url_for('school.all_examinations_results', tenant_slug=tenant_slug))
            
            # Mark all results as published
            publish_time = datetime.utcnow()
            for result in results:
                result.is_published = True
                result.published_at = publish_time
                result.updated_at = publish_time
            
            # Create or update publication record
            from examination_models import ExaminationPublication, PublicationStatus
            publication = session_db.query(ExaminationPublication).filter_by(
                examination_id=exam_id
            ).first()
            
            if publication:
                publication.status = PublicationStatus.PUBLISHED
                publication.published_date = publish_time
                publication.published_by = current_user.id
                publication.updated_at = publish_time
            else:
                publication = ExaminationPublication(
                    examination_id=exam_id,
                    status=PublicationStatus.PUBLISHED,
                    published_date=publish_time,
                    published_by=current_user.id,
                    created_by=current_user.id
                )
                session_db.add(publication)
            
            session_db.commit()
            
            class_msg = f" for class" if class_id else ""
            flash(f'Results published successfully{class_msg}. Students can now view their results.', 'success')
            logger.info(f"Published results for exam {exam_id}{class_msg} by user {current_user.id}")
            
            return redirect(url_for('school.all_examinations_results', tenant_slug=tenant_slug))
            
        except Exception as e:
            logger.error(f"Error in publish_results for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            session_db.rollback()
            flash('Error publishing results', 'error')
            return redirect(url_for('school.all_examinations_results', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    
    # ==================== UNPUBLISH RESULTS ====================
    @bp.route('/<tenant_slug>/examinations/<int:exam_id>/unpublish-results', methods=['POST'])
    @require_school_auth
    def unpublish_results(tenant_slug, exam_id):
        """Unpublish examination results"""
        session_db = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Get examination
            examination = session_db.query(Examination).filter_by(
                id=exam_id,
                tenant_id=tenant_id
            ).first()
            
            if not examination:
                flash('Examination not found', 'error')
                return redirect(url_for('school.all_examinations_results', tenant_slug=tenant_slug))
            
            # Get class_id from form if provided (for class-specific unpublishing)
            class_id = request.form.get('class_id', type=int)
            
            # Update all results for this examination (or specific class) to unpublished
            results_query = session_db.query(ExaminationResult).filter_by(
                examination_id=exam_id
            )
            
            if class_id:
                results_query = results_query.filter_by(class_id=class_id)
            
            results = results_query.all()
            
            if not results:
                flash('No results found to unpublish', 'warning')
                return redirect(url_for('school.all_examinations_results', tenant_slug=tenant_slug))
            
            # Mark all results as unpublished
            for result in results:
                result.is_published = False
                result.updated_at = datetime.utcnow()
            
            # Update publication record
            from examination_models import ExaminationPublication, PublicationStatus
            publication = session_db.query(ExaminationPublication).filter_by(
                examination_id=exam_id
            ).first()
            
            if publication:
                publication.status = PublicationStatus.UNPUBLISHED
                publication.updated_at = datetime.utcnow()
            
            session_db.commit()
            
            class_msg = f" for class" if class_id else ""
            flash(f'Results unpublished successfully{class_msg}. Students can no longer view these results.', 'success')
            logger.info(f"Unpublished results for exam {exam_id}{class_msg} by user {current_user.id}")
            
            return redirect(url_for('school.all_examinations_results', tenant_slug=tenant_slug))
            
        except Exception as e:
            logger.error(f"Error in unpublish_results for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            session_db.rollback()
            flash('Error unpublishing results', 'error')
            return redirect(url_for('school.all_examinations_results', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    
    # ==================== CLEAR RESULTS ====================
    @bp.route('/<tenant_slug>/examinations/<int:exam_id>/clear-results', methods=['POST'])
    @require_school_auth
    def clear_results(tenant_slug, exam_id):
        """Clear all results and grade calculations for an examination"""
        session_db = get_session()
        try:
            tenant_id = g.current_tenant.id
            
            # Get examination
            examination = session_db.query(Examination).filter_by(
                id=exam_id,
                tenant_id=tenant_id
            ).first()
            
            if not examination:
                flash('Examination not found', 'error')
                return redirect(url_for('school.all_examinations_results', tenant_slug=tenant_slug))
            
            # Get class_id from form if provided (for class-specific clearing)
            class_id = request.form.get('class_id', type=int)
            
            # Get confirmation from form
            confirm = request.form.get('confirm', '').lower()
            if confirm != 'yes':
                flash('Result clearing cancelled. Please confirm the action.', 'warning')
                return redirect(url_for('school.all_examinations_results', tenant_slug=tenant_slug))
            
            # Delete all results for this examination (or specific class)
            results_query = session_db.query(ExaminationResult).filter_by(
                examination_id=exam_id
            )
            
            if class_id:
                results_query = results_query.filter_by(class_id=class_id)
            
            results_count = results_query.count()
            
            if results_count == 0:
                flash('No results found to clear', 'warning')
                return redirect(url_for('school.all_examinations_results', tenant_slug=tenant_slug))
            
            # Delete results
            results_query.delete(synchronize_session=False)
            
            # Clear grades from individual marks as well
            marks_query = session_db.query(ExaminationMark).filter_by(
                examination_id=exam_id
            )
            
            if class_id:
                # Get all exam subjects for this class
                exam_subject_ids = [es.id for es in session_db.query(ExaminationSubject).filter_by(
                    examination_id=exam_id,
                    class_id=class_id
                ).all()]
                marks_query = marks_query.filter(ExaminationMark.examination_subject_id.in_(exam_subject_ids))
            
            marks = marks_query.all()
            for mark in marks:
                mark.grade = None
                mark.grade_point = None
                mark.is_passed = False
            
            # Delete or update publication record
            from examination_models import ExaminationPublication, PublicationStatus
            publication = session_db.query(ExaminationPublication).filter_by(
                examination_id=exam_id
            ).first()
            
            if publication:
                publication.status = PublicationStatus.DRAFT
                publication.published_date = None
                publication.updated_at = datetime.utcnow()
            
            session_db.commit()
            
            class_msg = f" for class" if class_id else ""
            flash(f'Successfully cleared {results_count} result(s){class_msg}. All grade calculations and report cards have been removed.', 'success')
            logger.info(f"Cleared {results_count} results for exam {exam_id}{class_msg} by user {current_user.id}")
            
            return redirect(url_for('school.all_examinations_results', tenant_slug=tenant_slug))
            
        except Exception as e:
            logger.error(f"Error in clear_results for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            session_db.rollback()
            flash('Error clearing results', 'error')
            return redirect(url_for('school.all_examinations_results', tenant_slug=tenant_slug))
        finally:
            session_db.close()


