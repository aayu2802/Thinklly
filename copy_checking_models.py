"""
Copy Checking Models for School ERP
Models for assigning teachers to check copies and enter marks
"""
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, 
    Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime
from models import Base


class CopyCheckingAssignment(Base):
    """Assignment of teacher for copy checking (marks entry) for exam subjects"""
    __tablename__ = 'copy_checking_assignments'
    __table_args__ = (
        UniqueConstraint('examination_subject_id', 'teacher_id', 
                        name='uq_copy_check_subject_teacher'),
        Index('idx_copy_check_exam_subject', 'examination_subject_id'),
        Index('idx_copy_check_teacher', 'teacher_id'),
    )
    
    id = Column(Integer, primary_key=True)
    examination_subject_id = Column(Integer, ForeignKey('examination_subjects.id', ondelete='CASCADE'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False)
    
    # Deadline for marks entry
    deadline = Column(DateTime, nullable=True)
    
    # Admin can add comments/instructions when assigning
    admin_comments = Column(Text, nullable=True)
    
    # Tracking
    assigned_by = Column(Integer, nullable=True)  # Admin user ID who assigned
    assigned_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    examination_subject = relationship("ExaminationSubject", backref="copy_checking_assignments")
    teacher = relationship("Teacher", backref="copy_checking_assignments")
    
    def __repr__(self):
        return f"<CopyCheckingAssignment Teacher {self.teacher_id} for ExamSubject {self.examination_subject_id}>"
