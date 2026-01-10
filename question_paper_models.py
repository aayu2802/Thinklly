"""
Question Paper Models for School ERP
Models for question paper setter/reviewer workflow
"""
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, ForeignKey, 
    Enum as SQLEnum, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from models import Base


# ===== ENUMS =====

class AssignmentRole(enum.Enum):
    """Role of teacher in question paper workflow"""
    SETTER = "SETTER"      # Creates question paper
    REVIEWER = "REVIEWER"  # Reviews question paper


class QuestionPaperStatus(enum.Enum):
    """Status of question paper in workflow"""
    DRAFT = "Draft"                      # Setter working on it
    SUBMITTED = "Submitted"              # Submitted for review
    UNDER_REVIEW = "Under Review"        # Being reviewed
    REVISION_REQUESTED = "Revision Requested"  # Sent back for revision
    APPROVED = "Approved"                # Approved by reviewer
    FINAL = "Final"                      # Marked final by admin
    SUPERSEDED = "Superseded"            # Another paper was approved instead


class ReviewAction(enum.Enum):
    """Action taken by reviewer"""
    APPROVED = "Approved"
    REVISION_REQUESTED = "Revision Requested"


# ===== MODELS =====

class QuestionPaperAssignment(Base):
    """Assignment of teachers as setters or reviewers for exam subjects"""
    __tablename__ = 'question_paper_assignments'
    __table_args__ = (
        UniqueConstraint('examination_subject_id', 'teacher_id', 'role', 
                        name='uq_qp_assignment_subject_teacher_role'),
        Index('idx_qp_assignment_exam_subject', 'examination_subject_id'),
        Index('idx_qp_assignment_teacher', 'teacher_id'),
    )
    
    id = Column(Integer, primary_key=True)
    examination_subject_id = Column(Integer, ForeignKey('examination_subjects.id', ondelete='CASCADE'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False)
    role = Column(SQLEnum(AssignmentRole, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    
    # Admin can add comments/instructions when assigning
    admin_comments = Column(Text, nullable=True)
    
    # Deadline for submission (setter) or review (reviewer)
    deadline = Column(DateTime, nullable=True)
    
    # Tracking
    created_by = Column(Integer, nullable=True)  # Admin user ID who assigned
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    examination_subject = relationship("ExaminationSubject", backref="question_paper_assignments")
    teacher = relationship("Teacher", backref="question_paper_assignments")
    
    def __repr__(self):
        return f"<QuestionPaperAssignment {self.teacher_id} as {self.role.value} for ExamSubject {self.examination_subject_id}>"


class QuestionPaper(Base):
    """Uploaded question paper"""
    __tablename__ = 'question_papers'
    __table_args__ = (
        Index('idx_qp_exam_subject', 'examination_subject_id'),
        Index('idx_qp_setter', 'setter_id'),
        Index('idx_qp_status', 'status'),
    )
    
    id = Column(Integer, primary_key=True)
    examination_subject_id = Column(Integer, ForeignKey('examination_subjects.id', ondelete='CASCADE'), nullable=False)
    setter_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False)
    
    # File information
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=True)  # Size in bytes
    file_type = Column(String(50), nullable=True)  # pdf, doc, docx
    
    # Version tracking (for re-uploads after revision)
    version = Column(Integer, default=1, nullable=False)
    
    # Status
    # Use values_callable to store enum values ('Draft', 'Submitted') instead of names ('DRAFT', 'SUBMITTED')
    status = Column(SQLEnum(QuestionPaperStatus, values_callable=lambda obj: [e.value for e in obj]), 
                   default=QuestionPaperStatus.DRAFT, nullable=False)
    
    # Timestamps
    submitted_at = Column(DateTime, nullable=True)  # When submitted for review
    approved_at = Column(DateTime, nullable=True)   # When approved by reviewer
    finalized_at = Column(DateTime, nullable=True)  # When marked final by admin
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    examination_subject = relationship("ExaminationSubject", backref="question_papers")
    setter = relationship("Teacher", backref="question_papers_created")
    reviews = relationship("QuestionPaperReview", back_populates="question_paper", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<QuestionPaper {self.id} v{self.version} for ExamSubject {self.examination_subject_id}>"
    
    @property
    def latest_review(self):
        """Get the most recent review for this paper"""
        if self.reviews:
            return sorted(self.reviews, key=lambda r: r.reviewed_at or datetime.min, reverse=True)[0]
        return None


class QuestionPaperReview(Base):
    """Review of a question paper by reviewer"""
    __tablename__ = 'question_paper_reviews'
    __table_args__ = (
        Index('idx_qp_review_paper', 'question_paper_id'),
        Index('idx_qp_review_reviewer', 'reviewer_id'),
    )
    
    id = Column(Integer, primary_key=True)
    question_paper_id = Column(Integer, ForeignKey('question_papers.id', ondelete='CASCADE'), nullable=False)
    reviewer_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False)
    
    # Review action and comments
    action = Column(SQLEnum(ReviewAction), nullable=False)
    comments = Column(Text, nullable=True)  # Reviewer's comments
    
    # Timestamp
    reviewed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    question_paper = relationship("QuestionPaper", back_populates="reviews")
    reviewer = relationship("Teacher", backref="question_paper_reviews")
    
    def __repr__(self):
        return f"<QuestionPaperReview {self.id} - {self.action.value} for Paper {self.question_paper_id}>"
