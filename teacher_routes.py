
from flask import render_template, request, redirect, url_for, flash, g, jsonify, current_app
from flask_login import current_user
from sqlalchemy import desc, or_, extract
from datetime import datetime
import logging

from db_single import get_session
from models import User, Tenant, Student, Exam, StudentMark
from teacher_models import Teacher, EmployeeStatusEnum

logger = logging.getLogger(__name__)

def register_teacher_routes(school_bp, require_school_auth):
    @school_bp.route('/<tenant_slug>/teachers')
    @require_school_auth
    def teachers(tenant_slug):
        """List all teachers in this school with filters, search, and pagination"""
        session_db = get_session()
        try:
            from teacher_models import Department, Designation, Subject, TeacherDepartment, TeacherDesignation, TeacherSubject
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            # Get filter parameters
            search_query = request.args.get('search', '').strip()
            department_id = request.args.get('department_id', '').strip()
            designation_id = request.args.get('designation_id', '').strip()
            subject_id = request.args.get('subject_id', '').strip()
            status = request.args.get('status', '').strip()
            sort_by = request.args.get('sort_by', 'newest').strip()
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 12))  # 12 cards per page for grid layout
            
            # Base query
            query = session_db.query(Teacher).filter_by(tenant_id=school.id)
            
            # Apply search filter
            if search_query:
                search_pattern = f"%{search_query}%"
                query = query.filter(
                    or_(
                        Teacher.first_name.ilike(search_pattern),
                        Teacher.last_name.ilike(search_pattern),
                        Teacher.email.ilike(search_pattern),
                        Teacher.employee_id.ilike(search_pattern),
                        Teacher.phone_primary.ilike(search_pattern)
                    )
                )
            
            # Apply department filter
            if department_id:
                query = query.join(TeacherDepartment).filter(
                    TeacherDepartment.department_id == int(department_id),
                    TeacherDepartment.removed_date.is_(None)
                )
            
            # Apply designation filter
            if designation_id:
                query = query.join(TeacherDesignation).filter(
                    TeacherDesignation.designation_id == int(designation_id),
                    TeacherDesignation.removed_date.is_(None)
                )
            
            # Apply subject filter
            if subject_id:
                query = query.join(TeacherSubject).filter(
                    TeacherSubject.subject_id == int(subject_id),
                    TeacherSubject.removed_date.is_(None)
                )
            
            # Apply status filter
            if status:
                query = query.filter(Teacher.employee_status == status)
            
            # Apply sorting
            # When no status filter, show Active first
            from sqlalchemy import case
            from teacher_models import EmployeeStatusEnum
            status_priority = case(
                (Teacher.employee_status == EmployeeStatusEnum.ACTIVE, 0),
                else_=1
            )
            
            if sort_by == 'newest':
                if not status:
                    query = query.order_by(status_priority, desc(Teacher.created_at))
                else:
                    query = query.order_by(desc(Teacher.created_at))
            elif sort_by == 'oldest':
                if not status:
                    query = query.order_by(status_priority, Teacher.created_at)
                else:
                    query = query.order_by(Teacher.created_at)
            elif sort_by == 'name_asc':
                if not status:
                    query = query.order_by(status_priority, Teacher.first_name, Teacher.last_name)
                else:
                    query = query.order_by(Teacher.first_name, Teacher.last_name)
            elif sort_by == 'name_desc':
                if not status:
                    query = query.order_by(status_priority, desc(Teacher.first_name), desc(Teacher.last_name))
                else:
                    query = query.order_by(desc(Teacher.first_name), desc(Teacher.last_name))
            elif sort_by == 'emp_id':
                if not status:
                    query = query.order_by(status_priority, Teacher.employee_id)
                else:
                    query = query.order_by(Teacher.employee_id)
            else:
                if not status:
                    query = query.order_by(status_priority, Teacher.first_name, Teacher.last_name)
                else:
                    query = query.order_by(Teacher.first_name, Teacher.last_name)
            
            # Get total count before pagination
            total_teachers = query.count()
            
            # Apply pagination
            offset = (page - 1) * per_page
            teachers = query.offset(offset).limit(per_page).all()
            
            # Calculate pagination data
            total_pages = (total_teachers + per_page - 1) // per_page  # Ceiling division
            has_prev = page > 1
            has_next = page < total_pages
            
            # Get filter options
            departments = session_db.query(Department).filter_by(
                tenant_id=school.id, is_active=True
            ).order_by(Department.name).all()
            
            designations = session_db.query(Designation).filter_by(
                tenant_id=school.id, is_active=True
            ).order_by(Designation.hierarchy_level, Designation.name).all()
            
            subjects = session_db.query(Subject).filter_by(
                tenant_id=school.id, is_active=True
            ).order_by(Subject.name).all()
            
            # Create filter object for template
            current_filters = {
                'search': search_query,
                'department_id': department_id,
                'designation_id': designation_id,
                'subject_id': subject_id,
                'status': status,
                'sort_by': sort_by,
                'page': page,
                'per_page': per_page
            }
            
            # Pagination info
            pagination = {
                'page': page,
                'per_page': per_page,
                'total': total_teachers,
                'total_pages': total_pages,
                'has_prev': has_prev,
                'has_next': has_next,
                'start': offset + 1 if total_teachers > 0 else 0,
                'end': min(offset + per_page, total_teachers)
            }
            
            return render_template('akademi/teacher/teacher.html', 
                                 school=school,
                                 teachers=teachers,
                                 departments=departments,
                                 designations=designations,
                                 subjects=subjects,
                                 current_filters=current_filters,
                                 pagination=pagination,
                                 current_user=current_user)
                                 
        except Exception as e:
            logger.error(f"Teachers list error for {tenant_slug}: {e}")
            import traceback
            traceback.print_exc()
            flash('Error loading teachers', 'error')
            return render_template('akademi/teacher/teacher.html', 
                                 school={'name': tenant_slug, 'slug': tenant_slug},
                                 teachers=[],
                                 departments=[],
                                 designations=[],
                                 subjects=[],
                                 current_filters={},
                                 pagination={'page': 1, 'total': 0, 'total_pages': 0})
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/teachers/add', methods=['GET', 'POST'])
    @require_school_auth
    def add_teacher(tenant_slug):
        """Add new teacher to this school"""
        # Allow school_admin and portal_admin to add teachers
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash(f'Access denied - admin only (Your role: {current_user.role})', 'error')
            return redirect(url_for('school.teachers', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            from teacher_validators import TeacherValidator, ValidationError, format_validation_error
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            
            if request.method == 'POST':
                try:
                    # Validate all form data using comprehensive validator
                    validated_data = TeacherValidator.validate_all_teacher_data(request.form)
                    
                except ValidationError as ve:
                    flash(format_validation_error(ve), 'error')
                    return render_template('akademi/teacher/add-teacher.html', school=school, form_data=request.form)
                except Exception as e:
                    flash(f'Validation error: {str(e)}', 'error')
                    return render_template('akademi/teacher/add-teacher.html', school=school, form_data=request.form)
                
                # Check if employee ID already exists in this school
                existing = session_db.query(Teacher).filter_by(
                    tenant_id=school.id,
                    employee_id=validated_data['employee_id']
                ).first()
                
                if existing:
                    flash('Employee ID already exists in this school', 'error')
                    return render_template('akademi/teacher/add-teacher.html', school=school, form_data=request.form)
                
                # Check if email already exists
                existing_email = session_db.query(Teacher).filter_by(email=validated_data['email']).first()
                if existing_email:
                    flash('Email already exists', 'error')
                    return render_template('akademi/teacher/add-teacher.html', school=school, form_data=request.form)
                
                # Handle file upload
                photo_url = None
                if 'photo' in request.files:
                    photo = request.files['photo']
                    if photo and photo.filename:
                        from werkzeug.utils import secure_filename
                        import os
                        
                        # Create tenant/employee specific upload directory
                        upload_dir = os.path.join('akademi', 'static', 'uploads', 'documents', str(school.id), 'teachers', validated_data['employee_id'])
                        os.makedirs(upload_dir, exist_ok=True)

                        # Secure the filename and save
                        filename = secure_filename(f"{validated_data['employee_id']}_{photo.filename}")
                        filepath = os.path.join(upload_dir, filename)
                        photo.save(filepath)
                        photo_url = f"uploads/documents/{school.id}/teachers/{validated_data['employee_id']}/{filename}"
                
                # Create new teacher with validated data
                new_teacher = Teacher(
                    tenant_id=school.id,
                    employee_id=validated_data['employee_id'],
                    first_name=validated_data['first_name'],
                    middle_name=validated_data['middle_name'],
                    last_name=validated_data['last_name'],
                    gender=validated_data['gender'],
                    date_of_birth=validated_data['date_of_birth'],
                    photo_url=photo_url,
                    email=validated_data['email'],
                    phone_primary=validated_data['phone_primary'],
                    phone_alternate=validated_data['phone_alternate'],
                    address_street=validated_data['address_street'],
                    address_city=validated_data['address_city'],
                    address_state=validated_data['address_state'],
                    address_pincode=validated_data['address_pincode'],
                    emergency_contact_name=validated_data['emergency_contact_name'],
                    emergency_contact_number=validated_data['emergency_contact_number'],
                    joining_date=validated_data['joining_date'],
                    employee_status=validated_data['employee_status']
                )
                
                session_db.add(new_teacher)
                session_db.commit()
                
                flash(f'Teacher "{validated_data["first_name"]} {validated_data["last_name"]}" added successfully!', 'success')
                return redirect(url_for('school.teachers', tenant_slug=tenant_slug))
            
            return render_template('akademi/teacher/add-teacher.html', school=school)
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Add teacher error for {tenant_slug}: {e}")
            flash(f'Error adding teacher: {str(e)}', 'error')
            return redirect(url_for('school.teachers', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/teachers/template.csv')
    @require_school_auth
    def download_teacher_template(tenant_slug):
        """Return a CSV template for bulk teacher upload (tenant-scoped)."""
        import csv
        import io

        headers = [
            'employee_id', 'first_name', 'middle_name', 'last_name', 'gender', 'date_of_birth',
            'email', 'phone_primary', 'phone_alternate', 'address_street', 'address_city', 'address_state', 'address_pincode',
            'emergency_contact_name', 'emergency_contact_number', 'joining_date', 'employee_status'
        ]

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerow(['EMP001', 'First', '', 'Last', 'Male', '1985-05-01', 'teacher@example.com', '9876500001', '', 'Street', 'City', 'State', '400001', 'Contact Name', '9876500001', '2020-06-01', 'Active'])

        csv_data = output.getvalue()
        output.close()

        from flask import make_response
        resp = make_response(csv_data)
        resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
        resp.headers['Content-Disposition'] = f'attachment; filename={tenant_slug}_teacher_upload_template.csv'
        return resp


    @school_bp.route('/<tenant_slug>/teachers/bulk-upload', methods=['POST'])
    @require_school_auth
    def bulk_upload_teachers(tenant_slug):
        """Tenant-scoped bulk CSV teacher upload handler."""
        import csv
        import io
        from datetime import datetime
        from sqlalchemy.exc import IntegrityError

        file = request.files.get('csv_file')
        if not file:
            flash('No file uploaded.', 'danger')
            return redirect(url_for('school.add_teacher', tenant_slug=tenant_slug))

        session_db = get_session()
        errors = []
        valid_rows = []

        try:
            stream = io.StringIO(file.stream.read().decode('utf-8-sig'))
            reader = csv.DictReader(stream)

            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'danger')
                return redirect(url_for('admin.admin_login'))

            # First pass: validate all rows
            seen_employee_ids = set()
            
            for row_no, row in enumerate(reader, start=2):
                row = {k.strip(): (v.strip() if v is not None else '') for k, v in row.items()}
                employee_id = row.get('employee_id')
                first_name = row.get('first_name')
                last_name = row.get('last_name')
                phone_primary = row.get('phone_primary')
                joining_date = row.get('joining_date')

                # Check required fields
                if not employee_id:
                    errors.append(f'Row {row_no}: employee_id is required')
                    continue
                if not first_name:
                    errors.append(f'Row {row_no}: first_name is required')
                    continue
                if not last_name:
                    errors.append(f'Row {row_no}: last_name is required')
                    continue
                if not phone_primary:
                    errors.append(f'Row {row_no}: phone_primary is required')
                    continue

                # Check duplicate employee_id in file
                if employee_id in seen_employee_ids:
                    errors.append(f'Row {row_no}: Duplicate employee_id "{employee_id}" in file')
                    continue
                seen_employee_ids.add(employee_id)

                # Check if employee_id already exists in database
                existing = session_db.query(Teacher).filter_by(
                    tenant_id=school.id, employee_id=employee_id
                ).first()
                if existing:
                    errors.append(f'Row {row_no}: Employee ID "{employee_id}" already exists')
                    continue

                # Parse dates
                dob = None
                if row.get('date_of_birth'):
                    try:
                        dob = datetime.strptime(row.get('date_of_birth'), '%Y-%m-%d').date()
                    except ValueError:
                        errors.append(f'Row {row_no}: Invalid date_of_birth format (use YYYY-MM-DD)')
                        continue

                jdate = datetime.utcnow().date()
                if joining_date:
                    try:
                        jdate = datetime.strptime(joining_date, '%Y-%m-%d').date()
                    except ValueError:
                        errors.append(f'Row {row_no}: Invalid joining_date format (use YYYY-MM-DD)')
                        continue

                # Normalize gender
                raw_gender = (row.get('gender') or '').strip()
                gender_val = None
                if raw_gender:
                    rg = raw_gender.upper()
                    if rg in ('M', 'MALE'):
                        gender_val = 'Male'
                    elif rg in ('F', 'FEMALE'):
                        gender_val = 'Female'
                    elif rg in ('O', 'OTHER'):
                        gender_val = 'Other'
                    else:
                        candidate = raw_gender.capitalize()
                        if candidate in ('Male', 'Female', 'Other'):
                            gender_val = candidate

                valid_rows.append({
                    'tenant_id': school.id,
                    'employee_id': employee_id,
                    'first_name': first_name,
                    'middle_name': row.get('middle_name') or None,
                    'last_name': last_name,
                    'gender': gender_val,
                    'date_of_birth': dob,
                    'email': row.get('email') or None,
                    'phone_primary': phone_primary,
                    'phone_alternate': row.get('phone_alternate') or None,
                    'address_street': row.get('address_street') or None,
                    'address_city': row.get('address_city') or None,
                    'address_state': row.get('address_state') or None,
                    'address_pincode': row.get('address_pincode') or None,
                    'emergency_contact_name': row.get('emergency_contact_name') or None,
                    'emergency_contact_number': row.get('emergency_contact_number') or None,
                    'joining_date': jdate,
                    'employee_status': row.get('employee_status') or 'Active'
                })

            # If any errors, abort entire upload
            if errors:
                error_msg = f'Upload failed. {len(errors)} error(s) found:<br>' + '<br>'.join(errors[:10])
                if len(errors) > 10:
                    error_msg += f'<br>... and {len(errors) - 10} more errors'
                flash(error_msg, 'danger')
                return redirect(url_for('school.add_teacher', tenant_slug=tenant_slug))

            if not valid_rows:
                flash('No valid rows found in CSV', 'warning')
                return redirect(url_for('school.add_teacher', tenant_slug=tenant_slug))

            # Second pass: insert all valid rows
            for row_data in valid_rows:
                new_teacher = Teacher(**row_data)
                session_db.add(new_teacher)

            session_db.commit()
            flash(f'Bulk upload successful: {len(valid_rows)} teachers added', 'success')

        except Exception as e:
            session_db.rollback()
            flash(f'Error processing CSV: {str(e)}', 'danger')
        finally:
            session_db.close()

        return redirect(url_for('school.add_teacher', tenant_slug=tenant_slug))
    
    # Old examinations route - replaced by new examination system
    # @school_bp.route('/<tenant_slug>/examinations')
    # @require_school_auth
    # def examinations(tenant_slug):
    #     """List all examinations in this school - View Results"""
    #     session_db = get_session()
    #     try:
    #         school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
    #         exams = session_db.query(Exam).filter_by(
    #             tenant_id=school.id
    #         ).order_by(desc(Exam.created_at)).all()
    #         
    #         return render_template('akademi/examination/view-results.html', 
    #                              school=school,
    #                              examinations=exams,
    #                              current_user=current_user)
    #                              
    #     except Exception as e:
    #         logger.error(f"Examinations list error for {tenant_slug}: {e}")
    #         flash('Error loading examinations', 'error')
    #         return render_template('akademi/examination/view-results.html', 
    #                              school={'name': tenant_slug, 'slug': tenant_slug},
    #                              examinations=[])
    #     finally:
    #         session_db.close()
       

    @school_bp.route('/<tenant_slug>/teachers/<int:id>')
    @require_school_auth
    def teacher_details(tenant_slug, id):
        """View individual teacher details"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
                
            teacher = session_db.query(Teacher).filter_by(
                id=id, tenant_id=school.id
            ).first()
            
            if not teacher:
                flash('Teacher not found', 'error')
                return redirect(url_for('school.teachers', tenant_slug=tenant_slug))
                
            return render_template('akademi/teacher/teacher-details.html', 
                                 school=school,
                                 teacher=teacher,
                                 current_user=current_user)
                                 
        except Exception as e:
            logger.error(f"Teacher details error for {tenant_slug}: {e}")
            flash('Error loading teacher details', 'error')
            return redirect(url_for('school.teachers', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/teachers/<int:id>/profile')
    @require_school_auth
    def teacher_profile(tenant_slug, id):
        """View comprehensive teacher profile with all related data"""
        session_db = get_session()
        try:
            from teacher_models import (
                Department, Designation, Subject,
                TeacherDepartment, TeacherDesignation, TeacherSubject,
                Qualification, TeacherExperience, TeacherCertification,
                TeacherDocument
            )
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
                
            teacher = session_db.query(Teacher).filter_by(
                id=id, tenant_id=school.id
            ).first()
            
            if not teacher:
                flash('Teacher not found', 'error')
                return redirect(url_for('school.teachers', tenant_slug=tenant_slug))
            
            # Get all related data
            departments = session_db.query(TeacherDepartment).filter_by(
                teacher_id=teacher.id, tenant_id=school.id, removed_date=None
            ).all()
            
            designations = session_db.query(TeacherDesignation).filter_by(
                teacher_id=teacher.id, tenant_id=school.id, removed_date=None
            ).all()
            
            subjects = session_db.query(TeacherSubject).filter_by(
                teacher_id=teacher.id, tenant_id=school.id, removed_date=None
            ).all()
            
            qualifications = session_db.query(Qualification).filter_by(
                teacher_id=teacher.id, tenant_id=school.id
            ).order_by(Qualification.is_highest.desc(), Qualification.year_of_completion.desc()).all()
            
            experiences = session_db.query(TeacherExperience).filter_by(
                teacher_id=teacher.id, tenant_id=school.id
            ).order_by(TeacherExperience.from_date.desc()).all()
            
            certifications = session_db.query(TeacherCertification).filter_by(
                teacher_id=teacher.id, tenant_id=school.id
            ).order_by(TeacherCertification.is_valid.desc(), TeacherCertification.issue_date.desc()).all()
            
            documents = session_db.query(TeacherDocument).filter_by(
                teacher_id=teacher.id, tenant_id=school.id
            ).order_by(TeacherDocument.uploaded_at.desc()).all()
            
            # Get primary designation
            primary_designation = session_db.query(TeacherDesignation).filter_by(
                teacher_id=teacher.id, tenant_id=school.id, is_primary=True, removed_date=None
            ).first()
                
            return render_template('akademi/teacher/teacher-profile.html', 
                                 school=school,
                                 teacher=teacher,
                                 departments=departments,
                                 designations=designations,
                                 subjects=subjects,
                                 qualifications=qualifications,
                                 experiences=experiences,
                                 certifications=certifications,
                                 documents=documents,
                                 primary_designation=primary_designation,
                                 current_user=current_user)
                                 
        except Exception as e:
            logger.error(f"Teacher profile error for {tenant_slug}: {e}")
            import traceback
            traceback.print_exc()
            flash('Error loading teacher profile', 'error')
            return redirect(url_for('school.teachers', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/teachers/<int:id>/profile/edit', methods=['GET', 'POST'])
    @require_school_auth
    def teacher_profile_edit(tenant_slug, id):
        """Edit/Complete teacher profile"""
        from werkzeug.utils import secure_filename
        import os
        from datetime import datetime
        from teacher_validators import TeacherValidator, ValidationError, format_validation_error
        
        session_db = get_session()
        try:
            from teacher_models import (
                Department, Designation, Subject,
                TeacherDepartment, TeacherDesignation, TeacherSubject,
                Qualification, TeacherExperience, TeacherCertification,
                TeacherDocument, TeacherBankingDetails
            )
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
                
            teacher = session_db.query(Teacher).filter_by(
                id=id, tenant_id=school.id
            ).first()
            
            if not teacher:
                flash('Teacher not found', 'error')
                return redirect(url_for('school.teachers', tenant_slug=tenant_slug))
            
            if request.method == 'POST':
                # Get the action type (save or finish)
                submit_action = request.form.get('submit_action', 'save')
                current_tab = request.args.get('tab', '0')
                
                try:
                    # Validate basic teacher information
                    validated_data = TeacherValidator.validate_all_teacher_data(request.form)
                    
                    # Store original status before update to detect resignation
                    original_status = teacher.employee_status
                    
                    # Update basic info with validated data
                    teacher.first_name = validated_data['first_name']
                    teacher.middle_name = validated_data['middle_name']
                    teacher.last_name = validated_data['last_name']
                    teacher.gender = validated_data['gender']
                    teacher.date_of_birth = validated_data['date_of_birth']
                    teacher.email = validated_data['email']
                    teacher.phone_primary = validated_data['phone_primary']
                    teacher.phone_alternate = validated_data['phone_alternate']
                    teacher.address_street = validated_data['address_street']
                    teacher.address_city = validated_data['address_city']
                    teacher.address_state = validated_data['address_state']
                    teacher.address_pincode = validated_data['address_pincode']
                    teacher.emergency_contact_name = validated_data['emergency_contact_name']
                    teacher.emergency_contact_number = validated_data['emergency_contact_number']
                    teacher.employee_id = validated_data['employee_id']
                    teacher.joining_date = validated_data['joining_date']
                    teacher.employee_status = validated_data['employee_status']
                    
                    # Check if status changed to RESIGNED and trigger cleanup
                    new_status = validated_data['employee_status']
                    if new_status == EmployeeStatusEnum.RESIGNED and original_status != EmployeeStatusEnum.RESIGNED:
                        from teacher_resignation_handler import handle_teacher_resignation
                        resignation_result = handle_teacher_resignation(
                            session=session_db,
                            teacher_id=id,
                            tenant_id=school.id
                        )
                        if resignation_result['success']:
                            logger.info(f"Teacher {id} resignation cleanup completed via profile edit")
                            # Add flash message about cleanup
                            cleanup_msg = f"Teacher marked as resigned. "
                            if resignation_result.get('timetable_schedules_deactivated', 0) > 0:
                                cleanup_msg += f"{resignation_result['timetable_schedules_deactivated']} schedules deactivated. "
                            if resignation_result.get('leave_applications_cancelled', 0) > 0:
                                cleanup_msg += f"{resignation_result['leave_applications_cancelled']} pending leaves cancelled. "
                            if resignation_result.get('pending_question_paper_assignments', 0) > 0 or resignation_result.get('pending_copy_checking_assignments', 0) > 0:
                                cleanup_msg += "Please reassign pending exam assignments."
                            flash(cleanup_msg, 'warning')
                    
                except ValidationError as ve:
                    flash(format_validation_error(ve), 'error')
                    # Reload form data
                    all_departments = session_db.query(Department).filter_by(tenant_id=school.id).order_by(Department.name).all()
                    all_designations = session_db.query(Designation).filter_by(tenant_id=school.id).order_by(Designation.name).all()
                    all_subjects = session_db.query(Subject).filter_by(tenant_id=school.id).order_by(Subject.name).all()
                    return render_template('akademi/teacher/edit-teacher-profile.html',
                                         teacher=teacher,
                                         school=school,
                                         all_departments=all_departments,
                                         all_designations=all_designations,
                                         all_subjects=all_subjects,
                                         current_user=current_user,
                                         current_tab=current_tab,
                                         form_data=request.form)
                except Exception as e:
                    flash(f'Validation error: {str(e)}', 'error')
                    all_departments = session_db.query(Department).filter_by(tenant_id=school.id).order_by(Department.name).all()
                    all_designations = session_db.query(Designation).filter_by(tenant_id=school.id).order_by(Designation.name).all()
                    all_subjects = session_db.query(Subject).filter_by(tenant_id=school.id).order_by(Subject.name).all()
                    return render_template('akademi/teacher/edit-teacher-profile.html',
                                         teacher=teacher,
                                         school=school,
                                         all_departments=all_departments,
                                         all_designations=all_designations,
                                         all_subjects=all_subjects,
                                         current_user=current_user,
                                         current_tab=current_tab,
                                         form_data=request.form)
                
                try:
                    
                    # Handle photo removal request from client
                    remove_photo = request.form.get('remove_photo', '0')
                    if remove_photo == '1':
                        try:
                            # Delete current photo file from disk if exists
                            if teacher.photo_url:
                                file_rel = teacher.photo_url.lstrip('/\\')
                                file_path = os.path.join('akademi', 'static', file_rel)
                                if os.path.exists(file_path):
                                    os.remove(file_path)
                                else:
                                    logger.debug(f"Teacher photo file not found for deletion: {file_path}")
                        except Exception as e:
                            logger.error(f"Error removing teacher photo file: {e}")
                        # Clear DB field
                        teacher.photo_url = None

                    # Handle photo upload (takes precedence over remove flag if a new file is uploaded)
                    if 'photo' in request.files:
                        photo = request.files['photo']
                        if photo and photo.filename:
                            # If an existing photo is present, attempt to delete it to avoid orphan files
                            try:
                                if teacher.photo_url:
                                    old_rel = teacher.photo_url.lstrip('/\\')
                                    old_path = os.path.join('akademi', 'static', old_rel)
                                    if os.path.exists(old_path):
                                        os.remove(old_path)
                            except Exception as e:
                                logger.error(f"Error removing old teacher photo before saving new one: {e}")
                            filename = secure_filename(photo.filename)
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            filename = f"{teacher.employee_id}_{timestamp}_{filename}"
                            # Save photo under tenant/teacher id folder
                            upload_folder = os.path.join('akademi', 'static', 'uploads', 'documents', str(school.id), 'teachers', str(teacher.id))
                            os.makedirs(upload_folder, exist_ok=True)
                            photo_path = os.path.join(upload_folder, filename)
                            photo.save(photo_path)
                            teacher.photo_url = f"uploads/documents/{school.id}/teachers/{teacher.id}/{filename}"
                    
                    session_db.commit()
                    
                    # Update Departments
                    # Delete existing departments
                    session_db.query(TeacherDepartment).filter_by(teacher_id=teacher.id).delete()
                    
                    dept_ids = request.form.getlist('dept_id[]')
                    dept_dates = request.form.getlist('dept_date[]')
                    dept_primaries = request.form.getlist('dept_primary[]')
                    
                    for i, dept_id in enumerate(dept_ids):
                        if dept_id:
                            td = TeacherDepartment(
                                tenant_id=school.id,  # FIX: Add tenant_id
                                teacher_id=teacher.id,
                                department_id=int(dept_id),
                                assigned_date=datetime.strptime(dept_dates[i], '%Y-%m-%d').date() if i < len(dept_dates) and dept_dates[i] else datetime.now().date(),
                                is_primary=(str(i) in dept_primaries)
                            )
                            session_db.add(td)
                    
                    # Update Designations
                    session_db.query(TeacherDesignation).filter_by(teacher_id=teacher.id).delete()
                    
                    desig_ids = request.form.getlist('desig_id[]')
                    desig_dates = request.form.getlist('desig_date[]')
                    desig_primaries = request.form.getlist('desig_primary[]')
                    
                    for i, desig_id in enumerate(desig_ids):
                        if desig_id:
                            td = TeacherDesignation(
                                tenant_id=school.id,  # FIX: Add tenant_id
                                teacher_id=teacher.id,
                                designation_id=int(desig_id),
                                assigned_date=datetime.strptime(desig_dates[i], '%Y-%m-%d').date() if i < len(desig_dates) and desig_dates[i] else datetime.now().date(),
                                is_primary=(str(i) in desig_primaries)
                            )
                            session_db.add(td)
                    
                    # Update Subjects
                    session_db.query(TeacherSubject).filter_by(teacher_id=teacher.id).delete()
                    
                    subj_ids = request.form.getlist('subj_id[]')
                    subj_proficiencies = request.form.getlist('subj_proficiency[]')
                    subj_dates = request.form.getlist('subj_date[]')
                    
                    for i, subj_id in enumerate(subj_ids):
                        if subj_id:
                            ts = TeacherSubject(
                                tenant_id=school.id,  # FIX: Add tenant_id
                                teacher_id=teacher.id,
                                subject_id=int(subj_id),
                                proficiency_level=subj_proficiencies[i] if i < len(subj_proficiencies) else 'Advanced',
                                assigned_date=datetime.strptime(subj_dates[i], '%Y-%m-%d').date() if i < len(subj_dates) and subj_dates[i] else datetime.now().date()
                            )
                            session_db.add(ts)
                    
                    # Update Qualifications
                    session_db.query(Qualification).filter_by(teacher_id=teacher.id).delete()
                    
                    qual_names = request.form.getlist('qual_name[]')
                    qual_types = request.form.getlist('qual_type[]')
                    qual_institutions = request.form.getlist('qual_institution[]')
                    qual_specializations = request.form.getlist('qual_specialization[]')
                    qual_years = request.form.getlist('qual_year[]')
                    qual_highest = request.form.getlist('qual_highest[]')
                    
                    for i, qual_name in enumerate(qual_names):
                        if qual_name:
                            # Get qualification type or default to 'Other'
                            qual_type = qual_types[i] if i < len(qual_types) and qual_types[i] else 'Other'
                            
                            q = Qualification(
                                tenant_id=school.id,  # FIX: Add tenant_id
                                teacher_id=teacher.id,
                                qualification_name=qual_name,
                                qualification_type=qual_type,  # FIX: This is required, not nullable
                                institution=qual_institutions[i] if i < len(qual_institutions) else None,
                                specialization=qual_specializations[i] if i < len(qual_specializations) else None,
                                year_of_completion=int(qual_years[i]) if i < len(qual_years) and qual_years[i] else None,
                                is_highest=(str(i) in qual_highest)
                            )
                            session_db.add(q)
                    
                    # Update Experience
                    session_db.query(TeacherExperience).filter_by(teacher_id=teacher.id).delete()
                    
                    exp_institutions = request.form.getlist('exp_institution[]')
                    exp_roles = request.form.getlist('exp_role[]')
                    exp_froms = request.form.getlist('exp_from[]')
                    exp_tos = request.form.getlist('exp_to[]')
                    exp_durations = request.form.getlist('exp_duration[]')
                    exp_descriptions = request.form.getlist('exp_description[]')
                    exp_reasons = request.form.getlist('exp_reason[]')
                    
                    for i, exp_inst in enumerate(exp_institutions):
                        if exp_inst:
                            e = TeacherExperience(
                                tenant_id=school.id,  # FIX: Add tenant_id
                                teacher_id=teacher.id,
                                institution=exp_inst,  # FIX: Changed from institution_name
                                role=exp_roles[i] if i < len(exp_roles) else None,
                                from_date=datetime.strptime(exp_froms[i], '%Y-%m-%d').date() if i < len(exp_froms) and exp_froms[i] else None,
                                to_date=datetime.strptime(exp_tos[i], '%Y-%m-%d').date() if i < len(exp_tos) and exp_tos[i] else None,
                                duration_months=int(exp_durations[i]) if i < len(exp_durations) and exp_durations[i] else None,
                                description=exp_descriptions[i] if i < len(exp_descriptions) else None,
                                reason_for_leaving=exp_reasons[i] if i < len(exp_reasons) else None
                            )
                            session_db.add(e)
                    
                    # Update Certifications
                    session_db.query(TeacherCertification).filter_by(teacher_id=teacher.id).delete()
                    
                    cert_names = request.form.getlist('cert_name[]')
                    cert_types = request.form.getlist('cert_type[]')
                    cert_authorities = request.form.getlist('cert_authority[]')
                    cert_numbers = request.form.getlist('cert_number[]')
                    cert_issue_dates = request.form.getlist('cert_issue_date[]')
                    cert_expiry_dates = request.form.getlist('cert_expiry_date[]')
                    cert_valids = request.form.getlist('cert_valid[]')
                    
                    for i, cert_name in enumerate(cert_names):
                        if cert_name:
                            # Get certification type or default to 'Other'
                            cert_type = cert_types[i] if i < len(cert_types) and cert_types[i] else 'Other'
                            
                            c = TeacherCertification(
                                tenant_id=school.id,  # FIX: Add tenant_id
                                teacher_id=teacher.id,
                                certification_name=cert_name,
                                certification_type=cert_type,  # FIX: This is required, not nullable
                                issuing_authority=cert_authorities[i] if i < len(cert_authorities) else None,
                                certificate_number=cert_numbers[i] if i < len(cert_numbers) else None,
                                issue_date=datetime.strptime(cert_issue_dates[i], '%Y-%m-%d').date() if i < len(cert_issue_dates) and cert_issue_dates[i] else None,
                                expiry_date=datetime.strptime(cert_expiry_dates[i], '%Y-%m-%d').date() if i < len(cert_expiry_dates) and cert_expiry_dates[i] else None,
                                is_valid=(str(i) in cert_valids)
                            )
                            session_db.add(c)
                    
                    # Update Banking Details
                    # Get banking form data
                    account_holder_name = request.form.get('account_holder_name', '').strip()
                    bank_name = request.form.get('bank_name', '').strip()
                    branch_name = request.form.get('branch_name', '').strip()
                    account_number = request.form.get('account_number', '').strip()
                    confirm_account_number = request.form.get('confirm_account_number', '').strip()
                    ifsc_code = request.form.get('ifsc_code', '').strip().upper()
                    account_type = request.form.get('account_type', '').strip()
                    pan_number = request.form.get('pan_number', '').strip().upper()
                    uan_number = request.form.get('uan_number', '').strip()
                    pf_account_number = request.form.get('pf_account_number', '').strip()
                    esi_number = request.form.get('esi_number', '').strip()
                    banking_notes = request.form.get('banking_notes', '').strip()
                    
                    # Only process if at least basic banking info is provided
                    if account_holder_name and bank_name and account_number and ifsc_code and account_type:
                        # Validate account numbers match
                        if confirm_account_number and account_number != confirm_account_number:
                            flash('Account numbers do not match!', 'error')
                        else:
                            # Check if banking details already exist
                            banking_details = session_db.query(TeacherBankingDetails).filter_by(teacher_id=teacher.id).first()
                            
                            if banking_details:
                                # Update existing
                                banking_details.account_holder_name = account_holder_name
                                banking_details.bank_name = bank_name
                                banking_details.branch_name = branch_name if branch_name else None
                                banking_details.account_number = account_number
                                banking_details.ifsc_code = ifsc_code
                                banking_details.account_type = account_type
                                banking_details.pan_number = pan_number if pan_number else None
                                banking_details.uan_number = uan_number if uan_number else None
                                banking_details.pf_account_number = pf_account_number if pf_account_number else None
                                banking_details.esi_number = esi_number if esi_number else None
                                banking_details.notes = banking_notes if banking_notes else None
                                banking_details.updated_at = datetime.now()
                            else:
                                # Create new
                                banking_details = TeacherBankingDetails(
                                    tenant_id=school.id,
                                    teacher_id=teacher.id,
                                    account_holder_name=account_holder_name,
                                    bank_name=bank_name,
                                    branch_name=branch_name if branch_name else None,
                                    account_number=account_number,
                                    ifsc_code=ifsc_code,
                                    account_type=account_type,
                                    pan_number=pan_number if pan_number else None,
                                    uan_number=uan_number if uan_number else None,
                                    pf_account_number=pf_account_number if pf_account_number else None,
                                    esi_number=esi_number if esi_number else None,
                                    notes=banking_notes if banking_notes else None
                                )
                                session_db.add(banking_details)
                    
                    # Handle Salary Structure
                    from teacher_models import TeacherSalary
                    from datetime import date
                    
                    basic_salary = request.form.get('basic_salary')
                    if basic_salary and float(basic_salary) > 0:
                        # Parse effective_from date
                        effective_from_str = request.form.get('effective_from')
                        if effective_from_str:
                            try:
                                effective_from = datetime.strptime(effective_from_str, '%Y-%m-%d').date()
                            except:
                                effective_from = date.today()
                        else:
                            effective_from = date.today()
                        
                        # Check if salary record exists
                        existing_salary = session_db.query(TeacherSalary).filter_by(
                            teacher_id=teacher.id,
                            is_active=True
                        ).first()
                        
                        salary_data = {
                            'basic_salary': float(request.form.get('basic_salary', 0)),
                            'grade_pay': float(request.form.get('grade_pay', 0)),
                            'hra': float(request.form.get('hra', 0)),
                            'da': float(request.form.get('da', 0)),
                            'ta': float(request.form.get('ta', 0)),
                            'medical_allowance': float(request.form.get('medical_allowance', 0)),
                            'special_allowance': float(request.form.get('special_allowance', 0)),
                            'other_allowances': float(request.form.get('other_allowances', 0)),
                            'pf_employee': float(request.form.get('pf_employee', 0)),
                            'pf_employer': float(request.form.get('pf_employer', 0)),
                            'esi_employee': float(request.form.get('esi_employee', 0)),
                            'esi_employer': float(request.form.get('esi_employer', 0)),
                            'professional_tax': float(request.form.get('professional_tax', 0)),
                            'tds': float(request.form.get('tds', 0)),
                            'other_deductions': float(request.form.get('other_deductions', 0)),
                            'effective_from': effective_from,
                            'notes': request.form.get('salary_notes', ''),
                        }
                        
                        if existing_salary:
                            # Update existing record
                            for key, value in salary_data.items():
                                if value is not None and value != '':
                                    setattr(existing_salary, key, value)
                            existing_salary.updated_at = datetime.now()
                        else:
                            # Create new salary record
                            new_salary = TeacherSalary(
                                tenant_id=school.id,
                                teacher_id=teacher.id,
                                is_active=True,
                                **salary_data
                            )
                            session_db.add(new_salary)
                    
                    # Handle document uploads
                    if 'documents[]' in request.files:
                        docs = request.files.getlist('documents[]')
                        doc_types = request.form.getlist('doc_type[]')
                        
                        for i, doc in enumerate(docs):
                            if doc and doc.filename:
                                filename = secure_filename(doc.filename)
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                filename = f"{teacher.employee_id}_{timestamp}_{filename}"

                                # Build tenant/teacher specific upload folder
                                upload_folder = os.path.join(
                                    'akademi', 'static', 'uploads', 'documents',
                                    str(school.id), 'teachers', str(teacher.id)
                                )
                                os.makedirs(upload_folder, exist_ok=True)

                                doc_path = os.path.join(upload_folder, filename)
                                doc.save(doc_path)

                                # Get file size
                                file_size = os.path.getsize(doc_path) // 1024  # KB

                                # Get doc type or default to 'Other'
                                doc_type = doc_types[i] if i < len(doc_types) and doc_types[i] else 'Other'

                                # Store relative path (relative to static folder)
                                rel_path = f"uploads/documents/{school.id}/teachers/{teacher.id}/{filename}"

                                td = TeacherDocument(
                                    tenant_id=school.id,
                                    teacher_id=teacher.id,
                                    doc_type=doc_type,
                                    file_name=doc.filename,
                                    file_path=rel_path,
                                    file_size_kb=file_size,
                                    mime_type=doc.content_type,
                                    uploaded_at=datetime.now()
                                )
                                session_db.add(td)
                    
                    session_db.commit()
                    flash('Teacher profile updated successfully!', 'success')
                    
                    # If 'finish' action, redirect to teacher profile
                    # If 'save' action, reload the edit page with the same tab
                    if submit_action == 'finish':
                        return redirect(url_for('school.teacher_profile', tenant_slug=tenant_slug, id=id))
                    else:
                        # Reload the edit page with the current tab
                        return redirect(url_for('school.teacher_profile_edit', tenant_slug=tenant_slug, id=id, tab=current_tab))
                    
                except Exception as e:
                    session_db.rollback()
                    logger.error(f"Error updating teacher profile: {str(e)}")
                    flash(f'Error updating profile: {str(e)}', 'error')
            
            # GET request - load data for form
            # Get current tab from URL parameter (for reload after save)
            current_tab = request.args.get('tab', '0')
            
            # Get all available departments, designations, subjects for dropdowns
            all_departments = session_db.query(Department).filter_by(tenant_id=school.id).order_by(Department.name).all()
            all_designations = session_db.query(Designation).filter_by(tenant_id=school.id).order_by(Designation.name).all()
            all_subjects = session_db.query(Subject).filter_by(tenant_id=school.id).order_by(Subject.name).all()
            
            return render_template('akademi/teacher/edit-teacher-profile.html',
                                 teacher=teacher,
                                 school=school,
                                 all_departments=all_departments,
                                 all_designations=all_designations,
                                 all_subjects=all_subjects,
                                 current_user=current_user,
                                 current_tab=current_tab)
                                 
        except Exception as e:
            logger.error(f"Error in teacher_profile_edit: {str(e)}")
            flash(f'An error occurred: {str(e)}', 'error')
            return redirect(url_for('school.teachers', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/teachers/<int:id>/delete', methods=['POST'])
    @require_school_auth
    def delete_teacher(tenant_slug, id):
        """Delete a teacher (soft delete by marking as removed with comprehensive cleanup)"""
        if current_user.role not in ['school_admin']:
            return jsonify({'success': False, 'message': 'Access denied - admin only'}), 403
        
        session_db = get_session()
        try:
            from teacher_resignation_handler import handle_teacher_resignation
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
                
            teacher = session_db.query(Teacher).filter_by(
                id=id, tenant_id=school.id
            ).first()
            
            if not teacher:
                return jsonify({'success': False, 'message': 'Teacher not found'}), 404
            
            # Use comprehensive resignation handler for cleanup
            # This handles: auth deactivation, timetable removal, leave cancellation, etc.
            result = handle_teacher_resignation(
                session=session_db,
                teacher_id=id,
                tenant_id=school.id
            )
            
            if not result['success']:
                return jsonify({
                    'success': False, 
                    'message': f'Error processing resignation: {result.get("error", "Unknown error")}'
                }), 500
            
            session_db.commit()
            
            # Build detailed success message
            message = f'Teacher "{result["teacher_name"]}" has been removed successfully.'
            details = []
            if result.get('timetable_schedules_deactivated', 0) > 0:
                details.append(f'{result["timetable_schedules_deactivated"]} timetable schedules deactivated')
            if result.get('class_assignments_ended', 0) > 0:
                details.append(f'{result["class_assignments_ended"]} class assignments ended')
            if result.get('leave_applications_cancelled', 0) > 0:
                details.append(f'{result["leave_applications_cancelled"]} pending leaves cancelled')
            if result.get('pending_question_paper_assignments', 0) > 0:
                details.append(f'{result["pending_question_paper_assignments"]} question paper assignments need reassignment')
            if result.get('pending_copy_checking_assignments', 0) > 0:
                details.append(f'{result["pending_copy_checking_assignments"]} copy checking assignments need reassignment')
            
            return jsonify({
                'success': True, 
                'message': message,
                'details': details,
                'cleanup_summary': result
            }), 200
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Delete teacher error for {tenant_slug}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False, 
                'message': f'Error deleting teacher: {str(e)}'
            }), 500
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/teacher-detail')
    @require_school_auth
    def teacher_detail_page(tenant_slug):
        """Teacher detail page - shows list of teachers with detail links"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
                
            teachers = session_db.query(Teacher).filter_by(
                tenant_id=school.id
            ).order_by(Teacher.name).all()
            
            return render_template('akademi/teacher/teacher-details.html', 
                                 school=school,
                                 teachers=teachers,
                                 current_user=current_user)
                                 
        except Exception as e:
            logger.error(f"Teacher detail page error for {tenant_slug}: {e}")
            flash('Error loading teacher detail page', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/teachers/<int:teacher_id>/documents/<int:doc_id>/delete', methods=['POST'])
    @require_school_auth
    def delete_teacher_document(tenant_slug, teacher_id, doc_id):
        """Delete a teacher document: remove file from disk and delete DB record"""
        # Only allow school admins or portal admins to delete documents
        if current_user.role not in ['school_admin', 'portal_admin']:
            return jsonify({'success': False, 'message': 'Access denied - admin only'}), 403

        import os
        session_db = get_session()
        try:
            from teacher_models import TeacherDocument, Teacher

            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404

            # Verify teacher exists
            teacher = session_db.query(Teacher).filter_by(id=teacher_id, tenant_id=school.id).first()
            if not teacher:
                return jsonify({'success': False, 'message': 'Teacher not found'}), 404

            doc = session_db.query(TeacherDocument).filter_by(id=doc_id, teacher_id=teacher_id, tenant_id=school.id).first()
            if not doc:
                return jsonify({'success': False, 'message': 'Document not found'}), 404

            # Attempt to remove the file from filesystem
            try:
                file_rel = (doc.file_path or '').lstrip('/\\')

                # If file_path already contains tenant/teacher subfolders, use it directly.
                # Otherwise, attempt legacy location under uploads/documents
                candidate_paths = []
                # Primary: path stored relative to static folder
                candidate_paths.append(os.path.join('akademi', 'static', file_rel))

                # Legacy fallback: if file_rel points to uploads/documents/<filename>, also check legacy flat folder
                parts = file_rel.split('/') if file_rel else []
                if len(parts) >= 2 and parts[0] == 'uploads' and parts[1] == 'documents' and len(parts) <= 3:
                    # legacy filename at uploads/documents/<filename>
                    candidate_paths.append(os.path.join('akademi', 'static', 'uploads', 'documents', parts[-1]))

                removed = False
                for fp in candidate_paths:
                    if os.path.exists(fp):
                        os.remove(fp)
                        removed = True
                        break
                if not removed:
                    logger.debug(f"Document file not found on disk for removal: tried {candidate_paths}")
            except Exception as e:
                # Log but continue to delete db record
                logger.error(f"Error removing document file {doc.file_path}: {e}")

            # Delete DB record
            session_db.delete(doc)
            session_db.commit()

            return jsonify({'success': True, 'message': 'Document deleted successfully', 'doc_id': doc_id}), 200

        except Exception as e:
            session_db.rollback()
            logger.error(f"Error deleting teacher document for {tenant_slug}: {e}")
            return jsonify({'success': False, 'message': f'Error deleting document: {str(e)}'}), 500
        finally:
            session_db.close()

    # ===== ADDITIONAL ROUTES =====
    
    
   
    # Old add_examination route - replaced by new examination system
    # @school_bp.route('/<tenant_slug>/examinations/add', methods=['GET', 'POST'])
    # @require_school_auth
    # def add_examination(tenant_slug):
    #     """Add new examination"""
    #     session_db = get_session()
    #     try:
    #         school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
    #         if not school:
    #             flash('School not found', 'error')
    #             return redirect(url_for('admin.admin_login'))
    #             
    #         if request.method == 'POST':
    #             # Handle form submission
    #             flash('Examination added successfully', 'success')
    #             return redirect(url_for('school.examinations', tenant_slug=tenant_slug))
    #             
    #         return render_template('akademi/examination/add-exam.html', 
    #                              school=school,
    #                              current_user=current_user)
    #                              
    #     except Exception as e:
    #         logger.error(f"Add examination error for {tenant_slug}: {e}")
    #         flash('Error adding examination', 'error')
    #         return redirect(url_for('school.examinations', tenant_slug=tenant_slug))
    #     finally:
    #         session_db.close()
    
    
    # ===== MASTER DATA ROUTES =====
    
    @school_bp.route('/<tenant_slug>/master-data')
    @require_school_auth
    def master_data(tenant_slug):
        """Master Data Management - Departments, Designations, Subjects, Classes, Academic Sessions"""
        session_db = get_session()
        try:
            from teacher_models import Department, Designation, Subject
            from models import Class, AcademicSession
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            # Get all master data
            departments = session_db.query(Department).filter_by(
                tenant_id=school.id
            ).order_by(Department.name).all()
            
            designations = session_db.query(Designation).filter_by(
                tenant_id=school.id
            ).order_by(Designation.hierarchy_level, Designation.name).all()
            
            subjects = session_db.query(Subject).filter_by(
                tenant_id=school.id
            ).order_by(Subject.subject_type, Subject.name).all()
            
            classes = session_db.query(Class).filter_by(
                tenant_id=school.id
            ).order_by(Class.class_name, Class.section).all()
            
            academic_sessions = session_db.query(AcademicSession).filter_by(
                tenant_id=school.id
            ).order_by(AcademicSession.start_date.desc()).all()
            
            # Get WhatsApp settings
            from notification_models import WhatsAppSettings
            whatsapp_settings = session_db.query(WhatsAppSettings).filter_by(
                tenant_id=school.id
            ).first()
            
            return render_template('akademi/master-data.html',
                                 school=school,
                                 departments=departments,
                                 designations=designations,
                                 subjects=subjects,
                                 classes=classes,
                                 academic_sessions=academic_sessions,
                                 whatsapp_settings=whatsapp_settings,
                                 current_user=current_user)
        except Exception as e:
            logger.error(f"Master data error for {tenant_slug}: {e}")
            flash('Error loading master data', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    # DEPARTMENT ROUTES
    @school_bp.route('/<tenant_slug>/departments/add', methods=['POST'])
    @require_school_auth
    def add_department(tenant_slug):
        """Add new department"""
        session_db = get_session()
        try:
            from teacher_models import Department
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            name = request.form.get('name', '').strip()
            code = request.form.get('code', '').strip()
            description = request.form.get('description', '').strip()
            is_active = request.form.get('is_active') == 'on'
            
            if not name:
                flash('Department name is required', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # Check if department with same name exists
            existing = session_db.query(Department).filter_by(
                tenant_id=school.id,
                name=name
            ).first()
            
            if existing:
                flash(f'Department "{name}" already exists', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            department = Department(
                tenant_id=school.id,
                name=name,
                code=code if code else None,
                description=description if description else None,
                is_active=is_active
            )
            
            session_db.add(department)
            session_db.commit()
            
            flash(f'Department "{name}" added successfully!', 'success')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Add department error: {e}")
            flash(f'Error adding department: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/departments/<int:id>/edit', methods=['POST'])
    @require_school_auth
    def edit_department(tenant_slug, id):
        """Edit department"""
        session_db = get_session()
        try:
            from teacher_models import Department
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            department = session_db.query(Department).filter_by(
                id=id, tenant_id=school.id
            ).first()
            
            if not department:
                flash('Department not found', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            name = request.form.get('name', '').strip()
            code = request.form.get('code', '').strip()
            description = request.form.get('description', '').strip()
            is_active = request.form.get('is_active') == 'on'
            
            if not name:
                flash('Department name is required', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # Check if another department with same name exists
            existing = session_db.query(Department).filter_by(
                tenant_id=school.id,
                name=name
            ).filter(Department.id != id).first()
            
            if existing:
                flash(f'Department "{name}" already exists', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            department.name = name
            department.code = code if code else None
            department.description = description if description else None
            department.is_active = is_active
            
            session_db.commit()
            flash(f'Department "{name}" updated successfully!', 'success')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Edit department error: {e}")
            flash(f'Error updating department: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/departments/<int:id>/delete')
    @require_school_auth
    def delete_department(tenant_slug, id):
        """Delete department"""
        session_db = get_session()
        try:
            from teacher_models import Department, TeacherDepartment
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            department = session_db.query(Department).filter_by(
                id=id, tenant_id=school.id
            ).first()
            
            if not department:
                flash('Department not found', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # Check if department has any teachers assigned
            teacher_count = session_db.query(TeacherDepartment).filter_by(department_id=id).count()
            if teacher_count > 0:
                flash(f'Cannot delete department "{department.name}". It has {teacher_count} teacher(s) assigned. Please reassign teachers first.', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            name = department.name
            session_db.delete(department)
            session_db.commit()
            
            flash(f'Department "{name}" deleted successfully!', 'success')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Delete department error: {e}")
            flash(f'Error deleting department: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/departments/bulk-upload', methods=['GET', 'POST'])
    @require_school_auth
    def bulk_upload_departments(tenant_slug):
        """Bulk upload departments via CSV file"""
        session_db = get_session()
        try:
            from teacher_models import Department
            import csv
            import io
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            if request.method == 'GET':
                if request.args.get('template') == '1':
                    from flask import Response
                    csv_content = "name,code,description\nScience,SCI,Science Department\nArts,ART,Arts Department\nCommerce,COM,"
                    return Response(
                        csv_content,
                        mimetype='text/csv',
                        headers={'Content-Disposition': 'attachment; filename=departments_template.csv'}
                    )
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            if 'csv_file' not in request.files:
                flash('No file uploaded', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            file = request.files['csv_file']
            if file.filename == '' or not file.filename.endswith('.csv'):
                flash('Please upload a valid CSV file', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            try:
                stream = io.StringIO(file.stream.read().decode('utf-8-sig'))
                reader = csv.DictReader(stream)
                
                if 'name' not in (reader.fieldnames or []):
                    flash('Missing required column: name', 'error')
                    return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
                
                # First pass: validate all rows
                errors = []
                valid_rows = []
                
                for row_num, row in enumerate(reader, start=2):
                    name = row.get('name', '').strip()
                    
                    if not name:
                        errors.append(f'Row {row_num}: Name is required')
                        continue
                    
                    existing = session_db.query(Department).filter_by(tenant_id=school.id, name=name).first()
                    if existing:
                        errors.append(f'Row {row_num}: Department "{name}" already exists')
                        continue
                    
                    # Check for duplicates within the file
                    if any(r['name'] == name for r in valid_rows):
                        errors.append(f'Row {row_num}: Duplicate name "{name}" in file')
                        continue
                    
                    valid_rows.append({
                        'name': name,
                        'code': row.get('code', '').strip() or None,
                        'description': row.get('description', '').strip() or None
                    })
                
                # If any errors, abort entire upload
                if errors:
                    error_msg = f'Upload failed. {len(errors)} error(s) found:<br>' + '<br>'.join(errors[:10])
                    if len(errors) > 10:
                        error_msg += f'<br>... and {len(errors) - 10} more errors'
                    flash(error_msg, 'error')
                    return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
                
                if not valid_rows:
                    flash('No valid rows found in CSV', 'warning')
                    return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
                
                # Second pass: insert all valid rows
                for row_data in valid_rows:
                    dept = Department(
                        tenant_id=school.id,
                        name=row_data['name'],
                        code=row_data['code'],
                        description=row_data['description'],
                        is_active=True
                    )
                    session_db.add(dept)
                
                session_db.commit()
                flash(f'Bulk upload successful: {len(valid_rows)} departments added', 'success')
                
            except Exception as e:
                session_db.rollback()
                flash(f'Error parsing CSV: {str(e)}', 'error')
            
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Bulk upload departments error: {e}")
            flash(f'Error uploading departments: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    # DESIGNATION ROUTES
    @school_bp.route('/<tenant_slug>/designations/add', methods=['POST'])
    @require_school_auth
    def add_designation(tenant_slug):
        """Add new designation"""
        session_db = get_session()
        try:
            from teacher_models import Designation
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            name = request.form.get('name', '').strip()
            code = request.form.get('code', '').strip()
            hierarchy_level = request.form.get('hierarchy_level', '').strip()
            description = request.form.get('description', '').strip()
            is_active = request.form.get('is_active') == 'on'
            
            if not name:
                flash('Designation name is required', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # Check if designation with same name exists
            existing = session_db.query(Designation).filter_by(
                tenant_id=school.id,
                name=name
            ).first()
            
            if existing:
                flash(f'Designation "{name}" already exists', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            designation = Designation(
                tenant_id=school.id,
                name=name,
                code=code if code else None,
                hierarchy_level=int(hierarchy_level) if hierarchy_level else None,
                description=description if description else None,
                is_active=is_active
            )
            
            session_db.add(designation)
            session_db.commit()
            
            flash(f'Designation "{name}" added successfully!', 'success')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Add designation error: {e}")
            flash(f'Error adding designation: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/designations/<int:id>/edit', methods=['POST'])
    @require_school_auth
    def edit_designation(tenant_slug, id):
        """Edit designation"""
        session_db = get_session()
        try:
            from teacher_models import Designation
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            designation = session_db.query(Designation).filter_by(
                id=id, tenant_id=school.id
            ).first()
            
            if not designation:
                flash('Designation not found', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            name = request.form.get('name', '').strip()
            code = request.form.get('code', '').strip()
            hierarchy_level = request.form.get('hierarchy_level', '').strip()
            description = request.form.get('description', '').strip()
            is_active = request.form.get('is_active') == 'on'
            
            if not name:
                flash('Designation name is required', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # Check if another designation with same name exists
            existing = session_db.query(Designation).filter_by(
                tenant_id=school.id,
                name=name
            ).filter(Designation.id != id).first()
            
            if existing:
                flash(f'Designation "{name}" already exists', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            designation.name = name
            designation.code = code if code else None
            designation.hierarchy_level = int(hierarchy_level) if hierarchy_level else None
            designation.description = description if description else None
            designation.is_active = is_active
            
            session_db.commit()
            flash(f'Designation "{name}" updated successfully!', 'success')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Edit designation error: {e}")
            flash(f'Error updating designation: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/designations/<int:id>/delete')
    @require_school_auth
    def delete_designation(tenant_slug, id):
        """Delete designation"""
        session_db = get_session()
        try:
            from teacher_models import Designation, TeacherDesignation
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            designation = session_db.query(Designation).filter_by(
                id=id, tenant_id=school.id
            ).first()
            
            if not designation:
                flash('Designation not found', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # Check if designation has any teachers assigned
            teacher_count = session_db.query(TeacherDesignation).filter_by(designation_id=id).count()
            if teacher_count > 0:
                flash(f'Cannot delete designation "{designation.name}". It has {teacher_count} teacher(s) assigned. Please reassign teachers first.', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            name = designation.name
            session_db.delete(designation)
            session_db.commit()
            
            flash(f'Designation "{name}" deleted successfully!', 'success')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Delete designation error: {e}")
            flash(f'Error deleting designation: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/designations/bulk-upload', methods=['GET', 'POST'])
    @require_school_auth
    def bulk_upload_designations(tenant_slug):
        """Bulk upload designations via CSV file"""
        session_db = get_session()
        try:
            from teacher_models import Designation
            import csv
            import io
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            if request.method == 'GET':
                if request.args.get('template') == '1':
                    from flask import Response
                    csv_content = "name,code,hierarchy_level,description\nPrincipal,PRIN,1,School Principal\nVice Principal,VP,2,Vice Principal\nPGT,PGT,3,Post Graduate Teacher"
                    return Response(
                        csv_content,
                        mimetype='text/csv',
                        headers={'Content-Disposition': 'attachment; filename=designations_template.csv'}
                    )
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            if 'csv_file' not in request.files:
                flash('No file uploaded', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            file = request.files['csv_file']
            if file.filename == '' or not file.filename.endswith('.csv'):
                flash('Please upload a valid CSV file', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            try:
                stream = io.StringIO(file.stream.read().decode('utf-8-sig'))
                reader = csv.DictReader(stream)
                
                if 'name' not in (reader.fieldnames or []):
                    flash('Missing required column: name', 'error')
                    return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
                
                # First pass: validate all rows
                errors = []
                valid_rows = []
                
                for row_num, row in enumerate(reader, start=2):
                    name = row.get('name', '').strip()
                    
                    if not name:
                        errors.append(f'Row {row_num}: Name is required')
                        continue
                    
                    existing = session_db.query(Designation).filter_by(tenant_id=school.id, name=name).first()
                    if existing:
                        errors.append(f'Row {row_num}: Designation "{name}" already exists')
                        continue
                    
                    # Check for duplicates within the file
                    if any(r['name'] == name for r in valid_rows):
                        errors.append(f'Row {row_num}: Duplicate name "{name}" in file')
                        continue
                    
                    hierarchy = row.get('hierarchy_level', '').strip()
                    valid_rows.append({
                        'name': name,
                        'code': row.get('code', '').strip() or None,
                        'hierarchy_level': int(hierarchy) if hierarchy.isdigit() else None,
                        'description': row.get('description', '').strip() or None
                    })
                
                # If any errors, abort entire upload
                if errors:
                    error_msg = f'Upload failed. {len(errors)} error(s) found:<br>' + '<br>'.join(errors[:10])
                    if len(errors) > 10:
                        error_msg += f'<br>... and {len(errors) - 10} more errors'
                    flash(error_msg, 'error')
                    return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
                
                if not valid_rows:
                    flash('No valid rows found in CSV', 'warning')
                    return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
                
                # Second pass: insert all valid rows
                for row_data in valid_rows:
                    desig = Designation(
                        tenant_id=school.id,
                        name=row_data['name'],
                        code=row_data['code'],
                        hierarchy_level=row_data['hierarchy_level'],
                        description=row_data['description'],
                        is_active=True
                    )
                    session_db.add(desig)
                
                session_db.commit()
                flash(f'Bulk upload successful: {len(valid_rows)} designations added', 'success')
                
            except Exception as e:
                session_db.rollback()
                flash(f'Error parsing CSV: {str(e)}', 'error')
            
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Bulk upload designations error: {e}")
            flash(f'Error uploading designations: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    # SUBJECT ROUTES
    @school_bp.route('/<tenant_slug>/subjects/add-master', methods=['POST'])
    @require_school_auth
    def add_subject_master(tenant_slug):
        """Add new subject"""
        session_db = get_session()
        try:
            from teacher_models import Subject
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            name = request.form.get('name', '').strip()
            code = request.form.get('code', '').strip()
            subject_type = request.form.get('subject_type', 'Academic').strip()
            description = request.form.get('description', '').strip()
            is_active = request.form.get('is_active') == 'on'
            
            if not name:
                flash('Subject name is required', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # Check if subject with same name exists
            existing = session_db.query(Subject).filter_by(
                tenant_id=school.id,
                name=name
            ).first()
            
            if existing:
                flash(f'Subject "{name}" already exists', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            subject = Subject(
                tenant_id=school.id,
                name=name,
                code=code if code else None,
                subject_type=subject_type,
                description=description if description else None,
                is_active=is_active
            )
            
            session_db.add(subject)
            session_db.commit()
            
            flash(f'Subject "{name}" added successfully!', 'success')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Add subject error: {e}")
            flash(f'Error adding subject: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/subjects/<int:id>/edit-master', methods=['POST'])
    @require_school_auth
    def edit_subject_master(tenant_slug, id):
        """Edit subject"""
        session_db = get_session()
        try:
            from teacher_models import Subject
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            subject = session_db.query(Subject).filter_by(
                id=id, tenant_id=school.id
            ).first()
            
            if not subject:
                flash('Subject not found', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            name = request.form.get('name', '').strip()
            code = request.form.get('code', '').strip()
            subject_type = request.form.get('subject_type', 'Academic').strip()
            description = request.form.get('description', '').strip()
            is_active = request.form.get('is_active') == 'on'
            
            if not name:
                flash('Subject name is required', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # Check if another subject with same name exists
            existing = session_db.query(Subject).filter_by(
                tenant_id=school.id,
                name=name
            ).filter(Subject.id != id).first()
            
            if existing:
                flash(f'Subject "{name}" already exists', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            subject.name = name
            subject.code = code if code else None
            subject.subject_type = subject_type
            subject.description = description if description else None
            subject.is_active = is_active
            
            session_db.commit()
            flash(f'Subject "{name}" updated successfully!', 'success')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Edit subject error: {e}")
            flash(f'Error updating subject: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/subjects/<int:id>/delete-master')
    @require_school_auth
    def delete_subject_master(tenant_slug, id):
        """Delete subject"""
        session_db = get_session()
        try:
            from teacher_models import Subject, TeacherSubject
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            subject = session_db.query(Subject).filter_by(
                id=id, tenant_id=school.id
            ).first()
            
            if not subject:
                flash('Subject not found', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # Check if subject has any teachers assigned
            teacher_count = session_db.query(TeacherSubject).filter_by(subject_id=id).count()
            if teacher_count > 0:
                flash(f'Cannot delete subject "{subject.name}". It has {teacher_count} teacher(s) assigned. Please reassign teachers first.', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # Check if subject is assigned to any classes
            try:
                from models import ClassSubjectAssignment
                class_count = session_db.query(ClassSubjectAssignment).filter_by(subject_id=id).count()
                if class_count > 0:
                    flash(f'Cannot delete subject "{subject.name}". It is assigned to {class_count} class(es). Please remove class assignments first.', 'error')
                    return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            except:
                pass  # Model/Table might not exist
            
            name = subject.name
            session_db.delete(subject)
            session_db.commit()
            
            flash(f'Subject "{name}" deleted successfully!', 'success')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Delete subject error: {e}")
            flash(f'Error deleting subject: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/subjects/bulk-upload', methods=['GET', 'POST'])
    @require_school_auth
    def bulk_upload_subjects(tenant_slug):
        """Bulk upload subjects via CSV file"""
        session_db = get_session()
        try:
            from teacher_models import Subject, SubjectTypeEnum
            import csv
            import io
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            if request.method == 'GET':
                if request.args.get('template') == '1':
                    from flask import Response
                    csv_content = "name,code,subject_type,description\nMathematics,MATH,Academic,Mathematics subject\nPhysics,PHY,Academic,Physics subject\nMusic,MUS,Co-curricular,Music class"
                    return Response(
                        csv_content,
                        mimetype='text/csv',
                        headers={'Content-Disposition': 'attachment; filename=subjects_template.csv'}
                    )
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            if 'csv_file' not in request.files:
                flash('No file uploaded', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            file = request.files['csv_file']
            if file.filename == '' or not file.filename.endswith('.csv'):
                flash('Please upload a valid CSV file', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            try:
                stream = io.StringIO(file.stream.read().decode('utf-8-sig'))
                reader = csv.DictReader(stream)
                
                if 'name' not in (reader.fieldnames or []):
                    flash('Missing required column: name', 'error')
                    return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
                
                # First pass: validate all rows
                errors = []
                valid_rows = []
                
                for row_num, row in enumerate(reader, start=2):
                    name = row.get('name', '').strip()
                    
                    if not name:
                        errors.append(f'Row {row_num}: Name is required')
                        continue
                    
                    existing = session_db.query(Subject).filter_by(tenant_id=school.id, name=name).first()
                    if existing:
                        errors.append(f'Row {row_num}: Subject "{name}" already exists')
                        continue
                    
                    # Check for duplicates within the file
                    if any(r['name'] == name for r in valid_rows):
                        errors.append(f'Row {row_num}: Duplicate name "{name}" in file')
                        continue
                    
                    # Parse subject type
                    subject_type_str = row.get('subject_type', 'Academic').strip()
                    try:
                        subject_type = SubjectTypeEnum(subject_type_str)
                    except ValueError:
                        subject_type = SubjectTypeEnum.ACADEMIC
                    
                    valid_rows.append({
                        'name': name,
                        'code': row.get('code', '').strip() or None,
                        'subject_type': subject_type,
                        'description': row.get('description', '').strip() or None
                    })
                
                # If any errors, abort entire upload
                if errors:
                    error_msg = f'Upload failed. {len(errors)} error(s) found:<br>' + '<br>'.join(errors[:10])
                    if len(errors) > 10:
                        error_msg += f'<br>... and {len(errors) - 10} more errors'
                    flash(error_msg, 'error')
                    return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
                
                if not valid_rows:
                    flash('No valid rows found in CSV', 'warning')
                    return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
                
                # Second pass: insert all valid rows
                for row_data in valid_rows:
                    subj = Subject(
                        tenant_id=school.id,
                        name=row_data['name'],
                        code=row_data['code'],
                        subject_type=row_data['subject_type'],
                        description=row_data['description'],
                        is_active=True
                    )
                    session_db.add(subj)
                
                session_db.commit()
                flash(f'Bulk upload successful: {len(valid_rows)} subjects added', 'success')
                
            except Exception as e:
                session_db.rollback()
                flash(f'Error parsing CSV: {str(e)}', 'error')
            
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Bulk upload subjects error: {e}")
            flash(f'Error uploading subjects: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    # CLASS ROUTES
    @school_bp.route('/<tenant_slug>/classes/add', methods=['POST'])
    @require_school_auth
    def add_class(tenant_slug):
        """Add new class"""
        session_db = get_session()
        try:
            from models import Class
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            class_name = request.form.get('class_name', '').strip()
            section = request.form.get('section', '').strip().upper()
            description = request.form.get('description', '').strip()
            
            if not class_name or not section:
                flash('Class name and section are required', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # Check if class already exists
            existing = session_db.query(Class).filter_by(
                tenant_id=school.id,
                class_name=class_name,
                section=section
            ).first()
            
            if existing:
                flash(f'Class {class_name}-{section} already exists', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            new_class = Class(
                tenant_id=school.id,
                class_name=class_name,
                section=section,
                description=description,
                is_active=True
            )
            
            session_db.add(new_class)
            session_db.commit()
            
            flash(f'Class {class_name}-{section} added successfully!', 'success')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Add class error: {e}")
            flash(f'Error adding class: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/classes/update/<int:id>', methods=['POST'])
    @require_school_auth
    def update_class(tenant_slug, id):
        """Update class"""
        session_db = get_session()
        try:
            from models import Class
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            class_obj = session_db.query(Class).filter_by(
                id=id, tenant_id=school.id
            ).first()
            
            if not class_obj:
                flash('Class not found', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            class_name = request.form.get('class_name', '').strip()
            section = request.form.get('section', '').strip().upper()
            description = request.form.get('description', '').strip()
            is_active = request.form.get('is_active') == 'on'
            
            if not class_name or not section:
                flash('Class name and section are required', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            class_obj.class_name = class_name
            class_obj.section = section
            class_obj.description = description
            class_obj.is_active = is_active
            
            session_db.commit()
            
            flash(f'Class {class_name}-{section} updated successfully!', 'success')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Update class error: {e}")
            flash(f'Error updating class: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/classes/delete/<int:id>', methods=['POST'])
    @require_school_auth
    def delete_class(tenant_slug, id):
        """Delete class"""
        session_db = get_session()
        try:
            from models import Class, Student
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            class_obj = session_db.query(Class).filter_by(
                id=id, tenant_id=school.id
            ).first()
            
            if not class_obj:
                flash('Class not found', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            class_name = f"{class_obj.class_name}-{class_obj.section}"
            
            # Check if class has any students
            student_count = session_db.query(Student).filter_by(class_id=id).count()
            if student_count > 0:
                flash(f'Cannot delete class "{class_name}". It has {student_count} student(s). Please transfer or remove students first.', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # Check for subject assignments
            try:
                from models import ClassSubjectAssignment
                assignment_count = session_db.query(ClassSubjectAssignment).filter_by(class_id=id).count()
                if assignment_count > 0:
                    flash(f'Cannot delete class "{class_name}". It has {assignment_count} subject assignment(s). Please remove assignments first.', 'error')
                    return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            except:
                pass  # Model/Table might not exist
            
            # Check for timetable entries
            try:
                from timetable_models import TimetableEntry
                timetable_count = session_db.query(TimetableEntry).filter_by(class_id=id).count()
                if timetable_count > 0:
                    flash(f'Cannot delete class "{class_name}". It has {timetable_count} timetable entries. Please remove timetable entries first.', 'error')
                    return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            except:
                pass  # Table/module might not exist
            
            session_db.delete(class_obj)
            session_db.commit()
            
            flash(f'Class "{class_name}" deleted successfully!', 'success')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Delete class error: {e}")
            flash(f'Error deleting class: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/classes/bulk-upload', methods=['GET', 'POST'])
    @require_school_auth
    def bulk_upload_classes(tenant_slug):
        """Bulk upload classes via CSV file"""
        session_db = get_session()
        try:
            from models import Class
            import csv
            import io
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            if request.method == 'GET':
                # Return sample CSV template download
                if request.args.get('template') == '1':
                    from flask import Response
                    csv_content = "class_name,section,description\n10,A,Science Section\n10,B,Commerce Section\n9,A,\n9,B,"
                    return Response(
                        csv_content,
                        mimetype='text/csv',
                        headers={'Content-Disposition': 'attachment; filename=classes_template.csv'}
                    )
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # POST - Process CSV upload
            if 'csv_file' not in request.files:
                flash('No file uploaded', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            file = request.files['csv_file']
            if file.filename == '':
                flash('No file selected', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            if not file.filename.endswith('.csv'):
                flash('Please upload a CSV file', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # Read and parse CSV
            try:
                stream = io.StringIO(file.stream.read().decode('utf-8-sig'))
                reader = csv.DictReader(stream)
                
                # Validate headers
                required_headers = ['class_name', 'section']
                headers = reader.fieldnames or []
                missing_headers = [h for h in required_headers if h not in headers]
                
                if missing_headers:
                    flash(f'Missing required columns: {", ".join(missing_headers)}', 'error')
                    return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
                
                # First pass: validate all rows
                errors = []
                valid_rows = []
                
                for row_num, row in enumerate(reader, start=2):
                    class_name = row.get('class_name', '').strip()
                    section = row.get('section', '').strip().upper()
                    description = row.get('description', '').strip() if 'description' in row else ''
                    
                    # Validate required fields
                    if not class_name:
                        errors.append(f'Row {row_num}: Class name is required')
                        continue
                    
                    if not section:
                        errors.append(f'Row {row_num}: Section is required')
                        continue
                    
                    # Check for duplicate in database
                    existing = session_db.query(Class).filter_by(
                        tenant_id=school.id,
                        class_name=class_name,
                        section=section
                    ).first()
                    
                    if existing:
                        errors.append(f'Row {row_num}: Class "{class_name}-{section}" already exists')
                        continue
                    
                    # Check for duplicates within the file
                    if any(r['class_name'] == class_name and r['section'] == section for r in valid_rows):
                        errors.append(f'Row {row_num}: Duplicate class "{class_name}-{section}" in file')
                        continue
                    
                    valid_rows.append({
                        'class_name': class_name,
                        'section': section,
                        'description': description
                    })
                
                # If any errors, abort entire upload
                if errors:
                    error_msg = f'Upload failed. {len(errors)} error(s) found:<br>' + '<br>'.join(errors[:10])
                    if len(errors) > 10:
                        error_msg += f'<br>... and {len(errors) - 10} more errors'
                    flash(error_msg, 'error')
                    return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
                
                if not valid_rows:
                    flash('No valid rows found in CSV', 'warning')
                    return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
                
                # Second pass: insert all valid rows
                for row_data in valid_rows:
                    new_class = Class(
                        tenant_id=school.id,
                        class_name=row_data['class_name'],
                        section=row_data['section'],
                        description=row_data['description'],
                        is_active=True
                    )
                    session_db.add(new_class)
                
                session_db.commit()
                flash(f'Bulk upload successful: {len(valid_rows)} classes added', 'success')
                
            except Exception as e:
                session_db.rollback()
                logger.error(f"CSV parsing error: {e}")
                flash(f'Error parsing CSV: {str(e)}', 'error')
            
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Bulk upload classes error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash(f'Error uploading classes: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    # ===== ACADEMIC SESSION ROUTES =====
    
    @school_bp.route('/<tenant_slug>/academic-sessions/add', methods=['POST'])
    @require_school_auth
    def add_academic_session(tenant_slug):
        """Add new academic session"""
        session_db = get_session()
        try:
            from models import AcademicSession
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            session_name = request.form.get('session_name', '').strip()
            start_date = request.form.get('start_date', '').strip()
            end_date = request.form.get('end_date', '').strip()
            is_current = request.form.get('is_current') == 'on'
            is_active = request.form.get('is_active') == 'on'
            
            if not session_name or not start_date or not end_date:
                flash('Session name, start date, and end date are required', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # Parse dates
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            if end_date_obj <= start_date_obj:
                flash('End date must be after start date', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # Check if session with same name exists
            existing = session_db.query(AcademicSession).filter_by(
                tenant_id=school.id,
                session_name=session_name
            ).first()
            
            if existing:
                flash(f'Academic session "{session_name}" already exists', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # If setting as current, unset other current sessions
            if is_current:
                session_db.query(AcademicSession).filter_by(
                    tenant_id=school.id,
                    is_current=True
                ).update({'is_current': False})
            
            academic_session = AcademicSession(
                tenant_id=school.id,
                session_name=session_name,
                start_date=start_date_obj,
                end_date=end_date_obj,
                is_current=is_current,
                is_active=is_active
            )
            
            session_db.add(academic_session)
            session_db.commit()
            
            flash(f'Academic session "{session_name}" added successfully!', 'success')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except ValueError as e:
            session_db.rollback()
            flash('Invalid date format. Please use YYYY-MM-DD', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        except Exception as e:
            session_db.rollback()
            logger.error(f"Add academic session error: {e}")
            flash(f'Error adding academic session: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/academic-sessions/<int:id>/edit', methods=['POST'])
    @require_school_auth
    def edit_academic_session(tenant_slug, id):
        """Edit academic session"""
        session_db = get_session()
        try:
            from models import AcademicSession
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            academic_session = session_db.query(AcademicSession).filter_by(
                id=id, tenant_id=school.id
            ).first()
            
            if not academic_session:
                flash('Academic session not found', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            session_name = request.form.get('session_name', '').strip()
            start_date = request.form.get('start_date', '').strip()
            end_date = request.form.get('end_date', '').strip()
            is_current = request.form.get('is_current') == 'on'
            is_active = request.form.get('is_active') == 'on'
            
            if not session_name or not start_date or not end_date:
                flash('Session name, start date, and end date are required', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # Parse dates
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            if end_date_obj <= start_date_obj:
                flash('End date must be after start date', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # If setting as current, unset other current sessions
            if is_current and not academic_session.is_current:
                session_db.query(AcademicSession).filter_by(
                    tenant_id=school.id,
                    is_current=True
                ).update({'is_current': False})
            
            academic_session.session_name = session_name
            academic_session.start_date = start_date_obj
            academic_session.end_date = end_date_obj
            academic_session.is_current = is_current
            academic_session.is_active = is_active
            
            session_db.commit()
            
            flash(f'Academic session "{session_name}" updated successfully!', 'success')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except ValueError as e:
            session_db.rollback()
            flash('Invalid date format. Please use YYYY-MM-DD', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        except Exception as e:
            session_db.rollback()
            logger.error(f"Edit academic session error: {e}")
            flash(f'Error editing academic session: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/academic-sessions/<int:id>/delete')
    @require_school_auth
    def delete_academic_session(tenant_slug, id):
        """Delete academic session"""
        session_db = get_session()
        try:
            from models import AcademicSession
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            academic_session = session_db.query(AcademicSession).filter_by(
                id=id, tenant_id=school.id
            ).first()
            
            if not academic_session:
                flash('Academic session not found', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            if academic_session.is_current:
                flash('Cannot delete current academic session. Set another session as current first.', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            session_name = academic_session.session_name
            session_db.delete(academic_session)
            session_db.commit()
            
            flash(f'Academic session "{session_name}" deleted successfully!', 'success')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Delete academic session error: {e}")
            flash(f'Error deleting academic session: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/academic-sessions/<int:id>/set-current')
    @require_school_auth
    def set_current_session(tenant_slug, id):
        """Set academic session as current"""
        session_db = get_session()
        try:
            from models import AcademicSession
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            academic_session = session_db.query(AcademicSession).filter_by(
                id=id, tenant_id=school.id
            ).first()
            
            if not academic_session:
                flash('Academic session not found', 'error')
                return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
            # Unset all other current sessions
            session_db.query(AcademicSession).filter_by(
                tenant_id=school.id,
                is_current=True
            ).update({'is_current': False})
            
            # Set this session as current
            academic_session.is_current = True
            academic_session.is_active = True  # Also activate it
            session_db.commit()
            
            flash(f'Academic session "{academic_session.session_name}" is now the current session!', 'success')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Set current session error: {e}")
            flash(f'Error setting current session: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    # ===== WHATSAPP SETTINGS ROUTES =====
    
    @school_bp.route('/<tenant_slug>/whatsapp-settings/save', methods=['POST'])
    @require_school_auth
    def save_whatsapp_settings(tenant_slug):
        """Save WhatsApp API settings"""
        session_db = get_session()
        try:
            from notification_models import WhatsAppSettings, WhatsAppProviderEnum
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            # Get or create WhatsApp settings
            whatsapp_settings = session_db.query(WhatsAppSettings).filter_by(
                tenant_id=school.id
            ).first()
            
            if not whatsapp_settings:
                whatsapp_settings = WhatsAppSettings(tenant_id=school.id)
                session_db.add(whatsapp_settings)
            
            # Update provider
            provider_value = request.form.get('provider', '').strip()
            if provider_value:
                try:
                    whatsapp_settings.provider = WhatsAppProviderEnum(provider_value)
                except ValueError:
                    whatsapp_settings.provider = WhatsAppProviderEnum.OTHER
            
            # Update credentials
            whatsapp_settings.api_key = request.form.get('api_key', '').strip() or None
            whatsapp_settings.api_secret = request.form.get('api_secret', '').strip() or None
            whatsapp_settings.access_token = request.form.get('access_token', '').strip() or None
            whatsapp_settings.phone_number_id = request.form.get('phone_number_id', '').strip() or None
            whatsapp_settings.business_account_id = request.form.get('business_account_id', '').strip() or None
            
            # Update settings
            whatsapp_settings.is_enabled = request.form.get('is_enabled') == '1'
            whatsapp_settings.sandbox_mode = request.form.get('sandbox_mode') == '1'
            
            # Update limits
            daily_limit = request.form.get('daily_limit', '1000')
            try:
                whatsapp_settings.daily_limit = int(daily_limit)
            except ValueError:
                whatsapp_settings.daily_limit = 1000
            
            # Update template settings
            whatsapp_settings.default_template_name = request.form.get('default_template_name', '').strip() or None
            whatsapp_settings.default_template_language = request.form.get('default_template_language', 'en').strip()
            
            # Update metadata
            whatsapp_settings.updated_by = current_user.id
            from datetime import datetime
            whatsapp_settings.updated_at = datetime.now()
            
            session_db.commit()
            flash('WhatsApp settings saved successfully!', 'success')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug) + '#whatsapp')
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Save WhatsApp settings error: {e}")
            flash(f'Error saving WhatsApp settings: {str(e)}', 'error')
            return redirect(url_for('school.master_data', tenant_slug=tenant_slug) + '#whatsapp')
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/whatsapp-settings/test', methods=['POST'])
    @require_school_auth
    def test_whatsapp_connection(tenant_slug):
        """Test WhatsApp API connection"""
        from flask import jsonify
        try:
            data = request.get_json()
            provider = data.get('provider', '')
            api_key = data.get('api_key', '')
            api_secret = data.get('api_secret', '')
            access_token = data.get('access_token', '')
            phone_number_id = data.get('phone_number_id', '')
            
            if not provider:
                return jsonify({'success': False, 'message': 'Please select a provider'})
            
            # Basic validation based on provider
            if provider == 'Meta Cloud API':
                if not access_token or not phone_number_id:
                    return jsonify({'success': False, 'message': 'Access Token and Phone Number ID are required for Meta Cloud API'})
                
                # Test Meta API connection
                import requests
                try:
                    url = f'https://graph.facebook.com/v18.0/{phone_number_id}'
                    headers = {'Authorization': f'Bearer {access_token}'}
                    response = requests.get(url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        return jsonify({'success': True, 'message': 'Meta Cloud API connection successful!'})
                    else:
                        error_msg = response.json().get('error', {}).get('message', 'Unknown error')
                        return jsonify({'success': False, 'message': f'API Error: {error_msg}'})
                except requests.RequestException as e:
                    return jsonify({'success': False, 'message': f'Connection error: {str(e)}'})
                    
            elif provider == 'Twilio':
                if not api_key or not api_secret:
                    return jsonify({'success': False, 'message': 'Account SID and Auth Token are required for Twilio'})
                
                # Test Twilio connection
                import requests
                try:
                    url = f'https://api.twilio.com/2010-04-01/Accounts/{api_key}.json'
                    response = requests.get(url, auth=(api_key, api_secret), timeout=10)
                    
                    if response.status_code == 200:
                        return jsonify({'success': True, 'message': 'Twilio connection successful!'})
                    else:
                        return jsonify({'success': False, 'message': 'Invalid Twilio credentials'})
                except requests.RequestException as e:
                    return jsonify({'success': False, 'message': f'Connection error: {str(e)}'})
            
            else:
                # For other providers, just validate that credentials are provided
                if not api_key:
                    return jsonify({'success': False, 'message': 'API Key is required'})
                return jsonify({'success': True, 'message': f'{provider} credentials provided. Please test by sending a message.'})
                
        except Exception as e:
            logger.error(f"Test WhatsApp connection error: {e}")
            return jsonify({'success': False, 'message': f'Error: {str(e)}'})

   
    # ===== TEACHER ATTENDANCE ROUTES =====
    
    @school_bp.route('/<tenant_slug>/teachers/attendance', methods=['GET', 'POST'])
    @require_school_auth
    def teacher_attendance(tenant_slug):
        """Mark and manage teacher attendance"""
        session_db = get_session()
        try:
            from teacher_models import Teacher, TeacherAttendance, AttendanceStatusEnum, EmployeeStatusEnum
            from attendance_helpers import mark_attendance, get_attendance_for_date, check_leave_and_automark
            from datetime import datetime as dt, date
            
            school = g.current_tenant
            
            # Get selected date from query params or form (use request.values so POST picks up the form field)
            selected_date_str = request.values.get('date', date.today().strftime('%Y-%m-%d'))
            # Optional search query to filter teachers
            search_query = request.values.get('search', '').strip()
            try:
                selected_date = dt.strptime(selected_date_str, '%Y-%m-%d').date()
            except Exception:
                selected_date = date.today()
            
            if request.method == 'POST':
                # Handle bulk attendance marking
                try:
                    marked_count = 0
                    errors = []
                    
                    # Get all form data
                    for key in request.form:
                        if key.startswith('status_'):
                            teacher_id = int(key.split('_')[1])
                            status_value = request.form[key]
                            
                            # Skip if no status selected
                            if not status_value:
                                continue
                            
                            # Get check-in and check-out times
                            check_in_str = request.form.get(f'check_in_{teacher_id}', '').strip()
                            check_out_str = request.form.get(f'check_out_{teacher_id}', '').strip()
                            remarks = request.form.get(f'remarks_{teacher_id}', '').strip()
                            
                            # Convert times if provided
                            check_in = None
                            check_out = None
                            
                            if check_in_str:
                                try:
                                    check_in = dt.strptime(check_in_str, '%H:%M').time()
                                except:
                                    pass
                            
                            if check_out_str:
                                try:
                                    check_out = dt.strptime(check_out_str, '%H:%M').time()
                                except:
                                    pass
                            
                            # Get status enum
                            status = AttendanceStatusEnum(status_value)
                            
                            # Mark attendance
                            success, message, _ = mark_attendance(
                                session_db, teacher_id, school.id, selected_date,
                                status, check_in, check_out, remarks, current_user.id
                            )
                            
                            if success:
                                marked_count += 1
                            else:
                                errors.append(f"Teacher ID {teacher_id}: {message}")
                    
                    if marked_count > 0:
                        flash(f'Attendance marked for {marked_count} teacher(s)', 'success')
                    
                    if errors:
                        for error in errors[:5]:  # Show first 5 errors
                            flash(error, 'error')
                    
                    # Preserve search when redirecting after POST
                    return redirect(url_for('school.teacher_attendance', tenant_slug=tenant_slug, date=selected_date_str, search=search_query))
                    
                except Exception as e:
                    logger.error(f"Bulk attendance marking error: {e}")
                    flash(f'Error marking attendance: {str(e)}', 'error')
            
            # Auto-mark teachers on approved leave
            check_leave_and_automark(session_db, school.id, selected_date)
            
            # Fetch all active teachers
            tquery = session_db.query(Teacher).filter_by(
                tenant_id=school.id,
                employee_status=EmployeeStatusEnum.ACTIVE
            )

            # Apply search filter if provided
            if search_query:
                sp = f"%{search_query}%"
                tquery = tquery.filter(
                    or_(
                        Teacher.first_name.ilike(sp),
                        Teacher.last_name.ilike(sp),
                        Teacher.email.ilike(sp),
                        Teacher.employee_id.ilike(sp),
                        Teacher.phone_primary.ilike(sp)
                    )
                )

            teachers = tquery.order_by(Teacher.first_name, Teacher.last_name).all()
            
            # Fetch existing attendance for selected date
            attendance_map = get_attendance_for_date(session_db, school.id, selected_date)
            
            context = {
                'school': school,
                'teachers': teachers,
                'selected_date': selected_date,
                'attendance_dict': attendance_map,
                'status_enum': AttendanceStatusEnum,
                'today': date.today(),
                'search_query': search_query
            }
            
            return render_template('akademi/teacher/teacher_attendance_mark.html', **context)
            
        except Exception as e:
            logger.error(f"Teacher attendance error: {e}")
            flash('Error loading attendance page', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/teachers/attendance/calendar')
    @require_school_auth
    def teacher_attendance_calendar(tenant_slug):
        """Calendar view of all teachers' attendance"""
        session_db = get_session()
        try:
            from teacher_models import Teacher, TeacherAttendance, EmployeeStatusEnum
            from datetime import datetime as dt
            from calendar import monthrange
            
            school = g.current_tenant
            
            # Get month, year and optional search
            month = request.args.get('month', dt.now().month, type=int)
            year = request.args.get('year', dt.now().year, type=int)
            search_query = request.args.get('search', '').strip()
            
            # Validate inputs
            if not (1 <= month <= 12):
                month = dt.now().month
                flash('Invalid month, showing current month', 'warning')
            
            if not (2000 <= year <= 2100):
                year = dt.now().year
                flash('Invalid year, showing current year', 'warning')
            
            # Get all active teachers (apply search if provided)
            tquery = session_db.query(Teacher).filter_by(
                tenant_id=school.id,
                employee_status=EmployeeStatusEnum.ACTIVE
            )
            if search_query:
                sp = f"%{search_query}%"
                tquery = tquery.filter(
                    or_(
                        Teacher.first_name.ilike(sp),
                        Teacher.last_name.ilike(sp),
                        Teacher.email.ilike(sp),
                        Teacher.employee_id.ilike(sp),
                        Teacher.phone_primary.ilike(sp)
                    )
                )
            teachers = tquery.order_by(Teacher.first_name).all()
            
            # Get all attendance records for the month
            attendance_records = session_db.query(TeacherAttendance).filter(
                TeacherAttendance.tenant_id == school.id,
                extract('month', TeacherAttendance.attendance_date) == month,
                extract('year', TeacherAttendance.attendance_date) == year
            ).all()
            
            # Create attendance map: {teacher_id: {date: record}}
            attendance_map = {}
            for record in attendance_records:
                if record.teacher_id not in attendance_map:
                    attendance_map[record.teacher_id] = {}
                attendance_map[record.teacher_id][record.attendance_date.day] = record
            
            # Get days in month
            _, num_days = monthrange(year, month)
            days = list(range(1, num_days + 1))
            
            context = {
                'school': school,
                'teachers': teachers,
                'attendance_map': attendance_map,
                'month': month,
                'year': year,
                'days': days,
                'month_name': dt(year, month, 1).strftime('%B'),
                'search_query': search_query
            }
            
            return render_template('akademi/teacher/teacher_attendance_calendar.html', **context)
            
        except Exception as e:
            logger.error(f"Attendance calendar error: {e}")
            flash('Error loading attendance calendar', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/teachers/<int:teacher_id>/attendance-history')
    @require_school_auth
    def teacher_attendance_history(tenant_slug, teacher_id):
        """View individual teacher's attendance history"""
        session_db = get_session()
        try:
            from teacher_models import Teacher
            from attendance_helpers import get_monthly_attendance, calculate_attendance_stats
            from datetime import datetime as dt
            
            school = g.current_tenant
            
            # Get teacher
            teacher = session_db.query(Teacher).filter_by(
                id=teacher_id,
                tenant_id=school.id
            ).first()
            
            if not teacher:
                flash('Teacher not found', 'error')
                return redirect(url_for('school.teachers', tenant_slug=tenant_slug))
            
            # Get month and year
            month = request.args.get('month', dt.now().month, type=int)
            year = request.args.get('year', dt.now().year, type=int)
            
            # Get attendance records
            records = get_monthly_attendance(session_db, teacher_id, month, year)
            
            # Get statistics
            stats = calculate_attendance_stats(session_db, teacher_id, month, year)
            
            context = {
                'school': school,
                'teacher': teacher,
                'records': records,
                'stats': stats,
                'month': month,
                'year': year,
                'month_name': dt(year, month, 1).strftime('%B')
            }
            
            return render_template('akademi/teacher/teacher_attendance_individual.html', **context)
            
        except Exception as e:
            logger.error(f"Teacher attendance history error: {e}")
            flash('Error loading attendance history', 'error')
            return redirect(url_for('school.teachers', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/api/attendance/mark', methods=['POST'])
    @require_school_auth
    def api_mark_attendance(tenant_slug):
        """AJAX endpoint to mark individual teacher attendance"""
        session_db = get_session()
        try:
            from teacher_models import AttendanceStatusEnum
            from attendance_helpers import mark_attendance
            from datetime import datetime as dt
            
            school = g.current_tenant
            data = request.get_json()
            
            # Validate required fields
            if not all(k in data for k in ['teacher_id', 'attendance_date', 'status']):
                return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400
            
            teacher_id = int(data['teacher_id'])
            attendance_date = dt.strptime(data['attendance_date'], '%Y-%m-%d').date()
            status = AttendanceStatusEnum(data['status'])
            
            # Parse times if provided
            check_in = None
            check_out = None
            
            if data.get('check_in'):
                check_in = dt.strptime(data['check_in'], '%H:%M').time()
            
            if data.get('check_out'):
                check_out = dt.strptime(data['check_out'], '%H:%M').time()
            
            remarks = data.get('remarks', '')
            
            # Mark attendance
            success, message, record = mark_attendance(
                session_db, teacher_id, school.id, attendance_date,
                status, check_in, check_out, remarks, current_user.id
            )
            
            if success:
                return jsonify({
                    'status': 'success',
                    'message': message,
                    'data': {
                        'id': record.id,
                        'status': record.status.value,
                        'working_hours': float(record.working_hours) if record.working_hours else 0
                    }
                })
            else:
                return jsonify({'status': 'error', 'message': message}), 400
                
        except Exception as e:
            logger.error(f"API mark attendance error: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
        finally:
            session_db.close()
    
   
    
    
    # ===== LEAVE QUOTA MANAGEMENT ROUTES =====
    
    @school_bp.route('/<tenant_slug>/leaves/quota-settings', methods=['GET', 'POST'])
    @require_school_auth
    def leave_quota_settings(tenant_slug):
        """
        Configure leave quota settings for the school
        GET: Display current settings
        POST: Update settings
        """
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            from leave_models import LeaveQuotaSettings
            from leave_helpers import get_current_academic_year, get_or_create_quota_settings
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            current_year = get_current_academic_year()
            
            if request.method == 'POST':
                try:
                    academic_year = request.form.get('academic_year', current_year).strip()
                    
                    # Get or create settings
                    settings = get_or_create_quota_settings(session_db, school.id, academic_year)
                    
                    # Update quota values
                    settings.cl_quota = float(request.form.get('cl_quota', 12.0))
                    settings.sl_quota = float(request.form.get('sl_quota', 12.0))
                    settings.el_quota = float(request.form.get('el_quota', 15.0))
                    settings.maternity_quota = float(request.form.get('maternity_quota', 180.0))
                    settings.paternity_quota = float(request.form.get('paternity_quota', 15.0))
                    
                    # Update policy settings
                    settings.allow_half_day = 'allow_half_day' in request.form
                    settings.allow_lop = 'allow_lop' in request.form
                    settings.duty_leave_unlimited = 'duty_leave_unlimited' in request.form
                    settings.max_continuous_days = int(request.form.get('max_continuous_days', 30))
                    settings.min_advance_days = int(request.form.get('min_advance_days', 1))
                    settings.weekend_counted = 'weekend_counted' in request.form
                    
                    settings.updated_at = datetime.utcnow()
                    session_db.commit()
                    
                    flash(f'Leave quota settings updated successfully for {academic_year}!', 'success')
                    return redirect(url_for('school.leave_quota_settings', tenant_slug=tenant_slug))
                    
                except Exception as e:
                    session_db.rollback()
                    logger.error(f"Error updating quota settings: {e}")
                    import traceback
                    traceback.print_exc()
                    flash(f'Error updating settings: {str(e)}', 'error')
            
            # GET request - load current settings
            settings = get_or_create_quota_settings(session_db, school.id, current_year)
            
            # Get list of academic years for dropdown
            all_years = session_db.query(LeaveQuotaSettings.academic_year).filter_by(
                tenant_id=school.id
            ).distinct().all()
            academic_years = [y[0] for y in all_years]
            if current_year not in academic_years:
                academic_years.append(current_year)
            academic_years.sort(reverse=True)
            
            return render_template('akademi/teacher/leaves/quota_settings.html',
                                 school=school,
                                 settings=settings,
                                 current_year=current_year,
                                 academic_years=academic_years,
                                 current_user=current_user)
                                 
        except Exception as e:
            logger.error(f"Quota settings error for {tenant_slug}: {e}")
            import traceback
            traceback.print_exc()
            flash('Error loading quota settings', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    
    @school_bp.route('/<tenant_slug>/leaves/balances', methods=['GET'])
    @require_school_auth
    def view_teacher_balances(tenant_slug):
        """
        View all teacher leave balances for current academic year
        """
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            from leave_models import TeacherLeaveBalance
            from leave_helpers import get_current_academic_year
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            # Get academic year from query param or use current
            academic_year = request.args.get('year', get_current_academic_year())
            
            # Get all active teachers with their balances
            from teacher_models import EmployeeStatusEnum
            teachers = session_db.query(Teacher).filter_by(
                tenant_id=school.id,
                employee_status=EmployeeStatusEnum.ACTIVE
            ).order_by(Teacher.first_name, Teacher.last_name).all()
            
            # Fetch balances
            balances = {}
            for teacher in teachers:
                balance = session_db.query(TeacherLeaveBalance).filter_by(
                    teacher_id=teacher.id,
                    academic_year=academic_year
                ).first()
                balances[teacher.id] = balance
            
            return render_template('akademi/teacher/leaves/view_balances.html',
                                 school=school,
                                 teachers=teachers,
                                 balances=balances,
                                 academic_year=academic_year,
                                 current_user=current_user)
                                 
        except Exception as e:
            logger.error(f"View balances error for {tenant_slug}: {e}")
            import traceback
            traceback.print_exc()
            flash('Error loading teacher balances', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    
    @school_bp.route('/<tenant_slug>/leaves/balances/initialize', methods=['POST'])
    @require_school_auth
    def initialize_balances(tenant_slug):
        """
        Initialize leave balances for all teachers
        """
        if current_user.role not in ['school_admin', 'portal_admin']:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        session_db = get_session()
        try:
            from leave_helpers import initialize_all_teacher_balances, get_current_academic_year
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            academic_year = request.form.get('academic_year', get_current_academic_year())
            force_reset = request.form.get('force_reset', 'false').lower() == 'true'
            
            # Initialize balances
            stats = initialize_all_teacher_balances(
                session_db, 
                school.id, 
                academic_year,
                force_reset
            )
            
            message = f"Initialization complete: {stats['initialized']} initialized, " \
                     f"{stats['already_exists']} already existed, " \
                     f"{stats['reset']} reset, " \
                     f"{stats['errors']} errors"
            
            return jsonify({
                'success': True,
                'message': message,
                'stats': stats
            }), 200
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Initialize balances error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500
        finally:
            session_db.close()
    
    
    @school_bp.route('/<tenant_slug>/leaves/balances/<int:teacher_id>', methods=['GET', 'POST'])
    @require_school_auth
    def edit_teacher_balance(tenant_slug, teacher_id):
        """
        View or edit individual teacher's leave balance
        """
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            from leave_models import TeacherLeaveBalance
            from leave_helpers import get_current_academic_year, update_teacher_balance
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            teacher = session_db.query(Teacher).filter_by(
                id=teacher_id,
                tenant_id=school.id
            ).first()
            
            if not teacher:
                flash('Teacher not found', 'error')
                return redirect(url_for('school.view_teacher_balances', tenant_slug=tenant_slug))
            
            academic_year = request.args.get('year', get_current_academic_year())
            
            if request.method == 'POST':
                try:
                    balance_updates = {
                        'cl_total': float(request.form.get('cl_total', 0)),
                        'sl_total': float(request.form.get('sl_total', 0)),
                        'el_total': float(request.form.get('el_total', 0)),
                        'maternity_total': float(request.form.get('maternity_total', 0)),
                        'paternity_total': float(request.form.get('paternity_total', 0)),
                        'el_carried_forward': float(request.form.get('el_carried_forward', 0)),
                        'notes': request.form.get('notes', '').strip()
                    }
                    
                    update_teacher_balance(session_db, teacher_id, academic_year, balance_updates)
                    
                    flash(f'Leave balance updated for {teacher.full_name}!', 'success')
                    return redirect(url_for('school.view_teacher_balances', tenant_slug=tenant_slug))
                    
                except Exception as e:
                    session_db.rollback()
                    logger.error(f"Error updating teacher balance: {e}")
                    flash(f'Error updating balance: {str(e)}', 'error')
            
            # GET request
            balance = session_db.query(TeacherLeaveBalance).filter_by(
                teacher_id=teacher_id,
                academic_year=academic_year
            ).first()
            
            return render_template('akademi/teacher/leaves/edit_balance.html',
                                 school=school,
                                 teacher=teacher,
                                 balance=balance,
                                 academic_year=academic_year,
                                 current_user=current_user)
                                 
        except Exception as e:
            logger.error(f"Edit balance error: {e}")
            import traceback
            traceback.print_exc()
            flash('Error loading balance editor', 'error')
            return redirect(url_for('school.view_teacher_balances', tenant_slug=tenant_slug))
        finally:
            session_db.close()


    # ===== LEAVE APPROVALS (School Admin) =====
    @school_bp.route('/<tenant_slug>/teacher-leaves')
    @require_school_auth
    def teacher_leaves_admin(tenant_slug):
        """Admin view for teacher leave management - matches student leaves pattern"""
        session_db = get_session()
        try:
            from leave_models import TeacherLeaveApplication, LeaveTypeEnum
            from teacher_models import Teacher, TeacherDocument
            
            school = g.current_tenant
            
            # Get filter parameters
            status_filter = request.args.get('status')
            leave_type_filter = request.args.get('leave_type')
            from_date_str = request.args.get('from_date')
            to_date_str = request.args.get('to_date')
            
            # Base query
            query = session_db.query(TeacherLeaveApplication).filter_by(tenant_id=school.id)
            
            # Apply filters
            if status_filter:
                query = query.filter(TeacherLeaveApplication.status == status_filter)
            
            if leave_type_filter:
                query = query.filter(TeacherLeaveApplication.leave_type == LeaveTypeEnum(leave_type_filter))
            
            if from_date_str:
                from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
                query = query.filter(TeacherLeaveApplication.start_date >= from_date)
            
            if to_date_str:
                to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
                query = query.filter(TeacherLeaveApplication.end_date <= to_date)
            
            # Order by latest first
            leaves = query.order_by(TeacherLeaveApplication.created_at.desc()).all()
            
            # Load teachers and attachments
            for leave in leaves:
                if leave.teacher_id:
                    leave.teacher = session_db.query(Teacher).filter_by(id=leave.teacher_id).first()
                else:
                    leave.teacher = None
                
                # Load attachments
                try:
                    docs = session_db.query(TeacherDocument).filter_by(
                        tenant_id=school.id,
                        teacher_id=leave.teacher_id
                    ).order_by(TeacherDocument.uploaded_at.desc()).all()
                    
                    attachments = []
                    for d in docs:
                        if leave.applied_date:
                            delta = (d.uploaded_at - leave.applied_date).total_seconds()
                            if abs(delta) <= 60*60*24:  # within 24 hours
                                attachments.append(d)
                        elif leave.created_at:
                            delta = (d.uploaded_at - leave.created_at).total_seconds()
                            if abs(delta) <= 60*60*24:
                                attachments.append(d)
                    leave.attachments = attachments
                except Exception:
                    leave.attachments = []
            
            # Calculate statistics
            stats = {
                'pending': session_db.query(TeacherLeaveApplication).filter_by(
                    tenant_id=school.id, 
                    status='Pending'
                ).count(),
                'approved': session_db.query(TeacherLeaveApplication).filter_by(
                    tenant_id=school.id, 
                    status='Approved'
                ).count(),
                'rejected': session_db.query(TeacherLeaveApplication).filter_by(
                    tenant_id=school.id, 
                    status='Rejected'
                ).count(),
                'total': session_db.query(TeacherLeaveApplication).filter_by(tenant_id=school.id).count()
            }
            
            return render_template('akademi/teacher/teacher_leaves_list.html',
                                 school=school,
                                 leaves=leaves,
                                 stats=stats,
                                 current_user=current_user)
                                 
        except Exception as e:
            logger.error(f"Teacher leaves admin error for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error loading teacher leaves', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/teacher-leaves/<int:leave_id>')
    @require_school_auth
    def teacher_leave_details_admin(tenant_slug, leave_id):
        """View detailed information about a teacher leave application"""
        session_db = get_session()
        try:
            from leave_models import TeacherLeaveApplication
            from teacher_models import Teacher, TeacherDocument
            
            school = g.current_tenant
            
            leave = session_db.query(TeacherLeaveApplication).filter_by(
                id=leave_id,
                tenant_id=school.id
            ).first()
            
            if not leave:
                return '<div class="alert alert-danger">Leave application not found</div>', 404
            
            # Load teacher
            if leave.teacher_id:
                leave.teacher = session_db.query(Teacher).filter_by(id=leave.teacher_id).first()
            
            # Load attachments
            try:
                docs = session_db.query(TeacherDocument).filter_by(
                    tenant_id=school.id,
                    teacher_id=leave.teacher_id
                ).order_by(TeacherDocument.uploaded_at.desc()).all()
                
                attachments = []
                for d in docs:
                    if leave.applied_date:
                        delta = (d.uploaded_at - leave.applied_date).total_seconds()
                        if abs(delta) <= 60*60*24:
                            attachments.append(d)
                    elif leave.created_at:
                        delta = (d.uploaded_at - leave.created_at).total_seconds()
                        if abs(delta) <= 60*60*24:
                            attachments.append(d)
                leave.attachments = attachments
            except Exception:
                leave.attachments = []
            
            return render_template('akademi/teacher/teacher_leave_details.html',
                                 school=school,
                                 leave=leave,
                                 current_user=current_user)
                                 
        except Exception as e:
            logger.error(f"Error loading teacher leave details: {e}")
            return '<div class="alert alert-danger">Error loading leave details</div>', 500
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/teacher-leaves/<int:leave_id>/approve', methods=['POST'])
    @require_school_auth
    def teacher_leave_approve(tenant_slug, leave_id):
        """Approve a teacher leave application"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash('Access denied', 'error')
            return redirect(url_for('school.teacher_leaves_admin', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            from leave_helpers import approve_leave_application
            
            success, message = approve_leave_application(session_db, leave_id, current_user.id, None)
            
            if success:
                flash(message, 'success')
            else:
                flash(message, 'error')
                
        except Exception as e:
            logger.error(f"Error approving teacher leave: {e}")
            flash('Error approving leave', 'error')
        finally:
            session_db.close()
        
        return redirect(url_for('school.teacher_leaves_admin', tenant_slug=tenant_slug))
    
    @school_bp.route('/<tenant_slug>/teacher-leaves/<int:leave_id>/reject', methods=['POST'])
    @require_school_auth
    def teacher_leave_reject(tenant_slug, leave_id):
        """Reject a teacher leave application"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash('Access denied', 'error')
            return redirect(url_for('school.teacher_leaves_admin', tenant_slug=tenant_slug))
        
        rejection_reason = request.form.get('rejection_reason')
        
        if not rejection_reason:
            flash('Rejection reason is required', 'error')
            return redirect(url_for('school.teacher_leaves_admin', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            from leave_helpers import reject_leave_application
            
            success, message = reject_leave_application(session_db, leave_id, current_user.id, rejection_reason)
            
            if success:
                flash(message, 'success')
            else:
                flash(message, 'error')
                
        except Exception as e:
            logger.error(f"Error rejecting teacher leave: {e}")
            flash('Error rejecting leave', 'error')
        finally:
            session_db.close()
        
        return redirect(url_for('school.teacher_leaves_admin', tenant_slug=tenant_slug))

    @school_bp.route('/<tenant_slug>/leaves/approvals')
    @require_school_auth
    def leave_approvals(tenant_slug):
        """
        List pending leave applications for school admins to approve/reject
        """
        if current_user.role not in ['school_admin', 'portal_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))

        session_db = get_session()
        try:
            from leave_models import TeacherLeaveApplication

            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))

            # Fetch pending leave applications for this tenant
            pending_apps = session_db.query(TeacherLeaveApplication).filter_by(
                tenant_id=school.id,
                status='Pending'
            ).order_by(TeacherLeaveApplication.created_at.desc()).all()

            # Load attachments for each application (TeacherDocument entries)
            from teacher_models import TeacherDocument
            for app in pending_apps:
                try:
                    docs = session_db.query(TeacherDocument).filter_by(
                        tenant_id=school.id,
                        teacher_id=app.teacher_id
                    ).order_by(TeacherDocument.uploaded_at.desc()).all()
                    # Attach only documents that were uploaded around the application time
                    # (simple heuristic: uploaded_at within +/- 1 day of applied_date)
                    attachments = []
                    for d in docs:
                        if not app.applied_date:
                            attachments.append(d)
                            continue
                        delta = (d.uploaded_at - app.applied_date).total_seconds()
                        if abs(delta) <= 60*60*24:  # within 24 hours
                            attachments.append(d)
                    app.attachments = attachments
                except Exception:
                    app.attachments = []

            return render_template('akademi/teacher/leaves/approvals.html',
                                 school=school,
                                 pending_apps=pending_apps,
                                 current_user=current_user)

        except Exception as e:
            logger.error(f"Error loading leave approvals for {tenant_slug}: {e}")
            flash('Error loading leave approvals', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()


    @school_bp.route('/<tenant_slug>/leaves/approve', methods=['POST'])
    @require_school_auth
    def api_approve_leave(tenant_slug):
        """API endpoint to approve a leave application (expects JSON or form with leave_id)"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            return jsonify({'success': False, 'message': 'Access denied'}), 403

        leave_id = request.form.get('leave_id') or (request.json and request.json.get('leave_id'))
        admin_notes = request.form.get('admin_notes') or (request.json and request.json.get('admin_notes'))

        if not leave_id:
            return jsonify({'success': False, 'message': 'leave_id is required'}), 400

        session_db = get_session()
        try:
            from leave_helpers import approve_leave_application

            success, message = approve_leave_application(session_db, int(leave_id), current_user.id, admin_notes)
            if success:
                return jsonify({'success': True, 'message': message}), 200
            else:
                return jsonify({'success': False, 'message': message}), 400

        except Exception as e:
            session_db.rollback()
            logger.error(f"Error approving leave: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()


    @school_bp.route('/<tenant_slug>/leaves/reject', methods=['POST'])
    @require_school_auth
    def api_reject_leave(tenant_slug):
        """API endpoint to reject a leave application (expects JSON or form with leave_id & reason)"""
        if current_user.role not in ['school_admin', 'portal_admin']:
            return jsonify({'success': False, 'message': 'Access denied'}), 403

        leave_id = request.form.get('leave_id') or (request.json and request.json.get('leave_id'))
        reason = request.form.get('reason') or (request.json and request.json.get('reason'))

        if not leave_id:
            return jsonify({'success': False, 'message': 'leave_id is required'}), 400

        session_db = get_session()
        try:
            from leave_helpers import reject_leave_application

            success, message = reject_leave_application(session_db, int(leave_id), current_user.id, reason)
            if success:
                return jsonify({'success': True, 'message': message}), 200
            else:
                return jsonify({'success': False, 'message': message}), 400

        except Exception as e:
            session_db.rollback()
            logger.error(f"Error rejecting leave: {e}")
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()

