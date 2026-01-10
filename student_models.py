"""
Student Profile Related Models for Multi-Tenant School Management System
This file contains student guardian, medical, previous school, sibling, document models, and authentication
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Date, Enum, BigInteger, Index, UniqueConstraint, DECIMAL
from sqlalchemy.orm import relationship
from datetime import datetime
from models import Base
import enum


# ===== STUDENT AUTH USER WRAPPER FOR FLASK-LOGIN =====

class StudentAuthUser:
    """Wrapper class for Flask-Login to work with StudentAuth (mirrors TeacherAuthUser)"""
    
    def __init__(self, student_auth_record):
        """Initialize with StudentAuth database record"""
        self.id = student_auth_record.id
        self.student_id = student_auth_record.student_id
        self.tenant_id = student_auth_record.tenant_id
        self.admission_number = student_auth_record.admission_number
        self.email = student_auth_record.email
        self._is_active = student_auth_record.is_active
        self.student = student_auth_record.student  # Student model instance
        self.role = 'student'  # For template/route checks
    
    def get_id(self):
        """Required by Flask-Login - returns unique identifier"""
        return f'student_{self.tenant_id}_{self.id}'
    
    @property
    def is_authenticated(self):
        """Required by Flask-Login"""
        return True
    
    @property
    def is_active(self):
        """Required by Flask-Login"""
        return self._is_active
    
    @property
    def is_anonymous(self):
        """Required by Flask-Login"""
        return False
    
    # Additional convenience properties
    @property
    def first_name(self):
        return self.student.first_name if self.student else ''
    
    @property
    def last_name(self):
        return self.student.last_name if self.student else ''
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def __repr__(self):
        return f"<StudentAuthUser id={self.id} admission={self.admission_number} tenant={self.tenant_id}>"


# ===== STUDENT AUTHENTICATION MODEL =====

class StudentAuth(Base):
    """Student Authentication - Login credentials for students (mirrors TeacherAuth)"""
    __tablename__ = 'student_auth'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'student_id', name='unique_student_auth'),
        UniqueConstraint('tenant_id', 'admission_number', name='unique_student_admission'),
        Index('idx_student_auth_email', 'email'),
        Index('idx_student_auth_mobile', 'mobile'),
        Index('idx_student_auth_admission', 'admission_number'),
        Index('idx_student_auth_student', 'student_id'),
        Index('idx_student_auth_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_student_auth_tenant'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id', ondelete='CASCADE', name='fk_student_auth_student'), nullable=False)
    admission_number = Column(String(50), nullable=False)
    email = Column(String(150), nullable=True)
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
    student = relationship("Student", backref="auth_account", uselist=False)

    def set_password(self, password):
        """Set password using werkzeug hashing (same as User and TeacherAuth model)"""
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password using werkzeug (same as User and TeacherAuth model)"""
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
        return f"<StudentAuth id={self.id} student_id={self.student_id} admission={self.admission_number}>"


# ===== ENUMS =====

# ===== ENUMS =====

class GuardianTypeEnum(enum.Enum):
    FATHER = "Father"
    MOTHER = "Mother"
    OTHER = "Other"

class StudentDocumentTypeEnum(enum.Enum):
    BIRTH_CERTIFICATE = "Birth Certificate"
    AADHAR_CARD = "Aadhar Card"
    TRANSFER_CERTIFICATE = "Transfer Certificate"
    MARKSHEET = "Marksheet"
    OTHER = "Other"

# ===== MODELS =====

class StudentGuardian(Base):
    """Extended guardian information beyond basic fields in Student model"""
    __tablename__ = 'student_guardians'
    __table_args__ = (
        UniqueConstraint('student_id', 'guardian_type', name='unique_student_guardian_type'),
        Index('idx_guardian_student', 'student_id'),
        Index('idx_guardian_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_guardian_tenant'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id', ondelete='CASCADE', name='fk_guardian_student'), nullable=False)
    guardian_type = Column(Enum(GuardianTypeEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    occupation = Column(String(100), nullable=True)
    annual_income = Column(DECIMAL(10, 2), nullable=True)
    phone_alternate = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    student = relationship("Student", back_populates="guardians")

    def __repr__(self):
        return f"<StudentGuardian student_id={self.student_id} type={self.guardian_type.value}>"


class StudentMedicalInfo(Base):
    """Medical and health information for students"""
    __tablename__ = 'student_medical_info'
    __table_args__ = (
        Index('idx_medical_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_medical_tenant'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id', ondelete='CASCADE', name='fk_medical_student'), nullable=False, unique=True)
    allergies = Column(Text, nullable=True)
    medical_conditions = Column(Text, nullable=True)
    emergency_medication = Column(String(200), nullable=True)
    doctor_name = Column(String(150), nullable=True)
    doctor_phone = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    student = relationship("Student", back_populates="medical_info")

    def __repr__(self):
        return f"<StudentMedicalInfo student_id={self.student_id}>"


class StudentPreviousSchool(Base):
    """Previous school records and transfer certificate details"""
    __tablename__ = 'student_previous_schools'
    __table_args__ = (
        Index('idx_prev_school_student', 'student_id'),
        Index('idx_prev_school_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_prev_school_tenant'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id', ondelete='CASCADE', name='fk_prev_school_student'), nullable=False)
    school_name = Column(String(200), nullable=False)
    last_class = Column(String(20), nullable=True)
    tc_number = Column(String(50), nullable=True)
    tc_date = Column(Date, nullable=True)
    last_percentage = Column(DECIMAL(5, 2), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    student = relationship("Student", back_populates="previous_schools")

    def __repr__(self):
        return f"<StudentPreviousSchool student_id={self.student_id} school={self.school_name}>"


class StudentSibling(Base):
    """Sibling information for students"""
    __tablename__ = 'student_siblings'
    __table_args__ = (
        Index('idx_sibling_student', 'student_id'),
        Index('idx_sibling_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_sibling_tenant'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id', ondelete='CASCADE', name='fk_sibling_student'), nullable=False)
    sibling_student_id = Column(Integer, ForeignKey('students.id', ondelete='SET NULL', name='fk_sibling_student_id'), nullable=True)
    sibling_name = Column(String(150), nullable=False)
    sibling_class = Column(String(20), nullable=True)
    sibling_admission_number = Column(String(20), nullable=True)
    is_in_same_school = Column(Boolean, default=False)
    other_school_name = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    student = relationship("Student", foreign_keys=[student_id], back_populates="siblings")
    sibling_student = relationship("Student", foreign_keys=[sibling_student_id])

    def __repr__(self):
        return f"<StudentSibling student_id={self.student_id} sibling={self.sibling_name}>"


class StudentDocument(Base):
    """Document storage for students (birth certificate, aadhar, TC, etc.)"""
    __tablename__ = 'student_documents'
    __table_args__ = (
        Index('idx_doc_student', 'student_id'),
        Index('idx_doc_tenant', 'tenant_id'),
        Index('idx_doc_type', 'doc_type'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_student_doc_tenant'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id', ondelete='CASCADE', name='fk_doc_student'), nullable=False)
    doc_type = Column(Enum(StudentDocumentTypeEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    student = relationship("Student", back_populates="documents")

    def __repr__(self):
        return f"<StudentDocument student_id={self.student_id} type={self.doc_type.value}>"
