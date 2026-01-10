"""
Teacher-related Models for Multi-Tenant School Management System
This file contains all teacher, department, designation, and related models
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Numeric, Date, Enum, BigInteger, Index, UniqueConstraint, Time, DECIMAL, Computed
from sqlalchemy.orm import relationship
from datetime import datetime
from models import Base
import enum

# ===== ENUMS =====
class GenderEnum(enum.Enum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"

class EmployeeStatusEnum(enum.Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    ON_LEAVE = "On Leave"
    RESIGNED = "Resigned"

class SubjectTypeEnum(enum.Enum):
    ACADEMIC = "Academic"
    CO_CURRICULAR = "Co-curricular"
    EXTRA_CURRICULAR = "Extra-curricular"

class ProficiencyLevelEnum(enum.Enum):
    EXPERT = "Expert"
    ADVANCED = "Advanced"
    INTERMEDIATE = "Intermediate"
    BASIC = "Basic"

class QualificationTypeEnum(enum.Enum):
    B_ED = "B.Ed"
    M_ED = "M.Ed"
    PHD = "PhD"
    M_SC = "M.Sc"
    M_A = "M.A"
    B_SC = "B.Sc"
    B_A = "B.A"
    B_PED = "B.PEd"
    M_PED = "M.PEd"
    NET = "NET"
    CTET = "CTET"
    OTHER = "Other"

class CertificationTypeEnum(enum.Enum):
    CTET = "CTET"
    TET = "TET"
    NET = "NET"
    PGCTE = "PGCTE"
    MONTESSORI = "Montessori"
    FIRST_AID = "First-Aid"
    OTHER = "Other"

class DocumentTypeEnum(enum.Enum):
    RESUME = "Resume"
    DEGREE = "Degree"
    MARKSHEET = "Marksheet"
    ID_PROOF = "ID Proof"
    EXPERIENCE_LETTER = "Experience Letter"
    POLICE_VERIFICATION = "Police Verification"
    MEDICAL_CERTIFICATE = "Medical Certificate"
    OTHER = "Other"

class AccountTypeEnum(enum.Enum):
    SAVINGS = "Savings"
    CURRENT = "Current"
    SALARY = "Salary"
    NRE = "NRE"
    NRO = "NRO"

class LeaveTypeEnum(enum.Enum):
    CASUAL = "Casual"
    SICK = "Sick"
    EARNED = "Earned"
    MATERNITY = "Maternity"
    PATERNITY = "Paternity"
    UNPAID = "Unpaid"
    OTHER = "Other"

class LeaveStatusEnum(enum.Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"

class AttendanceStatusEnum(enum.Enum):
    PRESENT = "Present"
    ABSENT = "Absent"
    HALF_DAY = "Half-Day"
    ON_LEAVE = "On Leave"
    HOLIDAY = "Holiday"
    WEEK_OFF = "Week Off"

# ===== CORE MODELS =====

class Teacher(Base):
    __tablename__ = 'teachers'
    __table_args__ = (
        Index('ix_teachers_tenant_id', 'tenant_id'),
        UniqueConstraint('employee_id', name='uq_teachers_employee_id'),
        UniqueConstraint('email', name='uq_teachers_email'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', name='fk_teacher_tenant'), nullable=False, index=True)

    # Basic Info
    employee_id = Column(String(50), nullable=False, unique=True)
    first_name = Column(String(100), nullable=False)
    middle_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=False)
    gender = Column(Enum(GenderEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    photo_url = Column(String(500), nullable=True)

    # Contact
    email = Column(String(150), nullable=False, unique=True)
    phone_primary = Column(String(20), nullable=False)
    phone_alternate = Column(String(20), nullable=True)
    address_street = Column(String(255), nullable=True)
    address_city = Column(String(100), nullable=True)
    address_state = Column(String(100), nullable=True)
    address_pincode = Column(String(6), nullable=True)
    emergency_contact_name = Column(String(150), nullable=True)
    emergency_contact_number = Column(String(20), nullable=True)

    # Professional
    joining_date = Column(Date, nullable=False)
    employee_status = Column(Enum(EmployeeStatusEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=EmployeeStatusEnum.ACTIVE)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", backref="teachers_list")
    departments = relationship("TeacherDepartment", back_populates="teacher", cascade="all, delete-orphan")
    designations = relationship("TeacherDesignation", back_populates="teacher", cascade="all, delete-orphan")
    subjects = relationship("TeacherSubject", back_populates="teacher", cascade="all, delete-orphan")
    qualifications = relationship("Qualification", back_populates="teacher", cascade="all, delete-orphan")
    experiences = relationship("TeacherExperience", back_populates="teacher", cascade="all, delete-orphan")
    certifications = relationship("TeacherCertification", back_populates="teacher", cascade="all, delete-orphan")
    documents = relationship("TeacherDocument", back_populates="teacher", cascade="all, delete-orphan")
    leaves = relationship("TeacherLeave", back_populates="teacher", cascade="all, delete-orphan")
    attendance_records = relationship("TeacherAttendance", back_populates="teacher", cascade="all, delete-orphan")
    banking_details = relationship("TeacherBankingDetails", back_populates="teacher", uselist=False, cascade="all, delete-orphan")
    salary_record = relationship("TeacherSalary", back_populates="teacher", uselist=False, cascade="all, delete-orphan",
                                  primaryjoin="and_(Teacher.id==foreign(TeacherSalary.teacher_id), TeacherSalary.is_active==True)")

    @property
    def full_name(self):
        if self.middle_name:
            return f"{self.first_name} {self.middle_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"
    
    @property
    def salary(self):
        """Get current active salary"""
        return self.salary_record

    def __repr__(self):
        return f"<Teacher id={self.id} employee_id={self.employee_id} name={self.full_name}>"


class Department(Base):
    __tablename__ = 'departments'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='unique_dept_per_tenant'),
        Index('idx_dept_tenant_active', 'tenant_id', 'is_active'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_dept_tenant'), nullable=False)
    name = Column(String(100), nullable=False)
    code = Column(String(20), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", backref="departments_list")
    teacher_departments = relationship("TeacherDepartment", back_populates="department", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Department id={self.id} name={self.name} code={self.code}>"


class Designation(Base):
    __tablename__ = 'designations'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='unique_desig_per_tenant'),
        Index('idx_desig_tenant_active', 'tenant_id', 'is_active'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_desig_tenant'), nullable=False)
    name = Column(String(100), nullable=False)
    code = Column(String(20), nullable=True)
    hierarchy_level = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", backref="designations_list")
    teacher_designations = relationship("TeacherDesignation", back_populates="designation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Designation id={self.id} name={self.name} code={self.code}>"


class Subject(Base):
    """Subject model for academic, co-curricular and extracurricular subjects"""
    __tablename__ = 'subjects'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='unique_subject_per_tenant'),
        Index('idx_subject_tenant_active', 'tenant_id', 'is_active'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_subject_tenant'), nullable=False)
    name = Column(String(100), nullable=False)
    code = Column(String(20), nullable=True)
    # class_id = Column(Integer, ForeignKey('classes.id', ondelete='CASCADE'), nullable=True)  # TODO: Add to database later
    subject_type = Column(Enum(SubjectTypeEnum, values_callable=lambda obj: [e.value for e in obj]), default=SubjectTypeEnum.ACADEMIC)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", backref="subjects_list")
    teacher_subjects = relationship("TeacherSubject", back_populates="subject", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Subject id={self.id} name={self.name} code={self.code}>"


# ===== JUNCTION/ASSOCIATION MODELS =====

class TeacherDepartment(Base):
    __tablename__ = 'teacher_departments'
    __table_args__ = (
        UniqueConstraint('teacher_id', 'department_id', 'tenant_id', name='unique_teacher_dept'),
        Index('idx_tdept_teacher', 'teacher_id'),
        Index('idx_tdept_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_tdept_tenant'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE', name='fk_tdept_teacher'), nullable=False)
    department_id = Column(BigInteger, ForeignKey('departments.id', ondelete='CASCADE', name='fk_tdept_dept'), nullable=False)
    is_primary = Column(Boolean, default=False)
    assigned_date = Column(Date, nullable=False)
    removed_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    teacher = relationship("Teacher", back_populates="departments")
    department = relationship("Department", back_populates="teacher_departments")

    def __repr__(self):
        return f"<TeacherDepartment teacher_id={self.teacher_id} dept_id={self.department_id}>"


class TeacherDesignation(Base):
    __tablename__ = 'teacher_designations'
    __table_args__ = (
        UniqueConstraint('teacher_id', 'designation_id', 'tenant_id', name='unique_teacher_desig'),
        Index('idx_tdesig_teacher', 'teacher_id'),
        Index('idx_tdesig_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_tdesig_tenant'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE', name='fk_tdesig_teacher'), nullable=False)
    designation_id = Column(BigInteger, ForeignKey('designations.id', ondelete='CASCADE', name='fk_tdesig_desig'), nullable=False)
    is_primary = Column(Boolean, default=False)
    assigned_date = Column(Date, nullable=False)
    removed_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    teacher = relationship("Teacher", back_populates="designations")
    designation = relationship("Designation", back_populates="teacher_designations")

    def __repr__(self):
        return f"<TeacherDesignation teacher_id={self.teacher_id} desig_id={self.designation_id}>"


class TeacherSubject(Base):
    __tablename__ = 'teacher_subjects'
    __table_args__ = (
        UniqueConstraint('teacher_id', 'subject_id', 'tenant_id', name='unique_teacher_subject'),
        Index('idx_tsubj_teacher', 'teacher_id'),
        Index('idx_tsubj_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_tsubj_tenant'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE', name='fk_tsubj_teacher'), nullable=False)
    subject_id = Column(BigInteger, ForeignKey('subjects.id', ondelete='CASCADE', name='fk_tsubj_subject'), nullable=False)
    proficiency_level = Column(Enum(ProficiencyLevelEnum, values_callable=lambda obj: [e.value for e in obj]), default=ProficiencyLevelEnum.ADVANCED)
    can_teach_classes = Column(String(200), nullable=True)  # JSON array or comma-separated
    assigned_date = Column(Date, nullable=False)
    removed_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    teacher = relationship("Teacher", back_populates="subjects")
    subject = relationship("Subject", back_populates="teacher_subjects")

    def __repr__(self):
        return f"<TeacherSubject teacher_id={self.teacher_id} subject_id={self.subject_id}>"


# ===== QUALIFICATION & EXPERIENCE MODELS =====

class Qualification(Base):
    __tablename__ = 'qualifications'
    __table_args__ = (
        Index('idx_qual_teacher', 'teacher_id'),
        Index('idx_qual_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_qual_tenant'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE', name='fk_qual_teacher'), nullable=False)
    qualification_type = Column(Enum(QualificationTypeEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    qualification_name = Column(String(100), nullable=False)
    specialization = Column(String(200), nullable=True)
    institution = Column(String(200), nullable=True)
    year_of_completion = Column(Integer, nullable=True)  # Using Integer instead of YEAR for SQLAlchemy compatibility
    total_experience = Column(Integer, nullable=True)
    is_highest = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    teacher = relationship("Teacher", back_populates="qualifications")

    def __repr__(self):
        return f"<Qualification teacher_id={self.teacher_id} type={self.qualification_type.value}>"


class TeacherExperience(Base):
    __tablename__ = 'teacher_experience'
    __table_args__ = (
        Index('idx_exp_teacher', 'teacher_id'),
        Index('idx_exp_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_exp_tenant'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE', name='fk_exp_teacher'), nullable=False)
    institution = Column(String(200), nullable=False)
    role = Column(String(100), nullable=False)
    from_date = Column(Date, nullable=False)
    to_date = Column(Date, nullable=True)  # NULL means current
    duration_months = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    reason_for_leaving = Column(String(255), nullable=True)
    is_verifiable = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    teacher = relationship("Teacher", back_populates="experiences")

    def __repr__(self):
        return f"<TeacherExperience teacher_id={self.teacher_id} institution={self.institution}>"


class TeacherCertification(Base):
    __tablename__ = 'teacher_certifications'
    __table_args__ = (
        Index('idx_cert_teacher', 'teacher_id'),
        Index('idx_cert_tenant', 'tenant_id'),
        Index('idx_cert_validity', 'expiry_date', 'is_valid'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_cert_tenant'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE', name='fk_cert_teacher'), nullable=False)
    certification_type = Column(Enum(CertificationTypeEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    certification_name = Column(String(100), nullable=False)
    issuing_authority = Column(String(200), nullable=True)
    certificate_number = Column(String(100), nullable=True)
    issue_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    is_valid = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    teacher = relationship("Teacher", back_populates="certifications")

    def __repr__(self):
        return f"<TeacherCertification teacher_id={self.teacher_id} type={self.certification_type.value}>"


class TeacherDocument(Base):
    __tablename__ = 'teacher_documents'
    __table_args__ = (
        Index('idx_doc_teacher', 'teacher_id'),
        Index('idx_doc_tenant', 'tenant_id'),
        Index('idx_doc_type', 'doc_type'),
        Index('idx_doc_verified', 'is_verified'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_teacher_doc_tenant'), nullable=False)
    teacher_id = Column(BigInteger, ForeignKey('teachers.id', ondelete='CASCADE', name='fk_doc_teacher'), nullable=False)
    doc_type = Column(Enum(DocumentTypeEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size_kb = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    version = Column(Integer, default=1)
    is_verified = Column(Boolean, default=False)
    verified_by = Column(BigInteger, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    teacher = relationship("Teacher", back_populates="documents")

    def __repr__(self):
        return f"<TeacherDocument teacher_id={self.teacher_id} type={self.doc_type.value}>"


class TeacherBankingDetails(Base):
    """Teacher Banking Details for salary disbursement"""
    __tablename__ = 'teacher_banking_details'
    __table_args__ = (
        UniqueConstraint('teacher_id', name='unique_teacher_banking'),
        Index('idx_banking_teacher', 'teacher_id'),
        Index('idx_banking_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_banking_tenant'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE', name='fk_banking_teacher'), nullable=False, unique=True)
    
    # Bank Account Information
    account_holder_name = Column(String(200), nullable=False)
    bank_name = Column(String(200), nullable=False)
    branch_name = Column(String(200), nullable=True)
    account_number = Column(String(50), nullable=False)
    confirm_account_number = Column(String(50), nullable=True)  # For validation during input
    ifsc_code = Column(String(11), nullable=False)
    account_type = Column(Enum(AccountTypeEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=AccountTypeEnum.SAVINGS)
    
    # Additional Banking Information
    pan_number = Column(String(10), nullable=True)
    uan_number = Column(String(12), nullable=True)  # Universal Account Number for PF
    pf_account_number = Column(String(50), nullable=True)  # Provident Fund
    esi_number = Column(String(17), nullable=True)  # Employee State Insurance
    
    # Verification Status
    is_verified = Column(Boolean, default=False)
    verified_by = Column(BigInteger, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    
    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    teacher = relationship("Teacher", back_populates="banking_details")

    def __repr__(self):
        return f"<TeacherBankingDetails teacher_id={self.teacher_id} bank={self.bank_name}>"


# ===== LEAVE & ATTENDANCE MODELS =====

class TeacherLeave(Base):
    __tablename__ = 'teacher_leaves'
    __table_args__ = (
        Index('idx_leave_teacher', 'teacher_id'),
        Index('idx_leave_tenant_date', 'tenant_id', 'from_date', 'to_date'),
        Index('idx_leave_status', 'status'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_leave_tenant'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE', name='fk_leave_teacher'), nullable=False)
    leave_type = Column(Enum(LeaveTypeEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    from_date = Column(Date, nullable=False)
    to_date = Column(Date, nullable=False)
    total_days = Column(DECIMAL(4, 1), nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(Enum(LeaveStatusEnum, values_callable=lambda obj: [e.value for e in obj]), default=LeaveStatusEnum.PENDING)
    approved_by = Column(BigInteger, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    teacher = relationship("Teacher", back_populates="leaves")

    def __repr__(self):
        return f"<TeacherLeave teacher_id={self.teacher_id} from={self.from_date} to={self.to_date} status={self.status.value}>"


class TeacherAttendance(Base):
    __tablename__ = 'teacher_attendance'
    __table_args__ = (
        UniqueConstraint('teacher_id', 'attendance_date', name='unique_teacher_date'),
        Index('idx_attend_teacher_date', 'teacher_id', 'attendance_date'),
        Index('idx_attend_tenant_date', 'tenant_id', 'attendance_date'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_attend_tenant'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE', name='fk_attend_teacher'), nullable=False)
    attendance_date = Column(Date, nullable=False)
    status = Column(Enum(AttendanceStatusEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    check_in_time = Column(Time, nullable=True)
    check_out_time = Column(Time, nullable=True)
    working_hours = Column(DECIMAL(4, 2), nullable=True)
    remarks = Column(Text, nullable=True)
    marked_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    teacher = relationship("Teacher", back_populates="attendance_records")

    def __repr__(self):
        return f"<TeacherAttendance teacher_id={self.teacher_id} date={self.attendance_date} status={self.status.value}>"


# ===== TEACHER AUTHENTICATION MODEL =====

class TeacherAuth(Base):
    """Teacher Authentication - Login credentials for teachers"""
    __tablename__ = 'teacher_auth'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'teacher_id', name='unique_teacher_auth'),
        Index('idx_teacher_auth_email', 'email'),
        Index('idx_teacher_auth_mobile', 'mobile'),
        Index('idx_teacher_auth_teacher', 'teacher_id'),
        Index('idx_teacher_auth_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_teacher_auth_tenant'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE', name='fk_teacher_auth_teacher'), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    mobile = Column(String(20), nullable=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Password Reset OTP fields
    reset_otp = Column(String(6), nullable=True)
    reset_otp_expires = Column(DateTime, nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    teacher = relationship("Teacher", backref="auth_account", uselist=False)

    def set_password(self, password):
        """Set password using werkzeug hashing (same as User model)"""
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password using werkzeug (same as User model)"""
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)
    
    def generate_reset_otp(self):
        """Generate a 6-digit OTP for password reset"""
        import random
        from datetime import timedelta
        self.reset_otp = str(random.randint(100000, 999999))
        self.reset_otp_expires = datetime.utcnow() + timedelta(minutes=10)
        return self.reset_otp
    
    def verify_reset_otp(self, otp):
        """Verify the reset OTP"""
        if not self.reset_otp or not self.reset_otp_expires:
            return False
        if datetime.utcnow() > self.reset_otp_expires:
            return False
        return self.reset_otp == otp
    
    def clear_reset_otp(self):
        """Clear the reset OTP after successful password reset"""
        self.reset_otp = None
        self.reset_otp_expires = None

    def __repr__(self):
        return f"<TeacherAuth id={self.id} teacher_id={self.teacher_id} email={self.email}>"


# ===== TEACHER SALARY MODEL =====

class TeacherSalary(Base):
    """Simplified Teacher Salary Structure"""
    __tablename__ = 'teacher_salary'
    __table_args__ = (
        Index('idx_salary_tenant', 'tenant_id'),
        Index('idx_salary_teacher', 'teacher_id'),
        Index('idx_salary_active', 'is_active'),
        UniqueConstraint('teacher_id', 'is_active', name='unique_teacher_active_salary'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False)
    
    # Core Salary
    basic_salary = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    grade_pay = Column(DECIMAL(10, 2), default=0.00)
    
    # Allowances
    hra = Column(DECIMAL(10, 2), default=0.00)
    da = Column(DECIMAL(10, 2), default=0.00)
    ta = Column(DECIMAL(10, 2), default=0.00)
    medical_allowance = Column(DECIMAL(10, 2), default=0.00)
    special_allowance = Column(DECIMAL(10, 2), default=0.00)
    other_allowances = Column(DECIMAL(10, 2), default=0.00)
    
    # Deductions
    pf_employee = Column(DECIMAL(10, 2), default=0.00)
    pf_employer = Column(DECIMAL(10, 2), default=0.00)
    esi_employee = Column(DECIMAL(10, 2), default=0.00)
    esi_employer = Column(DECIMAL(10, 2), default=0.00)
    professional_tax = Column(DECIMAL(10, 2), default=0.00)
    tds = Column(DECIMAL(10, 2), default=0.00)
    other_deductions = Column(DECIMAL(10, 2), default=0.00)
    
    # Auto-calculated fields (computed by database) - marked as non-insertable/updatable
    gross_salary = Column(DECIMAL(10, 2), Computed(
        "basic_salary + grade_pay + hra + da + ta + medical_allowance + special_allowance + other_allowances"
    ))
    total_deductions = Column(DECIMAL(10, 2), Computed(
        "pf_employee + esi_employee + professional_tax + tds + other_deductions"
    ))
    net_salary = Column(DECIMAL(10, 2), Computed(
        "gross_salary - total_deductions"
    ))
    annual_ctc = Column(DECIMAL(12, 2), Computed(
        "(gross_salary + pf_employer + esi_employer) * 12"
    ))
    
    # Effective Period
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Metadata
    notes = Column(Text, nullable=True)
    created_by = Column(BigInteger, nullable=True)
    approved_by = Column(BigInteger, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")
    teacher = relationship("Teacher", back_populates="salary_record")

    def __repr__(self):
        return f"<TeacherSalary teacher_id={self.teacher_id} basic={self.basic_salary} gross={self.gross_salary}>"

