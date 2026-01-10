"""
Fee Management Models for Multi-Tenant School Management System
This file contains all fee-related models including fee structures, payments, receipts, and analytics
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Numeric, Date, Enum, BigInteger, Index, UniqueConstraint, DECIMAL, Computed
from sqlalchemy.orm import relationship
from datetime import datetime, date
from models import Base
import enum


# ===== ENUMS =====

class FeeStatusEnum(enum.Enum):
    PENDING = "Pending"
    PARTIALLY_PAID = "Partially Paid"
    PAID = "Paid"
    OVERDUE = "Overdue"
    WAIVED = "Waived"
    CANCELLED = "Cancelled"


class PaymentModeEnum(enum.Enum):
    CASH = "Cash"
    CHEQUE = "Cheque"
    UPI = "UPI"
    BANK_TRANSFER = "Bank Transfer"
    DEMAND_DRAFT = "Demand Draft"
    DEBIT_CARD = "Debit Card"
    CREDIT_CARD = "Credit Card"
    ONLINE = "Online"
    OTHER = "Other"


class PaymentStatusEnum(enum.Enum):
    PENDING = "Pending"
    VERIFIED = "Verified"
    CANCELLED = "Cancelled"
    REVERSED = "Reversed"


class ConcessionTypeEnum(enum.Enum):
    SCHOLARSHIP = "Scholarship"
    CATEGORY_BASED = "Category Based"
    SIBLING_DISCOUNT = "Sibling Discount"
    MERIT_BASED = "Merit Based"
    STAFF_CHILD = "Staff Child"
    SPORTS_QUOTA = "Sports Quota"
    FINANCIAL_AID = "Financial Aid"
    OTHER = "Other"


class ConcessionModeEnum(enum.Enum):
    PERCENTAGE = "Percentage"
    FIXED_AMOUNT = "Fixed Amount"


class FineTypeEnum(enum.Enum):
    LATE_PAYMENT = "Late Payment"
    BOUNCED_CHEQUE = "Bounced Cheque"
    PENALTY = "Penalty"
    OTHER = "Other"


class InstallmentStatusEnum(enum.Enum):
    PENDING = "Pending"
    PAID = "Paid"
    OVERDUE = "Overdue"
    WAIVED = "Waived"


# ===== FEE CATEGORY MODEL =====

class FeeCategory(Base):
    """Fee categories like Tuition, Library, Lab, Sports, Transport, etc."""
    __tablename__ = 'fee_categories'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'category_code', name='unique_tenant_category_code'),
        Index('idx_fee_cat_tenant', 'tenant_id'),
        Index('idx_fee_cat_active', 'is_active'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    category_name = Column(String(100), nullable=False)
    category_code = Column(String(20), nullable=False)
    description = Column(Text, nullable=True)
    is_mandatory = Column(Boolean, default=True)  # Mandatory for all students
    is_active = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    structure_details = relationship("FeeStructureDetail", back_populates="category", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<FeeCategory {self.category_name} ({self.category_code})>"


# ===== FEE STRUCTURE MODEL =====

class FeeStructure(Base):
    """Fee structures defining fees for specific class/session combinations"""
    __tablename__ = 'fee_structures'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'session_id', 'class_id', 'structure_name', name='unique_tenant_session_class_structure'),
        Index('idx_fee_struct_tenant', 'tenant_id'),
        Index('idx_fee_struct_session', 'session_id'),
        Index('idx_fee_struct_class', 'class_id'),
        Index('idx_fee_struct_active', 'is_active'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    session_id = Column(Integer, ForeignKey('academic_sessions.id', ondelete='CASCADE'), nullable=False)
    class_id = Column(Integer, ForeignKey('classes.id', ondelete='CASCADE'), nullable=False)
    structure_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    valid_from = Column(Date, nullable=False)
    valid_to = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    session = relationship("AcademicSession")
    student_class = relationship("Class")
    details = relationship("FeeStructureDetail", back_populates="structure", cascade="all, delete-orphan")
    student_fees = relationship("StudentFee", back_populates="fee_structure", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<FeeStructure {self.structure_name}>"


# ===== FEE STRUCTURE DETAIL MODEL =====

class FeeStructureDetail(Base):
    """Individual fee components within a fee structure"""
    __tablename__ = 'fee_structure_details'
    __table_args__ = (
        UniqueConstraint('fee_structure_id', 'fee_category_id', 'installment_number', name='unique_structure_category_installment'),
        Index('idx_fee_detail_structure', 'fee_structure_id'),
        Index('idx_fee_detail_category', 'fee_category_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    fee_structure_id = Column(BigInteger, ForeignKey('fee_structures.id', ondelete='CASCADE'), nullable=False)
    fee_category_id = Column(BigInteger, ForeignKey('fee_categories.id', ondelete='CASCADE'), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    due_date = Column(Date, nullable=True)
    installment_number = Column(Integer, default=1)  # For quarterly/monthly installments
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    structure = relationship("FeeStructure", back_populates="details")
    category = relationship("FeeCategory", back_populates="structure_details")

    def __repr__(self):
        return f"<FeeStructureDetail {self.category.category_name}: {self.amount}>"


# ===== STUDENT FEE MODEL =====

class StudentFee(Base):
    """Fee assigned to individual students"""
    __tablename__ = 'student_fees'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'student_id', 'session_id', 'fee_structure_id', name='unique_student_session_fee'),
        Index('idx_student_fee_tenant', 'tenant_id'),
        Index('idx_student_fee_student', 'student_id'),
        Index('idx_student_fee_session', 'session_id'),
        Index('idx_student_fee_status', 'status'),
        Index('idx_student_fee_date', 'assigned_date'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    session_id = Column(Integer, ForeignKey('academic_sessions.id', ondelete='CASCADE'), nullable=False)
    fee_structure_id = Column(BigInteger, ForeignKey('fee_structures.id', ondelete='CASCADE'), nullable=False)
    
    # Amounts
    total_amount = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    discount_amount = Column(DECIMAL(10, 2), default=0.00)
    fine_amount = Column(DECIMAL(10, 2), default=0.00)
    net_amount = Column(DECIMAL(10, 2), Computed("total_amount - discount_amount + fine_amount"))
    paid_amount = Column(DECIMAL(10, 2), default=0.00)
    balance_amount = Column(DECIMAL(10, 2), Computed("total_amount - discount_amount + fine_amount - paid_amount"))
    
    # Discount details
    discount_reason = Column(Text, nullable=True)
    
    # Status and dates
    status = Column(Enum(FeeStatusEnum, values_callable=lambda obj: [e.value for e in obj]), default=FeeStatusEnum.PENDING)
    assigned_date = Column(Date, default=date.today)
    due_date = Column(Date, nullable=True)
    
    # Metadata
    remarks = Column(Text, nullable=True)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    student = relationship("Student", backref="fees")
    session = relationship("AcademicSession")
    fee_structure = relationship("FeeStructure", back_populates="student_fees")
    concessions = relationship("StudentFeeConcession", back_populates="student_fee", cascade="all, delete-orphan")
    fines = relationship("FeeFine", back_populates="student_fee", cascade="all, delete-orphan")
    receipts = relationship("FeeReceipt", back_populates="student_fee", cascade="all, delete-orphan")
    installments = relationship("FeeInstallment", back_populates="student_fee", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<StudentFee student_id={self.student_id} session_id={self.session_id} status={self.status.value}>"


# ===== STUDENT FEE CONCESSION MODEL =====

class StudentFeeConcession(Base):
    """Concessions, scholarships, and discounts applied to student fees"""
    __tablename__ = 'student_fee_concessions'
    __table_args__ = (
        Index('idx_concession_tenant', 'tenant_id'),
        Index('idx_concession_student_fee', 'student_fee_id'),
        Index('idx_concession_type', 'concession_type'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    student_fee_id = Column(BigInteger, ForeignKey('student_fees.id', ondelete='CASCADE'), nullable=False)
    concession_type = Column(Enum(ConcessionTypeEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    concession_mode = Column(Enum(ConcessionModeEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    concession_value = Column(DECIMAL(10, 2), nullable=False)  # Percentage or Amount
    actual_discount = Column(DECIMAL(10, 2), nullable=False)  # Calculated discount amount
    reason = Column(Text, nullable=True)
    
    # Approval details
    approved_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    # Validity
    valid_from = Column(Date, nullable=True)
    valid_to = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    student_fee = relationship("StudentFee", back_populates="concessions")
    approver = relationship("User")

    def __repr__(self):
        return f"<StudentFeeConcession type={self.concession_type.value} discount={self.actual_discount}>"


# ===== FEE RECEIPT MODEL =====

class FeeReceipt(Base):
    """Payment receipts for student fees"""
    __tablename__ = 'fee_receipts'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'receipt_number', name='unique_tenant_receipt_number'),
        Index('idx_receipt_tenant', 'tenant_id'),
        Index('idx_receipt_student', 'student_id'),
        Index('idx_receipt_student_fee', 'student_fee_id'),
        Index('idx_receipt_number', 'receipt_number'),
        Index('idx_receipt_date', 'receipt_date'),
        Index('idx_receipt_status', 'status'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    student_fee_id = Column(BigInteger, ForeignKey('student_fees.id', ondelete='CASCADE'), nullable=False)
    
    # Receipt details
    receipt_number = Column(String(50), nullable=False, unique=True)
    receipt_date = Column(Date, nullable=False, default=date.today)
    payment_date = Column(Date, nullable=False, default=date.today)
    
    # Payment details
    amount_paid = Column(DECIMAL(10, 2), nullable=False)
    fine_amount = Column(DECIMAL(10, 2), default=0.00)
    total_amount = Column(DECIMAL(10, 2), Computed("amount_paid + fine_amount"))
    payment_mode = Column(Enum(PaymentModeEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    payment_reference = Column(String(100), nullable=True)  # Cheque/Transaction number
    bank_name = Column(String(100), nullable=True)
    
    # Status
    status = Column(Enum(PaymentStatusEnum, values_callable=lambda obj: [e.value for e in obj]), default=PaymentStatusEnum.PENDING)
    remarks = Column(Text, nullable=True)
    
    # User tracking
    generated_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    verified_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    cancelled_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    student = relationship("Student", backref="fee_receipts")
    student_fee = relationship("StudentFee", back_populates="receipts")
    generator = relationship("User", foreign_keys=[generated_by])
    verifier = relationship("User", foreign_keys=[verified_by])
    canceller = relationship("User", foreign_keys=[cancelled_by])

    def __repr__(self):
        return f"<FeeReceipt {self.receipt_number} amount={self.amount_paid}>"


# ===== FEE FINE MODEL =====

class FeeFine(Base):
    """Fines applied to student fees for late payment, etc."""
    __tablename__ = 'fee_fines'
    __table_args__ = (
        Index('idx_fine_tenant', 'tenant_id'),
        Index('idx_fine_student_fee', 'student_fee_id'),
        Index('idx_fine_date', 'fine_date'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    student_fee_id = Column(BigInteger, ForeignKey('student_fees.id', ondelete='CASCADE'), nullable=False)
    fine_type = Column(Enum(FineTypeEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    fine_amount = Column(DECIMAL(10, 2), nullable=False)
    fine_date = Column(Date, nullable=False, default=date.today)
    reason = Column(Text, nullable=True)
    
    # Waiver details
    waived = Column(Boolean, default=False)
    waived_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    waived_at = Column(DateTime, nullable=True)
    waived_reason = Column(Text, nullable=True)
    
    # Metadata
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    student_fee = relationship("StudentFee", back_populates="fines")
    waiver_user = relationship("User")

    def __repr__(self):
        return f"<FeeFine type={self.fine_type.value} amount={self.fine_amount}>"


# ===== FEE INSTALLMENT MODEL =====

class FeeInstallment(Base):
    """Installment plan for student fees"""
    __tablename__ = 'fee_installments'
    __table_args__ = (
        UniqueConstraint('student_fee_id', 'installment_number', name='unique_student_fee_installment'),
        Index('idx_installment_tenant', 'tenant_id'),
        Index('idx_installment_student_fee', 'student_fee_id'),
        Index('idx_installment_due_date', 'due_date'),
        Index('idx_installment_status', 'status'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    student_fee_id = Column(BigInteger, ForeignKey('student_fees.id', ondelete='CASCADE'), nullable=False)
    installment_number = Column(Integer, nullable=False)
    installment_name = Column(String(100), nullable=True)  # "First Quarter", "Second Quarter", etc.
    due_date = Column(Date, nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    paid_amount = Column(DECIMAL(10, 2), default=0.00)
    balance_amount = Column(DECIMAL(10, 2), Computed("amount - paid_amount"))
    status = Column(Enum(InstallmentStatusEnum, values_callable=lambda obj: [e.value for e in obj]), default=InstallmentStatusEnum.PENDING)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    student_fee = relationship("StudentFee", back_populates="installments")

    def __repr__(self):
        return f"<FeeInstallment #{self.installment_number} amount={self.amount} status={self.status.value}>"


# ===== FEE COLLECTION SUMMARY MODEL (For Analytics) =====

class FeeCollectionSummary(Base):
    """Daily/Monthly fee collection summary for analytics"""
    __tablename__ = 'fee_collection_summary'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'summary_date', 'summary_type', name='unique_tenant_date_type'),
        Index('idx_collection_tenant', 'tenant_id'),
        Index('idx_collection_date', 'summary_date'),
        Index('idx_collection_type', 'summary_type'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    session_id = Column(Integer, ForeignKey('academic_sessions.id', ondelete='CASCADE'), nullable=True)
    summary_date = Column(Date, nullable=False)
    summary_type = Column(String(20), nullable=False)  # 'daily', 'monthly', 'yearly'
    
    # Collection statistics
    total_receipts = Column(Integer, default=0)
    total_collected = Column(DECIMAL(12, 2), default=0.00)
    cash_collected = Column(DECIMAL(12, 2), default=0.00)
    online_collected = Column(DECIMAL(12, 2), default=0.00)
    cheque_collected = Column(DECIMAL(12, 2), default=0.00)
    fine_collected = Column(DECIMAL(12, 2), default=0.00)
    
    # Metadata
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    session = relationship("AcademicSession")

    def __repr__(self):
        return f"<FeeCollectionSummary date={self.summary_date} collected={self.total_collected}>"
