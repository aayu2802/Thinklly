"""
Single Database Multi-Tenant Models
This file contains models that are shared across tenants and tenant-scoped models
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Numeric, Date, Enum, create_engine, BigInteger, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import enum

Base = declarative_base()

# ===== TENANT MODEL =====
class Tenant(Base):
    __tablename__ = 'tenants'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)  # URL identifier
    domain = Column(String(255), unique=True, nullable=True)  # Optional custom domain
    database_name = Column(String(100), nullable=True)  # For multi-DB setup (future)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Configuration
    settings = Column(Text, nullable=True)  # JSON string for tenant-specific settings
    
    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Tenant {self.name} ({self.slug})>'
    
    @property
    def display_name(self):
        return self.name

# ===== USER MODEL =====
class User(Base, UserMixin):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=True)  # NULL for portal admin
    username = Column(String(80), nullable=False)
    email = Column(String(120), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default='teacher')  # portal_admin, school_admin, teacher, student
    first_name = Column(String(50))
    last_name = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Password Reset OTP fields
    reset_otp = Column(String(6), nullable=True)
    reset_otp_expires = Column(DateTime, nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
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
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_id(self):
        """Return user ID in format needed by Flask-Login"""
        if self.tenant_id:
            return f"school_{self.tenant_id}_{self.id}"
        else:
            return f"admin_{self.id}"
    
    def __repr__(self):
        return f'<User {self.username} ({self.role})>'

# ===== ENUMS FOR TENANT-SCOPED MODELS =====
class GenderEnum(enum.Enum):
    MALE = "M"
    FEMALE = "F"
    OTHER = "O"

class CategoryEnum(enum.Enum):
    GENERAL = "General"
    SC = "SC"
    ST = "ST"
    OBC = "OBC"

class StudentStatusEnum(enum.Enum):
    ACTIVE = "Active"
    TRANSFERRED = "Transferred"
    LEFT = "Left"
    GRADUATED = "Graduated"

class ExamTypeEnum(enum.Enum):
    UNIT_TEST = "Unit Test"
    MID_TERM = "Mid Term"
    FINAL = "Final"
    ANNUAL = "Annual"

class GradeEnum(enum.Enum):
    A_PLUS = "A+"
    A = "A"
    B_PLUS = "B+"
    B = "B"
    C_PLUS = "C+"
    C = "C"
    D = "D"
    F = "F"

class EmployeeStatusEnum(enum.Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    ON_LEAVE = "On Leave"
    RESIGNED = "Resigned"

# Define SQLAlchemy Enum types
gender_enum = Enum('Male', 'Female', 'Other', name='gender_enum')
employee_status_enum = Enum('Active', 'Inactive', 'On Leave', 'Resigned', name='employee_status_enum')

# ===== TENANT-SCOPED MODELS =====

class Student(Base):
    __tablename__ = 'students'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    
    # Basic Information
    admission_number = Column(String(20), nullable=False)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    full_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(Enum(GenderEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    category = Column(Enum(CategoryEnum, values_callable=lambda obj: [e.value for e in obj]), default=CategoryEnum.GENERAL)
    blood_group = Column(String(5))
    aadhar_number = Column(String(12), unique=True)
    photo_url = Column(String(500), nullable=True)
    
    # Contact Information
    email = Column(String(120))
    phone = Column(String(20))
    address = Column(Text)
    city = Column(String(50))
    state = Column(String(50))
    pincode = Column(String(10))
    
    # Guardian Information
    father_name = Column(String(100), nullable=False)
    mother_name = Column(String(100))
    guardian_phone = Column(String(20), nullable=False)
    guardian_email = Column(String(120))
    
    # Academic Information
    class_id = Column(Integer, ForeignKey('classes.id'), nullable=False)
    session_id = Column(Integer, ForeignKey('academic_sessions.id'), nullable=False)
    roll_number = Column(String(10))
    admission_date = Column(Date, default=date.today)
    status = Column(Enum(StudentStatusEnum, values_callable=lambda obj: [e.value for e in obj]), default=StudentStatusEnum.ACTIVE)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")
    student_class = relationship("Class", back_populates="students")
    academic_session = relationship("AcademicSession", back_populates="students")
    marks = relationship("StudentMark", back_populates="student", cascade="all, delete-orphan")
    guardians = relationship("StudentGuardian", back_populates="student", cascade="all, delete-orphan")
    medical_info = relationship("StudentMedicalInfo", back_populates="student", uselist=False, cascade="all, delete-orphan")
    previous_schools = relationship("StudentPreviousSchool", back_populates="student", cascade="all, delete-orphan")
    siblings = relationship("StudentSibling", foreign_keys="StudentSibling.student_id", back_populates="student", cascade="all, delete-orphan")
    documents = relationship("StudentDocument", back_populates="student", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            'id': self.id,
            'admission_number': self.admission_number,
            'full_name': self.full_name,
            'gender': self.gender.value if self.gender else None,
            'class_name': f"{self.student_class.class_name}-{self.student_class.section}" if self.student_class else None,
            'roll_number': self.roll_number,
            'status': self.status.value if self.status else None
        }
    
    def __repr__(self):
        return f'<Student {self.full_name} ({self.admission_number})>'

class Class(Base):
    __tablename__ = 'classes'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    class_name = Column(String(10), nullable=False)  # e.g., "10", "9"
    section = Column(String(5), nullable=False)  # e.g., "A", "B"
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")
    students = relationship("Student", back_populates="student_class", cascade="all, delete-orphan")
    # subjects = relationship("Subject", back_populates="class_ref", cascade="all, delete-orphan")  # TODO: Re-enable after adding class_id to subjects table
    
    def __repr__(self):
        return f'<Class {self.class_name}-{self.section}>'


class AcademicSession(Base):
    __tablename__ = 'academic_sessions'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    session_name = Column(String(20), nullable=False)  # e.g., "2024-25"
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_current = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")
    students = relationship("Student", back_populates="academic_session", cascade="all, delete-orphan")
    # exams = relationship("Exam", back_populates="academic_session", cascade="all, delete-orphan")  # Deprecated: Use examination_models.Examination instead
    
    def __repr__(self):
        return f'<AcademicSession {self.session_name}>'


# ===== DEPRECATED EXAM MODELS =====
# NOTE: These models are deprecated and replaced by examination_models.py
# They are kept here for backward compatibility with existing database tables
# DO NOT use these models in new code - use examination_models.Examination instead

class Exam(Base):
    __tablename__ = 'exams'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    exam_name = Column(String(100), nullable=False)
    exam_type = Column(Enum(ExamTypeEnum), nullable=False)
    session_id = Column(Integer, ForeignKey('academic_sessions.id'), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")
    # academic_session = relationship("AcademicSession", back_populates="exams")  # Deprecated relationship
    exam_subjects = relationship("ExamSubject", back_populates="exam", cascade="all, delete-orphan")
    marks = relationship("StudentMark", back_populates="exam", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Exam {self.exam_name}>'

class ExamSubject(Base):
    __tablename__ = 'exam_subjects'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    exam_id = Column(Integer, ForeignKey('exams.id'), nullable=False)
    subject_id = Column(BigInteger, ForeignKey('subjects.id'), nullable=False)  # Changed to BigInteger to match subjects.id
    max_marks = Column(Integer, nullable=False)
    pass_marks = Column(Integer, nullable=False)
    
    # Relationships
    tenant = relationship("Tenant")
    exam = relationship("Exam", back_populates="exam_subjects")
    # subject = relationship("Subject", back_populates="exam_subjects")  # TODO: Re-enable after importing Subject
    
    def __repr__(self):
        return f'<ExamSubject {self.exam.exam_name} - {self.subject.subject_name}>'

class StudentMark(Base):
    __tablename__ = 'student_marks'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    exam_id = Column(Integer, ForeignKey('exams.id'), nullable=False)
    subject_id = Column(BigInteger, ForeignKey('subjects.id'), nullable=False)  # Changed to BigInteger to match subjects.id
    marks_obtained = Column(Numeric(5, 2), nullable=False)
    max_marks = Column(Integer, nullable=False)
    grade = Column(Enum(GradeEnum))
    is_absent = Column(Boolean, default=False)
    entered_by = Column(String(100))  # Username who entered marks
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")
    student = relationship("Student", back_populates="marks")
    exam = relationship("Exam", back_populates="marks")
    # subject = relationship("Subject", back_populates="marks")  # TODO: Re-enable after importing Subject
    
    def calculate_grade(self):
        """Calculate grade based on percentage"""
        if self.is_absent:
            return GradeEnum.F
        
        percentage = (float(self.marks_obtained) / self.max_marks) * 100
        
        if percentage >= 90:
            return GradeEnum.A_PLUS
        elif percentage >= 80:
            return GradeEnum.A
        elif percentage >= 70:
            return GradeEnum.B_PLUS
        elif percentage >= 60:
            return GradeEnum.B
        elif percentage >= 50:
            return GradeEnum.C_PLUS
        elif percentage >= 40:
            return GradeEnum.C
        elif percentage >= 33:
            return GradeEnum.D
        else:
            return GradeEnum.F
    
    def __repr__(self):
        return f'<StudentMark {self.student.full_name} - {self.subject.subject_name}: {self.marks_obtained}/{self.max_marks}>'


# ===== STUDENT ATTENDANCE ENUMS =====
class StudentAttendanceStatusEnum(enum.Enum):
    PRESENT = 'Present'
    ABSENT = 'Absent'
    HALF_DAY = 'Half-Day'
    ON_LEAVE = 'On Leave'
    HOLIDAY = 'Holiday'
    WEEK_OFF = 'Week Off'


class HolidayTypeEnum(enum.Enum):
    PUBLIC_HOLIDAY = 'Public Holiday'
    SCHOOL_EVENT = 'School Event'
    EXAM = 'Exam'
    VACATION = 'Vacation'
    OTHER = 'Other'


# ===== STUDENT ATTENDANCE MODEL =====
class StudentAttendance(Base):
    """Daily attendance records for students"""
    __tablename__ = 'student_attendance'
    __table_args__ = (
        UniqueConstraint('student_id', 'attendance_date', name='unique_student_date'),
        Index('idx_attend_student_date', 'student_id', 'attendance_date'),
        Index('idx_attend_class_date', 'class_id', 'attendance_date'),
        Index('idx_attend_tenant_date', 'tenant_id', 'attendance_date'),
        Index('idx_attend_status', 'status'),
        Index('idx_attend_date', 'attendance_date'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    class_id = Column(Integer, ForeignKey('classes.id', ondelete='CASCADE'), nullable=False)
    attendance_date = Column(Date, nullable=False)
    status = Column(Enum(StudentAttendanceStatusEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    check_in_time = Column(DateTime, nullable=True)
    check_out_time = Column(DateTime, nullable=True)
    remarks = Column(Text, nullable=True)
    marked_by = Column(BigInteger, nullable=True)  # User ID who marked
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    student = relationship("Student", backref="attendance_records")
    student_class = relationship("Class")

    def __repr__(self):
        return f"<StudentAttendance student_id={self.student_id} date={self.attendance_date} status={self.status.value}>"


# ===== STUDENT ATTENDANCE SUMMARY MODEL =====
class StudentAttendanceSummary(Base):
    """Monthly attendance summary for performance"""
    __tablename__ = 'student_attendance_summary'
    __table_args__ = (
        UniqueConstraint('student_id', 'month', 'year', name='unique_student_month_year'),
        Index('idx_summary_student', 'student_id'),
        Index('idx_summary_class', 'class_id'),
        Index('idx_summary_tenant', 'tenant_id'),
        Index('idx_summary_month_year', 'month', 'year'),
        Index('idx_summary_percentage', 'attendance_percentage'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    class_id = Column(Integer, ForeignKey('classes.id', ondelete='CASCADE'), nullable=False)
    month = Column(Integer, nullable=False)  # 1-12
    year = Column(Integer, nullable=False)
    total_working_days = Column(Integer, default=0)
    present_days = Column(Numeric(5, 2), default=0.00)  # Half-days counted as 0.5
    absent_days = Column(Integer, default=0)
    half_days = Column(Integer, default=0)
    leave_days = Column(Integer, default=0)
    holiday_days = Column(Integer, default=0)
    weekoff_days = Column(Integer, default=0)
    attendance_percentage = Column(Numeric(5, 2), default=0.00)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    student = relationship("Student", backref="attendance_summaries")
    student_class = relationship("Class")

    def __repr__(self):
        return f"<StudentAttendanceSummary student_id={self.student_id} {self.month}/{self.year} {self.attendance_percentage}%>"


# ===== STUDENT HOLIDAYS MODEL =====
class StudentHoliday(Base):
    """School holiday calendar with date range support"""
    __tablename__ = 'student_holidays'
    __table_args__ = (
        Index('idx_holiday_tenant', 'tenant_id'),
        Index('idx_holiday_start_date', 'start_date'),
        Index('idx_holiday_end_date', 'end_date'),
        Index('idx_holiday_class', 'class_id'),
        Index('idx_holiday_tenant_dates', 'tenant_id', 'start_date', 'end_date'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    class_id = Column(Integer, ForeignKey('classes.id', ondelete='CASCADE'), nullable=True)  # NULL = all classes
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)  # Same as start_date for single-day holidays
    holiday_name = Column(String(100), nullable=False)
    holiday_type = Column(Enum(HolidayTypeEnum, values_callable=lambda obj: [e.value for e in obj]), default=HolidayTypeEnum.PUBLIC_HOLIDAY)
    description = Column(Text, nullable=True)
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    student_class = relationship("Class")

    @property
    def duration_days(self):
        """Calculate number of days in holiday range"""
        return (self.end_date - self.start_date).days + 1

    @property
    def is_single_day(self):
        """Check if holiday is single day"""
        return self.start_date == self.end_date

    def __repr__(self):
        if self.is_single_day:
            return f"<StudentHoliday {self.holiday_name} on {self.start_date}>"
        return f"<StudentHoliday {self.holiday_name} {self.start_date} to {self.end_date}>"


# Note: Teacher and related models are now in teacher_models.py
# They are imported by db_single.py to register with Base.metadata
