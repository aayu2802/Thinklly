"""
Fee Management Helper Functions
Contains business logic for fee calculations, receipt generation, and analytics
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import func, and_, or_, extract, case
from sqlalchemy.orm import Session
from fee_models import (
    FeeCategory, FeeStructure, FeeStructureDetail, StudentFee, 
    StudentFeeConcession, FeeReceipt, FeeFine, FeeInstallment, FeeCollectionSummary,
    FeeStatusEnum, PaymentModeEnum, PaymentStatusEnum, ConcessionTypeEnum, 
    ConcessionModeEnum, FineTypeEnum, InstallmentStatusEnum
)
from models import Student, Class, AcademicSession, StudentStatusEnum
import random
import string


# ===== RECEIPT NUMBER GENERATION =====

def generate_receipt_number(session: Session, tenant_id: int) -> str:
    """Generate unique receipt number for tenant"""
    today = date.today()
    prefix = f"RCP-{today.year}{today.month:02d}"
    
    # Get count of receipts for current month
    count = session.query(func.count(FeeReceipt.id)).filter(
        FeeReceipt.tenant_id == tenant_id,
        extract('year', FeeReceipt.receipt_date) == today.year,
        extract('month', FeeReceipt.receipt_date) == today.month
    ).scalar() or 0
    
    receipt_number = f"{prefix}-{count + 1:05d}"
    
    # Ensure uniqueness
    while session.query(FeeReceipt).filter_by(receipt_number=receipt_number, tenant_id=tenant_id).first():
        count += 1
        receipt_number = f"{prefix}-{count + 1:05d}"
    
    return receipt_number


# ===== FEE CALCULATION HELPERS =====

def calculate_student_fee_total(session: Session, student_fee_id: int) -> dict:
    """Calculate total fee breakdown for a student fee"""
    student_fee = session.query(StudentFee).filter_by(id=student_fee_id).first()
    if not student_fee:
        return None
    
    # Get all concessions
    concessions = session.query(StudentFeeConcession).filter_by(
        student_fee_id=student_fee_id,
        is_active=True
    ).all()
    # Use Decimal for monetary sums to avoid float/Decimal mixing
    total_discount = sum((c.actual_discount or Decimal('0.00')) for c in concessions) if concessions else Decimal('0.00')
    
    # Get all fines (non-waived)
    fines = session.query(FeeFine).filter_by(
        student_fee_id=student_fee_id,
        waived=False
    ).all()
    total_fine = sum((f.fine_amount or Decimal('0.00')) for f in fines) if fines else Decimal('0.00')
    
    # Get total paid
    receipts = session.query(FeeReceipt).filter_by(
        student_fee_id=student_fee_id,
        status=PaymentStatusEnum.VERIFIED
    ).all()
    total_paid = sum((r.amount_paid or Decimal('0.00')) for r in receipts) if receipts else Decimal('0.00')

    # Ensure all arithmetic uses Decimal
    total_amt_dec = Decimal(student_fee.total_amount) if not isinstance(student_fee.total_amount, Decimal) else student_fee.total_amount
    net_amount_dec = total_amt_dec - Decimal(total_discount) + Decimal(total_fine)
    balance_dec = net_amount_dec - Decimal(total_paid)

    # Determine status using float values for compatibility with existing function
    status = determine_fee_status(float(net_amount_dec), float(total_paid), student_fee.due_date)

    return {
        'total_amount': float(total_amt_dec),
        'discount_amount': float(total_discount),
        'fine_amount': float(total_fine),
        'net_amount': float(net_amount_dec),
        'paid_amount': float(total_paid),
        'balance_amount': float(balance_dec),
        'status': status
    }


def determine_fee_status(net_amount: float, paid_amount: float, due_date: date) -> FeeStatusEnum:
    """Determine fee status based on payment and due date"""
    if paid_amount >= net_amount:
        return FeeStatusEnum.PAID
    elif paid_amount > 0:
        return FeeStatusEnum.PARTIALLY_PAID
    elif due_date and date.today() > due_date:
        return FeeStatusEnum.OVERDUE
    else:
        return FeeStatusEnum.PENDING


def calculate_concession_amount(base_amount: float, concession_mode: ConcessionModeEnum, concession_value: float) -> float:
    """Calculate actual discount from concession"""
    if concession_mode == ConcessionModeEnum.PERCENTAGE:
        return (base_amount * concession_value) / 100
    else:  # FIXED_AMOUNT
        return min(concession_value, base_amount)  # Don't exceed base amount


# ===== FEE STRUCTURE HELPERS =====

def assign_fee_to_student(session: Session, tenant_id: int, student_id: int, session_id: int, 
                          fee_structure_id: int, created_by: int = None) -> StudentFee:
    """Assign fee structure to a student"""
    
    # Check if already assigned
    existing = session.query(StudentFee).filter_by(
        tenant_id=tenant_id,
        student_id=student_id,
        session_id=session_id,
        fee_structure_id=fee_structure_id
    ).first()
    
    if existing:
        return existing
    
    # Get fee structure details
    fee_structure = session.query(FeeStructure).filter_by(id=fee_structure_id).first()
    if not fee_structure:
        raise ValueError("Fee structure not found")
    
    # Calculate total amount from structure details
    details = session.query(FeeStructureDetail).filter_by(fee_structure_id=fee_structure_id).all()
    total_amount = sum(float(d.amount) for d in details)
    
    # Create student fee
    student_fee = StudentFee(
        tenant_id=tenant_id,
        student_id=student_id,
        session_id=session_id,
        fee_structure_id=fee_structure_id,
        total_amount=Decimal(str(total_amount)),
        status=FeeStatusEnum.PENDING,
        assigned_date=date.today(),
        due_date=fee_structure.valid_to,
        created_by=created_by
    )
    
    session.add(student_fee)
    session.flush()
    
    # Create installments if structure has multiple installments
    installment_details = {}
    for detail in details:
        inst_num = detail.installment_number
        if inst_num not in installment_details:
            installment_details[inst_num] = {
                'amount': 0,
                'due_date': detail.due_date or fee_structure.valid_to
            }
        installment_details[inst_num]['amount'] += float(detail.amount)
    
    if len(installment_details) > 1:
        for inst_num, inst_data in installment_details.items():
            installment = FeeInstallment(
                tenant_id=tenant_id,
                student_fee_id=student_fee.id,
                installment_number=inst_num,
                installment_name=f"Installment {inst_num}",
                due_date=inst_data['due_date'],
                amount=Decimal(str(inst_data['amount'])),
                status=InstallmentStatusEnum.PENDING
            )
            session.add(installment)
    
    session.commit()
    return student_fee


def bulk_assign_fees_to_class(session: Session, tenant_id: int, class_id: int, 
                               session_id: int, fee_structure_id: int, created_by: int = None) -> int:
    """Assign fees to all students in a class"""
    students = session.query(Student).filter_by(
        tenant_id=tenant_id,
        class_id=class_id,
        status=StudentStatusEnum.ACTIVE
    ).all()
    
    count = 0
    for student in students:
        try:
            assign_fee_to_student(session, tenant_id, student.id, session_id, fee_structure_id, created_by)
            count += 1
        except Exception as e:
            print(f"Error assigning fee to student {student.id}: {e}")
            continue
    
    return count


# ===== PAYMENT PROCESSING =====

def process_fee_payment(session: Session, tenant_id: int, student_fee_id: int, 
                        amount_paid: float, payment_mode: PaymentModeEnum, 
                        payment_reference: str = None, bank_name: str = None,
                        payment_date: date = None, generated_by: int = None,
                        remarks: str = None) -> FeeReceipt:
    """Process fee payment and generate receipt"""
    
    student_fee = session.query(StudentFee).filter_by(id=student_fee_id).first()
    if not student_fee:
        raise ValueError("Student fee not found")
    
    # Calculate current balance
    fee_calc = calculate_student_fee_total(session, student_fee_id)
    balance = fee_calc['balance_amount']
    
    if amount_paid > balance:
        raise ValueError(f"Payment amount ({amount_paid}) exceeds balance ({balance})")
    
    # Generate receipt number
    receipt_number = generate_receipt_number(session, tenant_id)
    
    # Create receipt
    receipt = FeeReceipt(
        tenant_id=tenant_id,
        student_id=student_fee.student_id,
        student_fee_id=student_fee_id,
        receipt_number=receipt_number,
        receipt_date=date.today(),
        payment_date=payment_date or date.today(),
        amount_paid=Decimal(str(amount_paid)),
        fine_amount=Decimal('0.00'),
        payment_mode=payment_mode,
        payment_reference=payment_reference,
        bank_name=bank_name,
        status=PaymentStatusEnum.VERIFIED,  # Auto-verify manual payments
        generated_by=generated_by,
        verified_by=generated_by,
        verified_at=datetime.utcnow(),
        remarks=remarks
    )
    
    session.add(receipt)
    
    # Update student fee paid amount and status
    student_fee.paid_amount = (student_fee.paid_amount or Decimal('0.00')) + Decimal(str(amount_paid))
    new_calc = calculate_student_fee_total(session, student_fee_id)
    student_fee.status = new_calc['status']
    
    # Update installments if exist
    update_installment_payments(session, student_fee_id, amount_paid)
    
    session.commit()
    
    # Update collection summary
    update_collection_summary(session, tenant_id, student_fee.session_id, receipt.payment_date, payment_mode, amount_paid)
    
    return receipt


def update_installment_payments(session: Session, student_fee_id: int, amount_paid: float):
    """Distribute payment across pending installments"""
    installments = session.query(FeeInstallment).filter_by(
        student_fee_id=student_fee_id
    ).order_by(FeeInstallment.installment_number).all()
    
    if not installments:
        return
    
    remaining_amount = amount_paid
    
    for installment in installments:
        if remaining_amount <= 0:
            break
        
        balance = float(installment.amount) - float(installment.paid_amount or 0)
        
        if balance > 0:
            payment_for_installment = min(remaining_amount, balance)
            installment.paid_amount = (installment.paid_amount or Decimal('0.00')) + Decimal(str(payment_for_installment))
            
            if float(installment.paid_amount) >= float(installment.amount):
                installment.status = InstallmentStatusEnum.PAID
            
            remaining_amount -= payment_for_installment
    
    session.commit()


# ===== FINE MANAGEMENT =====

def apply_late_payment_fine(session: Session, student_fee_id: int, fine_amount: float, 
                            reason: str = None, created_by: int = None) -> FeeFine:
    """Apply late payment fine to student fee"""
    
    student_fee = session.query(StudentFee).filter_by(id=student_fee_id).first()
    if not student_fee:
        raise ValueError("Student fee not found")
    
    fine = FeeFine(
        tenant_id=student_fee.tenant_id,
        student_fee_id=student_fee_id,
        fine_type=FineTypeEnum.LATE_PAYMENT,
        fine_amount=Decimal(str(fine_amount)),
        fine_date=date.today(),
        reason=reason or "Late payment fine",
        created_by=created_by
    )
    
    session.add(fine)
    
    # Update student fee fine amount and status
    student_fee.fine_amount = (student_fee.fine_amount or Decimal('0.00')) + Decimal(str(fine_amount))
    fee_calc = calculate_student_fee_total(session, student_fee_id)
    student_fee.status = fee_calc['status']
    
    session.commit()
    return fine


def waive_fine(session: Session, fine_id: int, waived_by: int, waived_reason: str = None):
    """Waive a fine"""
    fine = session.query(FeeFine).filter_by(id=fine_id).first()
    if not fine:
        raise ValueError("Fine not found")
    
    fine.waived = True
    fine.waived_by = waived_by
    fine.waived_at = datetime.utcnow()
    fine.waived_reason = waived_reason
    
    # Update student fee
    student_fee = fine.student_fee
    student_fee.fine_amount = (student_fee.fine_amount or Decimal('0.00')) - fine.fine_amount
    
    fee_calc = calculate_student_fee_total(session, student_fee.id)
    student_fee.status = fee_calc['status']
    
    session.commit()


def auto_apply_late_fines(session: Session, tenant_id: int, fine_percentage: float = 2.0):
    """Automatically apply fines to overdue fees"""
    today = date.today()
    
    # Get overdue student fees
    overdue_fees = session.query(StudentFee).filter(
        StudentFee.tenant_id == tenant_id,
        StudentFee.status.in_([FeeStatusEnum.PENDING, FeeStatusEnum.PARTIALLY_PAID]),
        StudentFee.due_date < today
    ).all()
    
    count = 0
    for student_fee in overdue_fees:
        # Check if fine already applied today
        existing_fine = session.query(FeeFine).filter(
            FeeFine.student_fee_id == student_fee.id,
            FeeFine.fine_date == today,
            FeeFine.fine_type == FineTypeEnum.LATE_PAYMENT
        ).first()
        
        if not existing_fine:
            fee_calc = calculate_student_fee_total(session, student_fee.id)
            balance = fee_calc['balance_amount']
            
            if balance > 0:
                fine_amount = (balance * fine_percentage) / 100
                apply_late_payment_fine(session, student_fee.id, fine_amount, 
                                       f"Automatic late payment fine ({fine_percentage}%)")
                count += 1
    
    return count


# ===== CONCESSION/DISCOUNT MANAGEMENT =====

def apply_concession_to_student_fee(session: Session, student_fee_id: int, concession_type: ConcessionTypeEnum,
                                     concession_mode: ConcessionModeEnum, concession_value: float,
                                     reason: str = None, approved_by: int = None) -> StudentFeeConcession:
    """Apply concession/discount to student fee"""
    
    student_fee = session.query(StudentFee).filter_by(id=student_fee_id).first()
    if not student_fee:
        raise ValueError("Student fee not found")
    
    # Calculate actual discount
    actual_discount = calculate_concession_amount(float(student_fee.total_amount), concession_mode, concession_value)
    
    concession = StudentFeeConcession(
        tenant_id=student_fee.tenant_id,
        student_fee_id=student_fee_id,
        concession_type=concession_type,
        concession_mode=concession_mode,
        concession_value=Decimal(str(concession_value)),
        actual_discount=Decimal(str(actual_discount)),
        reason=reason,
        approved_by=approved_by,
        approved_at=datetime.utcnow() if approved_by else None,
        is_active=True
    )
    
    session.add(concession)
    
    # Update student fee discount amount and status
    student_fee.discount_amount = (student_fee.discount_amount or Decimal('0.00')) + Decimal(str(actual_discount))
    student_fee.discount_reason = reason
    fee_calc = calculate_student_fee_total(session, student_fee_id)
    student_fee.status = fee_calc['status']
    
    session.commit()
    return concession


def apply_bulk_concessions_to_category(session: Session, tenant_id: int, category: str,
                                        concession_type: ConcessionTypeEnum, concession_mode: ConcessionModeEnum,
                                        concession_value: float, session_id: int, approved_by: int = None):
    """Apply concession to all students of a specific category (SC/ST/OBC, etc.)"""
    
    students = session.query(Student).filter_by(
        tenant_id=tenant_id,
        category=category,
        status=StudentStatusEnum.ACTIVE
    ).all()
    
    count = 0
    for student in students:
        # Get student fees for the session
        student_fees = session.query(StudentFee).filter_by(
            tenant_id=tenant_id,
            student_id=student.id,
            session_id=session_id
        ).all()
        
        for student_fee in student_fees:
            try:
                apply_concession_to_student_fee(
                    session, student_fee.id, concession_type, concession_mode,
                    concession_value, f"{category} category concession", approved_by
                )
                count += 1
            except Exception as e:
                print(f"Error applying concession to student {student.id}: {e}")
                continue
    
    return count


# ===== ANALYTICS AND REPORTING =====

def get_fee_collection_summary(session: Session, tenant_id: int, start_date: date, 
                                end_date: date, session_id: int = None) -> dict:
    """Get fee collection summary for date range"""
    
    query = session.query(
        func.count(FeeReceipt.id).label('total_receipts'),
        func.sum(FeeReceipt.amount_paid).label('total_collected'),
        func.sum(case((FeeReceipt.payment_mode == PaymentModeEnum.CASH, FeeReceipt.amount_paid), else_=0)).label('cash_collected'),
        func.sum(case((FeeReceipt.payment_mode.in_([PaymentModeEnum.UPI, PaymentModeEnum.ONLINE, PaymentModeEnum.BANK_TRANSFER]), FeeReceipt.amount_paid), else_=0)).label('online_collected'),
        func.sum(case((FeeReceipt.payment_mode == PaymentModeEnum.CHEQUE, FeeReceipt.amount_paid), else_=0)).label('cheque_collected'),
        func.sum(FeeReceipt.fine_amount).label('fine_collected')
    ).filter(
        FeeReceipt.tenant_id == tenant_id,
        FeeReceipt.status == PaymentStatusEnum.VERIFIED,
        FeeReceipt.payment_date.between(start_date, end_date)
    )
    
    if session_id:
        query = query.join(StudentFee).filter(StudentFee.session_id == session_id)
    
    result = query.first()
    
    return {
        'total_receipts': result.total_receipts or 0,
        'total_collected': float(result.total_collected or 0),
        'cash_collected': float(result.cash_collected or 0),
        'online_collected': float(result.online_collected or 0),
        'cheque_collected': float(result.cheque_collected or 0),
        'fine_collected': float(result.fine_collected or 0)
    }


def get_outstanding_fees_summary(session: Session, tenant_id: int, session_id: int = None) -> dict:
    """Get summary of outstanding fees"""
    
    query = session.query(
        func.count(StudentFee.id).label('total_students'),
        func.sum(StudentFee.total_amount).label('total_amount'),
        func.sum(StudentFee.discount_amount).label('total_discount'),
        func.sum(StudentFee.fine_amount).label('total_fine'),
        func.sum(StudentFee.paid_amount).label('total_paid')
    ).filter(
        StudentFee.tenant_id == tenant_id,
        StudentFee.status.in_([FeeStatusEnum.PENDING, FeeStatusEnum.PARTIALLY_PAID, FeeStatusEnum.OVERDUE])
    )
    
    if session_id:
        query = query.filter(StudentFee.session_id == session_id)
    
    result = query.first()
    
    total_amount = float(result.total_amount or 0)
    total_discount = float(result.total_discount or 0)
    total_fine = float(result.total_fine or 0)
    total_paid = float(result.total_paid or 0)
    net_amount = total_amount - total_discount + total_fine
    outstanding = net_amount - total_paid
    # Calculate overdue amount and count (fees past due date and marked OVERDUE)
    today = date.today()
    overdue_query = session.query(
        func.sum(StudentFee.total_amount).label('o_total_amount'),
        func.sum(StudentFee.discount_amount).label('o_total_discount'),
        func.sum(StudentFee.fine_amount).label('o_total_fine'),
        func.sum(StudentFee.paid_amount).label('o_total_paid'),
        func.count(StudentFee.id).label('overdue_count')
    ).filter(
        StudentFee.tenant_id == tenant_id,
        StudentFee.status == FeeStatusEnum.OVERDUE,
        StudentFee.due_date < today
    )

    if session_id:
        overdue_query = overdue_query.filter(StudentFee.session_id == session_id)

    overdue_res = overdue_query.first()

    o_total_amount = float(overdue_res.o_total_amount or 0)
    o_total_discount = float(overdue_res.o_total_discount or 0)
    o_total_fine = float(overdue_res.o_total_fine or 0)
    o_total_paid = float(overdue_res.o_total_paid or 0)
    overdue_count = int(overdue_res.overdue_count or 0)

    overdue_net = o_total_amount - o_total_discount + o_total_fine
    overdue_outstanding = overdue_net - o_total_paid

    return {
        'total_students': result.total_students or 0,
        'total_amount': total_amount,
        'total_discount': total_discount,
        'total_fine': total_fine,
        'net_amount': net_amount,
        'total_paid': total_paid,
        'outstanding': outstanding,
        'overdue_amount': overdue_outstanding,
        'overdue_count': overdue_count
    }


def get_class_wise_collection(session: Session, tenant_id: int, session_id: int) -> list:
    """Get class-wise fee collection statistics"""
    
    results = session.query(
        Class.id,
        Class.class_name,
        Class.section,
        func.count(StudentFee.id).label('total_students'),
        func.sum(StudentFee.total_amount).label('total_amount'),
        func.sum(StudentFee.paid_amount).label('paid_amount'),
        func.count(case((StudentFee.status == FeeStatusEnum.PAID, 1))).label('paid_count'),
        func.count(case((StudentFee.status == FeeStatusEnum.PENDING, 1))).label('pending_count'),
        func.count(case((StudentFee.status == FeeStatusEnum.OVERDUE, 1))).label('overdue_count')
    ).join(
        FeeStructure, FeeStructure.class_id == Class.id
    ).join(
        StudentFee, StudentFee.fee_structure_id == FeeStructure.id
    ).filter(
        Class.tenant_id == tenant_id,
        StudentFee.session_id == session_id
    ).group_by(Class.id, Class.class_name, Class.section).all()
    
    class_data = []
    for row in results:
        total_amt = float(row.total_amount or 0)
        paid_amt = float(row.paid_amount or 0)
        collection_pct = (paid_amt / total_amt * 100) if total_amt > 0 else 0
        
        class_data.append({
            'class_id': row.id,
            'class_name': f"{row.class_name}-{row.section}",
            'total_students': row.total_students,
            'total_amount': total_amt,
            'paid_amount': paid_amt,
            'outstanding': total_amt - paid_amt,
            'collection_percentage': round(collection_pct, 2),
            'paid_count': row.paid_count,
            'pending_count': row.pending_count,
            'overdue_count': row.overdue_count
        })
    
    return class_data


def update_collection_summary(session: Session, tenant_id: int, session_id: int, 
                               payment_date: date, payment_mode: PaymentModeEnum, amount: float):
    """Update daily collection summary"""
    
    # Daily summary
    daily_summary = session.query(FeeCollectionSummary).filter_by(
        tenant_id=tenant_id,
        summary_date=payment_date,
        summary_type='daily'
    ).first()
    
    if not daily_summary:
        daily_summary = FeeCollectionSummary(
            tenant_id=tenant_id,
            session_id=session_id,
            summary_date=payment_date,
            summary_type='daily'
        )
        session.add(daily_summary)
    
    daily_summary.total_receipts = (daily_summary.total_receipts or 0) + 1
    daily_summary.total_collected = (daily_summary.total_collected or Decimal('0.00')) + Decimal(str(amount))
    
    if payment_mode == PaymentModeEnum.CASH:
        daily_summary.cash_collected = (daily_summary.cash_collected or Decimal('0.00')) + Decimal(str(amount))
    elif payment_mode in [PaymentModeEnum.UPI, PaymentModeEnum.ONLINE, PaymentModeEnum.BANK_TRANSFER]:
        daily_summary.online_collected = (daily_summary.online_collected or Decimal('0.00')) + Decimal(str(amount))
    elif payment_mode == PaymentModeEnum.CHEQUE:
        daily_summary.cheque_collected = (daily_summary.cheque_collected or Decimal('0.00')) + Decimal(str(amount))
    
    session.commit()


def get_defaulter_list(session: Session, tenant_id: int, session_id: int, days_overdue: int = 0) -> list:
    """Get list of students with overdue fees"""
    
    cutoff_date = date.today() - timedelta(days=days_overdue)
    
    defaulters = session.query(
        Student.id,
        Student.full_name,
        Student.admission_number,
        Student.guardian_phone,
        Student.guardian_email,
        Class.class_name,
        Class.section,
        StudentFee.id.label('student_fee_id'),
        StudentFee.due_date,
        StudentFee.total_amount,
        StudentFee.paid_amount,
        StudentFee.status
    ).join(
        StudentFee, StudentFee.student_id == Student.id
    ).join(
        FeeStructure, FeeStructure.id == StudentFee.fee_structure_id
    ).join(
        Class, Class.id == FeeStructure.class_id
    ).filter(
        Student.tenant_id == tenant_id,
        StudentFee.session_id == session_id,
        StudentFee.status.in_([FeeStatusEnum.PENDING, FeeStatusEnum.PARTIALLY_PAID, FeeStatusEnum.OVERDUE]),
        StudentFee.due_date <= cutoff_date
    ).all()
    
    defaulter_list = []
    for row in defaulters:
        full_name = row.full_name
        total = float(row.total_amount or 0)
        paid = float(row.paid_amount or 0)
        outstanding = total - paid
        days_late = (date.today() - row.due_date).days if row.due_date else 0
        
        defaulter_list.append({
            'student_id': row.id,
            'student_fee_id': row.student_fee_id,
            'student_name': full_name,
            'admission_number': row.admission_number,
            'guardian_phone': row.guardian_phone,
            'guardian_email': row.guardian_email,
            'class_name': f"{row.class_name}-{row.section}",
            'due_date': row.due_date.strftime('%Y-%m-%d') if row.due_date else None,
            'total_amount': total,
            'paid_amount': paid,
            'outstanding': outstanding,
            'days_overdue': days_late,
            'status': row.status.value
        })
    
    return defaulter_list


# ===== STUDENT-SPECIFIC HELPERS =====

def get_student_fee_details(session: Session, student_id: int, session_id: int = None) -> dict:
    """Get complete fee details for a student"""
    
    query = session.query(StudentFee).filter_by(student_id=student_id)
    if session_id:
        query = query.filter_by(session_id=session_id)
    
    student_fees = query.all()
    
    fee_details = []
    total_fees = 0
    total_paid = 0
    total_outstanding = 0
    
    for sf in student_fees:
        fee_calc = calculate_student_fee_total(session, sf.id)
        
        # Get receipts
        receipts = session.query(FeeReceipt).filter_by(
            student_fee_id=sf.id,
            status=PaymentStatusEnum.VERIFIED
        ).order_by(FeeReceipt.payment_date.desc()).all()
        
        receipt_list = [{
            'receipt_number': r.receipt_number,
            'payment_date': r.payment_date.strftime('%Y-%m-%d'),
            'amount_paid': float(r.amount_paid),
            'payment_mode': r.payment_mode.value
        } for r in receipts]
        
        # Get installments
        installments = session.query(FeeInstallment).filter_by(
            student_fee_id=sf.id
        ).order_by(FeeInstallment.installment_number).all()
        
        installment_list = [{
            'installment_number': i.installment_number,
            'installment_name': i.installment_name,
            'due_date': i.due_date.strftime('%Y-%m-%d'),
            'amount': float(i.amount),
            'paid_amount': float(i.paid_amount or 0),
            'balance': float(i.balance_amount),
            'status': i.status.value
        } for i in installments]
        
        fee_details.append({
            'fee_id': sf.id,
            'session_id': sf.session_id,
            'fee_structure_name': sf.fee_structure.structure_name,
            'assigned_date': sf.assigned_date.strftime('%Y-%m-%d'),
            'due_date': sf.due_date.strftime('%Y-%m-%d') if sf.due_date else None,
            'total_amount': fee_calc['total_amount'],
            'discount_amount': fee_calc['discount_amount'],
            'fine_amount': fee_calc['fine_amount'],
            'net_amount': fee_calc['net_amount'],
            'paid_amount': fee_calc['paid_amount'],
            'balance_amount': fee_calc['balance_amount'],
            'status': fee_calc['status'].value,
            'receipts': receipt_list,
            'installments': installment_list
        })
        
        total_fees += fee_calc['net_amount']
        total_paid += fee_calc['paid_amount']
        total_outstanding += fee_calc['balance_amount']
    
    return {
        'student_id': student_id,
        'fees': fee_details,
        'summary': {
            'total_fees': total_fees,
            'total_paid': total_paid,
            'total_outstanding': total_outstanding
        }
    }
