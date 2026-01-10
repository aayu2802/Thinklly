"""
Leave Management Models
Models for leave quota settings and teacher leave balances
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, BigInteger, Index, UniqueConstraint, DECIMAL, Date, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, date
import enum
from models import Base


class LeaveTypeEnum(enum.Enum):
    """Leave type enumeration"""
    CL = "CL"
    SL = "SL"
    EL = "EL"
    HALF_DAY = "Half-day"
    LOP = "LOP"
    DUTY_LEAVE = "Duty Leave"
    MATERNITY = "Maternity"


class StudentLeaveTypeEnum(enum.Enum):
    """Student leave type enumeration"""
    SICK_LEAVE = "Sick Leave"
    CASUAL_LEAVE = "Casual Leave"
    MEDICAL_LEAVE = "Medical Leave"
    FAMILY_EMERGENCY = "Family Emergency"
    OTHER = "Other"


class StudentLeaveStatusEnum(enum.Enum):
    """Student leave status enumeration"""
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    PATERNITY = "Paternity"


class LeaveStatusEnum(enum.Enum):
    """Leave application status enumeration"""
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"


class HalfDayPeriodEnum(enum.Enum):
    """Half day period enumeration"""
    FIRST_HALF = "First Half"
    SECOND_HALF = "Second Half"

class LeaveQuotaSettings(Base):
    """School-level leave quota configuration per academic year"""
    __tablename__ = 'leave_quota_settings'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'academic_year', name='unique_tenant_year'),
        Index('idx_tenant_active', 'tenant_id', 'is_active', 'academic_year'),
    )
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    academic_year = Column(String(10), nullable=False)  # "2024-25"
    
    # Leave Quotas
    cl_quota = Column(DECIMAL(4, 1), default=12.0, nullable=False)
    sl_quota = Column(DECIMAL(4, 1), default=12.0, nullable=False)
    el_quota = Column(DECIMAL(4, 1), default=15.0, nullable=False)
    maternity_quota = Column(DECIMAL(4, 1), default=180.0, nullable=False)
    paternity_quota = Column(DECIMAL(4, 1), default=15.0, nullable=False)
    
    # Policy Settings
    allow_half_day = Column(Boolean, default=True)
    allow_lop = Column(Boolean, default=True)
    duty_leave_unlimited = Column(Boolean, default=True)
    max_continuous_days = Column(Integer, default=30)
    min_advance_days = Column(Integer, default=1)
    weekend_counted = Column(Boolean, default=False)
    
    # Metadata
    is_active = Column(Boolean, default=True)
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", backref="leave_quota_settings_list")
    
    def __repr__(self):
        return f"<LeaveQuotaSettings tenant_id={self.tenant_id} year={self.academic_year}>"
    
    def to_dict(self):
        """Convert to dictionary for JSON responses"""
        return {
            'id': self.id,
            'academic_year': self.academic_year,
            'cl_quota': float(self.cl_quota),
            'sl_quota': float(self.sl_quota),
            'el_quota': float(self.el_quota),
            'maternity_quota': float(self.maternity_quota),
            'paternity_quota': float(self.paternity_quota),
            'allow_half_day': self.allow_half_day,
            'allow_lop': self.allow_lop,
            'duty_leave_unlimited': self.duty_leave_unlimited,
            'max_continuous_days': self.max_continuous_days,
            'min_advance_days': self.min_advance_days,
            'weekend_counted': self.weekend_counted,
            'is_active': self.is_active
        }


class TeacherLeaveBalance(Base):
    """Individual teacher leave balance per academic year"""
    __tablename__ = 'teacher_leave_balance'
    __table_args__ = (
        UniqueConstraint('teacher_id', 'academic_year', name='unique_teacher_year'),
        Index('idx_tenant_year', 'tenant_id', 'academic_year'),
        Index('idx_teacher', 'teacher_id'),
        Index('idx_balance_check', 'teacher_id', 'academic_year'),
    )
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False)
    academic_year = Column(String(10), nullable=False)
    
    # CL - Casual Leave
    cl_total = Column(DECIMAL(4, 1), default=12.0, nullable=False)
    cl_taken = Column(DECIMAL(4, 1), default=0, nullable=False)
    cl_pending = Column(DECIMAL(4, 1), default=0, nullable=False)
    # cl_balance is computed column in database
    
    # SL - Sick Leave
    sl_total = Column(DECIMAL(4, 1), default=12.0, nullable=False)
    sl_taken = Column(DECIMAL(4, 1), default=0, nullable=False)
    sl_pending = Column(DECIMAL(4, 1), default=0, nullable=False)
    # sl_balance is computed column in database
    
    # EL - Earned Leave
    el_total = Column(DECIMAL(4, 1), default=15.0, nullable=False)
    el_taken = Column(DECIMAL(4, 1), default=0, nullable=False)
    el_pending = Column(DECIMAL(4, 1), default=0, nullable=False)
    # el_balance is computed column in database
    
    # Maternity Leave
    maternity_total = Column(DECIMAL(4, 1), default=180.0, nullable=False)
    maternity_taken = Column(DECIMAL(4, 1), default=0, nullable=False)
    maternity_pending = Column(DECIMAL(4, 1), default=0, nullable=False)
    # maternity_balance is computed column in database
    
    # Paternity Leave
    paternity_total = Column(DECIMAL(4, 1), default=15.0, nullable=False)
    paternity_taken = Column(DECIMAL(4, 1), default=0, nullable=False)
    paternity_pending = Column(DECIMAL(4, 1), default=0, nullable=False)
    # paternity_balance is computed column in database
    
    # Other Leaves (no quota)
    lop_taken = Column(DECIMAL(4, 1), default=0, nullable=False)
    duty_leave_taken = Column(DECIMAL(4, 1), default=0, nullable=False)
    
    # Carry Forward
    el_carried_forward = Column(DECIMAL(4, 1), default=0, nullable=False)
    
    # Metadata
    notes = Column(Text, nullable=True)
    last_reset_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")
    teacher = relationship("Teacher", backref="leave_balances")
    
    def __repr__(self):
        return f"<TeacherLeaveBalance teacher_id={self.teacher_id} year={self.academic_year}>"
    
    @property
    def cl_balance(self):
        """Calculate CL balance"""
        return float(self.cl_total - self.cl_taken - self.cl_pending)
    
    @property
    def sl_balance(self):
        """Calculate SL balance"""
        return float(self.sl_total - self.sl_taken - self.sl_pending)
    
    @property
    def el_balance(self):
        """Calculate EL balance"""
        return float(self.el_total - self.el_taken - self.el_pending)
    
    @property
    def maternity_balance(self):
        """Calculate Maternity balance"""
        return float(self.maternity_total - self.maternity_taken - self.maternity_pending)
    
    @property
    def paternity_balance(self):
        """Calculate Paternity balance"""
        return float(self.paternity_total - self.paternity_taken - self.paternity_pending)
    
    def to_dict(self):
        """Convert to dictionary for JSON responses"""
        return {
            'id': self.id,
            'teacher_id': self.teacher_id,
            'academic_year': self.academic_year,
            'cl': {
                'total': float(self.cl_total),
                'taken': float(self.cl_taken),
                'pending': float(self.cl_pending),
                'balance': self.cl_balance
            },
            'sl': {
                'total': float(self.sl_total),
                'taken': float(self.sl_taken),
                'pending': float(self.sl_pending),
                'balance': self.sl_balance
            },
            'el': {
                'total': float(self.el_total),
                'taken': float(self.el_taken),
                'pending': float(self.el_pending),
                'balance': self.el_balance
            },
            'maternity': {
                'total': float(self.maternity_total),
                'taken': float(self.maternity_taken),
                'pending': float(self.maternity_pending),
                'balance': self.maternity_balance
            },
            'paternity': {
                'total': float(self.paternity_total),
                'taken': float(self.paternity_taken),
                'pending': float(self.paternity_pending),
                'balance': self.paternity_balance
            },
            'lop_taken': float(self.lop_taken),
            'duty_leave_taken': float(self.duty_leave_taken)
        }


class TeacherLeaveApplication(Base):
    """Teacher leave application with approval workflow"""
    __tablename__ = 'teacher_leave_applications'
    __table_args__ = (
        Index('idx_tenant_teacher', 'tenant_id', 'teacher_id'),
        Index('idx_status', 'status', 'applied_date'),
        Index('idx_dates', 'start_date', 'end_date'),
        Index('idx_tenant_status', 'tenant_id', 'status', 'applied_date'),
        Index('idx_teacher_year', 'teacher_id', 'academic_year', 'status'),
    )
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False)
    
    # Leave Details
    leave_type = Column(Enum(LeaveTypeEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_half_day = Column(Boolean, default=False)
    half_day_period = Column(Enum(HalfDayPeriodEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=True)
    total_days = Column(DECIMAL(3, 1), nullable=False)
    
    # Request Information
    reason = Column(Text, nullable=False)
    contact_during_leave = Column(String(100), nullable=True)
    address_during_leave = Column(Text, nullable=True)
    
    # Approval Workflow
    status = Column(Enum(LeaveStatusEnum, values_callable=lambda obj: [e.value for e in obj]), default=LeaveStatusEnum.PENDING)
    applied_date = Column(DateTime, default=datetime.utcnow)
    approved_by = Column(BigInteger, nullable=True)  # Admin user ID
    approved_date = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    admin_notes = Column(Text, nullable=True)
    
    # Metadata
    academic_year = Column(String(10), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")
    teacher = relationship("Teacher", backref="leave_applications")
    
    def __repr__(self):
        return f"<TeacherLeaveApplication id={self.id} teacher_id={self.teacher_id} type={self.leave_type.value} status={self.status.value}>"
    
    @property
    def status_badge_class(self):
        """Get Bootstrap badge class for status"""
        badge_map = {
            LeaveStatusEnum.PENDING: 'warning',
            LeaveStatusEnum.APPROVED: 'success',
            LeaveStatusEnum.REJECTED: 'danger',
            LeaveStatusEnum.CANCELLED: 'secondary'
        }
        return badge_map.get(self.status, 'secondary')
    
    @property
    def leave_type_display(self):
        """Get display name for leave type"""
        return self.leave_type.value
    
    @property
    def status_display(self):
        """Get display name for status"""
        return self.status.value
    
    @property
    def duration_display(self):
        """Get human-readable duration"""
        if self.is_half_day:
            return f"0.5 day ({self.half_day_period.value if self.half_day_period else 'Half'})"
        elif self.total_days == 1:
            return "1 day"
        else:
            return f"{float(self.total_days)} days"
    
    def to_dict(self):
        """Convert to dictionary for JSON responses"""
        return {
            'id': self.id,
            'teacher_id': self.teacher_id,
            'leave_type': self.leave_type.value,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'is_half_day': self.is_half_day,
            'half_day_period': self.half_day_period.value if self.half_day_period else None,
            'total_days': float(self.total_days),
            'reason': self.reason,
            'status': self.status.value,
            'status_badge': self.status_badge_class,
            'applied_date': self.applied_date.isoformat() if self.applied_date else None,
            'approved_date': self.approved_date.isoformat() if self.approved_date else None,
            'rejection_reason': self.rejection_reason,
            'academic_year': self.academic_year
        }


class StudentLeave(Base):
    """Student Leave Application Model"""
    __tablename__ = 'student_leaves'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    class_id = Column(Integer, ForeignKey('classes.id'), nullable=False)
    leave_type = Column(Enum(StudentLeaveTypeEnum), nullable=False)
    from_date = Column(Date, nullable=False)
    to_date = Column(Date, nullable=False)
    is_half_day = Column(Boolean, default=False)
    half_day_period = Column(String(20))
    reason = Column(Text, nullable=False)
    status = Column(Enum(StudentLeaveStatusEnum), default=StudentLeaveStatusEnum.PENDING, nullable=False)
    supporting_documents = Column(Text)  # JSON string of file paths
    applied_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_by = Column(Integer, ForeignKey('users.id'))
    reviewed_by_type = Column(String(50))  # 'admin' or 'teacher'
    reviewed_date = Column(DateTime)
    admin_remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship('Tenant', foreign_keys=[tenant_id])
    student = relationship('Student', foreign_keys=[student_id], backref='student_leaves')
    student_class = relationship('Class', foreign_keys=[class_id])
    reviewer = relationship('User', foreign_keys=[reviewed_by])
    
    @property
    def documents(self):
        """Get documents as list"""
        if self.supporting_documents:
            import json
            try:
                return json.loads(self.supporting_documents)
            except:
                return []
        return []
    
    def set_documents(self, doc_paths):
        """Set documents from list"""
        import json
        self.supporting_documents = json.dumps(doc_paths) if doc_paths else None
    
    @property
    def total_days(self):
        """Calculate total days of leave"""
        if self.is_half_day:
            return 0.5
        delta = self.to_date - self.from_date
        return delta.days + 1
    
    def __repr__(self):
        return f"<StudentLeave {self.id} - {self.student_id} - {self.status.value}>"
