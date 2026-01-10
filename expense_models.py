"""
Expense Management Models
Handles expense tracking, budgets, and financial reporting
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Numeric, Date, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from models import Base

class ExpenseCategoryEnum(enum.Enum):
    SALARIES = "Salaries"
    INFRASTRUCTURE = "Infrastructure"
    UTILITIES = "Utilities"
    SUPPLIES = "Supplies"
    TRANSPORTATION = "Transportation"
    MAINTENANCE = "Maintenance"
    EVENTS = "Events"
    TECHNOLOGY = "Technology"
    TRAINING = "Training"
    MARKETING = "Marketing"
    FOOD = "Food"
    MISCELLANEOUS = "Miscellaneous"

class PaymentMethodEnum(enum.Enum):
    CASH = "Cash"
    CHEQUE = "Cheque"
    BANK_TRANSFER = "Bank Transfer"
    UPI = "UPI"
    CREDIT_CARD = "Credit Card"
    DEBIT_CARD = "Debit Card"

class ExpenseStatusEnum(enum.Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    PAID = "Paid"

# ===== EXPENSE MODEL =====
class Expense(Base):
    __tablename__ = 'expenses'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    
    # Basic Information
    expense_date = Column(Date, nullable=False)
    category = Column(Enum(ExpenseCategoryEnum), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Financial Details
    amount = Column(Numeric(10, 2), nullable=False)
    payment_method = Column(Enum(PaymentMethodEnum), nullable=False)
    invoice_number = Column(String(100), nullable=True)
    receipt_number = Column(String(100), nullable=True)
    
    # Vendor Details
    vendor_name = Column(String(200), nullable=True)
    vendor_contact = Column(String(100), nullable=True)
    
    # Status and Approval
    status = Column(Enum(ExpenseStatusEnum), default=ExpenseStatusEnum.PENDING)
    approved_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    # Additional Info
    remarks = Column(Text, nullable=True)
    attachment_url = Column(String(500), nullable=True)
    
    # Audit Fields
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    creator = relationship("User", foreign_keys=[created_by], backref="created_expenses")
    approver = relationship("User", foreign_keys=[approved_by], backref="approved_expenses")
    
    def __repr__(self):
        return f'<Expense {self.title} - {self.amount}>'

# ===== BUDGET MODEL =====
class Budget(Base):
    __tablename__ = 'budgets'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    
    # Budget Period
    financial_year = Column(String(20), nullable=False)  # e.g., "2024-2025"
    month = Column(Integer, nullable=True)  # 1-12, NULL for yearly budget
    
    # Budget Details
    category = Column(Enum(ExpenseCategoryEnum), nullable=False)
    allocated_amount = Column(Numeric(12, 2), nullable=False)
    spent_amount = Column(Numeric(12, 2), default=0.00)
    
    # Additional Info
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Audit Fields
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    creator = relationship("User", backref="budgets")
    
    @property
    def remaining_amount(self):
        return float(self.allocated_amount) - float(self.spent_amount)
    
    @property
    def utilization_percentage(self):
        if self.allocated_amount > 0:
            return (float(self.spent_amount) / float(self.allocated_amount)) * 100
        return 0
    
    def __repr__(self):
        return f'<Budget {self.category.value} - {self.financial_year}>'

# ===== RECURRING EXPENSE MODEL =====
class RecurringExpense(Base):
    __tablename__ = 'recurring_expenses'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    
    # Basic Information
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(Enum(ExpenseCategoryEnum), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    
    # Recurrence Details
    frequency = Column(String(20), nullable=False)  # daily, weekly, monthly, yearly
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # NULL for indefinite
    
    # Additional Info
    vendor_name = Column(String(200), nullable=True)
    payment_method = Column(Enum(PaymentMethodEnum), nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Audit Fields
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    creator = relationship("User", backref="recurring_expenses")
    
    def __repr__(self):
        return f'<RecurringExpense {self.title} - {self.frequency}>'
