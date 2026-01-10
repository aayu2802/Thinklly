"""
Examination Models for School ERP
Fresh models for examination management
"""
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Float, Text, 
    Boolean, ForeignKey, Enum as SQLEnum, Time
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from models import Base


class ExaminationType(enum.Enum):
    """Types of examinations"""
    UNIT_TEST = "Unit Test"
    CLASS_TEST = "Class Test"
    MIDTERM = "Mid Term"
    FINAL = "Final"
    PRACTICAL = "Practical"
    ORAL = "Oral"
    PROJECT = "Project"
    ASSIGNMENT = "Assignment"


class ExaminationStatus(enum.Enum):
    """Status of examination"""
    DRAFT = "Draft"
    SCHEDULED = "Scheduled"
    ONGOING = "Ongoing"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class MarkEntryStatus(enum.Enum):
    """Status of mark entry"""
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    VERIFIED = "Verified"
    PUBLISHED = "Published"


class PublicationStatus(enum.Enum):
    """Publication status for results"""
    DRAFT = "Draft"
    SCHEDULED = "Scheduled"
    PUBLISHED = "Published"
    UNPUBLISHED = "Unpublished"


class NotificationStatus(enum.Enum):
    """Notification status"""
    PENDING = "Pending"
    SENT = "Sent"
    FAILED = "Failed"


class Examination(Base):
    """Main examination model"""
    __tablename__ = 'examinations'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    academic_session_id = Column(Integer, ForeignKey('academic_sessions.id'), nullable=False)
    
    # Basic Information
    exam_name = Column(String(200), nullable=False)
    exam_code = Column(String(50))
    exam_type = Column(SQLEnum(ExaminationType), nullable=False)
    
    # Dates
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    result_date = Column(Date)
    
    # Configuration
    total_marks = Column(Integer, default=100)
    passing_marks = Column(Integer, default=35)
    status = Column(SQLEnum(ExaminationStatus), default=ExaminationStatus.DRAFT)
    
    # Additional Info
    description = Column(Text)
    instructions = Column(Text)
    
    # Metadata
    created_by = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", backref="examinations")
    academic_session = relationship("AcademicSession", backref="examinations")
    subjects = relationship("ExaminationSubject", back_populates="examination", cascade="all, delete-orphan")
    schedules = relationship("ExaminationSchedule", back_populates="examination", cascade="all, delete-orphan")
    marks = relationship("ExaminationMark", back_populates="examination", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Examination {self.exam_name}>"


class ExaminationSubject(Base):
    """Subjects included in an examination"""
    __tablename__ = 'examination_subjects'
    
    id = Column(Integer, primary_key=True)
    examination_id = Column(Integer, ForeignKey('examinations.id'), nullable=False)
    subject_id = Column(Integer, ForeignKey('subjects.id'), nullable=False)  # Added ForeignKey
    class_id = Column(Integer, ForeignKey('classes.id'), nullable=False)
    
    # Marks Distribution
    theory_marks = Column(Integer, default=0)
    practical_marks = Column(Integer, default=0)
    internal_marks = Column(Integer, default=0)
    total_marks = Column(Integer, nullable=False)
    passing_marks = Column(Integer, nullable=False)
    
    # Status
    mark_entry_status = Column(SQLEnum(MarkEntryStatus), default=MarkEntryStatus.PENDING)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    examination = relationship("Examination", back_populates="subjects")
    subject = relationship("Subject")  # Added subject relationship
    class_ref = relationship("Class")
    
    def __repr__(self):
        return f"<ExaminationSubject {self.subject_id} in Exam {self.examination_id}>"


class ExaminationSchedule(Base):
    """Exam schedule/timetable"""
    __tablename__ = 'examination_schedules'
    
    id = Column(Integer, primary_key=True)
    examination_id = Column(Integer, ForeignKey('examinations.id'), nullable=False)
    examination_subject_id = Column(Integer, ForeignKey('examination_subjects.id'), nullable=False)
    
    # Schedule Details
    exam_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    duration_minutes = Column(Integer)
    
    # Venue
    room_number = Column(String(50))
    building = Column(String(100))
    
    # Instructions
    instructions = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    examination = relationship("Examination", back_populates="schedules")
    examination_subject = relationship("ExaminationSubject", backref="schedules")
    
    def __repr__(self):
        return f"<ExaminationSchedule {self.exam_date}>"


class ExaminationMark(Base):
    """Student marks for examination"""
    __tablename__ = 'examination_marks'
    
    id = Column(Integer, primary_key=True)
    examination_id = Column(Integer, ForeignKey('examinations.id'), nullable=False)
    examination_subject_id = Column(Integer, ForeignKey('examination_subjects.id'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    
    # Marks Components
    theory_marks_obtained = Column(Float, default=0)
    practical_marks_obtained = Column(Float, default=0)
    internal_marks_obtained = Column(Float, default=0)
    total_marks_obtained = Column(Float)
    
    # Status
    is_absent = Column(Boolean, default=False)
    is_passed = Column(Boolean, default=False)
    
    # Grade
    grade = Column(String(5))
    grade_point = Column(Float)
    remarks = Column(Text)
    
    # Entry Info
    entered_by = Column(Integer)
    entered_at = Column(DateTime)
    verified_by = Column(Integer)
    verified_at = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    examination = relationship("Examination", back_populates="marks")
    examination_subject = relationship("ExaminationSubject", backref="marks")
    student = relationship("Student", backref="examination_marks")
    
    def calculate_total(self):
        """Calculate total marks"""
        if not self.is_absent:
            self.total_marks_obtained = (
                (self.theory_marks_obtained or 0) + 
                (self.practical_marks_obtained or 0) + 
                (self.internal_marks_obtained or 0)
            )
        else:
            self.total_marks_obtained = 0
    
    def check_pass_status(self, passing_marks):
        """Check if student passed"""
        if self.is_absent:
            self.is_passed = False
        else:
            self.is_passed = (self.total_marks_obtained or 0) >= passing_marks
    
    def __repr__(self):
        return f"<ExaminationMark Student:{self.student_id} Exam:{self.examination_id}>"


class ExaminationResult(Base):
    """Overall examination results for students"""
    __tablename__ = 'examination_results'
    
    id = Column(Integer, primary_key=True)
    examination_id = Column(Integer, ForeignKey('examinations.id'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    class_id = Column(Integer, ForeignKey('classes.id'), nullable=False)
    
    # Overall Performance
    total_marks = Column(Float)
    marks_obtained = Column(Float)
    percentage = Column(Float)
    grade = Column(String(5))
    grade_point = Column(Float)
    
    # Status
    is_passed = Column(Boolean, default=False)
    is_published = Column(Boolean, default=False)  # Publication status
    rank = Column(Integer)
    rank_in_class = Column(Integer)
    
    # Attendance
    total_subjects = Column(Integer)
    subjects_appeared = Column(Integer)
    subjects_passed = Column(Integer)
    subjects_failed = Column(Integer)
    
    # Comments
    remarks = Column(Text)
    teacher_comment = Column(Text)
    principal_comment = Column(Text)
    
    # Metadata
    generated_at = Column(DateTime)
    published_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    examination = relationship("Examination", backref="results")
    class_ref = relationship("Class", backref="examination_results")
    student = relationship("Student", backref="examination_results")
    
    def calculate_percentage(self):
        """Calculate percentage"""
        if self.total_marks and self.total_marks > 0:
            self.percentage = (self.marks_obtained / self.total_marks) * 100
        else:
            self.percentage = 0
    
    def __repr__(self):
        return f"<ExaminationResult Student:{self.student_id} Exam:{self.examination_id}>"


class GradeScale(Base):
    """Grade scale configuration for examinations"""
    __tablename__ = 'grade_scales'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    
    # Grade Information
    grade_name = Column(String(10), nullable=False)  # A+, A, B+, B, etc.
    grade_point = Column(Float, nullable=False)  # GPA value (e.g., 4.0, 3.5)
    min_percentage = Column(Float, nullable=False)  # Minimum percentage
    max_percentage = Column(Float, nullable=False)  # Maximum percentage
    
    # Scale Configuration
    scale_name = Column(String(100), nullable=False)  # Name of the scale (e.g., "Default Grade Scale")
    scale_type = Column(String(20), default='letter')  # letter, numeric, percentage
    is_default = Column(Boolean, default=False)  # Is this the default scale?
    
    # Description
    description = Column(String(100))  # e.g., "Outstanding", "Excellent"
    remarks = Column(Text)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_passing = Column(Boolean, default=True)  # Is this a passing grade?
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", backref="grade_scales")
    
    def __repr__(self):
        return f"<GradeScale {self.grade_name} ({self.min_percentage}-{self.max_percentage}%)>"


class ExaminationPublication(Base):
    """Publication settings for examination results"""
    __tablename__ = 'examination_publications'
    
    id = Column(Integer, primary_key=True)
    examination_id = Column(Integer, ForeignKey('examinations.id'), nullable=False)
    
    # Publication Settings
    status = Column(SQLEnum(PublicationStatus), default=PublicationStatus.DRAFT)
    scheduled_date = Column(DateTime)
    published_date = Column(DateTime)
    
    # Visibility Settings
    show_marks = Column(Boolean, default=True)
    show_grade = Column(Boolean, default=True)
    show_rank = Column(Boolean, default=True)
    show_percentage = Column(Boolean, default=True)
    show_subject_wise = Column(Boolean, default=True)
    
    # Access Control
    allow_parent_view = Column(Boolean, default=True)
    allow_student_view = Column(Boolean, default=True)
    require_login = Column(Boolean, default=True)
    
    # Notification Settings
    send_sms = Column(Boolean, default=False)
    send_email = Column(Boolean, default=False)
    send_app_notification = Column(Boolean, default=True)
    
    # Additional Settings
    watermark_text = Column(String(100))
    footer_message = Column(Text)
    principal_signature = Column(String(255))  # File path
    
    # Metadata
    created_by = Column(Integer)
    published_by = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    examination = relationship("Examination", backref="publication", uselist=False)
    
    def __repr__(self):
        return f"<ExaminationPublication Exam:{self.examination_id} Status:{self.status.value}>"


class ResultNotification(Base):
    """Track result notifications sent to students/parents"""
    __tablename__ = 'result_notifications'
    
    id = Column(Integer, primary_key=True)
    examination_id = Column(Integer, ForeignKey('examinations.id'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    
    # Notification Details
    notification_type = Column(String(20))  # SMS, EMAIL, APP
    recipient_name = Column(String(100))
    recipient_contact = Column(String(100))  # Phone or Email
    
    # Status
    status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING)
    sent_at = Column(DateTime)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # Message Content
    message_template = Column(Text)
    message_sent = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    examination = relationship("Examination", backref="notifications")
    student = relationship("Student", backref="result_notifications")
    
    def __repr__(self):
        return f"<ResultNotification Student:{self.student_id} Type:{self.notification_type}>"
