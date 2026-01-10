from flask import render_template, request, redirect, url_for, flash, g, jsonify, current_app
from flask_login import current_user

from datetime import datetime
import logging

from db_single import get_session
from models import Tenant
from teacher_models import Teacher, EmployeeStatusEnum

logger = logging.getLogger(__name__)

def recalculate_slot_orders(session_db, tenant_id, day_of_week):
    """Recalculate slot_order for all time slots on a given day based on start_time"""
    from timetable_models import TimeSlot
    
    # Get all active slots for this day, ordered by start_time
    slots = session_db.query(TimeSlot).filter_by(
        tenant_id=tenant_id,
        day_of_week=day_of_week,
        is_active=True
    ).order_by(TimeSlot.start_time).all()
    
    # Update slot_order based on position
    for idx, slot in enumerate(slots, start=1):
        slot.slot_order = idx

def register_timetable_routes(school_bp, require_school_auth):
    """Register all timetable routes to the school blueprint"""
    @school_bp.route('/<tenant_slug>/timetable/time-slots', methods=['GET', 'POST'])
    @require_school_auth
    def time_slots(tenant_slug):
        """Manage time slots for the school"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            from timetable_models import TimeSlot, DayOfWeekEnum, SlotTypeEnum, TimeSlotClass
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            if request.method == 'POST':
                # Add new time slot - support creating the same slot across multiple days
                days = request.form.getlist('days') or []
                # Backwards compatibility: accept single day_of_week
                if not days:
                    single_day = request.form.get('day_of_week')
                    if single_day:
                        days = [single_day]

                # Validate that at least one day is selected
                if not days:
                    flash('Please select at least one day of the week', 'error')
                    return redirect(url_for('school.time_slots', tenant_slug=tenant_slug))

                start_time = request.form.get('start_time')
                end_time = request.form.get('end_time')
                slot_name = request.form.get('slot_name', '').strip()
                slot_type = request.form.get('slot_type', 'Regular')
                slot_order = request.form.get('slot_order', type=int)
                # Classes selected for this slot (optional) - multiple values allowed
                class_ids = request.form.getlist('class_ids') or []

                slot_type_enum = SlotTypeEnum[slot_type.upper()] if slot_type else SlotTypeEnum.REGULAR

                created_any = False
                errors = []
                for day_value in days:
                    try:
                        day_enum = DayOfWeekEnum[day_value.upper()] if day_value else None
                        # Skip if day_enum not valid
                        if not day_enum:
                            continue

                        # Check if identical slot already exists for this tenant/day (avoid UniqueConstraint error)
                        exists = session_db.query(TimeSlot).filter_by(
                            tenant_id=school.id,
                            day_of_week=day_enum,
                            start_time=datetime.strptime(start_time, '%H:%M').time() if start_time else None,
                            end_time=datetime.strptime(end_time, '%H:%M').time() if end_time else None
                        ).first()

                        if exists:
                            # skip duplicate
                            continue

                        time_slot = TimeSlot(
                            tenant_id=school.id,
                            day_of_week=day_enum,
                            start_time=datetime.strptime(start_time, '%H:%M').time() if start_time else None,
                            end_time=datetime.strptime(end_time, '%H:%M').time() if end_time else None,
                            slot_name=slot_name,
                            slot_type=slot_type_enum,
                            slot_order=0,  # Will be recalculated
                            is_active=True
                        )
                        session_db.add(time_slot)
                        # flush to get id for assignments
                        session_db.flush()
                        created_any = True

                        # If classes were selected, create TimeSlotClass assignments
                        for cls_id in class_ids:
                            try:
                                cls_int = int(cls_id)
                            except Exception:
                                continue
                            # verify class exists for tenant
                            from models import Class as ModelClass
                            class_obj = session_db.query(ModelClass).filter_by(id=cls_int, tenant_id=school.id, is_active=True).first()
                            if class_obj:
                                assignment = TimeSlotClass(
                                    tenant_id=school.id,
                                    time_slot_id=time_slot.id,
                                    class_id=cls_int,
                                    is_active=True
                                )
                                session_db.add(assignment)
                    except Exception as e:
                        session_db.rollback()
                        errors.append(str(e))

                try:
                    if created_any:
                        # Recalculate slot orders for all affected days
                        for day_value in days:
                            try:
                                day_enum = DayOfWeekEnum[day_value.upper()]
                                recalculate_slot_orders(session_db, school.id, day_enum)
                            except KeyError:
                                pass
                        session_db.commit()
                        flash('Time slot(s) added successfully!', 'success')
                    else:
                        # If no slot created and there were errors, show first error or a generic message
                        if errors:
                            flash(f'No time slots added: {errors[0]}', 'warning')
                        else:
                            flash('No new time slots were added (duplicates may already exist)', 'info')
                except Exception as e:
                    session_db.rollback()
                    logger.error(f"Error committing new time slots: {e}")
                    flash(f'Error adding time slots: {str(e)}', 'error')

                return redirect(url_for('school.time_slots', tenant_slug=tenant_slug))
            
            # GET request - show all time slots
            time_slots = session_db.query(TimeSlot).filter_by(
                tenant_id=school.id,
                is_active=True
            ).order_by(TimeSlot.day_of_week, TimeSlot.slot_order).all()
            
            # Get all classes for assignment dropdown
            from models import Class
            classes = session_db.query(Class).filter_by(tenant_id=school.id, is_active=True).order_by(Class.class_name, Class.section).all()
            
            # Get class assignments for each slot
            from timetable_models import TimeSlotClass
            slot_class_map = {}
            for slot in time_slots:
                assignments = session_db.query(TimeSlotClass).filter_by(
                    time_slot_id=slot.id,
                    tenant_id=school.id,
                    is_active=True
                ).all()
                slot_class_map[slot.id] = [a.class_ref for a in assignments if a.class_ref]
            
            return render_template('akademi/timetable/time_slots.html',
                                 school=school,
                                 time_slots=time_slots,
                                 classes=classes,
                                 slot_class_map=slot_class_map,
                                 current_user=current_user)
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"Time slots error: {e}")
            flash(f'Error managing time slots: {str(e)}', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/api/timetable/delete-time-slot/<int:slot_id>', methods=['POST'])
    @require_school_auth
    def delete_time_slot(tenant_slug, slot_id):
        """Delete a time slot"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        session_db = get_session()
        try:
            from timetable_models import TimeSlot, TimetableSchedule
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            # Check if time slot exists and belongs to this tenant
            time_slot = session_db.query(TimeSlot).filter_by(
                id=slot_id,
                tenant_id=school.id
            ).first()
            
            if not time_slot:
                return jsonify({'success': False, 'message': 'Time slot not found'}), 404
            
            # Check if time slot is being used in any timetable schedules
            schedules_using_slot = session_db.query(TimetableSchedule).filter_by(
                time_slot_id=slot_id,
                tenant_id=school.id,
                is_active=True
            ).count()
            
            if schedules_using_slot > 0:
                return jsonify({
                    'success': False, 
                    'message': f'Cannot delete: This time slot is used in {schedules_using_slot} timetable entries. Please remove those entries first.'
                }), 400
            
            # Delete the time slot
            session_db.delete(time_slot)
            session_db.commit()
            
            logger.info(f"Time slot {slot_id} deleted by user {current_user.id}")
            return jsonify({'success': True, 'message': 'Time slot deleted successfully'})
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"Delete time slot error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({'success': False, 'message': f'Error deleting time slot: {str(e)}'}), 500
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/api/timetable/assign-slot-to-class', methods=['POST'])
    @require_school_auth
    def assign_slot_to_class(tenant_slug):
        """Assign a time slot to one or more classes"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        session_db = get_session()
        try:
            from timetable_models import TimeSlot, TimeSlotClass
            from models import Class
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            slot_id = request.form.get('slot_id', type=int)
            class_ids = request.form.getlist('class_ids[]')
            
            if not slot_id or not class_ids:
                return jsonify({'success': False, 'message': 'Slot ID and class IDs are required'}), 400
            
            # Verify slot exists
            time_slot = session_db.query(TimeSlot).filter_by(id=slot_id, tenant_id=school.id).first()
            if not time_slot:
                return jsonify({'success': False, 'message': 'Time slot not found'}), 404
            
            # Delete existing assignments for this slot
            session_db.query(TimeSlotClass).filter_by(time_slot_id=slot_id, tenant_id=school.id).delete()
            
            # Create new assignments
            for class_id in class_ids:
                class_obj = session_db.query(Class).filter_by(id=int(class_id), tenant_id=school.id).first()
                if class_obj:
                    assignment = TimeSlotClass(
                        tenant_id=school.id,
                        time_slot_id=slot_id,
                        class_id=int(class_id),
                        is_active=True
                    )
                    session_db.add(assignment)
            
            session_db.commit()
            return jsonify({'success': True, 'message': 'Time slot assigned to classes successfully'})
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"Assign slot to class error: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/timetable/class-assignments', methods=['GET', 'POST'])
    @require_school_auth
    def class_assignments(tenant_slug):
        """Assign teachers to classes with subjects"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            from timetable_models import ClassTeacherAssignment
            from teacher_models import Subject
            from models import Class
            from timetable_helpers import get_current_academic_year
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            if request.method == 'POST':
                class_id = request.form.get('class_id', type=int)
                teacher_id = request.form.get('teacher_id', type=int)
                subject_id = request.form.get('subject_id', type=int)
                is_class_teacher = request.form.get('is_class_teacher') == 'on'
                
                # Check if this assignment already exists (active or removed)
                existing_assignment = session_db.query(ClassTeacherAssignment).filter_by(
                    tenant_id=school.id,
                    class_id=class_id,
                    teacher_id=teacher_id,
                    subject_id=subject_id
                ).first()
                
                if existing_assignment:
                    # If assignment was previously removed, reactivate it
                    if existing_assignment.removed_date is not None:
                        existing_assignment.removed_date = None
                        existing_assignment.assigned_date = datetime.now().date()
                        existing_assignment.is_class_teacher = is_class_teacher
                        existing_assignment.updated_at = datetime.now()
                        session_db.commit()
                        flash('Teacher assignment reactivated successfully!', 'success')
                    else:
                        # Assignment already exists and is active
                        flash('This teacher is already assigned to this class and subject!', 'warning')
                else:
                    # Create new assignment
                    assignment = ClassTeacherAssignment(
                        tenant_id=school.id,
                        class_id=class_id,
                        teacher_id=teacher_id,
                        subject_id=subject_id,
                        is_class_teacher=is_class_teacher,
                        assigned_date=datetime.now().date()
                    )
                    
                    session_db.add(assignment)
                    session_db.commit()
                    flash('Teacher assigned successfully!', 'success')
                
                return redirect(url_for('school.class_assignments', tenant_slug=tenant_slug))
            
            # GET - show all assignments
            from sqlalchemy.orm import joinedload
            assignments = session_db.query(ClassTeacherAssignment).options(
                joinedload(ClassTeacherAssignment.class_ref),
                joinedload(ClassTeacherAssignment.teacher),
                joinedload(ClassTeacherAssignment.subject)
            ).filter_by(
                tenant_id=school.id
            ).filter(ClassTeacherAssignment.removed_date.is_(None)).all()
            
            classes = session_db.query(Class).filter_by(
                tenant_id=school.id,
                is_active=True
            ).all()
            
            teachers = session_db.query(Teacher).filter_by(
                tenant_id=school.id,
                employee_status=EmployeeStatusEnum.ACTIVE
            ).all()
            
            subjects = session_db.query(Subject).filter_by(
                tenant_id=school.id,
                is_active=True
            ).all()
            
            # Get teacher-subject relationships for filtering
            from teacher_models import TeacherSubject
            teacher_subjects_query = session_db.query(TeacherSubject).filter_by(
                tenant_id=school.id
            ).filter(TeacherSubject.removed_date.is_(None)).all()
            
            # Create a mapping of subject_id to list of teacher_ids
            subject_teachers_map = {}
            for ts in teacher_subjects_query:
                if ts.subject_id not in subject_teachers_map:
                    subject_teachers_map[ts.subject_id] = []
                subject_teachers_map[ts.subject_id].append(ts.teacher_id)
            
            # Serialize teachers with their subjects
            teachers_data = []
            for teacher in teachers:
                teacher_subject_ids = []
                for ts in teacher_subjects_query:
                    if ts.teacher_id == teacher.id:
                        teacher_subject_ids.append(ts.subject_id)
                
                teachers_data.append({
                    'id': teacher.id,
                    'first_name': teacher.first_name,
                    'last_name': teacher.last_name,
                    'full_name': f"{teacher.first_name} {teacher.last_name}",
                    'email': teacher.email,
                    'subject_ids': teacher_subject_ids
                })
            
            # Serialize assignments for JavaScript
            assignments_data = []
            for assignment in assignments:
                assignments_data.append({
                    'id': assignment.id,
                    'class_id': assignment.class_id,
                    'teacher_id': assignment.teacher_id,
                    'subject_id': assignment.subject_id,
                    'is_class_teacher': assignment.is_class_teacher,
                    'academic_year': assignment.academic_year,
                    'assigned_date': assignment.assigned_date.strftime('%Y-%m-%d'),
                    'class_ref': {
                        'id': assignment.class_ref.id,
                        'class_name': assignment.class_ref.class_name,
                        'section': assignment.class_ref.section
                    },
                    'teacher': {
                        'id': assignment.teacher.id,
                        'first_name': assignment.teacher.first_name,
                        'last_name': assignment.teacher.last_name,
                        'email': assignment.teacher.email
                    },
                    'subject': {
                        'id': assignment.subject.id,
                        'name': assignment.subject.name
                    }
                })
            
            # Serialize subjects for JavaScript
            subjects_data = []
            for subject in subjects:
                subjects_data.append({
                    'id': subject.id,
                    'name': subject.name,
                    'code': subject.code if hasattr(subject, 'code') else None
                })
            
            return render_template('akademi/timetable/class_assignments.html',
                                 school=school,
                                 assignments=assignments_data,
                                 classes=classes,
                                 teachers=teachers_data,
                                 subjects=subjects_data,
                                 current_user=current_user)
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"Class assignments error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash(f'Error managing assignments: {str(e)}', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/timetable/remove-assignment', methods=['POST'])
    @require_school_auth
    def remove_class_assignment(tenant_slug):
        """Remove a class-teacher assignment and associated timetable periods"""
        logger.info(f"Remove assignment route called for tenant: {tenant_slug}")
        logger.info(f"Form data: {request.form}")
        logger.info(f"Current user: {current_user.email if current_user else 'None'}")
        
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            from timetable_models import ClassTeacherAssignment, TimetableSchedule
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            assignment_id = request.form.get('assignment_id', type=int)
            logger.info(f"Attempting to remove assignment ID: {assignment_id}")
            
            assignment = session_db.query(ClassTeacherAssignment).filter_by(
                id=assignment_id,
                tenant_id=school.id
            ).first()
            
            if assignment:
                logger.info(f"Found assignment: {assignment.id} - Setting removed_date")
                
                # Mark assignment as removed
                assignment.removed_date = datetime.now().date()
                
                # Delete all timetable periods for this class-teacher-subject combination
                deleted_periods = session_db.query(TimetableSchedule).filter_by(
                    tenant_id=school.id,
                    class_id=assignment.class_id,
                    teacher_id=assignment.teacher_id,
                    subject_id=assignment.subject_id
                ).delete(synchronize_session=False)
                
                logger.info(f"Deleted {deleted_periods} timetable period(s) for this assignment")
                
                session_db.commit()
                logger.info("Assignment removed successfully")
                
                if deleted_periods > 0:
                    flash(f'Assignment removed successfully! {deleted_periods} timetable period(s) also deleted.', 'success')
                else:
                    flash('Assignment removed successfully!', 'success')
            else:
                logger.warning(f"Assignment {assignment_id} not found for tenant {school.id}")
                flash('Assignment not found', 'error')
                
            return redirect(url_for('school.class_assignments', tenant_slug=tenant_slug))
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"Remove assignment error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash(f'Error removing assignment: {str(e)}', 'error')
            return redirect(url_for('school.class_assignments', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/timetable/bulk-assign-teachers', methods=['POST'])
    @require_school_auth
    def bulk_assign_teachers(tenant_slug):
        """Bulk assign teachers to all subjects for a class"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            from timetable_models import ClassTeacherAssignment
            from teacher_models import Subject
            from timetable_helpers import get_current_academic_year
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            class_id = request.form.get('bulk_class_id', type=int)
            academic_year = request.form.get('bulk_academic_year', get_current_academic_year())
            
            if not class_id:
                flash('Class is required', 'error')
                return redirect(url_for('school.class_assignments', tenant_slug=tenant_slug))
            
            # Get all subjects
            subjects = session_db.query(Subject).filter_by(
                tenant_id=school.id,
                is_active=True
            ).all()
            
            created_count = 0
            updated_count = 0
            skipped_count = 0
            
            # Process each subject
            for subject in subjects:
                teacher_field = f'teacher_{subject.id}'
                class_teacher_field = f'class_teacher_{subject.id}'
                
                teacher_id = request.form.get(teacher_field, type=int)
                is_class_teacher = request.form.get(class_teacher_field) == 'on'
                
                # Skip if no teacher selected for this subject
                if not teacher_id:
                    skipped_count += 1
                    continue
                
                # Check if assignment already exists
                existing = session_db.query(ClassTeacherAssignment).filter_by(
                    tenant_id=school.id,
                    class_id=class_id,
                    teacher_id=teacher_id,
                    subject_id=subject.id
                ).first()
                
                if existing:
                    if existing.removed_date is not None:
                        # Reactivate removed assignment
                        existing.removed_date = None
                        existing.assigned_date = datetime.now().date()
                        existing.is_class_teacher = is_class_teacher
                        existing.updated_at = datetime.now()
                        updated_count += 1
                    else:
                        # Update existing assignment
                        existing.is_class_teacher = is_class_teacher
                        existing.updated_at = datetime.now()
                        updated_count += 1
                else:
                    # Create new assignment
                    assignment = ClassTeacherAssignment(
                        tenant_id=school.id,
                        class_id=class_id,
                        teacher_id=teacher_id,
                        subject_id=subject.id,
                        is_class_teacher=is_class_teacher,
                        assigned_date=datetime.now().date()
                    )
                    session_db.add(assignment)
                    created_count += 1
            
            session_db.commit()
            
            # Create success message
            message_parts = []
            if created_count > 0:
                message_parts.append(f'{created_count} new assignment(s) created')
            if updated_count > 0:
                message_parts.append(f'{updated_count} assignment(s) updated')
            if skipped_count > 0:
                message_parts.append(f'{skipped_count} subject(s) skipped (no teacher selected)')
            
            flash(' Ã¢â‚¬Â¢ '.join(message_parts) if message_parts else 'No changes made', 'success')
            return redirect(url_for('school.class_assignments', tenant_slug=tenant_slug))
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"Bulk assign teachers error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash(f'Error during bulk assignment: {str(e)}', 'error')
            return redirect(url_for('school.class_assignments', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/timetable/create', methods=['GET', 'POST'])
    @require_school_auth
    def create_timetable(tenant_slug):
        """Create/edit timetable for classes - New step-by-step workflow"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            from timetable_models import TimetableSchedule, TimeSlot, DayOfWeekEnum
            from timetable_helpers import check_scheduling_conflicts, get_current_academic_year
            from models import Class
            from teacher_models import Subject
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            if request.method == 'POST':
                # Handle form submission for adding a schedule
                class_id = request.form.get('class_id', type=int)
                subject_id = request.form.get('subject_id', type=int)
                day_of_week_form = request.form.get('day_of_week')  # For validation only
                time_slot_id = request.form.get('time_slot_id', type=int)
                teacher_id = request.form.get('teacher_id', type=int)
                room_number = request.form.get('room_number', '').strip()
                academic_year = request.form.get('academic_year', get_current_academic_year())
                
                # Debug logging to see what values we're receiving
                logger.info(f"Form data received - class_id: {class_id}, subject_id: {subject_id}, day: {day_of_week_form}, slot: {time_slot_id}, teacher: {teacher_id}")
                
                # Validate all required fields
                missing_fields = []
                if not class_id:
                    missing_fields.append('Class')
                if not subject_id:
                    missing_fields.append('Subject')
                if not time_slot_id:
                    missing_fields.append('Time Slot')
                if not teacher_id:
                    missing_fields.append('Teacher')
                
                if missing_fields:
                    flash(f'Please fill in the following required fields: {", ".join(missing_fields)}', 'error')
                    return redirect(url_for('school.create_timetable', tenant_slug=tenant_slug))
                
                # Fetch the TimeSlot to derive day_of_week (authoritative source)
                from timetable_models import TimeSlot
                time_slot = session_db.query(TimeSlot).filter_by(
                    id=time_slot_id,
                    tenant_id=school.id
                ).first()
                
                if not time_slot:
                    flash('Invalid time slot selected', 'error')
                    return redirect(url_for('school.create_timetable', tenant_slug=tenant_slug))
                
                # Derive day_of_week from TimeSlot (prevents data inconsistency)
                day_enum = time_slot.day_of_week
                
                # Optional: Validate form day matches slot day (catch UI bugs)
                if day_of_week_form:
                    try:
                        form_day_enum = DayOfWeekEnum[day_of_week_form.upper()]
                        if form_day_enum != day_enum:
                            logger.warning(f"Day mismatch - form: {day_of_week_form}, slot: {day_enum.value}. Using slot's day.")
                    except:
                        pass  # Ignore invalid form day, we use slot's day anyway
                
                # Check if schedule already exists for this class/day/slot
                existing = session_db.query(TimetableSchedule).filter_by(
                    tenant_id=school.id,
                    class_id=class_id,
                    day_of_week=day_enum,
                    time_slot_id=time_slot_id,
                    academic_year=academic_year,
                    is_active=True
                ).first()
                
                if existing:
                    flash('A schedule already exists for this class at this time slot. Please delete it first.', 'error')
                    return redirect(url_for('school.create_timetable', tenant_slug=tenant_slug))
                
                # Check for teacher conflicts (teacher already scheduled at this time)
                teacher_conflict = session_db.query(TimetableSchedule).filter_by(
                    tenant_id=school.id,
                    teacher_id=teacher_id,
                    day_of_week=day_enum,
                    time_slot_id=time_slot_id,
                    academic_year=academic_year,
                    is_active=True
                ).first()
                
                if teacher_conflict:
                    flash('This teacher is already scheduled for another class at this time.', 'error')
                    return redirect(url_for('school.create_timetable', tenant_slug=tenant_slug))
                
                # Create new schedule
                schedule = TimetableSchedule(
                    tenant_id=school.id,
                    class_id=class_id,
                    time_slot_id=time_slot_id,
                    day_of_week=day_enum,
                    teacher_id=teacher_id,
                    subject_id=subject_id,
                    room_number=room_number if room_number else None,
                    academic_year=academic_year,
                    effective_from=datetime.now().date(),
                    is_active=True
                )
                
                session_db.add(schedule)
                session_db.commit()
                flash('Period added successfully to timetable!', 'success')
                return redirect(url_for('school.create_timetable', tenant_slug=tenant_slug))
            
            # GET - show timetable creation interface
            # Get all active classes
            classes = session_db.query(Class).filter_by(
                tenant_id=school.id,
                is_active=True
            ).order_by(Class.class_name, Class.section).all()
            
            # Get all active subjects
            subjects = session_db.query(Subject).filter_by(
                tenant_id=school.id,
                is_active=True
            ).order_by(Subject.name).all()
            
            # Get days of week for dropdown
            days_of_week = [
                {'value': 'MONDAY', 'label': 'Monday'},
                {'value': 'TUESDAY', 'label': 'Tuesday'},
                {'value': 'WEDNESDAY', 'label': 'Wednesday'},
                {'value': 'THURSDAY', 'label': 'Thursday'},
                {'value': 'FRIDAY', 'label': 'Friday'},
                {'value': 'SATURDAY', 'label': 'Saturday'},
                {'value': 'SUNDAY', 'label': 'Sunday'}
            ]
            
            # Get current academic year
            academic_year = get_current_academic_year()
            
            return render_template('akademi/timetable/create_timetable_new.html',
                                 school=school,
                                 classes=classes,
                                 subjects=subjects,
                                 days_of_week=days_of_week,
                                 academic_year=academic_year,
                                 current_user=current_user)
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"Create timetable error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash(f'Error creating timetable: {str(e)}', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/timetable/view', methods=['GET'])
    @require_school_auth
    def view_timetables(tenant_slug):
        """View all timetables"""
        session_db = get_session()
        try:
            from timetable_models import TimetableSchedule
            from timetable_helpers import get_class_schedule, get_teacher_schedule, get_current_academic_year
            from models import Class
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            view_type = request.args.get('view', 'class')
            entity_id = request.args.get('id', type=int)
            academic_year = request.args.get('year', get_current_academic_year())
            
            schedule = {}
            entity_name = ""
            
            if view_type == 'class' and entity_id:
                schedule = get_class_schedule(session_db, entity_id, school.id, academic_year)
                class_obj = session_db.query(Class).get(entity_id)
                if class_obj:
                    entity_name = f"Class {class_obj.class_name}-{class_obj.section}"
            elif view_type == 'teacher' and entity_id:
                schedule = get_teacher_schedule(session_db, entity_id, school.id, academic_year)
                teacher = session_db.query(Teacher).get(entity_id)
                if teacher:
                    entity_name = f"{teacher.full_name}"
            
            # Get all classes and teachers for dropdowns
            classes = session_db.query(Class).filter_by(
                tenant_id=school.id,
                is_active=True
            ).all()
            
            teachers = session_db.query(Teacher).filter_by(
                tenant_id=school.id,
                employee_status=EmployeeStatusEnum.ACTIVE
            ).all()
            
            return render_template('akademi/timetable/view_timetables.html',
                                 school=school,
                                 schedule=schedule,
                                 entity_name=entity_name,
                                 view_type=view_type,
                                 classes=classes,
                                 teachers=teachers,
                                 academic_year=academic_year,
                                 current_user=current_user)
        
        except Exception as e:
            logger.error(f"View timetables error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash(f'Error viewing timetables: {str(e)}', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/api/timetable/delete/<int:schedule_id>', methods=['POST'])
    @require_school_auth
    def delete_schedule(tenant_slug, schedule_id):
        """Delete a timetable schedule entry"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        session_db = get_session()
        try:
            from timetable_models import TimetableSchedule
            
            schedule = session_db.query(TimetableSchedule).filter_by(
                id=schedule_id,
                tenant_id=current_user.tenant_id
            ).first()
            
            if not schedule:
                return jsonify({'success': False, 'message': 'Schedule not found'}), 404
            
            session_db.delete(schedule)
            session_db.commit()
            
            return jsonify({'success': True, 'message': 'Schedule deleted successfully'})
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"Delete schedule error: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()

    # ===== VIEW TIMETABLE - NEW SELF-CONTAINED ROUTE =====
    
    @school_bp.route('/<tenant_slug>/timetable/view-class', methods=['GET'])
    @require_school_auth
    def view_class_timetable(tenant_slug):
        """View complete timetable for a selected class - completely self-contained"""
        session_db = get_session()
        try:
            from timetable_models import TimetableSchedule, TimeSlot, DayOfWeekEnum, TimeSlotClass
            from models import Class
            from teacher_models import Subject, Teacher
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            # Get all active classes for dropdown
            classes = session_db.query(Class).filter_by(
                tenant_id=school.id,
                is_active=True
            ).order_by(Class.class_name, Class.section).all()
            
            # Get selected class ID from query parameter
            selected_class_id = request.args.get('class_id', type=int)
            
            # Initialize timetable data
            timetable_data = None
            selected_class = None
            
            if selected_class_id:
                # Fetch the selected class
                selected_class = session_db.query(Class).filter_by(
                    id=selected_class_id,
                    tenant_id=school.id
                ).first()
                
                if selected_class:
                    # Fetch time slots assigned to this class (or unrestricted slots)
                    # Get all slots IDs that are either unrestricted or assigned to this class
                    all_tenant_slots = session_db.query(TimeSlot).filter_by(
                        tenant_id=school.id,
                        is_active=True
                    ).all()
                    
                    # Filter slots based on class assignments
                    time_slots = []
                    for slot in all_tenant_slots:
                        # Check if this slot has any class restrictions
                        restrictions = session_db.query(TimeSlotClass).filter_by(
                            time_slot_id=slot.id
                        ).count()
                        
                        if restrictions == 0:
                            # No restrictions - available to all classes
                            time_slots.append(slot)
                        else:
                            # Has restrictions - check if this class is included
                            is_assigned = session_db.query(TimeSlotClass).filter_by(
                                time_slot_id=slot.id,
                                class_id=selected_class_id
                            ).first()
                            if is_assigned:
                                time_slots.append(slot)
                    
                    # Sort the filtered slots
                    time_slots.sort(key=lambda x: (x.day_of_week.value, x.slot_order or 0, x.start_time))
                    
                    # Fetch all timetable schedules for this class
                    schedules = session_db.query(TimetableSchedule).filter_by(
                        tenant_id=school.id,
                        class_id=selected_class_id,
                        is_active=True
                    ).all()
                    
                    # Create a mapping of (day, time_slot_id) -> schedule
                    schedule_map = {}
                    for schedule in schedules:
                        key = (schedule.day_of_week.value, schedule.time_slot_id)
                        
                        # Get teacher and subject details
                        teacher = session_db.query(Teacher).get(schedule.teacher_id)
                        subject = session_db.query(Subject).get(schedule.subject_id)
                        
                        schedule_map[key] = {
                            'id': schedule.id,  # Add schedule ID for delete functionality
                            'subject': subject.name if subject else 'N/A',
                            'teacher': f"{teacher.first_name} {teacher.last_name}" if teacher else 'N/A',
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
            
            return render_template('akademi/timetable/view_class_timetable.html',
                                 school=school,
                                 classes=classes,
                                 selected_class=selected_class,
                                 timetable_data=timetable_data,
                                 current_user=current_user)
        
        except Exception as e:
            logger.error(f"View class timetable error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash(f'Error viewing timetable: {str(e)}', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/timetable/view-teacher', methods=['GET'])
    @require_school_auth
    def view_teacher_timetable(tenant_slug):
        """View complete timetable for a selected teacher - self-contained"""
        session_db = get_session()
        try:
            from timetable_models import TimetableSchedule, TimeSlot, DayOfWeekEnum, SubstituteAssignment
            from models import Class
            from teacher_models import Subject, Teacher
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            # Get all active teachers for dropdown
            teachers = session_db.query(Teacher).filter_by(
                tenant_id=school.id,
                employee_status=EmployeeStatusEnum.ACTIVE
            ).order_by(Teacher.first_name, Teacher.last_name).all()
            
            # Get selected teacher ID from query parameter
            selected_teacher_id = request.args.get('teacher_id', type=int)
            
            # Get selected date (default to today)
            from datetime import date
            selected_date_str = request.args.get('date')
            if selected_date_str:
                try:
                    selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
                except:
                    selected_date = date.today()
            else:
                selected_date = date.today()
            
            # Initialize timetable data
            timetable_data = None
            selected_teacher = None
            
            if selected_teacher_id:
                # Fetch the selected teacher
                selected_teacher = session_db.query(Teacher).filter_by(
                    id=selected_teacher_id,
                    tenant_id=school.id
                ).first()
                
                if selected_teacher:
                    # Fetch all timetable schedules for this teacher
                    schedules = session_db.query(TimetableSchedule).filter_by(
                        tenant_id=school.id,
                        teacher_id=selected_teacher_id,
                        is_active=True
                    ).all()
                    
                    # Get all unique time slots from the schedules
                    time_slot_ids = set(s.time_slot_id for s in schedules)
                    time_slots = session_db.query(TimeSlot).filter(
                        TimeSlot.id.in_(time_slot_ids),
                        TimeSlot.is_active == True
                    ).all() if time_slot_ids else []
                    
                    # Sort the filtered slots
                    time_slots.sort(key=lambda x: (x.day_of_week.value, x.slot_order or 0, x.start_time))
                    
                    # Create a mapping of (day, time_slot_id) -> schedule
                    schedule_map = {}
                    for schedule in schedules:
                        key = (schedule.day_of_week.value, schedule.time_slot_id)
                        
                        # Get class and subject details
                        class_obj = session_db.query(Class).get(schedule.class_id)
                        subject = session_db.query(Subject).get(schedule.subject_id)
                        
                        # Check for substitute on selected date
                        substitute = session_db.query(SubstituteAssignment).filter_by(
                            schedule_id=schedule.id,
                            date=selected_date
                        ).first()
                        
                        schedule_map[key] = {
                            'id': schedule.id,
                            'class': f"{class_obj.class_name}-{class_obj.section}" if class_obj else 'N/A',
                            'subject': subject.name if subject else 'N/A',
                            'room': schedule.room_number or '-',
                            'has_substitute': substitute is not None,
                            'substitute_name': f"{substitute.substitute_teacher.first_name} {substitute.substitute_teacher.last_name}" if substitute and substitute.substitute_teacher else None
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
                                        'class': matching_slot.slot_type.value,
                                        'subject': '-',
                                        'room': '-',
                                        'is_break': True
                                    }
                                else:
                                    row['periods'][day] = {
                                        'is_empty': True,
                                        'time_slot_id': matching_slot.id
                                    }
                            else:
                                row['periods'][day] = None
                        
                        timetable_grid.append(row)
                    
                    timetable_data = {
                        'grid': timetable_grid,
                        'days': days_order
                    }
            
            return render_template('akademi/timetable/view_teacher_timetable.html',
                                 school=school,
                                 teachers=teachers,
                                 selected_teacher=selected_teacher,
                                 selected_date=selected_date,
                                 timetable_data=timetable_data,
                                 current_user=current_user)
        
        except Exception as e:
            logger.error(f"View teacher timetable error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash(f'Error viewing timetable: {str(e)}', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    # ===== SUBSTITUTION MANAGEMENT =====

    @school_bp.route('/<tenant_slug>/timetable/substitutions', methods=['GET'])
    @require_school_auth
    def substitution_dashboard(tenant_slug):
        """Substitution management dashboard - see teachers on leave and assign substitutes"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            from timetable_models import TimetableSchedule, TimeSlot, DayOfWeekEnum, SubstituteAssignment
            from leave_models import TeacherLeaveApplication, LeaveStatusEnum
            from models import Class
            from teacher_models import Subject, Teacher
            from datetime import date, timedelta
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            # Get selected date (default to today)
            selected_date_str = request.args.get('date')
            if selected_date_str:
                try:
                    selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
                except:
                    selected_date = date.today()
            else:
                selected_date = date.today()
            
            # Get day of week from selected date
            day_name = selected_date.strftime('%A')
            try:
                day_enum = DayOfWeekEnum[day_name.upper()]
            except:
                day_enum = None
            
            # Get teachers on approved leave for selected date
            teachers_on_leave = session_db.query(TeacherLeaveApplication).filter(
                TeacherLeaveApplication.tenant_id == school.id,
                TeacherLeaveApplication.status == LeaveStatusEnum.APPROVED,
                TeacherLeaveApplication.start_date <= selected_date,
                TeacherLeaveApplication.end_date >= selected_date
            ).all()
            
            # Build list of affected periods
            affected_periods = []
            for leave in teachers_on_leave:
                teacher = session_db.query(Teacher).get(leave.teacher_id)
                if not teacher:
                    continue
                
                # Get teacher's scheduled periods for this day
                if day_enum:
                    schedules = session_db.query(TimetableSchedule).filter_by(
                        tenant_id=school.id,
                        teacher_id=teacher.id,
                        day_of_week=day_enum,
                        is_active=True
                    ).all()
                    
                    for schedule in schedules:
                        time_slot = session_db.query(TimeSlot).get(schedule.time_slot_id)
                        class_obj = session_db.query(Class).get(schedule.class_id)
                        subject = session_db.query(Subject).get(schedule.subject_id)
                        
                        # Check if substitute already assigned
                        existing_sub = session_db.query(SubstituteAssignment).filter_by(
                            schedule_id=schedule.id,
                            date=selected_date
                        ).first()
                        
                        substitute_teacher = None
                        if existing_sub:
                            substitute_teacher = session_db.query(Teacher).get(existing_sub.substitute_teacher_id)
                        
                        affected_periods.append({
                            'schedule_id': schedule.id,
                            'teacher_id': teacher.id,
                            'teacher_name': f"{teacher.first_name} {teacher.last_name}",
                            'class': f"{class_obj.class_name}-{class_obj.section}" if class_obj else 'N/A',
                            'subject': subject.name if subject else 'N/A',
                            'time': f"{time_slot.start_time.strftime('%H:%M')} - {time_slot.end_time.strftime('%H:%M')}" if time_slot else 'N/A',
                            'time_slot_order': time_slot.slot_order if time_slot else 0,
                            'leave_reason': leave.reason or 'Leave',
                            'has_substitute': existing_sub is not None,
                            'substitute_id': existing_sub.id if existing_sub else None,
                            'substitute_teacher_id': existing_sub.substitute_teacher_id if existing_sub else None,
                            'substitute_name': f"{substitute_teacher.first_name} {substitute_teacher.last_name}" if substitute_teacher else None
                        })
            
            # Sort by time
            affected_periods.sort(key=lambda x: x['time_slot_order'])
            
            # ALSO get all substitutions for this date (including manual ones where teacher isn't on leave)
            all_substitutions_today = session_db.query(SubstituteAssignment).filter_by(
                tenant_id=school.id,
                date=selected_date
            ).all()
            
            # Get schedule IDs already in affected_periods (from leave-based logic)
            existing_schedule_ids = set(p['schedule_id'] for p in affected_periods)
            
            #Add manual substitutions that aren't already shown
            for sub in all_substitutions_today:
                if sub.schedule_id not in existing_schedule_ids:
                    # This is a manual substitution (teacher not on leave)
                    schedule = session_db.query(TimetableSchedule).get(sub.schedule_id)
                    if not schedule:
                        continue
                    
                    time_slot = session_db.query(TimeSlot).get(schedule.time_slot_id)
                    class_obj = session_db.query(Class).get(schedule.class_id)
                    subject = session_db.query(Subject).get(schedule.subject_id)
                    original_teacher = session_db.query(Teacher).get(sub.original_teacher_id)
                    substitute_teacher = session_db.query(Teacher).get(sub.substitute_teacher_id)
                    
                    affected_periods.append({
                        'schedule_id': schedule.id,
                        'teacher_id': sub.original_teacher_id,
                        'teacher_name': f"{original_teacher.first_name} {original_teacher.last_name}" if original_teacher else 'N/A',
                        'class': f"{class_obj.class_name}-{class_obj.section}" if class_obj else 'N/A',
                        'subject': subject.name if subject else 'N/A',
                        'time': f"{time_slot.start_time.strftime('%H:%M')} - {time_slot.end_time.strftime('%H:%M')}" if time_slot else 'N/A',
                        'time_slot_order': time_slot.slot_order if time_slot else 0,
                        'leave_reason': sub.reason or 'Manual Assignment',  # Use substitution reason
                        'has_substitute': True,
                        'substitute_id': sub.id,
                        'substitute_teacher_id': sub.substitute_teacher_id,
                        'substitute_name': f"{substitute_teacher.first_name} {substitute_teacher.last_name}" if substitute_teacher else None
                    })
            
            # Re-sort after adding manual substitutions
            affected_periods.sort(key=lambda x: x['time_slot_order'])
            
            # Get all active teachers for substitute dropdown (excluding those on leave)
            leave_teacher_ids = [leave.teacher_id for leave in teachers_on_leave]
            available_teachers = session_db.query(Teacher).filter(
                Teacher.tenant_id == school.id,
                Teacher.employee_status == EmployeeStatusEnum.ACTIVE,
                ~Teacher.id.in_(leave_teacher_ids) if leave_teacher_ids else True
            ).order_by(Teacher.first_name, Teacher.last_name).all()
            
            # Summary stats (now includes all substitutions)
            total_substitutions = len(all_substitutions_today)
            stats = {
                'teachers_on_leave': len(set(leave.teacher_id for leave in teachers_on_leave)),
                'total_periods_affected': len(affected_periods),
                'periods_with_substitute': total_substitutions,
                'periods_need_substitute': len(affected_periods) - total_substitutions
            }
            
            return render_template('akademi/timetable/substitution_dashboard.html',
                                 school=school,
                                 selected_date=selected_date,
                                 day_name=day_name,
                                 affected_periods=affected_periods,
                                 available_teachers=available_teachers,
                                 stats=stats,
                                 current_user=current_user)
        
        except Exception as e:
            logger.error(f"Substitution dashboard error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash(f'Error loading substitution dashboard: {str(e)}', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/api/timetable/assign-substitute', methods=['POST'])
    @require_school_auth
    def assign_substitute(tenant_slug):
        """Assign a substitute teacher to a period"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        session_db = get_session()
        try:
            from timetable_models import TimetableSchedule, SubstituteAssignment
            from teacher_models import Teacher
            from datetime import date
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'message': 'No data provided'}), 400
            
            schedule_id = int(data.get('schedule_id', 0))
            substitute_teacher_id = int(data.get('substitute_teacher_id', 0))
            date_str = data.get('date', '')
            reason = data.get('reason', '')
            
            if not all([schedule_id, substitute_teacher_id, date_str]):
                return jsonify({'success': False, 'message': 'Missing required fields'}), 400
            
            try:
                assignment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except:
                return jsonify({'success': False, 'message': 'Invalid date format'}), 400
            
            # Verify schedule exists
            schedule = session_db.query(TimetableSchedule).filter_by(
                id=schedule_id,
                tenant_id=school.id
            ).first()
            
            if not schedule:
                return jsonify({'success': False, 'message': 'Schedule not found'}), 404
            
            # Verify substitute teacher exists
            substitute = session_db.query(Teacher).filter_by(
                id=substitute_teacher_id,
                tenant_id=school.id
            ).first()
            
            if not substitute:
                return jsonify({'success': False, 'message': 'Substitute teacher not found'}), 404
            
            # Check if assignment already exists for this date
            existing = session_db.query(SubstituteAssignment).filter_by(
                schedule_id=schedule_id,
                date=assignment_date
            ).first()
            
            if existing:
                # Update existing assignment
                existing.substitute_teacher_id = substitute_teacher_id
                existing.reason = reason
                existing.updated_at = datetime.utcnow()
            else:
                # Create new assignment
                assignment = SubstituteAssignment(
                    tenant_id=school.id,
                    schedule_id=schedule_id,
                    original_teacher_id=schedule.teacher_id,
                    substitute_teacher_id=substitute_teacher_id,
                    date=assignment_date,
                    reason=reason,
                    created_by=current_user.id
                )
                session_db.add(assignment)
            
            session_db.commit()
            
            return jsonify({
                'success': True, 
                'message': f'Substitute {substitute.first_name} {substitute.last_name} assigned successfully'
            })
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"Assign substitute error: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/api/timetable/remove-substitute/<int:substitute_id>', methods=['POST', 'DELETE'])
    @require_school_auth
    def remove_substitute(tenant_slug, substitute_id):
        """Remove a substitute assignment"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        session_db = get_session()
        try:
            from timetable_models import SubstituteAssignment
            
            assignment = session_db.query(SubstituteAssignment).filter_by(
                id=substitute_id,
                tenant_id=current_user.tenant_id
            ).first()
            
            if not assignment:
                return jsonify({'success': False, 'message': 'Assignment not found'}), 404
            
            session_db.delete(assignment)
            session_db.commit()
            
            logger.info(f"Substitute assignment removed: id={substitute_id}")
            return jsonify({'success': True, 'message': 'Substitute removed successfully'})
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"Remove substitute error: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/api/timetable/teacher-schedule/<int:teacher_id>', methods=['GET'])
    @require_school_auth
    def get_teacher_schedule_for_date(tenant_slug, teacher_id):
        """Get teacher's schedule for a specific date (for manual substitution)"""
        session_db = get_session()
        try:
            from timetable_models import TimetableSchedule, TimeSlot, DayOfWeekEnum
            from models import Class
            from teacher_models import Subject, Teacher
            from datetime import datetime
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            # Get the date from query parameter
            date_str = request.args.get('date')
            if not date_str:
                return jsonify({'success': False, 'message': 'Date parameter required'}), 400
            
            try:
                selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except:
                return jsonify({'success': False, 'message': 'Invalid date format'}), 400
            
            # Get day of week
            day_name = selected_date.strftime('%A')
            try:
                day_enum = DayOfWeekEnum[day_name.upper()]
            except:
                return jsonify({'success': False, 'message': 'Invalid day'}), 400
            
            # Get teacher's schedule for this day
            schedules = session_db.query(TimetableSchedule).filter_by(
                tenant_id=school.id,
                teacher_id=teacher_id,
                day_of_week=day_enum,
                is_active=True
            ).all()
            
            schedule_list = []
            for schedule in schedules:
                time_slot = session_db.query(TimeSlot).get(schedule.time_slot_id)
                class_obj = session_db.query(Class).get(schedule.class_id)
                subject = session_db.query(Subject).get(schedule.subject_id)
                
                if time_slot:
                    schedule_list.append({
                        'id': schedule.id,
                        'time': f"{time_slot.start_time.strftime('%H:%M')} - {time_slot.end_time.strftime('%H:%M')}",
                        'class': f"{class_obj.class_name}-{class_obj.section}" if class_obj else 'N/A',
                        'subject': subject.name if subject else 'N/A',
                        'slot_order': time_slot.slot_order or 0
                    })
            
            # Sort by time
            schedule_list.sort(key=lambda x: x['slot_order'])
            
            return jsonify({'success': True, 'schedules': schedule_list})
        
        except Exception as e:
            logger.error(f"Get teacher schedule error: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()

    # ===== Timetable AJAX APIs =====

    @school_bp.route('/<tenant_slug>/api/timetable/class-subjects')
    @require_school_auth
    def api_class_subjects(tenant_slug):
        """Return subjects for the tenant (show all subjects irrespective of assignment)"""
        session_db = get_session()
        try:
            from teacher_models import Subject

            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404

            # Show all active subjects for the tenant
            subjects = session_db.query(Subject).filter_by(
                tenant_id=school.id,
                is_active=True
            ).order_by(Subject.name).all()
            return jsonify({'success': True, 'subjects': [{'id': s.id, 'name': s.name} for s in subjects]})
        except Exception as e:
            logger.error(f"API class-subjects error: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/api/timetable/available-teachers')
    @require_school_auth
    def api_available_teachers(tenant_slug):
        """Return available teachers for given class, subject, day and time slot"""
        session_db = get_session()
        try:
            from timetable_models import ClassTeacherAssignment, TimetableSchedule, DayOfWeekEnum
            from teacher_models import Teacher
            from timetable_helpers import get_current_academic_year

            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404

            class_id = request.args.get('class_id', type=int)
            subject_id = request.args.get('subject_id', type=int)
            day_of_week = request.args.get('day_of_week')  # Expect enum name e.g., MONDAY
            time_slot_id = request.args.get('time_slot_id', type=int)
            academic_year = request.args.get('academic_year', get_current_academic_year())

            if not all([class_id, subject_id, day_of_week, time_slot_id]):
                return jsonify({'success': False, 'message': 'class_id, subject_id, day_of_week, time_slot_id are required'}), 400

            try:
                day_enum = DayOfWeekEnum[day_of_week.upper()]
            except Exception:
                return jsonify({'success': False, 'message': 'Invalid day_of_week'}), 400

            # Teachers assigned to this class+subject
            assigned_teacher_ids = [row[0] for row in session_db.query(ClassTeacherAssignment.teacher_id).filter(
                ClassTeacherAssignment.tenant_id == school.id,
                ClassTeacherAssignment.class_id == class_id,
                ClassTeacherAssignment.subject_id == subject_id,
                ClassTeacherAssignment.removed_date.is_(None)
            ).distinct().all()]

            if not assigned_teacher_ids:
                return jsonify({'success': True, 'teachers': []})

            # Filter out teachers who already have a class at that day/slot
            busy_teacher_ids = [row[0] for row in session_db.query(TimetableSchedule.teacher_id).filter(
                TimetableSchedule.tenant_id == school.id,
                TimetableSchedule.day_of_week == day_enum,
                TimetableSchedule.time_slot_id == time_slot_id,
                TimetableSchedule.academic_year == academic_year,
                TimetableSchedule.is_active == True
            ).distinct().all()]

            available_ids = [tid for tid in assigned_teacher_ids if tid not in set(busy_teacher_ids)]

            if not available_ids:
                return jsonify({'success': True, 'teachers': []})

            teachers = session_db.query(Teacher).filter(Teacher.id.in_(available_ids)).order_by(Teacher.first_name, Teacher.last_name).all()
            data = [{'id': t.id, 'name': t.full_name} for t in teachers]
            return jsonify({'success': True, 'teachers': data})
        except Exception as e:
            logger.error(f"API available-teachers error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/api/timetable/class-schedule')
    @require_school_auth
    def api_class_schedule(tenant_slug):
        """Return a flat class schedule list for rendering a table"""
        session_db = get_session()
        try:
            from timetable_models import TimeSlot
            from timetable_helpers import get_class_schedule

            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404

            class_id = request.args.get('class_id', type=int)
            if not class_id:
                return jsonify({'success': False, 'message': 'class_id is required'}), 400

            schedule = get_class_schedule(session_db, class_id, school.id)
            return jsonify({'success': True, 'schedule': schedule})
        except Exception as e:
            logger.error(f"API class-schedule error: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/api/timetable/time-slots-by-day')
    @require_school_auth
    def api_time_slots_by_day(tenant_slug):
        """Return time slots filtered by day of week and optionally by class"""
        session_db = get_session()
        try:
            from timetable_models import TimeSlot, DayOfWeekEnum, TimeSlotClass

            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404

            day_of_week = request.args.get('day_of_week')
            if not day_of_week:
                return jsonify({'success': False, 'message': 'day_of_week is required'}), 400

            try:
                day_enum = DayOfWeekEnum[day_of_week.upper()]
            except Exception:
                return jsonify({'success': False, 'message': 'Invalid day_of_week'}), 400

            # Get optional class_id parameter for filtering
            class_id = request.args.get('class_id')

            # Get time slots for the specified day
            time_slots = session_db.query(TimeSlot).filter_by(
                tenant_id=school.id,
                day_of_week=day_enum,
                is_active=True
            ).order_by(TimeSlot.slot_order, TimeSlot.start_time).all()

            # Filter by class if provided (same logic as teacher/student filtering)
            if class_id:
                try:
                    class_id = int(class_id)
                    filtered_slots = []
                    
                    for slot in time_slots:
                        # Get class restrictions for this slot
                        slot_restrictions = session_db.query(TimeSlotClass).filter_by(
                            time_slot_id=slot.id,
                            is_active=True
                        ).all()
                        
                        # If no restrictions, slot is available to all classes
                        if not slot_restrictions:
                            filtered_slots.append(slot)
                        else:
                            # Check if this class is in the allowed list
                            allowed_class_ids = [r.class_id for r in slot_restrictions]
                            if class_id in allowed_class_ids:
                                filtered_slots.append(slot)
                    
                    time_slots = filtered_slots
                except ValueError:
                    logger.warning(f"Invalid class_id format: {class_id}")

            slots_data = [{
                'id': slot.id,
                'slot_name': slot.slot_name,
                'start_time': slot.start_time.strftime('%H:%M') if slot.start_time else '',
                'end_time': slot.end_time.strftime('%H:%M') if slot.end_time else '',
                'slot_type': slot.slot_type.value if slot.slot_type else 'Regular',
                'slot_order': slot.slot_order
            } for slot in time_slots]

            return jsonify({'success': True, 'time_slots': slots_data})
        except Exception as e:
            logger.error(f"API time-slots-by-day error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()

    # ===== SLOT GROUPS MANAGEMENT =====

    @school_bp.route('/<tenant_slug>/timetable/slot-groups', methods=['GET', 'POST'])
    @require_school_auth
    def slot_groups(tenant_slug):
        """Manage time slot groups for bulk period definition"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            from timetable_models import TimeSlotGroup, TimeSlotGroupClass, TimeSlot, TimeSlotClass
            from models import Class
            from sqlalchemy import func
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            if request.method == 'POST':
                # Create new group
                name = request.form.get('name', '').strip()
                display_order = request.form.get('display_order', 0, type=int)
                class_ids = request.form.getlist('class_ids')
                
                if not name:
                    flash('Group name is required', 'error')
                    return redirect(url_for('school.slot_groups', tenant_slug=tenant_slug))
                
                # Check if group name already exists
                existing = session_db.query(TimeSlotGroup).filter_by(
                    tenant_id=school.id,
                    name=name
                ).first()
                
                if existing:
                    flash('A group with this name already exists', 'error')
                    return redirect(url_for('school.slot_groups', tenant_slug=tenant_slug))
                
                # Create new group
                group = TimeSlotGroup(
                    tenant_id=school.id,
                    name=name,
                    display_order=display_order,
                    is_active=True
                )
                session_db.add(group)
                session_db.flush()  # Get the ID
                
                # Add class members
                for class_id in class_ids:
                    try:
                        class_int = int(class_id)
                        # Verify class exists
                        class_obj = session_db.query(Class).filter_by(
                            id=class_int,
                            tenant_id=school.id,
                            is_active=True
                        ).first()
                        if class_obj:
                            member = TimeSlotGroupClass(
                                tenant_id=school.id,
                                group_id=group.id,
                                class_id=class_int,
                                is_active=True
                            )
                            session_db.add(member)
                    except (ValueError, TypeError):
                        continue
                
                session_db.commit()
                flash(f'Time slot group "{name}" created successfully!', 'success')
                return redirect(url_for('school.slot_groups', tenant_slug=tenant_slug))
            
            # GET - List all groups
            groups = session_db.query(TimeSlotGroup).filter_by(
                tenant_id=school.id,
                is_active=True
            ).order_by(TimeSlotGroup.display_order, TimeSlotGroup.name).all()
            
            # Get all active classes
            all_classes = session_db.query(Class).filter_by(
                tenant_id=school.id,
                is_active=True
            ).order_by(Class.class_name, Class.section).all()
            
            # Get all class IDs that are assigned to any group
            assigned_class_ids = set()
            for group in groups:
                for member in group.group_classes:
                    if member.is_active:
                        assigned_class_ids.add(member.class_id)
            
            # Find unassigned classes
            unassigned_classes = [
                {'id': cls.id, 'name': f"{cls.class_name}-{cls.section}"}
                for cls in all_classes
                if cls.id not in assigned_class_ids
            ]
            
            # Build group data with timing info
            groups_data = []
            group_colors = ['#FFD93D', '#6BCB77', '#4D96FF', '#FF6B6B', '#C9B1FF', '#FF9F45']
            
            for idx, group in enumerate(groups):
                class_names = []
                class_ids_in_group = []
                
                for member in group.group_classes:
                    if member.class_ref and member.is_active:
                        class_names.append(f"{member.class_ref.class_name}-{member.class_ref.section}")
                        class_ids_in_group.append(member.class_id)
                
                # Calculate timing range from time slots assigned to these classes
                timing_start = None
                timing_end = None
                period_duration = None
                slot_count = 0
                
                if class_ids_in_group:
                    # Get all time slots assigned to classes in this group
                    slot_ids = session_db.query(TimeSlotClass.time_slot_id).filter(
                        TimeSlotClass.class_id.in_(class_ids_in_group),
                        TimeSlotClass.is_active == True
                    ).distinct().all()
                    slot_ids = [s[0] for s in slot_ids]
                    
                    if slot_ids:
                        # Get min start time and max end time
                        time_range = session_db.query(
                            func.min(TimeSlot.start_time),
                            func.max(TimeSlot.end_time)
                        ).filter(
                            TimeSlot.id.in_(slot_ids),
                            TimeSlot.is_active == True
                        ).first()
                        
                        if time_range[0] and time_range[1]:
                            timing_start = time_range[0].strftime('%I:%M %p')
                            timing_end = time_range[1].strftime('%I:%M %p')
                        
                        # Calculate average period duration
                        slots = session_db.query(TimeSlot).filter(
                            TimeSlot.id.in_(slot_ids),
                            TimeSlot.is_active == True,
                            TimeSlot.slot_type == 'Regular'
                        ).all()
                        
                        slot_count = len(slots)
                        if slots:
                            durations = []
                            for slot in slots:
                                if slot.start_time and slot.end_time:
                                    # Calculate duration in minutes
                                    start_mins = slot.start_time.hour * 60 + slot.start_time.minute
                                    end_mins = slot.end_time.hour * 60 + slot.end_time.minute
                                    durations.append(end_mins - start_mins)
                            if durations:
                                period_duration = sum(durations) // len(durations)
                
                is_configured = slot_count > 0
                
                groups_data.append({
                    'id': group.id,
                    'name': group.name,
                    'display_order': group.display_order,
                    'class_count': len(class_names),
                    'class_names': class_names,
                    'class_ids': class_ids_in_group,
                    'color': group_colors[idx % len(group_colors)],
                    'timing_start': timing_start,
                    'timing_end': timing_end,
                    'period_duration': period_duration,
                    'is_configured': is_configured,
                    'slot_count': slot_count
                })
            # Calculate next display order for new group
            max_order = 0
            for g in groups_data:
                if g['display_order'] and g['display_order'] > max_order:
                    max_order = g['display_order']
            next_display_order = max_order + 1
            
            return render_template('akademi/timetable/slot_groups.html',
                                 school=school,
                                 groups=groups_data,
                                 classes=all_classes,
                                 unassigned_classes=unassigned_classes,
                                 next_display_order=next_display_order,
                                 current_user=current_user)
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"Slot groups error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash(f'Error managing slot groups: {str(e)}', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/api/timetable/slot-groups/<int:group_id>/update', methods=['POST'])
    @require_school_auth
    def update_slot_group(tenant_slug, group_id):
        """Update a time slot group"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        session_db = get_session()
        try:
            from timetable_models import TimeSlotGroup, TimeSlotGroupClass
            from models import Class
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            group = session_db.query(TimeSlotGroup).filter_by(
                id=group_id,
                tenant_id=school.id
            ).first()
            
            if not group:
                return jsonify({'success': False, 'message': 'Group not found'}), 404
            
            # Update group details
            name = request.form.get('name', '').strip()
            display_order = request.form.get('display_order', 0, type=int)
            class_ids = request.form.getlist('class_ids[]')
            
            if name:
                # Check for duplicate name (excluding current group)
                existing = session_db.query(TimeSlotGroup).filter(
                    TimeSlotGroup.tenant_id == school.id,
                    TimeSlotGroup.name == name,
                    TimeSlotGroup.id != group_id
                ).first()
                if existing:
                    return jsonify({'success': False, 'message': 'A group with this name already exists'}), 400
                group.name = name
            
            group.display_order = display_order
            
            # Update class members - remove all existing and add new ones
            session_db.query(TimeSlotGroupClass).filter_by(
                group_id=group_id,
                tenant_id=school.id
            ).delete()
            
            for class_id in class_ids:
                try:
                    class_int = int(class_id)
                    class_obj = session_db.query(Class).filter_by(
                        id=class_int,
                        tenant_id=school.id,
                        is_active=True
                    ).first()
                    if class_obj:
                        member = TimeSlotGroupClass(
                            tenant_id=school.id,
                            group_id=group_id,
                            class_id=class_int,
                            is_active=True
                        )
                        session_db.add(member)
                except (ValueError, TypeError):
                    continue
            
            session_db.commit()
            return jsonify({'success': True, 'message': 'Group updated successfully'})
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"Update slot group error: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/api/timetable/slot-groups/<int:group_id>/delete', methods=['POST'])
    @require_school_auth
    def delete_slot_group(tenant_slug, group_id):
        """Delete a time slot group and all its associated time slots"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        session_db = get_session()
        try:
            from timetable_models import TimeSlotGroup, TimeSlotGroupClass, TimeSlot, TimeSlotClass
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            group = session_db.query(TimeSlotGroup).filter_by(
                id=group_id,
                tenant_id=school.id
            ).first()
            
            if not group:
                return jsonify({'success': False, 'message': 'Group not found'}), 404
            
            group_name = group.name
            
            # Get all class IDs in this group
            class_ids = [member.class_id for member in group.group_classes if member.is_active]
            
            # Find all time slots that are ONLY assigned to classes in this group
            # (i.e., slots where all TimeSlotClass entries belong to this group's classes)
            deleted_slots = 0
            if class_ids:
                # Get all time slot IDs that have assignments to ANY of the group's classes
                slot_ids_to_check = session_db.query(TimeSlotClass.time_slot_id).filter(
                    TimeSlotClass.class_id.in_(class_ids),
                    TimeSlotClass.tenant_id == school.id
                ).distinct().all()
                slot_ids_to_check = [s[0] for s in slot_ids_to_check]
                
                for slot_id in slot_ids_to_check:
                    # Check if this slot has assignments outside of the group's classes
                    external_assignments = session_db.query(TimeSlotClass).filter(
                        TimeSlotClass.time_slot_id == slot_id,
                        ~TimeSlotClass.class_id.in_(class_ids)
                    ).count()
                    
                    if external_assignments == 0:
                        # This slot is only used by this group - delete it
                        session_db.query(TimeSlotClass).filter_by(time_slot_id=slot_id).delete()
                        session_db.query(TimeSlot).filter_by(id=slot_id).delete()
                        deleted_slots += 1
                    else:
                        # Slot is shared - just remove the assignments for this group's classes
                        session_db.query(TimeSlotClass).filter(
                            TimeSlotClass.time_slot_id == slot_id,
                            TimeSlotClass.class_id.in_(class_ids)
                        ).delete(synchronize_session='fetch')
            
            # Delete group members
            session_db.query(TimeSlotGroupClass).filter_by(group_id=group_id).delete()
            
            # Delete the group itself
            session_db.delete(group)
            session_db.commit()
            
            message = f'Group "{group_name}" deleted successfully'
            if deleted_slots > 0:
                message += f' along with {deleted_slots} time slot(s)'
            
            return jsonify({'success': True, 'message': message})
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"Delete slot group error: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/api/timetable/slot-groups/<int:group_id>/classes', methods=['GET'])
    @require_school_auth
    def get_slot_group_classes(tenant_slug, group_id):
        """Get classes for a specific slot group"""
        session_db = get_session()
        try:
            from timetable_models import TimeSlotGroup, TimeSlotGroupClass
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            group = session_db.query(TimeSlotGroup).filter_by(
                id=group_id,
                tenant_id=school.id
            ).first()
            
            if not group:
                return jsonify({'success': False, 'message': 'Group not found'}), 404
            
            classes_data = []
            for member in group.group_classes:
                if member.class_ref and member.is_active:
                    classes_data.append({
                        'id': member.class_id,
                        'name': f"{member.class_ref.class_name}-{member.class_ref.section}"
                    })
            
            return jsonify({
                'success': True,
                'group_name': group.name,
                'classes': classes_data
            })
        
        except Exception as e:
            logger.error(f"Get slot group classes error: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()

    # ===== BULK TIME SLOTS CREATION =====

    @school_bp.route('/<tenant_slug>/timetable/bulk-time-slots', methods=['GET', 'POST'])
    @require_school_auth
    def bulk_time_slots(tenant_slug):
        """Create time slots for all classes in a group at once"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            from timetable_models import TimeSlotGroup, TimeSlotGroupClass, TimeSlot, TimeSlotClass, DayOfWeekEnum, SlotTypeEnum
            from models import Class
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            if request.method == 'POST':
                import json
            
                # Create time slots for all classes in the selected group
                group_id = request.form.get('group_id', type=int)
                days_str = request.form.get('days', '')  # Comma-separated days
                periods_json = request.form.get('periods_json', '[]')
            
                if not group_id:
                    flash('Please select a slot group', 'error')
                    return redirect(url_for('school.bulk_time_slots', tenant_slug=tenant_slug))
            
                days = [d.strip() for d in days_str.split(',') if d.strip()]
                if not days:
                    flash('Please select at least one day', 'error')
                    return redirect(url_for('school.bulk_time_slots', tenant_slug=tenant_slug))
            
                try:
                    periods = json.loads(periods_json)
                except json.JSONDecodeError:
                    flash('Invalid period data', 'error')
                    return redirect(url_for('school.bulk_time_slots', tenant_slug=tenant_slug))
            
                if not periods:
                    flash('Please add at least one period', 'error')
                    return redirect(url_for('school.bulk_time_slots', tenant_slug=tenant_slug))
            
                # Get the group and its classes
                group = session_db.query(TimeSlotGroup).filter_by(
                    id=group_id,
                    tenant_id=school.id,
                    is_active=True
                ).first()
            
                if not group:
                    flash('Slot group not found', 'error')
                    return redirect(url_for('school.bulk_time_slots', tenant_slug=tenant_slug))
            
                # Get class IDs from the group
                class_ids = [m.class_id for m in group.group_classes if m.is_active]
            
                if not class_ids:
                    flash('The selected group has no classes', 'error')
                    return redirect(url_for('school.bulk_time_slots', tenant_slug=tenant_slug))
            
                created_slots = 0
                created_assignments = 0
            
                for day_value in days:
                    try:
                        day_enum = DayOfWeekEnum[day_value.upper()]
                    
                        for period in periods:
                            slot_name = period.get('slot_name', '')
                            start_time = period.get('start_time', '')
                            end_time = period.get('end_time', '')
                            slot_type = period.get('slot_type', 'REGULAR')
                        
                            if not start_time or not end_time:
                                continue
                        
                            slot_type_enum = SlotTypeEnum[slot_type.upper()] if slot_type else SlotTypeEnum.REGULAR
                        
                            # Check if identical slot already exists
                            exists = session_db.query(TimeSlot).filter_by(
                                tenant_id=school.id,
                                day_of_week=day_enum,
                                start_time=datetime.strptime(start_time, '%H:%M').time(),
                                end_time=datetime.strptime(end_time, '%H:%M').time()
                            ).first()
                        
                            if exists:
                                # Use existing slot, just add class assignments
                                time_slot = exists
                            else:
                                # Create new time slot
                                time_slot = TimeSlot(
                                    tenant_id=school.id,
                                    day_of_week=day_enum,
                                    start_time=datetime.strptime(start_time, '%H:%M').time(),
                                    end_time=datetime.strptime(end_time, '%H:%M').time(),
                                    slot_name=slot_name,
                                    slot_type=slot_type_enum,
                                    slot_order=0,  # Will be recalculated
                                    is_active=True
                                )
                                session_db.add(time_slot)
                                session_db.flush()
                                created_slots += 1
                        
                            # Create TimeSlotClass assignments for each class in the group
                            for class_id in class_ids:
                                # Check if assignment already exists
                                existing_assignment = session_db.query(TimeSlotClass).filter_by(
                                    time_slot_id=time_slot.id,
                                    class_id=class_id
                                ).first()
                            
                                if not existing_assignment:
                                    assignment = TimeSlotClass(
                                        tenant_id=school.id,
                                        time_slot_id=time_slot.id,
                                        class_id=class_id,
                                        is_active=True
                                    )
                                    session_db.add(assignment)
                                    created_assignments += 1
                    
                    except Exception as e:
                        logger.error(f"Error creating slots for {day_value}: {e}")
                        continue
                
                # Recalculate slot orders for all affected days
                for day_value in days:
                    try:
                        day_enum = DayOfWeekEnum[day_value.upper()]
                        recalculate_slot_orders(session_db, school.id, day_enum)
                    except KeyError:
                        pass
                
                session_db.commit()
                
                if created_slots > 0 or created_assignments > 0:
                    flash(f'Successfully created {created_slots} time slot(s) with {created_assignments} class assignment(s) for group "{group.name}"!', 'success')
                    # Redirect to view the group's slots
                    return redirect(url_for('school.view_group_slots', tenant_slug=tenant_slug, group_id=group_id))
                else:
                    flash('No new time slots were created (slots may already exist)', 'info')
                
                return redirect(url_for('school.bulk_time_slots', tenant_slug=tenant_slug))
            
            # GET - Show bulk creation form
            groups = session_db.query(TimeSlotGroup).filter_by(
                tenant_id=school.id,
                is_active=True
            ).order_by(TimeSlotGroup.display_order, TimeSlotGroup.name).all()
            
            # Check for pre-selected group from query param
            preselected_group_id = request.args.get('group_id', type=int)
            preselected_group = None
            
            # Build groups data with class info
            groups_data = []
            for group in groups:
                class_names = []
                for member in group.group_classes:
                    if member.class_ref and member.is_active:
                        class_names.append(f"{member.class_ref.class_name}-{member.class_ref.section}")
                
                group_data = {
                    'id': group.id,
                    'name': group.name,
                    'class_count': len(class_names),
                    'class_names': class_names
                }
                groups_data.append(group_data)
                
                # Track preselected group
                if preselected_group_id and group.id == preselected_group_id:
                    preselected_group = group_data
            
            return render_template('akademi/timetable/bulk_time_slots.html',
                                 school=school,
                                 groups=groups_data,
                                 preselected_group=preselected_group,
                                 current_user=current_user)
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"Bulk time slots error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash(f'Error creating bulk time slots: {str(e)}', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/timetable/slot-groups/<int:group_id>/view', methods=['GET'])
    @require_school_auth
    def view_group_slots(tenant_slug, group_id):
        """View all time slots configured for a specific group"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            from timetable_models import TimeSlotGroup, TimeSlotGroupClass, TimeSlot, TimeSlotClass, DayOfWeekEnum
            from models import Class
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            # Get the group
            group = session_db.query(TimeSlotGroup).filter_by(
                id=group_id,
                tenant_id=school.id,
                is_active=True
            ).first()
            
            if not group:
                flash('Group not found', 'error')
                return redirect(url_for('school.slot_groups', tenant_slug=tenant_slug))
            
            # Get class IDs in this group
            class_ids_in_group = [m.class_id for m in group.group_classes if m.is_active]
            
            # Get class names for display
            class_names = []
            for member in group.group_classes:
                if member.class_ref and member.is_active:
                    class_names.append(f"{member.class_ref.class_name}-{member.class_ref.section}")
            
            # Get all time slot IDs assigned to these classes
            slot_ids = []
            if class_ids_in_group:
                slot_ids = [s[0] for s in session_db.query(TimeSlotClass.time_slot_id).filter(
                    TimeSlotClass.class_id.in_(class_ids_in_group),
                    TimeSlotClass.is_active == True
                ).distinct().all()]
            
            # Get time slots organized by day
            days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            slots_by_day = {day: [] for day in days_order}
            
            if slot_ids:
                slots = session_db.query(TimeSlot).filter(
                    TimeSlot.id.in_(slot_ids),
                    TimeSlot.is_active == True
                ).order_by(TimeSlot.slot_order, TimeSlot.start_time).all()
                
                for slot in slots:
                    day_name = slot.day_of_week.value
                    if day_name in slots_by_day:
                        slots_by_day[day_name].append({
                            'id': slot.id,
                            'slot_name': slot.slot_name or f"Period {slot.slot_order or ''}",
                            'start_time': slot.start_time.strftime('%I:%M %p') if slot.start_time else '',
                            'end_time': slot.end_time.strftime('%I:%M %p') if slot.end_time else '',
                            'slot_type': slot.slot_type.value if slot.slot_type else 'Regular',
                            'slot_order': slot.slot_order or 0,
                            'duration': None
                        })
                        
                        # Calculate duration
                        if slot.start_time and slot.end_time:
                            start_mins = slot.start_time.hour * 60 + slot.start_time.minute
                            end_mins = slot.end_time.hour * 60 + slot.end_time.minute
                            slots_by_day[day_name][-1]['duration'] = end_mins - start_mins
            
            # Count total slots and active days
            total_slots = sum(len(slots) for slots in slots_by_day.values())
            active_days = [day for day in days_order if slots_by_day[day]]
            
            # Get timing range
            timing_start = None
            timing_end = None
            if slot_ids:
                from sqlalchemy import func
                time_range = session_db.query(
                    func.min(TimeSlot.start_time),
                    func.max(TimeSlot.end_time)
                ).filter(
                    TimeSlot.id.in_(slot_ids),
                    TimeSlot.is_active == True
                ).first()
                
                if time_range[0] and time_range[1]:
                    timing_start = time_range[0].strftime('%I:%M %p')
                    timing_end = time_range[1].strftime('%I:%M %p')
            
            group_data = {
                'id': group.id,
                'name': group.name,
                'class_count': len(class_names),
                'class_names': class_names,
                'total_slots': total_slots,
                'active_days': len(active_days),
                'timing_start': timing_start,
                'timing_end': timing_end
            }
            
            return render_template('akademi/timetable/view_group_slots.html',
                                 school=school,
                                 group=group_data,
                                 slots_by_day=slots_by_day,
                                 days_order=days_order,
                                 current_user=current_user)
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"View group slots error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash(f'Error viewing group slots: {str(e)}', 'error')
            return redirect(url_for('school.slot_groups', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/api/timetable/delete-time-slots', methods=['POST'])
    @require_school_auth
    def delete_time_slots(tenant_slug):
        """Delete multiple time slots at once"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        session_db = get_session()
        try:
            from timetable_models import TimeSlot, TimeSlotClass
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            slot_ids = request.form.getlist('slot_ids[]')
            
            if not slot_ids:
                return jsonify({'success': False, 'message': 'No time slots selected'}), 400
            
            deleted_count = 0
            for slot_id in slot_ids:
                try:
                    slot_int = int(slot_id)
                    # Verify slot belongs to this school
                    slot = session_db.query(TimeSlot).filter_by(
                        id=slot_int,
                        tenant_id=school.id
                    ).first()
                    
                    if slot:
                        # Delete associated TimeSlotClass entries first
                        session_db.query(TimeSlotClass).filter_by(
                            time_slot_id=slot_int
                        ).delete()
                        
                        # Delete the time slot
                        session_db.delete(slot)
                        deleted_count += 1
                except (ValueError, TypeError):
                    continue
            
            session_db.commit()
            return jsonify({
                'success': True, 
                'message': f'Successfully deleted {deleted_count} time slot(s)'
            })
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"Delete time slots error: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/api/timetable/update-time-slot/<int:slot_id>', methods=['POST'])
    @require_school_auth
    def update_time_slot(tenant_slug, slot_id):
        """Update a time slot's details"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        session_db = get_session()
        try:
            from timetable_models import TimeSlot, SlotTypeEnum
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            # Get the time slot
            slot = session_db.query(TimeSlot).filter_by(
                id=slot_id,
                tenant_id=school.id
            ).first()
            
            if not slot:
                return jsonify({'success': False, 'message': 'Time slot not found'}), 404
            
            # Update fields
            slot_name = request.form.get('slot_name', '').strip()
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            slot_type = request.form.get('slot_type', 'REGULAR')
            
            time_changed = False
            
            if slot_name:
                slot.slot_name = slot_name
            
            if start_time:
                new_start = datetime.strptime(start_time, '%H:%M').time()
                if slot.start_time != new_start:
                    slot.start_time = new_start
                    time_changed = True
            
            if end_time:
                slot.end_time = datetime.strptime(end_time, '%H:%M').time()
            
            if slot_type:
                try:
                    slot.slot_type = SlotTypeEnum[slot_type.upper()]
                except KeyError:
                    pass
            
            # Recalculate slot orders if time changed
            if time_changed:
                recalculate_slot_orders(session_db, school.id, slot.day_of_week)
            
            session_db.commit()
            return jsonify({
                'success': True, 
                'message': 'Time slot updated successfully'
            })
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"Update time slot error: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/api/timetable/get-time-slot/<int:slot_id>', methods=['GET'])
    @require_school_auth
    def get_time_slot(tenant_slug, slot_id):
        """Get a time slot's details for editing"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        session_db = get_session()
        try:
            from timetable_models import TimeSlot
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            slot = session_db.query(TimeSlot).filter_by(
                id=slot_id,
                tenant_id=school.id
            ).first()
            
            if not slot:
                return jsonify({'success': False, 'message': 'Time slot not found'}), 404
            
            return jsonify({
                'success': True,
                'slot': {
                    'id': slot.id,
                    'slot_name': slot.slot_name or '',
                    'start_time': slot.start_time.strftime('%H:%M') if slot.start_time else '',
                    'end_time': slot.end_time.strftime('%H:%M') if slot.end_time else '',
                    'slot_type': slot.slot_type.name if slot.slot_type else 'REGULAR',
                    'slot_order': slot.slot_order or 1,
                    'day_of_week': slot.day_of_week.value if slot.day_of_week else ''
                }
            })
        
        except Exception as e:
            logger.error(f"Get time slot error: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()

    # ==========================================
    # WORKLOAD REPORT ROUTES
    # ==========================================

    @school_bp.route('/<tenant_slug>/timetable/workload-report', methods=['GET'])
    @require_school_auth
    def workload_report(tenant_slug):
        """Teacher workload analytics dashboard"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            from timetable_helpers import (
                get_or_create_workload_settings,
                get_all_teachers_workload,
                identify_workload_issues,
                get_subject_distribution,
                get_class_distribution,
                get_workload_stats
            )
            from teacher_models import Department
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            # Get filters from query params
            filters = {
                'department': request.args.get('department', 'all'),
                'status': request.args.get('status', 'all')
            }
            
            # Get settings
            settings = get_or_create_workload_settings(session_db, school.id)
            
            # Get workload data
            workload_data = get_all_teachers_workload(session_db, school.id, filters)
            
            # Get stats
            stats = get_workload_stats(workload_data)
            
            # Generate alerts
            alerts = identify_workload_issues(workload_data, settings)
            
            # Get distributions
            subject_distribution = get_subject_distribution(session_db, school.id)
            class_distribution = get_class_distribution(session_db, school.id)
            
            # Get departments for filter dropdown
            departments = session_db.query(Department.name).filter_by(
                tenant_id=school.id, is_active=True
            ).distinct().all()
            departments = [d[0] for d in departments]
            
            return render_template(
                'akademi/timetable/workload_report.html',
                school=school,
                workload_data=workload_data,
                stats=stats,
                alerts=alerts,
                subject_distribution=subject_distribution,
                class_distribution=class_distribution,
                departments=departments,
                settings=settings,
                current_filters=filters
            )
        
        except Exception as e:
            logger.error(f"Workload report error: {e}")
            import traceback
            traceback.print_exc()
            flash('Error loading workload report', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/timetable/workload-settings', methods=['GET', 'POST'])
    @require_school_auth
    def workload_settings(tenant_slug):
        """Configure workload thresholds"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            from timetable_helpers import get_or_create_workload_settings
            from teacher_models import Department
            import json
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            settings = get_or_create_workload_settings(session_db, school.id)
            
            if request.method == 'POST':
                # Update settings
                settings.max_periods_per_week = int(request.form.get('max_periods', 35))
                settings.max_consecutive_periods = int(request.form.get('max_consecutive', 4))
                settings.optimal_min_percent = int(request.form.get('optimal_min', 60))
                settings.optimal_max_percent = int(request.form.get('optimal_max', 85))
                
                # Handle department overrides
                dept_overrides = {}
                dept_names = request.form.getlist('dept_name[]')
                dept_max_periods = request.form.getlist('dept_max_periods[]')
                
                for i, dept_name in enumerate(dept_names):
                    if dept_name and dept_max_periods[i]:
                        dept_overrides[dept_name] = {
                            'max_periods_per_week': int(dept_max_periods[i])
                        }
                
                settings.set_department_overrides(dept_overrides)
                session_db.commit()
                
                flash('Workload settings saved successfully', 'success')
                return redirect(url_for('school.workload_report', tenant_slug=tenant_slug))
            
            # Get departments for override dropdown
            departments = session_db.query(Department).filter_by(
                tenant_id=school.id, is_active=True
            ).all()
            
            return render_template(
                'akademi/timetable/workload_settings.html',
                school=school,
                settings=settings,
                departments=departments
            )
        
        except Exception as e:
            logger.error(f"Workload settings error: {e}")
            flash('Error loading workload settings', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/api/timetable/workload-data', methods=['GET'])
    @require_school_auth
    def workload_api(tenant_slug):
        """JSON API for AJAX filtering of workload data"""
        session_db = get_session()
        try:
            from timetable_helpers import (
                get_all_teachers_workload,
                get_workload_stats
            )
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            filters = {
                'department': request.args.get('department', 'all'),
                'status': request.args.get('status', 'all')
            }
            
            workload_data = get_all_teachers_workload(session_db, school.id, filters)
            stats = get_workload_stats(workload_data)
            
            return jsonify({
                'success': True,
                'workload_data': workload_data,
                'stats': stats
            })
        
        except Exception as e:
            logger.error(f"Workload API error: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()

    # ===== AUTO TIMETABLE GENERATION ROUTES =====
    
    @school_bp.route('/<tenant_slug>/timetable/auto-generate', methods=['GET'])
    @require_school_auth
    def auto_generate_timetable_page(tenant_slug):
        """Auto generate timetable for a class"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            from models import Class
            from timetable_models import ClassTeacherAssignment
            from timetable_helpers import get_current_academic_year
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            # Get all active classes
            classes = session_db.query(Class).filter_by(
                tenant_id=school.id,
                is_active=True
            ).order_by(Class.class_name, Class.section).all()
            
            academic_year = get_current_academic_year()
            
            return render_template('akademi/timetable/auto_generate.html',
                                 school=school,
                                 classes=classes,
                                 academic_year=academic_year,
                                 current_user=current_user)
        
        except Exception as e:
            logger.error(f"Auto generate page error: {e}")
            import traceback
            traceback.print_exc()
            flash(f'Error loading auto generate page: {str(e)}', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/api/timetable/class-assignments/<int:class_id>', methods=['GET'])
    @require_school_auth
    def get_class_assignments_api(tenant_slug, class_id):
        """Get teacher-subject assignments for a class"""
        session_db = get_session()
        try:
            from models import Class
            from timetable_models import ClassTeacherAssignment
            from teacher_models import Teacher, Subject
            from timetable_helpers import get_current_academic_year
            from sqlalchemy.orm import joinedload
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            academic_year = get_current_academic_year()
            
            # Get class info
            class_obj = session_db.query(Class).filter_by(
                id=class_id,
                tenant_id=school.id
            ).first()
            
            if not class_obj:
                return jsonify({'success': False, 'message': 'Class not found'}), 404
            
            # Get all teacher-subject assignments for this class
            assignments = session_db.query(ClassTeacherAssignment).options(
                joinedload(ClassTeacherAssignment.teacher),
                joinedload(ClassTeacherAssignment.subject)
            ).filter(
                ClassTeacherAssignment.tenant_id == school.id,
                ClassTeacherAssignment.class_id == class_id,
                ClassTeacherAssignment.removed_date.is_(None)
            ).all()
            
            assignments_data = []
            class_teacher_id = None
            
            for assignment in assignments:
                if assignment.is_class_teacher:
                    class_teacher_id = assignment.teacher_id
                
                assignments_data.append({
                    'id': assignment.id,
                    'teacher_id': assignment.teacher_id,
                    'teacher_name': f"{assignment.teacher.first_name} {assignment.teacher.last_name}" if assignment.teacher else 'N/A',
                    'subject_id': assignment.subject_id,
                    'subject_name': assignment.subject.name if assignment.subject else 'N/A',
                    'is_class_teacher': assignment.is_class_teacher
                })
            
            return jsonify({
                'success': True,
                'class_name': f"{class_obj.class_name}-{class_obj.section}",
                'class_teacher_id': class_teacher_id,
                'assignments': assignments_data
            })
        
        except Exception as e:
            logger.error(f"Get class assignments API error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/api/timetable/auto-generate', methods=['POST'])
    @require_school_auth
    def auto_generate_api(tenant_slug):
        """Generate or apply auto-generated timetable"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        session_db = get_session()
        try:
            from timetable_helpers import (
                auto_generate_timetable,
                apply_generated_timetable,
                get_current_academic_year
            )
            from teacher_models import Teacher, Subject
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'message': 'No data provided'}), 400
            
            class_id = data.get('class_id')
            period_config = data.get('period_config', {})
            class_teacher_first_slot = data.get('class_teacher_first_slot', False)
            action = data.get('action', 'preview')  # 'preview' or 'apply'
            academic_year = data.get('academic_year', get_current_academic_year())
            
            if not class_id:
                return jsonify({'success': False, 'message': 'Class ID is required'}), 400
            
            if not period_config:
                return jsonify({'success': False, 'message': 'Period configuration is required'}), 400
            
            # Generate the timetable
            result = auto_generate_timetable(
                session_db,
                class_id,
                school.id,
                period_config,
                class_teacher_first_slot,
                academic_year
            )
            
            if not result['success'] and result['errors']:
                return jsonify({
                    'success': False,
                    'message': result['errors'][0],
                    'errors': result['errors']
                }), 400
            
            # Enrich schedule data with teacher/subject names for display
            for schedule in result['schedules']:
                teacher = session_db.query(Teacher).get(schedule['teacher_id'])
                subject = session_db.query(Subject).get(schedule['subject_id'])
                schedule['teacher_name'] = f"{teacher.first_name} {teacher.last_name}" if teacher else 'N/A'
                schedule['subject_name'] = subject.name if subject else 'N/A'
            
            if action == 'apply':
                # Apply the generated timetable to database
                apply_result = apply_generated_timetable(
                    session_db,
                    class_id,
                    school.id,
                    result['schedules'],
                    academic_year,
                    clear_existing=True
                )
                
                if not apply_result['success']:
                    return jsonify({
                        'success': False,
                        'message': 'Failed to apply timetable',
                        'errors': apply_result['errors']
                    }), 500
                
                return jsonify({
                    'success': True,
                    'message': f"Timetable applied successfully! {apply_result['created']} periods created.",
                    'created': apply_result['created'],
                    'warnings': result['warnings']
                })
            
            # Preview mode - just return the generated schedules
            return jsonify({
                'success': True,
                'schedules': result['schedules'],
                'warnings': result['warnings'],
                'total_scheduled': len(result['schedules'])
            })
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"Auto generate API error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()

