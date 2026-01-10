"""
Library Management Models
Multi-tenant library management system for tracking books and student issues
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Numeric, Date, Enum, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from models import Base
from datetime import datetime, date
import enum

# ===== ENUMS =====
class BookStatusEnum(enum.Enum):
    AVAILABLE = "Available"
    ISSUED = "Issued"
    DAMAGED = "Damaged"
    LOST = "Lost"
    UNDER_MAINTENANCE = "Under Maintenance"

class IssueStatusEnum(enum.Enum):
    ISSUED = "Issued"
    RETURNED = "Returned"
    OVERDUE = "Overdue"
    LOST = "Lost"

class BookConditionEnum(enum.Enum):
    NEW = "New"
    GOOD = "Good"
    FAIR = "Fair"
    POOR = "Poor"
    DAMAGED = "Damaged"

# ===== MODELS =====

class LibraryCategory(Base):
    """Library book categories/genres"""
    __tablename__ = 'library_categories'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    
    name = Column(String(100), nullable=False)  # Fiction, Science, Mathematics, etc.
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    books = relationship("LibraryBook", back_populates="category")
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='uq_library_category_tenant_name'),
        Index('idx_library_category_tenant', 'tenant_id'),
    )
    
    def __repr__(self):
        return f'<LibraryCategory {self.name}>'


class LibraryBook(Base):
    """Library books inventory"""
    __tablename__ = 'library_books'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    category_id = Column(Integer, ForeignKey('library_categories.id'), nullable=True)
    
    # Book Information
    accession_number = Column(String(50), nullable=False)  # Unique library identifier
    isbn = Column(String(20), nullable=True)
    title = Column(String(255), nullable=False)
    author = Column(String(255), nullable=False)
    publisher = Column(String(200), nullable=True)
    publication_year = Column(Integer, nullable=True)
    edition = Column(String(50), nullable=True)
    language = Column(String(50), default='English')
    
    # Physical Details
    pages = Column(Integer, nullable=True)
    price = Column(Numeric(10, 2), nullable=True)
    condition = Column(Enum(BookConditionEnum, values_callable=lambda obj: [e.value for e in obj]), default=BookConditionEnum.GOOD)
    rack_number = Column(String(50), nullable=True)  # Physical location
    
    # Status
    status = Column(Enum(BookStatusEnum, values_callable=lambda obj: [e.value for e in obj]), default=BookStatusEnum.AVAILABLE)
    total_copies = Column(Integer, default=1)
    available_copies = Column(Integer, default=1)
    
    # Metadata
    description = Column(Text, nullable=True)
    cover_image_url = Column(String(500), nullable=True)
    added_date = Column(Date, default=date.today)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    category = relationship("LibraryCategory", back_populates="books")
    issues = relationship("LibraryIssue", back_populates="book", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'accession_number', name='uq_library_book_tenant_accession'),
        Index('idx_library_book_tenant', 'tenant_id'),
        Index('idx_library_book_status', 'tenant_id', 'status'),
        Index('idx_library_book_isbn', 'isbn'),
    )
    
    def __repr__(self):
        return f'<LibraryBook {self.accession_number}: {self.title}>'


class LibraryIssue(Base):
    """Book issue/return tracking"""
    __tablename__ = 'library_issues'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    book_id = Column(Integer, ForeignKey('library_books.id'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    
    # Issue Details
    issue_number = Column(String(50), nullable=False)  # Auto-generated: ISS-YYYYMM-XXXXX
    issue_date = Column(Date, nullable=False, default=date.today)
    due_date = Column(Date, nullable=False)
    return_date = Column(Date, nullable=True)
    
    # Status
    status = Column(Enum(IssueStatusEnum, values_callable=lambda obj: [e.value for e in obj]), default=IssueStatusEnum.ISSUED)
    
    # Condition tracking
    issue_condition = Column(Enum(BookConditionEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=True)
    return_condition = Column(Enum(BookConditionEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=True)
    
    # Fine calculation
    fine_amount = Column(Numeric(10, 2), default=0.00)
    fine_paid = Column(Boolean, default=False)
    fine_paid_date = Column(Date, nullable=True)
    
    # Notes
    issue_remarks = Column(Text, nullable=True)
    return_remarks = Column(Text, nullable=True)
    
    # Issued by
    issued_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    returned_by_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    book = relationship("LibraryBook", back_populates="issues")
    student = relationship("Student")
    issued_by = relationship("User", foreign_keys=[issued_by_user_id])
    returned_by = relationship("User", foreign_keys=[returned_by_user_id])
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'issue_number', name='uq_library_issue_tenant_number'),
        Index('idx_library_issue_tenant', 'tenant_id'),
        Index('idx_library_issue_student', 'tenant_id', 'student_id'),
        Index('idx_library_issue_book', 'tenant_id', 'book_id'),
        Index('idx_library_issue_status', 'tenant_id', 'status'),
        Index('idx_library_issue_due_date', 'tenant_id', 'due_date', 'status'),
    )
    
    def __repr__(self):
        return f'<LibraryIssue {self.issue_number}: Book#{self.book_id} to Student#{self.student_id}>'
    
    @property
    def is_overdue(self):
        """Check if book return is overdue"""
        if self.status == IssueStatusEnum.ISSUED and self.due_date < date.today():
            return True
        return False
    
    @property
    def days_overdue(self):
        """Calculate number of days overdue"""
        if self.is_overdue:
            return (date.today() - self.due_date).days
        return 0


class LibrarySettings(Base):
    """Library configuration settings per tenant"""
    __tablename__ = 'library_settings'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, unique=True)
    
    # Issue Rules
    max_books_per_student = Column(Integer, default=3)
    issue_duration_days = Column(Integer, default=14)  # Default 2 weeks
    
    # Fine Configuration
    fine_per_day = Column(Numeric(10, 2), default=5.00)
    max_fine_amount = Column(Numeric(10, 2), default=500.00)
    grace_period_days = Column(Integer, default=0)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_library_settings_tenant', 'tenant_id'),
    )
    
    def __repr__(self):
        return f'<LibrarySettings Tenant#{self.tenant_id}>'
