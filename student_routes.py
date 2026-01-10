"""
Student Routes for School ERP
Extracted from school_routes_dynamic.py
"""

from flask import render_template, request, redirect, url_for, flash, g, jsonify, current_app
from flask_login import current_user
from sqlalchemy import desc, or_, extract
from datetime import datetime
import logging

from db_single import get_session
from models import Tenant, Student

logger = logging.getLogger(__name__)


def register_student_routes(school_bp, require_school_auth):
    """Register all student routes to the school blueprint"""
    
    # PASTE ALL STUDENT ROUTES HERE
    @school_bp.route('/<tenant_slug>/students')
    @require_school_auth
    def students(tenant_slug):
        """List all students in this school with filters, search, and pagination"""
        session_db = get_session()
        try:
            from models import AcademicSession, Class
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            # Get filter parameters
            search_query = request.args.get('search', '').strip()
            class_id = request.args.get('class_id', '').strip()
            session_id = request.args.get('session_id', '').strip()
            gender = request.args.get('gender', '').strip()
            status = request.args.get('status', '').strip()
            sort_by = request.args.get('sort_by', 'newest').strip()
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 12))  # 12 cards per page for grid layout
            
            # Base query
            query = session_db.query(Student).filter_by(tenant_id=school.id)
            
            # Apply search filter
            if search_query:
                search_pattern = f"%{search_query}%"
                query = query.filter(
                    or_(
                        Student.full_name.ilike(search_pattern),
                        Student.admission_number.ilike(search_pattern),
                        Student.roll_number.ilike(search_pattern),
                        Student.email.ilike(search_pattern),
                        Student.father_name.ilike(search_pattern)
                    )
                )
            
            # Apply filters
            if class_id:
                query = query.filter(Student.class_id == int(class_id))
            if session_id:
                query = query.filter(Student.session_id == int(session_id))
            if gender:
                query = query.filter(Student.gender == gender)
            if status:
                query = query.filter(Student.status == status)
            
            # Apply sorting
            # When no status filter, show Active first
            from sqlalchemy import case
            from models import StudentStatusEnum
            status_priority = case(
                (Student.status == StudentStatusEnum.ACTIVE, 0),
                else_=1
            )
            
            if sort_by == 'newest':
                if not status:
                    query = query.order_by(status_priority, desc(Student.created_at))
                else:
                    query = query.order_by(desc(Student.created_at))
            elif sort_by == 'oldest':
                if not status:
                    query = query.order_by(status_priority, asc(Student.created_at))
                else:
                    query = query.order_by(asc(Student.created_at))
            elif sort_by == 'name_asc':
                if not status:
                    query = query.order_by(status_priority, asc(Student.full_name))
                else:
                    query = query.order_by(asc(Student.full_name))
            elif sort_by == 'name_desc':
                if not status:
                    query = query.order_by(status_priority, desc(Student.full_name))
                else:
                    query = query.order_by(desc(Student.full_name))
            elif sort_by == 'admission_no':
                if not status:
                    query = query.order_by(status_priority, asc(Student.admission_number))
                else:
                    query = query.order_by(asc(Student.admission_number))
            elif sort_by == 'roll_no':
                if not status:
                    query = query.order_by(status_priority, asc(Student.roll_number))
                else:
                    query = query.order_by(asc(Student.roll_number))
            else:
                if not status:
                    query = query.order_by(status_priority, desc(Student.created_at))
                else:
                    query = query.order_by(desc(Student.created_at))
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            offset = (page - 1) * per_page
            students = query.limit(per_page).offset(offset).all()
            
            # Prepare pagination data
            total_pages = (total + per_page - 1) // per_page
            pagination = {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': total_pages,
                'has_prev': page > 1,
                'has_next': page < total_pages,
                'start': offset + 1 if students else 0,
                'end': min(offset + per_page, total)
            }
            
            # Get classes and sessions for filters
            classes = session_db.query(Class).filter_by(tenant_id=school.id).all()
            academic_sessions = session_db.query(AcademicSession).filter_by(tenant_id=school.id).all()
            
            # Current filters
            current_filters = {
                'search': search_query,
                'class_id': class_id,
                'session_id': session_id,
                'gender': gender,
                'status': status,
                'sort_by': sort_by,
                'per_page': per_page
            }
            
            return render_template('akademi/student/students_view.html', 
                                 school=school,
                                 students=students,
                                 classes=classes,
                                 academic_sessions=academic_sessions,
                                 current_filters=current_filters,
                                 pagination=pagination,
                                 current_user=current_user)
                                 
        except Exception as e:
            logger.error(f"Students list error for {tenant_slug}: {e}")
            flash('Error loading students', 'error')
            return render_template('akademi/student/students_view.html', 
                                 school={'name': tenant_slug, 'slug': tenant_slug},
                                 students=[],
                                 classes=[],
                                 academic_sessions=[],
                                 current_filters={},
                                 pagination={'total': 0})
        finally:
            session_db.close()
    @school_bp.route('/<tenant_slug>/students/<int:id>')
    @require_school_auth
    def student_details(tenant_slug, id):
        """View individual student details"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
                
            student = session_db.query(Student).filter_by(
                id=id, tenant_id=school.id
            ).first()
            
            if not student:
                flash('Student not found', 'error')
                return redirect(url_for('school.students', tenant_slug=tenant_slug))
                
            return render_template('akademi/student/student-details.html', 
                                 school=school,
                                 student=student,
                                 current_user=current_user)
                                 
        except Exception as e:
            logger.error(f"Student details error for {tenant_slug}: {e}")
            flash('Error loading student details', 'error')
            return redirect(url_for('school.students', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/students/<int:id>/profile')
    @require_school_auth
    def student_profile_view(tenant_slug, id):
        """View comprehensive student profile with all related data (admin view)"""
        session_db = get_session()
        try:
            from student_models import (
                StudentGuardian, StudentMedicalInfo, StudentPreviousSchool,
                StudentSibling, StudentDocument
            )
            
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
                
            student = session_db.query(Student).filter_by(
                id=id, tenant_id=school.id
            ).first()
            
            if not student:
                flash('Student not found', 'error')
                return redirect(url_for('school.students', tenant_slug=tenant_slug))
            
            # Get all related data
            guardians = session_db.query(StudentGuardian).filter_by(
                student_id=student.id, tenant_id=school.id
            ).all()
            
            medical_info = session_db.query(StudentMedicalInfo).filter_by(
                student_id=student.id, tenant_id=school.id
            ).first()
            
            previous_schools = session_db.query(StudentPreviousSchool).filter_by(
                student_id=student.id, tenant_id=school.id
            ).order_by(StudentPreviousSchool.tc_date.desc()).all()
            
            siblings = session_db.query(StudentSibling).filter_by(
                student_id=student.id, tenant_id=school.id
            ).all()
            
            documents = session_db.query(StudentDocument).filter_by(
                student_id=student.id, tenant_id=school.id
            ).order_by(StudentDocument.uploaded_at.desc()).all()
                
            return render_template('akademi/student/student-profile.html', 
                                 school=school,
                                 student=student,
                                 guardians=guardians,
                                 medical_info=medical_info,
                                 previous_schools=previous_schools,
                                 siblings=siblings,
                                 documents=documents,
                                 current_user=current_user)
                                 
        except Exception as e:
            logger.error(f"Student profile error for {tenant_slug}: {e}")
            import traceback
            traceback.print_exc()
            flash('Error loading student profile', 'error')
            return redirect(url_for('school.students', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/student-detail')
    @require_school_auth
    def student_detail_page(tenant_slug):
        """Student detail page - shows list of students with detail links"""
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
                
            students = session_db.query(Student).filter_by(
                tenant_id=school.id
            ).order_by(Student.full_name).all()
            
            return render_template('akademi/student/student-details.html', 
                                 school=school,
                                 students=students,
                                 current_user=current_user)
                                 
        except Exception as e:
            logger.error(f"Student detail page error for {tenant_slug}: {e}")
            flash('Error loading student detail page', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/students/add', methods=['GET', 'POST'])
    @require_school_auth
    def add_student(tenant_slug):
        """Add new student to this school"""
        if current_user.role not in ['school_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.students', tenant_slug=tenant_slug))
        
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            
            if request.method == 'POST':
                name = request.form.get('name', '').strip()
                email = request.form.get('email', '').strip()
                student_id = request.form.get('student_id', '').strip()
                class_name = request.form.get('class_name', '').strip()
                
                if not all([name, student_id, class_name]):
                    flash('Name, student ID, and class are required', 'error')
                    return render_template('akademi/student/add-student.html', school=school)
                
                # Check if student ID already exists in this school
                existing = session_db.query(Student).filter_by(
                    tenant_id=tenant_slug,
                    student_id=student_id
                ).first()
                
                if existing:
                    flash('Student ID already exists in this school', 'error')
                    return render_template('akademi/student/add-student.html', school=school)
                
                # Create new student
                new_student = Student(
                    name=name,
                    email=email if email else None,
                    student_id=student_id,
                    class_name=class_name,
                    tenant_id=tenant_slug
                )
                
                session_db.add(new_student)
                session_db.commit()
                
                flash(f'Student "{name}" added successfully!', 'success')
                return redirect(url_for('school.students', tenant_slug=tenant_slug))
            
            return render_template('akademi/student/add-student.html', school=school)
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Add student error for {tenant_slug}: {e}")
            flash('Error adding student', 'error')
            return redirect(url_for('school.students', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/students/add-new', methods=['GET', 'POST'])
    @require_school_auth
    def add_student_new(tenant_slug):
        """New student registration form - similar to add teacher"""
        if current_user.role not in ['school_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.students', tenant_slug=tenant_slug))
        
        from werkzeug.utils import secure_filename
        from models import AcademicSession, Class, GenderEnum, CategoryEnum, StudentStatusEnum
        import os
        
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            
            if request.method == 'POST':
                # Get form data - strip whitespace
                admission_number = request.form.get('admission_number', '').strip()
                first_name = request.form.get('first_name', '').strip()
                last_name = request.form.get('last_name', '').strip()
                gender = request.form.get('gender', '').strip()
                date_of_birth = request.form.get('date_of_birth', '').strip()
                category = request.form.get('category', 'General').strip()
                blood_group = request.form.get('blood_group', '').strip()
                aadhar_number = request.form.get('aadhar_number', '').strip()
                email = request.form.get('email', '').strip()
                phone = request.form.get('phone', '').strip()
                address = request.form.get('address', '').strip()
                city = request.form.get('city', '').strip()
                state = request.form.get('state', '').strip()
                pincode = request.form.get('pincode', '').strip()
                father_name = request.form.get('father_name', '').strip()
                mother_name = request.form.get('mother_name', '').strip()
                guardian_phone = request.form.get('guardian_phone', '').strip()
                guardian_email = request.form.get('guardian_email', '').strip()
                class_id = request.form.get('class_id', '').strip()
                session_id = request.form.get('session_id', '').strip()
                roll_number = request.form.get('roll_number', '').strip()
                admission_date = request.form.get('admission_date', '').strip()
                
                # Validate required fields
                if not admission_number:
                    flash('Admission number is required', 'error')
                    academic_sessions = session_db.query(AcademicSession).filter_by(tenant_id=school.id).all()
                    classes = session_db.query(Class).filter_by(tenant_id=school.id).all()
                    context = {
                        "page_title": "Register New Student",
                        "school": school,
                        "academic_sessions": academic_sessions,
                        "classes": classes,
                        "form_data": request.form
                    }
                    return render_template("akademi/student/add-student-new.html", **context)
                
                # Convert empty strings to None for optional unique fields
                aadhar_number = aadhar_number if aadhar_number else None
                email = email if email else None
                
                # Check if admission number already exists in this school
                existing = session_db.query(Student).filter_by(
                    tenant_id=school.id,
                    admission_number=admission_number
                ).first()
                
                logger.info(f"Checking admission number '{admission_number}' for tenant {school.id}: existing={existing}")
                
                if existing:
                    flash('Admission number already exists in this school', 'error')
                    # GET request data for re-rendering form
                    academic_sessions = session_db.query(AcademicSession).filter_by(tenant_id=school.id).all()
                    classes = session_db.query(Class).filter_by(tenant_id=school.id).all()
                    context = {
                        "page_title": "Register New Student",
                        "school": school,
                        "academic_sessions": academic_sessions,
                        "classes": classes,
                        "form_data": request.form
                    }
                    return render_template("akademi/student/add-student-new.html", **context)
                
                # Handle file upload (after validation)
                photo_url = None
                if 'photo' in request.files:
                    photo = request.files['photo']
                    if photo and photo.filename:
                        # Create tenant/student specific upload directory
                        upload_dir = os.path.join('akademi', 'static', 'uploads', 'documents', str(school.id), 'students', str(admission_number))
                        os.makedirs(upload_dir, exist_ok=True)

                        # Secure the filename and save
                        filename = secure_filename(f"{admission_number}_{photo.filename}")
                        filepath = os.path.join(upload_dir, filename)
                        photo.save(filepath)
                        photo_url = f"uploads/documents/{school.id}/students/{admission_number}/{filename}"
                
                # Check if email already exists (if provided)
                if email:
                    existing_email = session_db.query(Student).filter_by(email=email).first()
                    if existing_email:
                        flash('Email already exists', 'error')
                        academic_sessions = session_db.query(AcademicSession).filter_by(tenant_id=school.id).all()
                        classes = session_db.query(Class).filter_by(tenant_id=school.id).all()
                        context = {
                            "page_title": "Register New Student",
                            "school": school,
                            "academic_sessions": academic_sessions,
                            "classes": classes,
                            "form_data": request.form
                        }
                        return render_template("akademi/student/add-student-new.html", **context)
                
                # Check if aadhar number already exists (if provided)
                if aadhar_number:
                    existing_aadhar = session_db.query(Student).filter_by(aadhar_number=aadhar_number).first()
                    if existing_aadhar:
                        flash('Aadhar number already exists', 'error')
                        academic_sessions = session_db.query(AcademicSession).filter_by(tenant_id=school.id).all()
                        classes = session_db.query(Class).filter_by(tenant_id=school.id).all()
                        context = {
                            "page_title": "Register New Student",
                            "school": school,
                            "academic_sessions": academic_sessions,
                            "classes": classes,
                            "form_data": request.form
                        }
                        return render_template("akademi/student/add-student-new.html", **context)
                
                # Parse dates
                dob = datetime.strptime(date_of_birth, '%Y-%m-%d').date() if date_of_birth else None
                adm_date = datetime.strptime(admission_date, '%Y-%m-%d').date() if admission_date else datetime.today().date()
                
                # Convert gender from form value to enum value
                if gender == 'Male':
                    gender_value = 'M'
                elif gender == 'Female':
                    gender_value = 'F'
                elif gender == 'Other':
                    gender_value = 'O'
                else:
                    gender_value = gender  # Already in correct format (M, F, O)
                
                # Create new student - use raw string values for enum columns
                new_student = Student(
                    tenant_id=school.id,
                    admission_number=admission_number,
                    first_name=first_name,
                    last_name=last_name,
                    full_name=f"{first_name} {last_name}",
                    date_of_birth=dob,
                    gender=gender_value,  # Pass the converted value 'M', 'F', or 'O'
                    category=category,  # Pass the raw value 'General', 'SC', etc.
                    blood_group=blood_group,
                    aadhar_number=aadhar_number,
                    photo_url=photo_url,
                    email=email,
                    phone=phone,
                    address=address,
                    city=city,
                    state=state,
                    pincode=pincode,
                    father_name=father_name,
                    mother_name=mother_name,
                    guardian_phone=guardian_phone,
                    guardian_email=guardian_email,
                    class_id=int(class_id),
                    session_id=int(session_id),
                    roll_number=roll_number,
                    admission_date=adm_date,
                    status='Active'  # Pass the raw value instead of enum
                )
                
                # Save to database
                try:
                    session_db.add(new_student)
                    session_db.commit()
                    
                    flash('Student registered successfully!', 'success')
                    return redirect(url_for('school.students', tenant_slug=tenant_slug))
                except Exception as commit_error:
                    session_db.rollback()
                    logger.error(f"Database commit error: {commit_error}")
                    logger.error(f"Admission number value: repr={repr(admission_number)}, type={type(admission_number)}")
                    
                    from sqlalchemy.exc import IntegrityError
                    if isinstance(commit_error, IntegrityError):
                        error_msg = str(commit_error)
                        if 'admission_number' in error_msg or 'unique_admission_number' in error_msg or 'unique_tenant_admission_number' in error_msg:
                            flash('Error: Admission number already exists!', 'danger')
                        elif 'email' in error_msg:
                            flash('Error: Email already exists!', 'danger')
                        elif 'aadhar_number' in error_msg:
                            flash('Error: Aadhar number already exists!', 'danger')
                        else:
                            flash(f'Error: Database constraint violated - {error_msg}', 'danger')
                    else:
                        flash(f'Error saving student: {str(commit_error)}', 'danger')
                    
                    academic_sessions = session_db.query(AcademicSession).filter_by(tenant_id=school.id).all()
                    classes = session_db.query(Class).filter_by(tenant_id=school.id).all()
                    context = {
                        "page_title": "Register New Student",
                        "school": school,
                        "academic_sessions": academic_sessions,
                        "classes": classes,
                        "form_data": request.form
                    }
                    return render_template("akademi/student/add-student-new.html", **context)
            
            # GET request - show registration form
            academic_sessions = session_db.query(AcademicSession).filter_by(tenant_id=school.id).all()
            classes = session_db.query(Class).filter_by(tenant_id=school.id).all()
            
            context = {
                "page_title": "Register New Student",
                "school": school,
                "academic_sessions": academic_sessions,
                "classes": classes
            }
            return render_template("akademi/student/add-student-new.html", **context)
            
        except Exception as e:
            from sqlalchemy.exc import IntegrityError
            session_db.rollback()
            if isinstance(e, IntegrityError):
                if 'admission_number' in str(e):
                    flash('Error: Admission number already exists!', 'danger')
                elif 'email' in str(e):
                    flash('Error: Email already exists!', 'danger')
                elif 'aadhar_number' in str(e):
                    flash('Error: Aadhar number already exists!', 'danger')
                else:
                    flash('Error: Database integrity constraint violated!', 'danger')
            else:
                logger.error(f"Add student new error for {tenant_slug}: {e}")
                flash(f'Error registering student: {str(e)}', 'danger')
            return redirect(url_for('school.add_student_new', tenant_slug=tenant_slug))
        finally:
            session_db.close()


    @school_bp.route('/<tenant_slug>/students/template.csv')
    @require_school_auth
    def download_student_template(tenant_slug):
        """Return a CSV template for bulk student upload (tenant-scoped)."""
        import csv
        import io


        # Template uses human-friendly names only for class and session:
        # - class: use values like "10-A" (class_name-section) or variants like "10 A" or "10A"
        # - session: use session_name like "2024-25"
        headers = [
            'admission_number', 'first_name', 'last_name', 'gender', 'date_of_birth',
            'category', 'blood_group', 'aadhar_number', 'email', 'phone', 'address',
            'city', 'state', 'pincode', 'father_name', 'mother_name', 'guardian_phone',
            'guardian_email', 'class', 'session', 'roll_number', 'admission_date'
        ]

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        # Example row using names (required): class as "10-A" and session as "2024-25"
        writer.writerow(['STU001', 'First', 'Last', 'M', '2010-01-01', 'General', '', '', 'student@example.com', '9876543210', '', 'City', 'State', '110001', 'Father Name', 'Mother Name', '9876543210', 'parent@example.com', '10-A', '2024-25', '01', '2025-04-01'])
        # Another example: alternate formatting for class name (no dash)
        writer.writerow(['STU002', 'Second', 'Last', 'F', '2011-02-02', 'General', '', '', 'student2@example.com', '9876500000', '', 'City', 'State', '110002', 'Father2', 'Mother2', '9876500000', 'parent2@example.com', '10A', '2024-25', '02', '2025-04-02'])

        csv_data = output.getvalue()
        output.close()

        from flask import make_response
        resp = make_response(csv_data)
        resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
        resp.headers['Content-Disposition'] = f'attachment; filename={tenant_slug}_student_upload_template.csv'
        return resp


    @school_bp.route('/<tenant_slug>/students/bulk-upload', methods=['POST'])
    @require_school_auth
    def bulk_upload_students(tenant_slug):
        """Tenant-scoped bulk CSV student upload handler.
        Mirrors the upload logic but uses the tenant DB session and redirects back to tenant page.
        """
        import csv
        import io
        from datetime import datetime
        from sqlalchemy.exc import IntegrityError
        from models import Student, Class, AcademicSession, Tenant

        file = request.files.get('csv_file')
        if not file:
            flash('No file uploaded.', 'danger')
            return redirect(url_for('school.add_student_new', tenant_slug=tenant_slug))

        session_db = get_session()
        success = 0
        errors = []
        row_no = 1

        try:
            stream = io.StringIO(file.stream.read().decode('utf-8-sig'))
            reader = csv.DictReader(stream)

            import re

            def resolve_class_id(field_value, tenant_id):
                """Resolve a class identifier provided as a name like '10-A'. Returns int id or None.

                NOTE: numeric IDs are no longer accepted. Only human-friendly names are supported.
                """
                if not field_value:
                    return None
                v = field_value.strip()
                # try format 'ClassName-Section' e.g., '10-A'
                if '-' in v:
                    parts = v.split('-', 1)
                    cname = parts[0].strip()
                    section = parts[1].strip()
                    cls = session_db.query(Class).filter_by(tenant_id=tenant_id, class_name=cname, section=section, is_active=True).first()
                    if cls:
                        return cls.id
                # try match by combined name (class_name+section)
                compact = re.sub(r'\s+', '', v)
                candidate = session_db.query(Class).filter_by(tenant_id=tenant_id, is_active=True).all()
                for c in candidate:
                    if f"{c.class_name}{c.section}".lower() == compact.lower() or f"{c.class_name}-{c.section}".lower() == v.lower():
                        return c.id
                # try match by class_name only (if unique)
                cls = session_db.query(Class).filter_by(tenant_id=tenant_id, class_name=v, is_active=True).first()
                if cls:
                    return cls.id
                return None

            def resolve_session_id(field_value, tenant_id):
                """Resolve an academic session by session_name like '2024-25'.

                NOTE: numeric IDs are no longer accepted.
                """
                if not field_value:
                    return None
                v = field_value.strip()
                sess = session_db.query(AcademicSession).filter_by(tenant_id=tenant_id, session_name=v).first()
                if sess:
                    return sess.id
                # try partial match
                sess = session_db.query(AcademicSession).filter(AcademicSession.tenant_id == tenant_id, AcademicSession.session_name.ilike(f"%{v}%")).first()
                if sess:
                    return sess.id
                return None

            # Two-phase processing: first validate all rows (resolve class/session, parse values,
            # check CSV-level duplicates and required fields). If any row has an error, do not
            # commit anything. This ensures atomic behavior per user's request.
            tenant = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            tenant_id = tenant.id

            parsed_rows = []
            csv_admission_nums = set()
            csv_aadhars = set()

            for row in reader:
                row_no += 1
                row = {k.strip(): (v.strip() if v is not None else '') for k, v in row.items()}
                admission_number = row.get('admission_number')
                first_name = row.get('first_name')
                last_name = row.get('last_name')
                guardian_phone = row.get('guardian_phone')
                # Require name-based columns: 'class' (e.g., '10-A') and 'session' (e.g., '2024-25')
                class_field = row.get('class')
                session_field = row.get('session')

                # Basic required checks
                if not admission_number or not first_name or not last_name or not guardian_phone:
                    errors.append(f'Row {row_no}: Missing required basic fields (admission_number, first_name, last_name, guardian_phone)')
                    continue

                # Duplicate check inside CSV
                if admission_number in csv_admission_nums:
                    errors.append(f'Row {row_no}: Duplicate admission_number "{admission_number}" in uploaded file')
                    continue
                csv_admission_nums.add(admission_number)

                aadhar_val = row.get('aadhar_number') or None
                if aadhar_val:
                    if aadhar_val in csv_aadhars:
                        errors.append(f'Row {row_no}: Duplicate aadhar_number "{aadhar_val}" in uploaded file')
                        continue
                    csv_aadhars.add(aadhar_val)

                # Resolve class/session to IDs
                class_id = resolve_class_id(class_field, tenant_id) if class_field else None
                session_id = resolve_session_id(session_field, tenant_id) if session_field else None

                if not class_id:
                    errors.append(f'Row {row_no}: Unknown or missing class "{class_field}"')
                    continue
                if not session_id:
                    errors.append(f'Row {row_no}: Unknown or missing session "{session_field}"')
                    continue

                # Parse dates
                try:
                    dob = None
                    if row.get('date_of_birth'):
                        dob = datetime.strptime(row.get('date_of_birth'), '%Y-%m-%d').date()

                    adm_date = datetime.strptime(row.get('admission_date'), '%Y-%m-%d').date() if row.get('admission_date') else datetime.now().date()
                except Exception as e:
                    errors.append(f'Row {row_no}: Date parse error - {str(e)}')
                    continue

                gender = row.get('gender') or 'M'
                category = row.get('category') or 'General'

                parsed_rows.append({
                    'row_no': row_no,
                    'admission_number': admission_number,
                    'first_name': first_name,
                    'last_name': last_name,
                    'full_name': f"{first_name} {last_name}",
                    'date_of_birth': dob,
                    'gender': gender,
                    'category': category,
                    'blood_group': row.get('blood_group'),
                    'aadhar_number': aadhar_val,
                    'email': row.get('email') or None,
                    'phone': row.get('phone') or None,
                    'address': row.get('address') or None,
                    'city': row.get('city') or None,
                    'state': row.get('state') or None,
                    'pincode': row.get('pincode') or None,
                    'father_name': row.get('father_name') or None,
                    'mother_name': row.get('mother_name') or None,
                    'guardian_phone': row.get('guardian_phone'),
                    'guardian_email': row.get('guardian_email') or None,
                    'class_id': int(class_id),
                    'session_id': int(session_id),
                    'roll_number': row.get('roll_number') or None,
                    'admission_date': adm_date,
                })

            # If there were CSV-level errors, do not proceed to DB checks or commits
            if errors:
                # close session and report
                session_db.close()
                error_msg = f'Upload failed. {len(errors)} error(s) found:<br>' + '<br>'.join(errors[:10])
                if len(errors) > 10:
                    error_msg += f'<br>... and {len(errors) - 10} more errors'
                flash(error_msg, 'danger')
                return redirect(url_for('school.add_student_new', tenant_slug=tenant_slug))

            # Check for uniqueness conflicts against DB (admission_number and aadhar)
            admission_list = [r['admission_number'] for r in parsed_rows]
            existing_adms = session_db.query(Student.admission_number).filter(Student.tenant_id == tenant_id, Student.admission_number.in_(admission_list)).all()
            if existing_adms:
                for ea in existing_adms:
                    errors.append(f'Admission number already exists: {ea[0]}')

            aadhar_list = [r['aadhar_number'] for r in parsed_rows if r['aadhar_number']]
            if aadhar_list:
                existing_aadhars = session_db.query(Student.aadhar_number).filter(Student.tenant_id == tenant_id, Student.aadhar_number.in_(aadhar_list)).all()
                if existing_aadhars:
                    for ea in existing_aadhars:
                        errors.append(f'Aadhar number already exists: {ea[0]}')

            if errors:
                session_db.close()
                error_msg = f'Upload failed. {len(errors)} error(s) found:<br>' + '<br>'.join(errors[:10])
                if len(errors) > 10:
                    error_msg += f'<br>... and {len(errors) - 10} more errors'
                flash(error_msg, 'danger')
                return redirect(url_for('school.add_student_new', tenant_slug=tenant_slug))

            # All validations passed; create Student objects and commit in one transaction
            students_to_add = []
            for r in parsed_rows:
                s = Student(
                    tenant_id=tenant_id,
                    admission_number=r['admission_number'],
                    first_name=r['first_name'],
                    last_name=r['last_name'],
                    full_name=r['full_name'],
                    date_of_birth=r['date_of_birth'],
                    gender=r['gender'],
                    category=r['category'],
                    blood_group=r['blood_group'],
                    aadhar_number=r['aadhar_number'] or None,
                    email=r['email'],
                    phone=r['phone'],
                    address=r['address'],
                    city=r['city'],
                    state=r['state'],
                    pincode=r['pincode'],
                    father_name=r['father_name'],
                    mother_name=r['mother_name'],
                    guardian_phone=r['guardian_phone'],
                    guardian_email=r['guardian_email'],
                    class_id=r['class_id'],
                    session_id=r['session_id'],
                    roll_number=r['roll_number'],
                    admission_date=r['admission_date'],
                    status='Active'
                )
                students_to_add.append(s)

            try:
                session_db.add_all(students_to_add)
                session_db.commit()
                success = len(students_to_add)
            except IntegrityError as ie:
                session_db.rollback()
                errors.append(f'Integrity error during commit: {str(ie.orig) if hasattr(ie, "orig") else str(ie)}')
            except Exception as e:
                session_db.rollback()
                errors.append(f'Error during commit: {str(e)}')

            try:
                session_db.commit()
            except Exception:
                session_db.rollback()

        finally:
            session_db.close()

        summary = f'Imported {success} students.'
        if errors:
            summary += f' {len(errors)} rows had errors.'
            for e in errors[:10]:
                flash(e, 'warning')

        flash(summary, 'success' if success else 'danger')
        return redirect(url_for('school.add_student_new', tenant_slug=tenant_slug))
    
    @school_bp.route('/<tenant_slug>/students/<int:id>/profile/edit', methods=['GET', 'POST'])
    @require_school_auth
    def student_profile_edit(tenant_slug, id):
        """Edit/Complete student profile - similar to teacher profile edit"""
        if current_user.role not in ['school_admin']:
            flash('Access denied - admin only', 'error')
            return redirect(url_for('school.students', tenant_slug=tenant_slug))
        
        from werkzeug.utils import secure_filename
        from student_models import StudentGuardian, StudentMedicalInfo, StudentPreviousSchool, StudentSibling, StudentDocument, GuardianTypeEnum, StudentDocumentTypeEnum
        from models import Class, AcademicSession
        import os
        
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                flash('School not found', 'error')
                return redirect(url_for('admin.admin_login'))
            
            # Get student with all relationships
            student = session_db.query(Student).filter_by(
                id=id,
                tenant_id=school.id
            ).first()
            
            if not student:
                flash('Student not found', 'error')
                return redirect(url_for('school.students', tenant_slug=tenant_slug))
            
            # Fetch active classes & sessions for dropdowns
            classes = session_db.query(Class).filter_by(tenant_id=school.id, is_active=True).order_by(Class.class_name, Class.section).all()
            sessions = session_db.query(AcademicSession).filter_by(tenant_id=school.id, is_active=True).order_by(AcademicSession.start_date.desc()).all()

            if request.method == 'POST':
                try:
                    current_tab = int(request.form.get('current_tab', 0))
                    
                    # Update Basic Info (Tab 1)
                    student.first_name = request.form.get('first_name', '').strip()
                    student.last_name = request.form.get('last_name', '').strip()
                    student.full_name = f"{student.first_name} {student.last_name}"
                    
                    dob_str = request.form.get('date_of_birth', '').strip()
                    if dob_str:
                        student.date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date()
                    
                    # Convert gender from form value to enum value
                    gender_value = request.form.get('gender', '').strip()
                    if gender_value == 'Male':
                        student.gender = 'M'
                    elif gender_value == 'Female':
                        student.gender = 'F'
                    elif gender_value == 'Other':
                        student.gender = 'O'
                    else:
                        student.gender = gender_value  # Already in correct format (M, F, O)
                    
                    student.category = request.form.get('category', 'General').strip()
                    student.blood_group = request.form.get('blood_group', '').strip()
                    student.aadhar_number = request.form.get('aadhar_number', '').strip() or None
                    student.email = request.form.get('email', '').strip() or None
                    student.phone = request.form.get('phone', '').strip()
                    student.address = request.form.get('address', '').strip()
                    student.city = request.form.get('city', '').strip()
                    student.state = request.form.get('state', '').strip()
                    student.pincode = request.form.get('pincode', '').strip()
                    student.father_name = request.form.get('father_name', '').strip()
                    student.mother_name = request.form.get('mother_name', '').strip()
                    student.guardian_phone = request.form.get('guardian_phone', '').strip()
                    student.guardian_email = request.form.get('guardian_email', '').strip() or None

                    # Academic Info updates (Class / Session)
                    new_class_id = request.form.get('class_id', type=int)
                    new_session_id = request.form.get('session_id', type=int)
                    if new_class_id:
                        cls = session_db.query(Class).filter_by(id=new_class_id, tenant_id=school.id, is_active=True).first()
                        if cls:
                            student.class_id = cls.id
                    if new_session_id:
                        sess = session_db.query(AcademicSession).filter_by(id=new_session_id, tenant_id=school.id, is_active=True).first()
                        if sess:
                            student.session_id = sess.id

                    # Roll Number update
                    student.roll_number = request.form.get('roll_number', '').strip() or None
                    
                    # Handle photo upload
                    if 'photo' in request.files:
                        photo = request.files['photo']
                        if photo and photo.filename:
                            upload_dir = os.path.join('akademi', 'static', 'uploads', 'documents', str(school.id), 'students', str(student.admission_number))
                            os.makedirs(upload_dir, exist_ok=True)
                            filename = secure_filename(f"{student.admission_number}_{photo.filename}")
                            filepath = os.path.join(upload_dir, filename)
                            photo.save(filepath)
                            student.photo_url = f"uploads/documents/{school.id}/students/{student.admission_number}/{filename}"
                    
                    # Update Guardian Extended Info (Tab 2)
                    # Delete existing guardians and recreate
                    session_db.query(StudentGuardian).filter_by(student_id=student.id).delete()
                    
                    # Father
                    father_occupation = request.form.get('father_occupation', '').strip()
                    father_income = request.form.get('father_income', '').strip()
                    father_phone_alt = request.form.get('father_phone_alt', '').strip()
                    if father_occupation or father_income or father_phone_alt:
                        father_guardian = StudentGuardian(
                            tenant_id=school.id,
                            student_id=student.id,
                            guardian_type='Father',
                            occupation=father_occupation or None,
                            annual_income=float(father_income) if father_income else None,
                            phone_alternate=father_phone_alt or None
                        )
                        session_db.add(father_guardian)
                    
                    # Mother
                    mother_occupation = request.form.get('mother_occupation', '').strip()
                    mother_income = request.form.get('mother_income', '').strip()
                    mother_phone_alt = request.form.get('mother_phone_alt', '').strip()
                    if mother_occupation or mother_income or mother_phone_alt:
                        mother_guardian = StudentGuardian(
                            tenant_id=school.id,
                            student_id=student.id,
                            guardian_type='Mother',
                            occupation=mother_occupation or None,
                            annual_income=float(mother_income) if mother_income else None,
                            phone_alternate=mother_phone_alt or None
                        )
                        session_db.add(mother_guardian)
                    
                    # Other Guardian
                    other_occupation = request.form.get('other_occupation', '').strip()
                    other_income = request.form.get('other_income', '').strip()
                    other_phone_alt = request.form.get('other_phone_alt', '').strip()
                    if other_occupation or other_income or other_phone_alt:
                        other_guardian = StudentGuardian(
                            tenant_id=school.id,
                            student_id=student.id,
                            guardian_type='Other',
                            occupation=other_occupation or None,
                            annual_income=float(other_income) if other_income else None,
                            phone_alternate=other_phone_alt or None
                        )
                        session_db.add(other_guardian)
                    
                    # Update Medical Info (Tab 3)
                    allergies = request.form.get('allergies', '').strip()
                    medical_conditions = request.form.get('medical_conditions', '').strip()
                    emergency_medication = request.form.get('emergency_medication', '').strip()
                    doctor_name = request.form.get('doctor_name', '').strip()
                    doctor_phone = request.form.get('doctor_phone', '').strip()
                    
                    if student.medical_info:
                        student.medical_info.allergies = allergies or None
                        student.medical_info.medical_conditions = medical_conditions or None
                        student.medical_info.emergency_medication = emergency_medication or None
                        student.medical_info.doctor_name = doctor_name or None
                        student.medical_info.doctor_phone = doctor_phone or None
                    else:
                        medical_info = StudentMedicalInfo(
                            tenant_id=school.id,
                            student_id=student.id,
                            allergies=allergies or None,
                            medical_conditions=medical_conditions or None,
                            emergency_medication=emergency_medication or None,
                            doctor_name=doctor_name or None,
                            doctor_phone=doctor_phone or None
                        )
                        session_db.add(medical_info)
                    
                    # Update Previous Schools (Tab 4)
                    session_db.query(StudentPreviousSchool).filter_by(student_id=student.id).delete()
                    
                    prev_school_names = request.form.getlist('prev_school_name[]')
                    prev_school_classes = request.form.getlist('prev_school_class[]')
                    prev_school_tcs = request.form.getlist('prev_school_tc[]')
                    prev_school_tc_dates = request.form.getlist('prev_school_tc_date[]')
                    prev_school_percentages = request.form.getlist('prev_school_percentage[]')
                    
                    for i, school_name in enumerate(prev_school_names):
                        if school_name.strip():
                            tc_date = None
                            if i < len(prev_school_tc_dates) and prev_school_tc_dates[i]:
                                try:
                                    tc_date = datetime.strptime(prev_school_tc_dates[i], '%Y-%m-%d').date()
                                except:
                                    pass
                            
                            prev_school = StudentPreviousSchool(
                                tenant_id=school.id,
                                student_id=student.id,
                                school_name=school_name.strip(),
                                last_class=prev_school_classes[i].strip() if i < len(prev_school_classes) else None,
                                tc_number=prev_school_tcs[i].strip() if i < len(prev_school_tcs) else None,
                                tc_date=tc_date,
                                last_percentage=float(prev_school_percentages[i]) if i < len(prev_school_percentages) and prev_school_percentages[i] else None
                            )
                            session_db.add(prev_school)
                    
                    # Update Siblings (Tab 4)
                    session_db.query(StudentSibling).filter_by(student_id=student.id).delete()
                    
                    sibling_names = request.form.getlist('sibling_name[]')
                    sibling_classes = request.form.getlist('sibling_class[]')
                    sibling_admissions = request.form.getlist('sibling_admission[]')
                    sibling_same_schools = request.form.getlist('sibling_same_school[]')
                    sibling_other_schools = request.form.getlist('sibling_other_school[]')
                    
                    for i, sibling_name in enumerate(sibling_names):
                        if sibling_name.strip():
                            is_same_school = str(i) in sibling_same_schools or (i < len(sibling_same_schools) and sibling_same_schools[i] == '1')
                            
                            sibling = StudentSibling(
                                tenant_id=school.id,
                                student_id=student.id,
                                sibling_name=sibling_name.strip(),
                                sibling_class=sibling_classes[i].strip() if i < len(sibling_classes) else None,
                                sibling_admission_number=sibling_admissions[i].strip() if i < len(sibling_admissions) else None,
                                is_in_same_school=is_same_school,
                                other_school_name=sibling_other_schools[i].strip() if i < len(sibling_other_schools) else None
                            )
                            session_db.add(sibling)
                    
                    # Handle Document Uploads (Tab 5)
                    doc_types = request.form.getlist('doc_type[]')
                    doc_files = request.files.getlist('doc_file[]')
                    
                    for i, doc_type in enumerate(doc_types):
                        if doc_type and i < len(doc_files) and doc_files[i].filename:
                            doc_file = doc_files[i]
                            upload_dir = os.path.join('akademi', 'static', 'uploads', 'documents', str(school.id), 'students', str(student.admission_number), 'documents')
                            os.makedirs(upload_dir, exist_ok=True)
                            
                            filename = secure_filename(doc_file.filename)
                            filepath = os.path.join(upload_dir, filename)
                            doc_file.save(filepath)
                            
                            doc = StudentDocument(
                                tenant_id=school.id,
                                student_id=student.id,
                                doc_type=doc_type,
                                file_name=filename,
                                file_path=f"uploads/documents/{school.id}/students/{student.admission_number}/documents/{filename}"
                            )
                            session_db.add(doc)
                    
                    session_db.commit()
                    flash('Student profile updated successfully!', 'success')
                    
                    # Return to the same tab
                    return redirect(url_for('school.student_profile_edit', tenant_slug=tenant_slug, id=student.id) + f'?tab={current_tab}')
                    
                except Exception as e:
                    session_db.rollback()
                    logger.error(f"Student profile update error: {e}")
                    flash(f'Error updating profile: {str(e)}', 'error')
                    return redirect(url_for('school.student_profile_edit', tenant_slug=tenant_slug, id=student.id))
            
            # GET request
            current_tab = request.args.get('tab', 0, type=int)
            
            return render_template('akademi/student/edit-student-profile.html',
                                 school=school,
                                 student=student,
                                 classes=classes,
                                 sessions=sessions,
                                 current_tab=current_tab,
                                 current_user=current_user)
        
        except Exception as e:
            logger.error(f"Student profile edit error for {tenant_slug}: {e}")
            flash('Error loading student profile', 'error')
            return redirect(url_for('school.students', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/students/<int:student_id>/documents/<int:doc_id>/delete', methods=['POST'])
    @require_school_auth
    def delete_student_document(tenant_slug, student_id, doc_id):
        """Delete a student document"""
        if current_user.role not in ['school_admin']:
            return jsonify({'error': 'Access denied'}), 403
        
        from student_models import StudentDocument
        import os
        
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'error': 'School not found'}), 404
            
            doc = session_db.query(StudentDocument).filter_by(
                id=doc_id,
                student_id=student_id,
                tenant_id=school.id
            ).first()
            
            if not doc:
                return jsonify({'error': 'Document not found'}), 404
            
            # Delete file from disk
            file_path = os.path.join('akademi', 'static', doc.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)
            
            session_db.delete(doc)
            session_db.commit()
            
            return jsonify({'success': True}), 200
        
        except Exception as e:
            session_db.rollback()
            logger.error(f"Delete student document error: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session_db.close()

    # ===== STUDENT ATTENDANCE ROUTES =====
    
    @school_bp.route('/<tenant_slug>/students/attendance/mark', methods=['GET', 'POST'])
    @require_school_auth
    def student_attendance_mark(tenant_slug):
        """Mark student attendance by class"""
        session_db = get_session()
        try:
            from models import Student, Class, StudentAttendance, StudentAttendanceStatusEnum
            from student_attendance_helpers import mark_student_attendance, get_student_attendance_for_date, check_holidays_and_automark
            from datetime import datetime as dt, date
            from sqlalchemy.orm import joinedload
            
            school = g.current_tenant
            
            # Get selected date and class from query params
            selected_date_str = request.values.get('date', date.today().strftime('%Y-%m-%d'))
            class_id = request.values.get('class_id', type=int)
            
            try:
                selected_date = dt.strptime(selected_date_str, '%Y-%m-%d').date()
            except Exception:
                selected_date = date.today()
            
            if request.method == 'POST':
                # Check if date is a holiday first
                if class_id and check_holidays_and_automark(session_db, school.id, class_id, selected_date):
                    flash('Cannot mark attendance on a holiday', 'error')
                    return redirect(url_for('school.student_attendance_mark', tenant_slug=tenant_slug, 
                                          date=selected_date_str, class_id=class_id))
                
                # Handle bulk attendance marking
                try:
                    marked_count = 0
                    errors = []
                    
                    # Get all form data
                    for key in request.form:
                        if key.startswith('status_'):
                            student_id = int(key.split('_')[1])
                            status_value = request.form[key]
                            
                            # Skip if no status selected
                            if not status_value:
                                continue
                            
                            # Get student's class_id
                            student = session_db.query(Student).get(student_id)
                            if not student:
                                continue
                            
                            # Get check-in and check-out times
                            check_in_str = request.form.get(f'check_in_{student_id}', '').strip()
                            check_out_str = request.form.get(f'check_out_{student_id}', '').strip()
                            remarks = request.form.get(f'remarks_{student_id}', '').strip()
                            
                            # Convert times if provided
                            check_in = None
                            check_out = None
                            
                            if check_in_str:
                                try:
                                    check_in = dt.strptime(f"{selected_date} {check_in_str}", '%Y-%m-%d %H:%M')
                                except:
                                    pass
                            
                            if check_out_str:
                                try:
                                    check_out = dt.strptime(f"{selected_date} {check_out_str}", '%Y-%m-%d %H:%M')
                                except:
                                    pass
                            
                            # Get status enum
                            status = StudentAttendanceStatusEnum(status_value)
                            
                            # Mark attendance
                            success, message, _ = mark_student_attendance(
                                session_db, student_id, student.class_id, school.id, selected_date,
                                status, check_in, check_out, remarks, current_user.id
                            )
                            
                            if success:
                                marked_count += 1
                            else:
                                errors.append(f"Student ID {student_id}: {message}")
                    
                    if marked_count > 0:
                        flash(f'Attendance marked for {marked_count} student(s)', 'success')
                    
                    if errors:
                        for error in errors[:5]:  # Show first 5 errors
                            flash(error, 'error')
                    
                    return redirect(url_for('school.student_attendance_mark', tenant_slug=tenant_slug, 
                                          date=selected_date_str, class_id=class_id))
                    
                except Exception as e:
                    logger.error(f"Bulk student attendance error: {e}")
                    flash(f'Error marking attendance: {str(e)}', 'error')
            
            # Fetch all classes
            classes = session_db.query(Class).filter_by(
                tenant_id=school.id,
                is_active=True
            ).order_by(Class.class_name, Class.section).all()
            
            # Fetch students for selected class
            students = []
            if class_id:
                students = session_db.query(Student).options(
                    joinedload(Student.student_class)
                ).filter_by(
                    tenant_id=school.id,
                    class_id=class_id
                ).order_by(Student.roll_number, Student.full_name).all()
            
            # Fetch existing attendance for selected date and class
            attendance_dict = {}
            if class_id:
                attendance_dict = get_student_attendance_for_date(session_db, school.id, class_id, selected_date)
            
            # Check if it's a holiday
            is_holiday = False
            if class_id:
                is_holiday = check_holidays_and_automark(session_db, school.id, class_id, selected_date)
            
            context = {
                'school': school,
                'classes': classes,
                'selected_class_id': class_id,
                'students': students,
                'selected_date': selected_date,
                'attendance_dict': attendance_dict,
                'status_enum': StudentAttendanceStatusEnum,
                'today': date.today(),
                'is_holiday': is_holiday
            }
            
            return render_template('akademi/student/student_attendance_mark.html', **context)
            
        except Exception as e:
            logger.error(f"Student attendance error: {e}")
            flash('Error loading attendance page', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/students/attendance/calendar')
    @require_school_auth
    def student_attendance_calendar(tenant_slug):
        """Calendar view of student attendance by class"""
        session_db = get_session()
        try:
            from models import Student, Class, StudentAttendanceSummary
            from datetime import datetime as dt
            from calendar import monthrange
            from sqlalchemy.orm import joinedload
            
            school = g.current_tenant
            
            # Get month, year and class
            month = request.args.get('month', dt.now().month, type=int)
            year = request.args.get('year', dt.now().year, type=int)
            class_id = request.args.get('class_id', type=int)
            
            # Validate inputs
            if not (1 <= month <= 12):
                month = dt.now().month
                flash('Invalid month, showing current month', 'warning')
            
            # Fetch all classes
            classes = session_db.query(Class).filter_by(
                tenant_id=school.id,
                is_active=True
            ).order_by(Class.class_name, Class.section).all()
            
            # Fetch summaries for selected class
            summaries = []
            if class_id:
                summaries = session_db.query(StudentAttendanceSummary).options(
                    joinedload(StudentAttendanceSummary.student)
                ).filter(
                    StudentAttendanceSummary.class_id == class_id,
                    StudentAttendanceSummary.month == month,
                    StudentAttendanceSummary.year == year,
                    StudentAttendanceSummary.tenant_id == school.id
                ).all()
            
            # Calculate class average
            class_average = 0
            if summaries:
                total_percentage = sum(float(s.attendance_percentage) for s in summaries)
                class_average = round(total_percentage / len(summaries), 2)
            
            context = {
                'school': school,
                'classes': classes,
                'selected_class_id': class_id,
                'summaries': summaries,
                'month': month,
                'year': year,
                'month_name': dt(year, month, 1).strftime('%B'),
                'class_average': class_average,
                'current_month': dt.now().month,
                'current_year': dt.now().year
            }
            
            return render_template('akademi/student/student_attendance_calendar.html', **context)
            
        except Exception as e:
            logger.error(f"Student attendance calendar error: {e}")
            flash('Error loading calendar', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/students/<int:student_id>/attendance/history')
    @require_school_auth
    def student_attendance_history(tenant_slug, student_id):
        """Individual student attendance history"""
        session_db = get_session()
        try:
            from models import Student, StudentAttendance
            from student_attendance_helpers import calculate_student_attendance_stats, get_student_monthly_calendar
            from datetime import datetime as dt
            from sqlalchemy.orm import joinedload
            
            school = g.current_tenant
            
            # Get month and year
            month = request.args.get('month', dt.now().month, type=int)
            year = request.args.get('year', dt.now().year, type=int)
            
            # Fetch student
            student = session_db.query(Student).options(
                joinedload(Student.student_class)
            ).filter_by(
                id=student_id,
                tenant_id=school.id
            ).first()
            
            if not student:
                flash('Student not found', 'error')
                return redirect(url_for('school.students', tenant_slug=tenant_slug))
            
            # Get monthly records
            calendar_data = get_student_monthly_calendar(session_db, student_id, month, year)
            
            # Calculate stats
            stats = calculate_student_attendance_stats(session_db, student_id, month, year)
            
            # Add parse_date filter for template
            def parse_date(date_str):
                try:
                    return dt.strptime(date_str, '%Y-%m-%d')
                except:
                    return None
            
            current_app.jinja_env.filters['parse_date'] = parse_date
            
            context = {
                'school': school,
                'student': student,
                'calendar_data': calendar_data,
                'stats': stats,
                'month': month,
                'year': year,
                'month_name': dt(year, month, 1).strftime('%B')
            }
            
            return render_template('akademi/student/student_attendance_individual.html', **context)
            
        except Exception as e:
            logger.error(f"Student attendance history error: {e}")
            flash('Error loading attendance history', 'error')
            return redirect(url_for('school.students', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/students/attendance/<int:attendance_id>/delete', methods=['POST'])
    @require_school_auth
    def delete_student_attendance(tenant_slug, attendance_id):
        """Delete a student attendance record"""
        session_db = get_session()
        try:
            from models import StudentAttendance
            from student_attendance_helpers import update_student_attendance_summary
            
            school = g.current_tenant
            
            # Fetch attendance record
            attendance = session_db.query(StudentAttendance).filter_by(
                id=attendance_id,
                tenant_id=school.id
            ).first()
            
            if not attendance:
                flash('Attendance record not found', 'error')
                return redirect(request.referrer or url_for('school.dashboard', tenant_slug=tenant_slug))
            
            # Store details for summary update
            student_id = attendance.student_id
            class_id = attendance.class_id
            month = attendance.attendance_date.month
            year = attendance.attendance_date.year
            
            # Delete record
            session_db.delete(attendance)
            session_db.commit()
            
            # Update summary
            update_student_attendance_summary(session_db, student_id, class_id, school.id, month, year)
            
            flash('Attendance record deleted successfully', 'success')
            return redirect(request.referrer or url_for('school.student_attendance_mark', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Error deleting attendance: {e}")
            flash('Error deleting attendance record', 'error')
            return redirect(request.referrer or url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/students/holidays', methods=['GET', 'POST'])
    @require_school_auth
    def student_holidays(tenant_slug):
        """Manage student holidays"""
        session_db = get_session()
        try:
            from models import StudentHoliday, Class, HolidayTypeEnum
            from datetime import datetime as dt
            
            school = g.current_tenant
            
            if request.method == 'POST':
                try:
                    # Add new holiday
                    start_date_str = request.form.get('start_date')
                    end_date_str = request.form.get('end_date')
                    holiday_name = request.form.get('holiday_name')
                    holiday_type = request.form.get('holiday_type')
                    class_id = request.form.get('class_id', type=int)
                    description = request.form.get('description', '')
                    
                    start_date = dt.strptime(start_date_str, '%Y-%m-%d').date()
                    end_date = dt.strptime(end_date_str, '%Y-%m-%d').date()
                    
                    # Validate date range
                    if end_date < start_date:
                        flash('End date cannot be before start date', 'error')
                        return redirect(url_for('school.student_holidays', tenant_slug=tenant_slug))
                    
                    new_holiday = StudentHoliday(
                        tenant_id=school.id,
                        class_id=class_id if class_id else None,
                        start_date=start_date,
                        end_date=end_date,
                        holiday_name=holiday_name,
                        holiday_type=HolidayTypeEnum(holiday_type),
                        description=description,
                        created_by=current_user.id
                    )
                    
                    session_db.add(new_holiday)
                    session_db.commit()
                    
                    flash('Holiday added successfully', 'success')
                    return redirect(url_for('school.student_holidays', tenant_slug=tenant_slug))
                    
                except Exception as e:
                    logger.error(f"Error adding holiday: {e}")
                    flash(f'Error adding holiday: {str(e)}', 'error')
            
            # Fetch all holidays
            year = request.args.get('year', dt.now().year, type=int)
            
            holidays = session_db.query(StudentHoliday).filter(
                StudentHoliday.tenant_id == school.id,
                extract('year', StudentHoliday.start_date) == year
            ).order_by(StudentHoliday.start_date).all()
            
            # Fetch all classes
            classes = session_db.query(Class).filter_by(
                tenant_id=school.id,
                is_active=True
            ).order_by(Class.class_name, Class.section).all()
            
            context = {
                'school': school,
                'holidays': holidays,
                'classes': classes,
                'year': year,
                'holiday_types': HolidayTypeEnum,
                'current_year': dt.now().year
            }
            
            return render_template('akademi/student/student_holidays.html', **context)
            
        except Exception as e:
            logger.error(f"Holidays management error: {e}")
            flash('Error loading holidays', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/students/holidays/<int:holiday_id>/delete', methods=['POST'])
    @require_school_auth
    def delete_student_holiday(tenant_slug, holiday_id):
        """Delete a holiday"""
        session_db = get_session()
        try:
            from models import StudentHoliday
            
            school = g.current_tenant
            
            holiday = session_db.query(StudentHoliday).filter_by(
                id=holiday_id,
                tenant_id=school.id
            ).first()
            
            if holiday:
                session_db.delete(holiday)
                session_db.commit()
                flash('Holiday deleted successfully', 'success')
            else:
                flash('Holiday not found', 'error')
                
        except Exception as e:
            logger.error(f"Error deleting holiday: {e}")
            flash('Error deleting holiday', 'error')
        finally:
            session_db.close()
        
        return redirect(url_for('school.student_holidays', tenant_slug=tenant_slug))
    
    # ===== STUDENT LEAVE MANAGEMENT (ADMIN) ROUTES =====
    
    @school_bp.route('/<tenant_slug>/students/leaves')
    @require_school_auth
    def student_leaves_admin(tenant_slug):
        """Admin view for student leave management"""
        session_db = get_session()
        try:
            from leave_models import StudentLeave, StudentLeaveStatusEnum
            from models import Class
            from sqlalchemy.orm import joinedload
            
            school = g.current_tenant
            
            # Get filter parameters
            status_filter = request.args.get('status')
            class_id = request.args.get('class_id', type=int)
            from_date_str = request.args.get('from_date')
            to_date_str = request.args.get('to_date')
            
            # Base query
            query = session_db.query(StudentLeave).filter_by(tenant_id=school.id).options(
                joinedload(StudentLeave.student),
                joinedload(StudentLeave.student_class),
                joinedload(StudentLeave.reviewer)
            )
            
            # Apply filters
            if status_filter:
                query = query.filter(StudentLeave.status == StudentLeaveStatusEnum(status_filter))
            
            if class_id:
                query = query.filter(StudentLeave.class_id == class_id)
            
            if from_date_str:
                from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
                query = query.filter(StudentLeave.from_date >= from_date)
            
            if to_date_str:
                to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
                query = query.filter(StudentLeave.to_date <= to_date)
            
            # Order by latest first
            leaves = query.order_by(StudentLeave.applied_date.desc()).all()
            
            # Get all classes for filter dropdown
            classes = session_db.query(Class).filter_by(tenant_id=school.id).order_by(Class.class_name, Class.section).all()
            
            # Calculate statistics
            stats = {
                'pending': session_db.query(StudentLeave).filter_by(
                    tenant_id=school.id, 
                    status=StudentLeaveStatusEnum.PENDING
                ).count(),
                'approved': session_db.query(StudentLeave).filter_by(
                    tenant_id=school.id, 
                    status=StudentLeaveStatusEnum.APPROVED
                ).count(),
                'rejected': session_db.query(StudentLeave).filter_by(
                    tenant_id=school.id, 
                    status=StudentLeaveStatusEnum.REJECTED
                ).count(),
                'total': session_db.query(StudentLeave).filter_by(tenant_id=school.id).count()
            }
            
            return render_template('akademi/student/student_leaves_list.html',
                                 school=school,
                                 leaves=leaves,
                                 classes=classes,
                                 stats=stats,
                                 current_user=current_user)
                                 
        except Exception as e:
            logger.error(f"Student leaves admin error for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error loading student leaves', 'error')
            return redirect(url_for('school.dashboard', tenant_slug=tenant_slug))
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/students/leaves/<int:leave_id>')
    @require_school_auth
    def student_leave_details_admin(tenant_slug, leave_id):
        """View detailed information about a leave application"""
        session_db = get_session()
        try:
            from leave_models import StudentLeave
            from sqlalchemy.orm import joinedload
            
            school = g.current_tenant
            
            leave = session_db.query(StudentLeave).filter_by(
                id=leave_id,
                tenant_id=school.id
            ).options(
                joinedload(StudentLeave.student),
                joinedload(StudentLeave.student_class),
                joinedload(StudentLeave.reviewer)
            ).first()
            
            if not leave:
                return '<div class="alert alert-danger">Leave application not found</div>', 404
            
            return render_template('akademi/student/student_leave_details.html',
                                 school=school,
                                 leave=leave,
                                 current_user=current_user)
                                 
        except Exception as e:
            logger.error(f"Student leave details error for {tenant_slug}: {e}")
            return '<div class="alert alert-danger">Error loading leave details</div>', 500
        finally:
            session_db.close()
    
    @school_bp.route('/<tenant_slug>/students/leaves/<int:leave_id>/approve', methods=['POST'])
    @require_school_auth
    def student_leave_approve_admin(tenant_slug, leave_id):
        """Approve a student leave application"""
        session_db = get_session()
        try:
            from student_leave_helpers import approve_leave
            
            school = g.current_tenant
            
            # Approve leave using helper function
            success, message = approve_leave(
                db_session=session_db,
                leave_id=leave_id,
                reviewer_id=current_user.id,
                reviewer_type='School Admin',
                remarks=None
            )
            
            if success:
                flash(message, 'success')
            else:
                flash(message, 'error')
            
        except Exception as e:
            logger.error(f"Error approving leave for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error approving leave', 'error')
            session_db.rollback()
        finally:
            session_db.close()
        
        return redirect(url_for('school.student_leaves_admin', tenant_slug=tenant_slug))
    
    @school_bp.route('/<tenant_slug>/students/leaves/<int:leave_id>/reject', methods=['POST'])
    @require_school_auth
    def student_leave_reject_admin(tenant_slug, leave_id):
        """Reject a student leave application"""
        session_db = get_session()
        try:
            from student_leave_helpers import reject_leave
            
            school = g.current_tenant
            remarks = request.form.get('remarks', '')
            
            if not remarks:
                flash('Rejection reason is required', 'error')
                return redirect(url_for('school.student_leaves_admin', tenant_slug=tenant_slug))
            
            # Reject leave using helper function
            success, message = reject_leave(
                db_session=session_db,
                leave_id=leave_id,
                reviewer_id=current_user.id,
                reviewer_type='School Admin',
                remarks=remarks
            )
            
            if success:
                flash(message, 'success')
            else:
                flash(message, 'error')
            
        except Exception as e:
            logger.error(f"Error rejecting leave for {tenant_slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            flash('Error rejecting leave', 'error')
            session_db.rollback()
        finally:
            session_db.close()
        
        return redirect(url_for('school.student_leaves_admin', tenant_slug=tenant_slug))
    
 # ===== STUDENT PROMOTION ROUTES =====
    
    @school_bp.route('/<tenant_slug>/students/promotion', methods=['GET'])
    @require_school_auth
    def student_promotion(tenant_slug):
        """Student promotion wizard - promote students to next class/session"""
        session_db = get_session()
        try:
            from models import AcademicSession, Class, Student, StudentStatusEnum
            
            school = g.current_tenant
            
            # Get all sessions and classes
            sessions = session_db.query(AcademicSession).filter_by(
                tenant_id=school.id, is_active=True
            ).order_by(AcademicSession.start_date.desc()).all()
            
            classes = session_db.query(Class).filter_by(
                tenant_id=school.id, is_active=True
            ).order_by(Class.class_name, Class.section).all()
            
            # Get source session and class from query params
            source_session_id = request.args.get('source_session', type=int)
            source_class_id = request.args.get('source_class', type=int)
            
            students = []
            source_session = None
            source_class = None
            
            if source_session_id and source_class_id:
                source_session = session_db.query(AcademicSession).filter_by(
                    id=source_session_id, tenant_id=school.id
                ).first()
                source_class = session_db.query(Class).filter_by(
                    id=source_class_id, tenant_id=school.id
                ).first()
                
                if source_session and source_class:
                    students = session_db.query(Student).filter_by(
                        tenant_id=school.id,
                        session_id=source_session_id,
                        class_id=source_class_id,
                        status=StudentStatusEnum.ACTIVE
                    ).order_by(Student.roll_number, Student.full_name).all()
            
            return render_template('akademi/student/student_promotion.html',
                                 school=school,
                                 sessions=sessions,
                                 classes=classes,
                                 students=students,
                                 source_session=source_session,
                                 source_class=source_class,
                                 source_session_id=source_session_id,
                                 source_class_id=source_class_id)
                                 
        except Exception as e:
            logger.error(f"Student promotion error: {e}")
            flash(f'Error loading promotion page: {str(e)}', 'error')
            return redirect(url_for('school.students', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/students/promotion/execute', methods=['POST'])
    @require_school_auth
    def execute_student_promotion(tenant_slug):
        """Execute student promotion"""
        session_db = get_session()
        try:
            from models import AcademicSession, Class, Student, StudentStatusEnum
            
            school = g.current_tenant
            
            # Get form data
            source_session_id = request.form.get('source_session_id', type=int)
            source_class_id = request.form.get('source_class_id', type=int)
            target_session_id = request.form.get('target_session_id', type=int)
            target_class_id = request.form.get('target_class_id', type=int)
            student_ids = request.form.getlist('student_ids')
            failed_student_ids = request.form.getlist('failed_student_ids')
            action = request.form.get('action', 'promote')  # promote, retain, or mark_left
            
            if not all([source_session_id, target_session_id, target_class_id]):
                flash('Please select source session, target session, and target class', 'error')
                return redirect(url_for('school.student_promotion', tenant_slug=tenant_slug))
            
            if not student_ids and action == 'promote':
                flash('Please select at least one student to promote', 'error')
                return redirect(url_for('school.student_promotion', tenant_slug=tenant_slug,
                                      source_session=source_session_id, source_class=source_class_id))
            
            # Validate sessions and classes exist
            target_session = session_db.query(AcademicSession).filter_by(
                id=target_session_id, tenant_id=school.id
            ).first()
            target_class = session_db.query(Class).filter_by(
                id=target_class_id, tenant_id=school.id
            ).first()
            
            if not target_session or not target_class:
                flash('Invalid target session or class', 'error')
                return redirect(url_for('school.student_promotion', tenant_slug=tenant_slug))
            
            promoted_count = 0
            retained_count = 0
            failed_count = 0
            
            # Process promotions
            if student_ids:
                for student_id in student_ids:
                    student = session_db.query(Student).filter_by(
                        id=int(student_id), tenant_id=school.id
                    ).first()
                    if student:
                        student.session_id = target_session_id
                        student.class_id = target_class_id
                        student.roll_number = None  # Reset roll number for new class
                        promoted_count += 1
            
            # Process failed/retained students (keep in same class, move to new session)
            if failed_student_ids:
                retain_class_id = request.form.get('retain_class_id', type=int) or source_class_id
                for student_id in failed_student_ids:
                    student = session_db.query(Student).filter_by(
                        id=int(student_id), tenant_id=school.id
                    ).first()
                    if student:
                        student.session_id = target_session_id
                        student.class_id = retain_class_id  # Same class or specified retain class
                        student.roll_number = None
                        retained_count += 1
            
            session_db.commit()
            
            message_parts = []
            if promoted_count:
                message_parts.append(f'{promoted_count} student(s) promoted to {target_class.class_name}-{target_class.section}')
            if retained_count:
                message_parts.append(f'{retained_count} student(s) retained')
            
            if message_parts:
                flash(' | '.join(message_parts), 'success')
            else:
                flash('No students were updated', 'warning')
                
            return redirect(url_for('school.student_promotion', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Execute promotion error: {e}")
            flash(f'Error executing promotion: {str(e)}', 'error')
            return redirect(url_for('school.student_promotion', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/students/promotion/bulk', methods=['POST'])
    @require_school_auth
    def bulk_promote_class(tenant_slug):
        """Bulk promote entire class"""
        session_db = get_session()
        try:
            from models import AcademicSession, Class, Student, StudentStatusEnum
            
            school = g.current_tenant
            
            source_session_id = request.form.get('source_session_id', type=int)
            source_class_id = request.form.get('source_class_id', type=int)
            target_session_id = request.form.get('target_session_id', type=int)
            target_class_id = request.form.get('target_class_id', type=int)
            
            if not all([source_session_id, source_class_id, target_session_id, target_class_id]):
                flash('Please provide all required fields', 'error')
                return redirect(url_for('school.student_promotion', tenant_slug=tenant_slug))
            
            # Get all active students in source class/session
            students = session_db.query(Student).filter_by(
                tenant_id=school.id,
                session_id=source_session_id,
                class_id=source_class_id,
                status=StudentStatusEnum.ACTIVE
            ).all()
            
            target_class = session_db.query(Class).filter_by(
                id=target_class_id, tenant_id=school.id
            ).first()
            
            count = 0
            for student in students:
                student.session_id = target_session_id
                student.class_id = target_class_id
                student.roll_number = None  # Reset roll numbers
                count += 1
            
            session_db.commit()
            
            flash(f'Successfully promoted {count} students to {target_class.class_name}-{target_class.section}!', 'success')
            return redirect(url_for('school.student_promotion', tenant_slug=tenant_slug))
            
        except Exception as e:
            session_db.rollback()
            logger.error(f"Bulk promotion error: {e}")
            flash(f'Error in bulk promotion: {str(e)}', 'error')
            return redirect(url_for('school.student_promotion', tenant_slug=tenant_slug))
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/students/promotion/summary')
    @require_school_auth
    def promotion_summary(tenant_slug):
        """Get promotion summary as JSON for AJAX"""
        session_db = get_session()
        try:
            from models import AcademicSession, Class, Student, StudentStatusEnum
            from sqlalchemy import func
            
            school = g.current_tenant
            session_id = request.args.get('session_id', type=int)
            
            if not session_id:
                return jsonify({'error': 'Session ID required'}), 400
            
            # Get class-wise student counts
            class_counts = session_db.query(
                Class.id,
                Class.class_name,
                Class.section,
                func.count(Student.id).label('student_count')
            ).outerjoin(
                Student, 
                (Student.class_id == Class.id) & 
                (Student.session_id == session_id) &
                (Student.status == StudentStatusEnum.ACTIVE)
            ).filter(
                Class.tenant_id == school.id,
                Class.is_active == True
            ).group_by(Class.id, Class.class_name, Class.section).order_by(
                Class.class_name, Class.section
            ).all()
            
            result = [{
                'id': c.id,
                'class_name': c.class_name,
                'section': c.section,
                'display': f'{c.class_name}-{c.section}',
                'student_count': c.student_count
            } for c in class_counts]
            
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Promotion summary error: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            session_db.close()

    @school_bp.route('/<tenant_slug>/students/<int:student_id>/change-status', methods=['POST'])
    @require_school_auth
    def change_student_status(tenant_slug, student_id):
        """Change student status (Transfer, Leave, Graduate) with proper cleanup"""
        from flask_login import current_user
        
        if current_user.role not in ['school_admin']:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        
        session_db = get_session()
        try:
            school = session_db.query(Tenant).filter_by(slug=tenant_slug).first()
            if not school:
                return jsonify({'success': False, 'message': 'School not found'}), 404
            
            # Get student
            student = session_db.query(Student).filter_by(
                id=student_id,
                tenant_id=school.id
            ).first()
            
            if not student:
                return jsonify({'success': False, 'message': 'Student not found'}), 404
            
            # Get requested status
            new_status = request.form.get('new_status') or request.json.get('new_status') if request.is_json else request.form.get('new_status')
            
            if not new_status:
                return jsonify({'success': False, 'message': 'New status is required'}), 400
            
            valid_statuses = ['TRANSFERRED', 'LEFT', 'GRADUATED', 'ACTIVE']
            if new_status.upper() not in valid_statuses:
                return jsonify({'success': False, 'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
            
            # If changing to ACTIVE (reactivating)
            if new_status.upper() == 'ACTIVE':
                from models import StudentStatusEnum
                student.status = StudentStatusEnum.ACTIVE
                session_db.commit()
                return jsonify({
                    'success': True,
                    'message': f'Student "{student.full_name}" has been reactivated.',
                    'details': ['Status changed to Active']
                })
            
            # For departure statuses, use the handler
            from student_departure_handler import handle_student_departure
            
            result = handle_student_departure(
                session=session_db,
                student_id=student_id,
                tenant_id=school.id,
                departure_type=new_status.upper()
            )
            
            if result['success']:
                session_db.commit()
                return jsonify(result)
            else:
                session_db.rollback()
                return jsonify(result), 400
                
        except Exception as e:
            session_db.rollback()
            logger.error(f"Change student status error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({'success': False, 'message': str(e)}), 500
        finally:
            session_db.close()
