"""
Fee Management Routes for School Admin Portal
Handles all fee-related operations including structure management, payments, receipts, and analytics
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, g, send_file, abort
from functools import wraps
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import joinedload
from db_single import get_session
from models import Tenant, Student, Class, AcademicSession, StudentStatusEnum
from fee_models import (
    FeeCategory, FeeStructure, FeeStructureDetail, StudentFee,
    StudentFeeConcession, FeeReceipt, FeeFine, FeeInstallment, FeeCollectionSummary,
    FeeStatusEnum, PaymentModeEnum, PaymentStatusEnum, ConcessionTypeEnum,
    ConcessionModeEnum, FineTypeEnum, InstallmentStatusEnum
)
from fee_helpers import (
    generate_receipt_number, calculate_student_fee_total, assign_fee_to_student,
    bulk_assign_fees_to_class, process_fee_payment, apply_late_payment_fine,
    waive_fine, apply_concession_to_student_fee, apply_bulk_concessions_to_category,
    get_fee_collection_summary, get_outstanding_fees_summary, get_class_wise_collection,
    get_defaulter_list, get_student_fee_details, auto_apply_late_fines
)
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch


def create_fee_routes(school_blueprint, require_school_auth):
    """Add fee management routes to school blueprint"""
    
    # ===== FEE CATEGORY MANAGEMENT =====
    
    @school_blueprint.route('/<tenant_slug>/fee-categories')
    @require_school_auth
    def fee_categories(tenant_slug):
        """List all fee categories"""
        session = get_session()
        tenant_id = g.current_tenant.id
        
        categories = session.query(FeeCategory).filter_by(
            tenant_id=tenant_id
        ).order_by(FeeCategory.display_order, FeeCategory.category_name).all()
        
        return render_template('akademi/fees/fee_categories.html', categories=categories, school=g.current_tenant)
    
    
    @school_blueprint.route('/<tenant_slug>/fee-categories/add', methods=['GET', 'POST'])
    @require_school_auth
    def add_fee_category(tenant_slug):
        """Add new fee category"""
        if request.method == 'POST':
            session = get_session()
            tenant_id = g.current_tenant.id
            
            category = FeeCategory(
                tenant_id=tenant_id,
                category_name=request.form['category_name'],
                category_code=request.form['category_code'].upper(),
                description=request.form.get('description'),
                is_mandatory=request.form.get('is_mandatory') == 'on',
                display_order=int(request.form.get('display_order', 0))
            )
            
            try:
                session.add(category)
                session.commit()
                flash('Fee category added successfully', 'success')
                return redirect(url_for('school.fee_categories', tenant_slug=g.current_tenant.slug))
            except Exception as e:
                session.rollback()
                flash(f'Error adding fee category: {str(e)}', 'error')
        
        return render_template('akademi/fees/add_fee_category.html', school=g.current_tenant)
    
    
    @school_blueprint.route('/<tenant_slug>/fee-categories/<int:category_id>/edit', methods=['GET', 'POST'])
    @require_school_auth
    def edit_fee_category(tenant_slug, category_id):
        """Edit fee category"""
        session = get_session()
        tenant_id = g.current_tenant.id
        
        category = session.query(FeeCategory).filter_by(
            id=category_id, tenant_id=tenant_id
        ).first()
        
        if not category:
            abort(404)
        
        if request.method == 'POST':
            category.category_name = request.form['category_name']
            category.category_code = request.form['category_code'].upper()
            category.description = request.form.get('description')
            category.is_mandatory = request.form.get('is_mandatory') == 'on'
            category.display_order = int(request.form.get('display_order', 0))
            
            try:
                session.commit()
                flash('Fee category updated successfully', 'success')
                return redirect(url_for('school.fee_categories', tenant_slug=g.current_tenant.slug))
            except Exception as e:
                session.rollback()
                flash(f'Error updating fee category: {str(e)}', 'error')
        
        return render_template('akademi/fees/edit_fee_category.html', category=category, school=g.current_tenant)
    
    
    @school_blueprint.route('/<tenant_slug>/fee-categories/<int:category_id>/toggle-status', methods=['POST'])
    @require_school_auth
    def toggle_fee_category_status(tenant_slug, category_id):
        """Toggle fee category active status"""
        session = get_session()
        tenant_id = g.current_tenant.id
        
        category = session.query(FeeCategory).filter_by(
            id=category_id, tenant_id=tenant_id
        ).first()
        
        if not category:
            abort(404)
        
        category.is_active = not category.is_active
        session.commit()
        
        status = "activated" if category.is_active else "deactivated"
        flash(f'Fee category {status} successfully', 'success')
        return redirect(url_for('school.fee_categories', tenant_slug=g.current_tenant.slug))


    @school_blueprint.route('/<tenant_slug>/fee-categories/<int:category_id>/delete', methods=['POST'])
    @require_school_auth
    def delete_fee_category(tenant_slug, category_id):
        """Delete a fee category if not in use by any fee structure details"""
        session = get_session()
        tenant_id = g.current_tenant.id

        category = session.query(FeeCategory).filter_by(id=category_id, tenant_id=tenant_id).first()
        if not category:
            abort(404)

        # Prevent deletion if category is referenced in any fee structure details
        details_count = session.query(FeeStructureDetail).filter_by(fee_category_id=category_id).count()
        if details_count > 0:
            flash('Cannot delete category: it is used in one or more fee structures. Remove those references first.', 'error')
            return redirect(url_for('school.fee_categories', tenant_slug=g.current_tenant.slug))

        try:
            session.delete(category)
            session.commit()
            flash('Fee category deleted successfully', 'success')
        except Exception as e:
            session.rollback()
            flash(f'Error deleting fee category: {str(e)}', 'error')

        return redirect(url_for('school.fee_categories', tenant_slug=g.current_tenant.slug))
    
    
    # ===== FEE STRUCTURE MANAGEMENT =====
    
    @school_blueprint.route('/<tenant_slug>/fee-structures')
    @require_school_auth
    def fee_structures(tenant_slug):
        """List all fee structures"""
        session = get_session()
        tenant_id = g.current_tenant.id
        
        session_id = request.args.get('session_id', type=int)
        class_id = request.args.get('class_id', type=int)
        
        query = session.query(FeeStructure).filter_by(tenant_id=tenant_id)
        
        if session_id:
            query = query.filter_by(session_id=session_id)
        if class_id:
            query = query.filter_by(class_id=class_id)
        
        structures = query.order_by(desc(FeeStructure.created_at)).all()
        
        # Get sessions and classes for filters
        sessions = session.query(AcademicSession).filter_by(tenant_id=tenant_id).all()
        classes = session.query(Class).filter_by(tenant_id=tenant_id).all()
        # Get active fee categories so the Add Structure modal can populate the select
        categories = session.query(FeeCategory).filter_by(tenant_id=tenant_id, is_active=True).order_by(FeeCategory.display_order, FeeCategory.category_name).all()
        
        return render_template('akademi/fees/fee_structures.html', 
                     structures=structures,
                     sessions=sessions,
                     classes=classes,
                     categories=categories,
                     selected_session=session_id,
                     selected_class=class_id,
                     school=g.current_tenant)    
    @school_blueprint.route('/<tenant_slug>/fee-structures/add', methods=['GET', 'POST'])
    @require_school_auth
    def add_fee_structure(tenant_slug):
        """Add new fee structure"""
        session = get_session()
        tenant_id = g.current_tenant.id
        
        if request.method == 'POST':
            # Create fee structure
            fee_structure = FeeStructure(
                tenant_id=tenant_id,
                session_id=int(request.form['session_id']),
                class_id=int(request.form['class_id']),
                structure_name=request.form['structure_name'],
                description=request.form.get('description'),
                valid_from=datetime.strptime(request.form['valid_from'], '%Y-%m-%d').date(),
                valid_to=datetime.strptime(request.form['valid_to'], '%Y-%m-%d').date() if request.form.get('valid_to') else None,
                created_by=g.current_user.id if hasattr(g, 'current_user') else None
            )
            
            try:
                session.add(fee_structure)
                session.flush()
                
                # Add fee structure details
                category_ids = request.form.getlist('category_id[]')
                amounts = request.form.getlist('amount[]')
                due_dates = request.form.getlist('due_date[]')
                installment_numbers = request.form.getlist('installment_number[]')
                
                for i, category_id in enumerate(category_ids):
                    if category_id and amounts[i]:
                        detail = FeeStructureDetail(
                            tenant_id=tenant_id,
                            fee_structure_id=fee_structure.id,
                            fee_category_id=int(category_id),
                            amount=Decimal(amounts[i]),
                            due_date=datetime.strptime(due_dates[i], '%Y-%m-%d').date() if due_dates[i] else None,
                            installment_number=int(installment_numbers[i]) if installment_numbers[i] else 1
                        )
                        session.add(detail)
                
                session.commit()
                flash('Fee structure created successfully', 'success')
                return redirect(url_for('school.fee_structures', tenant_slug=g.current_tenant.slug))
            
            except Exception as e:
                session.rollback()
                flash(f'Error creating fee structure: {str(e)}', 'error')
        
        # GET request - show form
        sessions = session.query(AcademicSession).filter_by(tenant_id=tenant_id).all()
        classes = session.query(Class).filter_by(tenant_id=tenant_id).all()
        categories = session.query(FeeCategory).filter_by(tenant_id=tenant_id, is_active=True).all()
        
        return render_template('akademi/fees/add_fee_structure.html', 
                             sessions=sessions,
                             classes=classes,
                             categories=categories,
                             school=g.current_tenant)    
    @school_blueprint.route('/<tenant_slug>/fee-structures/<int:structure_id>')
    @require_school_auth
    def view_fee_structure(tenant_slug, structure_id):
        """View fee structure details"""
        session = get_session()
        tenant_id = g.current_tenant.id
        
        structure = session.query(FeeStructure).filter_by(
            id=structure_id, tenant_id=tenant_id
        ).first()
        
        if not structure:
            abort(404)
        
        details = session.query(FeeStructureDetail).options(
            joinedload(FeeStructureDetail.category)
        ).filter_by(
            fee_structure_id=structure_id
        ).order_by(FeeStructureDetail.installment_number, FeeStructureDetail.id).all()
        
        total_amount = sum(float(d.amount) for d in details)
        
        return render_template('akademi/fees/view_fee_structure.html', 
                             structure=structure,
                             details=details,
                             total_amount=total_amount,
                             school=g.current_tenant)
    
    
    @school_blueprint.route('/<tenant_slug>/fee-structures/<int:structure_id>/assign', methods=['GET', 'POST'])
    @require_school_auth
    def assign_fee_structure(tenant_slug, structure_id):
        """Assign fee structure to students"""
        db_session = get_session()
        tenant_id = g.current_tenant.id
        
        structure = db_session.query(FeeStructure).filter_by(
            id=structure_id, tenant_id=tenant_id
        ).first()
        
        if not structure:
            abort(404)
        
        if request.method == 'POST':
            assignment_type = request.form.get('assignment_type')
            user_id = g.current_user.id if hasattr(g, 'current_user') else None
            
            try:
                # Support assigning to a single class (existing), multiple classes,
                # a contiguous class range (from/to) or individual students.
                # 1) Single class (legacy)
                if assignment_type == 'class':
                    count = bulk_assign_fees_to_class(
                        db_session, tenant_id, structure.class_id,
                        structure.session_id, structure_id, user_id
                    )
                    flash(f'Fee structure assigned to {count} students', 'success')

                # 2) Multiple classes (from multi-select checkboxes or multi-select control)
                elif request.form.getlist('class_ids[]'):
                    class_ids = [int(cid) for cid in request.form.getlist('class_ids[]') if cid]
                    total_assigned = 0
                    for cid in class_ids:
                        assigned = bulk_assign_fees_to_class(
                            db_session, tenant_id, cid,
                            structure.session_id, structure_id, user_id
                        )
                        total_assigned += assigned
                    flash(f'Fee structure assigned to {total_assigned} students across {len(class_ids)} classes', 'success')

                # 3) Class range (from_class_id & to_class_id) - selects classes with id in inclusive range
                elif request.form.get('from_class_id') and request.form.get('to_class_id'):
                    try:
                        from_id = int(request.form.get('from_class_id'))
                        to_id = int(request.form.get('to_class_id'))
                    except ValueError:
                        from_id = to_id = None

                    if from_id and to_id:
                        low, high = (from_id, to_id) if from_id <= to_id else (to_id, from_id)
                        classes_in_range = db_session.query(Class).filter(
                            Class.tenant_id == tenant_id,
                            Class.id >= low,
                            Class.id <= high
                        ).order_by(Class.id).all()
                        class_ids = [c.id for c in classes_in_range]
                        total_assigned = 0
                        for cid in class_ids:
                            assigned = bulk_assign_fees_to_class(
                                db_session, tenant_id, cid,
                                structure.session_id, structure_id, user_id
                            )
                            total_assigned += assigned
                        flash(f'Fee structure assigned to {total_assigned} students across {len(class_ids)} classes (range)', 'success')

                # 4) Individual students
                elif assignment_type == 'individual':
                    student_ids = request.form.getlist('student_ids[]')
                    count = 0
                    for student_id in student_ids:
                        assign_fee_to_student(
                            db_session, tenant_id, int(student_id),
                            structure.session_id, structure_id, user_id
                        )
                        count += 1
                    flash(f'Fee structure assigned to {count} students', 'success')
                
                return redirect(url_for('school.view_fee_structure', 
                                       tenant_slug=g.current_tenant.slug,
                                       structure_id=structure_id))
            
            except Exception as e:
                flash(f'Error assigning fee structure: {str(e)}', 'error')
        
        # GET request - show assignment form
        students = db_session.query(Student).filter_by(
            tenant_id=tenant_id,
            class_id=structure.class_id,
            status=StudentStatusEnum.ACTIVE
        ).all()
        
        # Get already assigned students
        assigned_student_ids = db_session.query(StudentFee.student_id).filter_by(
            tenant_id=tenant_id,
            session_id=structure.session_id,
            fee_structure_id=structure_id
        ).all()
        assigned_ids = [sid[0] for sid in assigned_student_ids]

        # Provide list of classes so UI can support multi-select or range selection
        classes = db_session.query(Class).filter_by(tenant_id=tenant_id).order_by(Class.id).all()

        return render_template('akademi/fees/assign_fee_structure.html', 
                             structure=structure,
                             students=students,
                             assigned_ids=assigned_ids,
                             classes=classes,
                             school=g.current_tenant)


    @school_blueprint.route('/<tenant_slug>/fee-structures/<int:structure_id>/delete', methods=['POST'])
    @require_school_auth
    def delete_fee_structure(tenant_slug, structure_id):
        """Delete a fee structure if it is not assigned to any students"""
        session = get_session()
        tenant_id = g.current_tenant.id

        structure = session.query(FeeStructure).filter_by(id=structure_id, tenant_id=tenant_id).first()
        if not structure:
            abort(404)

        # Prevent deletion if structure has assigned student fees
        assigned_count = session.query(StudentFee).filter_by(fee_structure_id=structure_id).count()
        if assigned_count > 0:
            flash('Cannot delete fee structure: it has been assigned to students. Unassign or remove student fees first.', 'error')
            return redirect(url_for('school.fee_structures', tenant_slug=g.current_tenant.slug))

        try:
            session.delete(structure)
            session.commit()
            flash('Fee structure deleted successfully', 'success')
        except Exception as e:
            session.rollback()
            flash(f'Error deleting fee structure: {str(e)}', 'error')

        return redirect(url_for('school.fee_structures', tenant_slug=g.current_tenant.slug))
    
    
    # ===== STUDENT FEE MANAGEMENT =====
    
    @school_blueprint.route('/<tenant_slug>/manage-student-fees')
    @require_school_auth
    def manage_student_fees(tenant_slug):
        """List all student fees (admin view)"""
        session = get_session()
        tenant_id = g.current_tenant.id
        
        # Filters
        structure_id = request.args.get('structure_id', type=int)
        session_id = request.args.get('session_id', type=int)
        class_id = request.args.get('class_id', type=int)
        status = request.args.get('status')
        search = request.args.get('search', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        query = session.query(StudentFee).filter_by(tenant_id=tenant_id)
        
        if session_id:
            query = query.filter_by(session_id=session_id)
        if status:
            query = query.filter_by(status=FeeStatusEnum[status.upper()])
        if structure_id:
            query = query.filter_by(fee_structure_id=structure_id)
        if class_id or search:
            query = query.join(Student)
            if class_id:
                query = query.filter(Student.class_id == class_id)
            if search:
                query = query.filter(
                    or_(
                        Student.first_name.ilike(f'%{search}%'),
                        Student.last_name.ilike(f'%{search}%'),
                        Student.admission_number.ilike(f'%{search}%')
                    )
                )
        
        total = query.count()
        student_fees = query.options(
            joinedload(StudentFee.student).joinedload(Student.student_class)
        ).order_by(desc(StudentFee.created_at)).limit(per_page).offset((page - 1) * per_page).all()
        
        # Get sessions and classes for filters
        sessions = session.query(AcademicSession).filter_by(tenant_id=tenant_id).all()
        classes = session.query(Class).filter_by(tenant_id=tenant_id).all()
        structures = session.query(FeeStructure).filter_by(tenant_id=tenant_id).order_by(desc(FeeStructure.created_at)).all()
        total_pages = (total + per_page - 1) // per_page
        
        return render_template('akademi/fees/student_fees.html',
                             student_fees=student_fees,
                             sessions=sessions,
                             classes=classes,
                             page=page,
                             structures=structures,
                             total_pages=total_pages,
                             total=total,
                             school=g.current_tenant)
    
    
    @school_blueprint.route('/<tenant_slug>/student-fees/<int:student_fee_id>/delete', methods=['POST'])
    @require_school_auth
    def delete_student_fee(tenant_slug, student_fee_id):
        """Delete a student fee assignment if no payments have been made"""
        session = get_session()
        tenant_id = g.current_tenant.id

        student_fee = session.query(StudentFee).filter_by(id=student_fee_id, tenant_id=tenant_id).first()
        if not student_fee:
            abort(404)

        # Prevent deletion if any payments have been made
        paid_amount = float(student_fee.paid_amount or 0)
        if paid_amount > 0:
            flash('Cannot delete student fee: payments have already been received. Please reverse payments first.', 'error')
            return redirect(url_for('school.manage_student_fees', tenant_slug=g.current_tenant.slug))

        # Check for receipts
        receipts_count = session.query(FeeReceipt).filter_by(student_fee_id=student_fee_id).count()
        if receipts_count > 0:
            flash('Cannot delete student fee: receipts exist for this fee. Delete receipts first.', 'error')
            return redirect(url_for('school.manage_student_fees', tenant_slug=g.current_tenant.slug))

        try:
            session.delete(student_fee)
            session.commit()
            flash('Student fee assignment deleted successfully', 'success')
        except Exception as e:
            session.rollback()
            flash(f'Error deleting student fee: {str(e)}', 'error')

        return redirect(url_for('school.manage_student_fees', tenant_slug=g.current_tenant.slug))


    @school_blueprint.route('/<tenant_slug>/student-fees/<int:student_fee_id>')
    @require_school_auth
    def view_student_fee(tenant_slug, student_fee_id):
        """View student fee details"""
        session = get_session()
        tenant_id = g.current_tenant.id
        
        student_fee = session.query(StudentFee).options(
            joinedload(StudentFee.student).joinedload(Student.student_class),
            joinedload(StudentFee.session),
            joinedload(StudentFee.fee_structure)
        ).filter_by(
            id=student_fee_id, tenant_id=tenant_id
        ).first()
        
        if not student_fee:
            abort(404)
        
        # Get fee calculation
        fee_calc = calculate_student_fee_total(session, student_fee_id)
        
        # Get receipts
        receipts = session.query(FeeReceipt).filter_by(
            student_fee_id=student_fee_id
        ).order_by(desc(FeeReceipt.receipt_date)).all()
        
        # Get concessions
        concessions = session.query(StudentFeeConcession).filter_by(
            student_fee_id=student_fee_id,
            is_active=True
        ).all()
        
        # Get fines
        fines = session.query(FeeFine).filter_by(
            student_fee_id=student_fee_id
        ).all()
        
        # Get installments
        installments = session.query(FeeInstallment).filter_by(
            student_fee_id=student_fee_id
        ).order_by(FeeInstallment.installment_number).all()
        
        # Get structure details
        structure_details = session.query(FeeStructureDetail).options(
            joinedload(FeeStructureDetail.category)
        ).filter_by(
            fee_structure_id=student_fee.fee_structure_id
        ).all()
        
        return render_template('akademi/fees/view_student_fee.html',
                     student_fee=student_fee,
                     fee_calc=fee_calc,
                     receipts=receipts,
                     concessions=concessions,
                     fines=fines,
                     installments=installments,
                     structure_details=structure_details,
                     school=g.current_tenant,
                     today=date.today())
    
    
    # ===== PAYMENT & RECEIPT MANAGEMENT =====
    
    @school_blueprint.route('/<tenant_slug>/student-fees/<int:student_fee_id>/pay', methods=['GET', 'POST'])
    @require_school_auth
    def pay_student_fee(tenant_slug, student_fee_id):
        """Process fee payment"""
        session = get_session()
        tenant_id = g.current_tenant.id
        
        student_fee = session.query(StudentFee).options(
            joinedload(StudentFee.student).joinedload(Student.student_class),
            joinedload(StudentFee.session),
            joinedload(StudentFee.fee_structure)
        ).filter_by(
            id=student_fee_id, tenant_id=tenant_id
        ).first()
        
        if not student_fee:
            abort(404)
        
        fee_calc = calculate_student_fee_total(session, student_fee_id)
        
        if request.method == 'POST':
            try:
                amount_paid = float(request.form['amount_paid'])
                payment_mode = PaymentModeEnum[request.form['payment_mode'].upper().replace(' ', '_')]
                payment_date = datetime.strptime(request.form['payment_date'], '%Y-%m-%d').date()
                payment_reference = request.form.get('payment_reference')
                bank_name = request.form.get('bank_name')
                remarks = request.form.get('remarks')
                user_id = g.current_user.id if hasattr(g, 'current_user') else None
                
                receipt = process_fee_payment(
                    session, tenant_id, student_fee_id, amount_paid, payment_mode,
                    payment_reference, bank_name, payment_date, user_id, remarks
                )
                
                flash(f'Payment processed successfully. Receipt No: {receipt.receipt_number}', 'success')
                return redirect(url_for('school.view_receipt', 
                                       tenant_slug=g.current_tenant.slug,
                                       receipt_id=receipt.id))
            
            except Exception as e:
                flash(f'Error processing payment: {str(e)}', 'error')
        
        return render_template('akademi/fees/pay_student_fee.html',
                             student_fee=student_fee,
                             fee_calc=fee_calc,
                             payment_modes=PaymentModeEnum,
                             today=date.today().strftime('%Y-%m-%d'),
                             school=g.current_tenant)
    
    
    @school_blueprint.route('/<tenant_slug>/receipts')
    @require_school_auth
    def receipts(tenant_slug):
        """List all fee receipts"""
        session = get_session()
        tenant_id = g.current_tenant.id
        
        # Filters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        payment_mode = request.args.get('payment_mode')
        status = request.args.get('status')
        search = request.args.get('search', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        query = session.query(FeeReceipt).filter_by(tenant_id=tenant_id)
        
        if start_date:
            query = query.filter(FeeReceipt.payment_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        if end_date:
            query = query.filter(FeeReceipt.payment_date <= datetime.strptime(end_date, '%Y-%m-%d').date())
        if payment_mode:
            query = query.filter_by(payment_mode=PaymentModeEnum[payment_mode.upper().replace(' ', '_')])
        if status:
            query = query.filter_by(status=PaymentStatusEnum[status.upper()])
        
        if search:
            query = query.filter(
                or_(
                    FeeReceipt.receipt_number.ilike(f'%{search}%'),
                    FeeReceipt.payment_reference.ilike(f'%{search}%')
                )
            )
        
        total = query.count()
        receipts = query.order_by(desc(FeeReceipt.receipt_date)).limit(per_page).offset((page - 1) * per_page).all()
        
        total_pages = (total + per_page - 1) // per_page
        
        return render_template('akademi/fees/receipts.html',
                             receipts=receipts,
                             page=page,
                             total_pages=total_pages,
                             total=total,
                             payment_modes=PaymentModeEnum,
                             payment_statuses=PaymentStatusEnum,
                             school=g.current_tenant)
    
    
    @school_blueprint.route('/<tenant_slug>/receipts/<int:receipt_id>')
    @require_school_auth
    def view_receipt(tenant_slug, receipt_id):
        """View receipt details"""
        session = get_session()
        tenant_id = g.current_tenant.id
        
        receipt = session.query(FeeReceipt).options(
            joinedload(FeeReceipt.student_fee).joinedload(StudentFee.session),
            joinedload(FeeReceipt.student_fee).joinedload(StudentFee.fee_structure)
        ).filter_by(
            id=receipt_id, tenant_id=tenant_id
        ).first()
        
        if not receipt:
            abort(404)
        
        return render_template('akademi/fees/view_receipt.html', receipt=receipt, school=g.current_tenant)

    @school_blueprint.route('/<tenant_slug>/receipts/<int:receipt_id>/delete', methods=['POST'])
    @require_school_auth
    def delete_receipt(tenant_slug, receipt_id):
        """Delete a receipt and reverse its payment effects where possible"""
        session = get_session()
        tenant_id = g.current_tenant.id

        receipt = session.query(FeeReceipt).filter_by(id=receipt_id, tenant_id=tenant_id).first()
        if not receipt:
            abort(404)

        try:
            student_fee = session.query(StudentFee).filter_by(id=receipt.student_fee_id).first() if receipt.student_fee_id else None
            amount_to_reverse = Decimal(receipt.amount_paid or 0)

            # Delete the receipt record
            session.delete(receipt)
            session.flush()

            if student_fee:
                # Recompute paid_amount from remaining verified receipts
                remaining_paid = session.query(func.coalesce(func.sum(FeeReceipt.amount_paid), 0)).filter_by(
                    student_fee_id=student_fee.id,
                    status=PaymentStatusEnum.VERIFIED
                ).scalar() or 0
                student_fee.paid_amount = Decimal(remaining_paid)

                # Reverse installment payments starting from latest installment
                installments = session.query(FeeInstallment).filter_by(student_fee_id=student_fee.id).order_by(FeeInstallment.installment_number.desc()).all()
                remaining = amount_to_reverse
                for inst in installments:
                    if remaining <= 0:
                        break
                    paid = inst.paid_amount or Decimal('0.00')
                    if paid > 0:
                        deduct = min(paid, remaining)
                        inst.paid_amount = paid - Decimal(deduct)
                        # update status
                        if float(inst.paid_amount) >= float(inst.amount):
                            inst.status = InstallmentStatusEnum.PAID
                        else:
                            inst.status = InstallmentStatusEnum.PENDING
                        remaining -= deduct

                # Recompute fee status based on remaining receipts
                fee_calc = calculate_student_fee_total(session, student_fee.id)
                student_fee.status = fee_calc['status']

            # Update collection summary for the date if exists (best-effort)
            try:
                cs = session.query(FeeCollectionSummary).filter_by(
                    tenant_id=tenant_id,
                    summary_date=receipt.payment_date,
                    summary_type='daily'
                ).first()
                if cs:
                    cs.total_receipts = max((cs.total_receipts or 1) - 1, 0)
                    cs.total_collected = (cs.total_collected or Decimal('0.00')) - Decimal(amount_to_reverse)
                    if cs.total_collected < 0:
                        cs.total_collected = Decimal('0.00')
                    session.add(cs)
            except Exception:
                # Ignore collection summary errors
                pass

            session.commit()
            flash('Receipt deleted and payment reversed (where applicable).', 'success')
        except Exception as e:
            session.rollback()
            flash(f'Error deleting receipt: {str(e)}', 'error')

        return redirect(url_for('school.receipts', tenant_slug=g.current_tenant.slug))
    
    
    @school_blueprint.route('/<tenant_slug>/receipts/<int:receipt_id>/print')
    @require_school_auth
    def print_receipt(tenant_slug, receipt_id):
        """Print receipt PDF"""
        session = get_session()
        tenant_id = g.current_tenant.id
        
        receipt = session.query(FeeReceipt).filter_by(
            id=receipt_id, tenant_id=tenant_id
        ).first()
        
        if not receipt:
            abort(404)
        
        # Generate PDF
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Header
        p.setFont("Helvetica-Bold", 20)
        p.drawCentredString(width/2, height - 50, g.current_tenant.name)
        p.setFont("Helvetica", 12)
        p.drawCentredString(width/2, height - 70, "Fee Receipt")
        
        # Receipt details
        y = height - 120
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, y, f"Receipt No: {receipt.receipt_number}")
        p.drawRightString(width - 50, y, f"Date: {receipt.receipt_date.strftime('%d-%b-%Y')}")
        
        y -= 30
        p.setFont("Helvetica", 11)
        student = receipt.student
        p.drawString(50, y, f"Student Name: {student.full_name}")
        y -= 20
        p.drawString(50, y, f"Admission No: {student.admission_number}")
        class_display = f"{student.student_class.class_name}-{student.student_class.section}" if student.student_class else 'N/A'
        p.drawString(300, y, f"Class: {class_display}")
        
        # Payment details
        y -= 40
        p.setFont("Helvetica-Bold", 11)
        p.drawString(50, y, "Payment Details:")
        y -= 25
        p.setFont("Helvetica", 11)
        
        details = [
            ("Amount Paid:", f"₹ {receipt.amount_paid:,.2f}"),
            ("Fine Amount:", f"₹ {receipt.fine_amount:,.2f}"),
            ("Total Amount:", f"₹ {receipt.total_amount:,.2f}"),
            ("Payment Mode:", receipt.payment_mode.value),
            ("Payment Date:", receipt.payment_date.strftime('%d-%b-%Y'))
        ]
        
        if receipt.payment_reference:
            details.append(("Reference/Cheque No:", receipt.payment_reference))
        if receipt.bank_name:
            details.append(("Bank Name:", receipt.bank_name))
        
        for label, value in details:
            p.drawString(70, y, label)
            p.drawString(250, y, str(value))
            y -= 20
        
        # Footer
        y = 100
        p.drawString(50, y, f"Generated by: {receipt.generator.username if receipt.generator else 'System'}")
        p.drawString(50, y - 20, f"Generated at: {receipt.created_at.strftime('%d-%b-%Y %I:%M %p')}")
        
        p.drawCentredString(width/2, 50, "This is a computer-generated receipt")
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"receipt_{receipt.receipt_number}.pdf", mimetype='application/pdf')
    
    
    # ===== CONCESSION/DISCOUNT MANAGEMENT =====
    
    @school_blueprint.route('/<tenant_slug>/student-fees/<int:student_fee_id>/add-concession', methods=['GET', 'POST'])
    @require_school_auth
    def add_concession(tenant_slug, student_fee_id):
        """Add concession to student fee"""
        session = get_session()
        tenant_id = g.current_tenant.id
        
        student_fee = session.query(StudentFee).options(
            joinedload(StudentFee.student).joinedload(Student.student_class),
            joinedload(StudentFee.session),
            joinedload(StudentFee.fee_structure)
        ).filter_by(
            id=student_fee_id, tenant_id=tenant_id
        ).first()
        
        if not student_fee:
            abort(404)
        
        if request.method == 'POST':
            try:
                concession_type = ConcessionTypeEnum[request.form['concession_type'].upper().replace(' ', '_')]
                concession_mode = ConcessionModeEnum[request.form['concession_mode'].upper().replace(' ', '_')]
                concession_value = float(request.form['concession_value'])
                reason = request.form.get('reason')
                user_id = g.current_user.id if hasattr(g, 'current_user') else None
                
                concession = apply_concession_to_student_fee(
                    session, student_fee_id, concession_type, concession_mode,
                    concession_value, reason, user_id
                )
                
                flash('Concession applied successfully', 'success')
                return redirect(url_for('school.view_student_fee',
                                       tenant_slug=g.current_tenant.slug,
                                       student_fee_id=student_fee_id))
            
            except Exception as e:
                flash(f'Error applying concession: {str(e)}', 'error')
        
        return render_template('akademi/fees/add_concession.html',
                             student_fee=student_fee,
                             concession_types=ConcessionTypeEnum,
                             concession_modes=ConcessionModeEnum,
                             school=g.current_tenant)
    
    
    # ===== FINE MANAGEMENT =====
    
    @school_blueprint.route('/<tenant_slug>/student-fees/<int:student_fee_id>/add-fine', methods=['GET', 'POST'])
    @require_school_auth
    def add_fine(tenant_slug, student_fee_id):
        """Add fine to student fee"""
        session = get_session()
        tenant_id = g.current_tenant.id
        
        student_fee = session.query(StudentFee).options(
            joinedload(StudentFee.student).joinedload(Student.student_class),
            joinedload(StudentFee.session),
            joinedload(StudentFee.fee_structure)
        ).filter_by(
            id=student_fee_id, tenant_id=tenant_id
        ).first()
        
        if not student_fee:
            abort(404)
        
        if request.method == 'POST':
            try:
                fine_amount = float(request.form['fine_amount'])
                reason = request.form.get('reason')
                user_id = g.current_user.id if hasattr(g, 'current_user') else None
                
                fine = apply_late_payment_fine(session, student_fee_id, fine_amount, reason, user_id)
                
                flash('Fine applied successfully', 'success')
                return redirect(url_for('school.view_student_fee',
                                       tenant_slug=g.current_tenant.slug,
                                       student_fee_id=student_fee_id))
            
            except Exception as e:
                flash(f'Error applying fine: {str(e)}', 'error')
        
        return render_template('akademi/fees/add_fine.html', 
                             student_fee=student_fee, 
                             school=g.current_tenant,
                             today=date.today())
    
    
    @school_blueprint.route('/<tenant_slug>/fines/<int:fine_id>/waive', methods=['POST'])
    @require_school_auth
    def waive_student_fine(tenant_slug, fine_id):
        """Waive a fine"""
        session = get_session()
        user_id = g.current_user.id if hasattr(g, 'current_user') else None
        reason = request.form.get('reason')
        
        try:
            waive_fine(session, fine_id, user_id, reason)
            flash('Fine waived successfully', 'success')
        except Exception as e:
            flash(f'Error waiving fine: {str(e)}', 'error')
        
        return redirect(request.referrer or url_for('school.manage_student_fees', tenant_slug=g.current_tenant.slug))
    
    
    # ===== ANALYTICS & REPORTS =====
    
    @school_blueprint.route('/<tenant_slug>/fee-analytics')
    @require_school_auth
    def fee_analytics(tenant_slug):
        """Fee collection analytics dashboard"""
        session = get_session()
        tenant_id = g.current_tenant.id
        
        # Get filters
        session_id = request.args.get('session_id', type=int)
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if not start_date_str:
            start_date = date.today().replace(day=1)  # First day of current month
        else:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        
        if not end_date_str:
            end_date = date.today()
        else:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
        # Get collection summary
        collection_summary = get_fee_collection_summary(session, tenant_id, start_date, end_date, session_id)
        
        # Get outstanding summary
        outstanding_summary = get_outstanding_fees_summary(session, tenant_id, session_id)
        
        # Get class-wise collection
        class_wise = []
        if session_id:
            class_wise = get_class_wise_collection(session, tenant_id, session_id)
        
        # Get defaulters
        defaulters = get_defaulter_list(session, tenant_id, session_id or session.query(AcademicSession).filter_by(tenant_id=tenant_id, is_active=True).first().id, days_overdue=0)
        
        # Get sessions for filter
        sessions = session.query(AcademicSession).filter_by(tenant_id=tenant_id).all()
        
        return render_template('akademi/fees/fee_analytics.html',
                             collection_summary=collection_summary,
                             outstanding_summary=outstanding_summary,
                             class_wise=class_wise,
                             defaulters=defaulters[:20],  # Top 20 defaulters
                             sessions=sessions,
                             
                             selected_session=session_id,
                             start_date=start_date,
                             end_date=end_date,
                             school=g.current_tenant)
    
    
    @school_blueprint.route('/<tenant_slug>/defaulters-report')
    @require_school_auth
    def defaulters_report(tenant_slug):
        """Defaulters list report"""
        session = get_session()
        tenant_id = g.current_tenant.id
        
        session_id = request.args.get('session_id', type=int)
        days_overdue = request.args.get('days_overdue', 0, type=int)
        
        if not session_id:
            active_session = session.query(AcademicSession).filter_by(tenant_id=tenant_id, is_active=True).first()
            session_id = active_session.id if active_session else None
        
        defaulters = get_defaulter_list(session, tenant_id, session_id, days_overdue) if session_id else []
        
        sessions = session.query(AcademicSession).filter_by(tenant_id=tenant_id).all()
        
        return render_template('akademi/fees/defaulters_report.html',
                             defaulters=defaulters,
                             sessions=sessions,
                             selected_session=session_id,
                             days_overdue=days_overdue,
                             school=g.current_tenant)
    
    
    # ===== API ENDPOINTS =====
    
    @school_blueprint.route('/<tenant_slug>/api/student-fee-details/<int:student_id>')
    @require_school_auth
    def api_student_fee_details(tenant_slug, student_id):
        """Get student fee details (API)"""
        session = get_session()
        session_id = request.args.get('session_id', type=int)
        
        fee_details = get_student_fee_details(session, student_id, session_id)
        
        return jsonify(fee_details)
    
    
    @school_blueprint.route('/<tenant_slug>/api/fee-categories')
    @require_school_auth
    def api_fee_categories(tenant_slug):
        """Get all fee categories (API)"""
        session = get_session()
        tenant_id = g.current_tenant.id
        
        categories = session.query(FeeCategory).filter_by(
            tenant_id=tenant_id, is_active=True
        ).all()
        
        return jsonify([{
            'id': c.id,
            'name': c.category_name,
            'code': c.category_code,
            'is_mandatory': c.is_mandatory
        } for c in categories])
    
    
    @school_blueprint.route('/<tenant_slug>/api/auto-apply-fines', methods=['POST'])
    @require_school_auth
    def api_auto_apply_fines(tenant_slug):
        """Auto-apply late payment fines (API)"""
        session = get_session()
        tenant_id = g.current_tenant.id
        fine_percentage = request.json.get('fine_percentage', 2.0)
        
        try:
            count = auto_apply_late_fines(session, tenant_id, fine_percentage)
            return jsonify({'success': True, 'count': count, 'message': f'Fines applied to {count} students'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500


# Export function to be called from main blueprint
def register_fee_routes(school_blueprint, require_school_auth):
    """Register all fee management routes with school blueprint"""
    create_fee_routes(school_blueprint, require_school_auth)
