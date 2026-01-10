"""
Chat Models for Teacher-Student Communication
Enables real-time messaging between teachers and their students
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum, BigInteger, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from db_single import Base


# ===== ENUMS =====

class SenderTypeEnum(enum.Enum):
    TEACHER = "teacher"
    STUDENT = "student"


# ===== CHAT CONVERSATION MODEL =====

class ChatConversation(Base):
    """
    Represents a chat conversation between a teacher and a student.
    Each teacher-student pair has exactly one conversation.
    """
    __tablename__ = 'chat_conversations'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'teacher_id', 'student_id', name='unique_teacher_student_conversation'),
        Index('idx_chat_conv_tenant', 'tenant_id'),
        Index('idx_chat_conv_teacher', 'teacher_id'),
        Index('idx_chat_conv_student', 'student_id'),
        Index('idx_chat_conv_last_message', 'last_message_at'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_chat_conv_tenant'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE', name='fk_chat_conv_teacher'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id', ondelete='CASCADE', name='fk_chat_conv_student'), nullable=False)
    
    # Conversation metadata
    last_message_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Unread counts for each side
    teacher_unread_count = Column(Integer, default=0)
    student_unread_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    tenant = relationship("Tenant")
    teacher = relationship("Teacher", backref="chat_conversations")
    student = relationship("Student", backref="chat_conversations")
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ChatMessage.created_at")

    def __repr__(self):
        return f"<ChatConversation id={self.id} teacher={self.teacher_id} student={self.student_id}>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'teacher_id': self.teacher_id,
            'student_id': self.student_id,
            'teacher_name': self.teacher.full_name if self.teacher else None,
            'student_name': self.student.full_name if self.student else None,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
            'teacher_unread_count': self.teacher_unread_count,
            'student_unread_count': self.student_unread_count,
            'is_active': self.is_active,
        }


# ===== CHAT MESSAGE MODEL =====

class ChatMessage(Base):
    """
    Individual message in a chat conversation.
    """
    __tablename__ = 'chat_messages'
    __table_args__ = (
        Index('idx_chat_msg_conversation', 'conversation_id'),
        Index('idx_chat_msg_sender', 'sender_type'),
        Index('idx_chat_msg_created', 'created_at'),
        Index('idx_chat_msg_unread', 'is_read'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(BigInteger, ForeignKey('chat_conversations.id', ondelete='CASCADE', name='fk_chat_msg_conversation'), nullable=False)
    
    # Sender information
    sender_type = Column(Enum(SenderTypeEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    sender_id = Column(Integer, nullable=False)  # teacher_id or student_id depending on sender_type
    
    # Message content
    message = Column(Text, nullable=False)
    
    # File Attachment
    attachment_url = Column(String(500), nullable=True)
    attachment_type = Column(String(50), nullable=True) # image, document, video, etc.
    attachment_name = Column(String(255), nullable=True) # Original filename
    
    # Read status
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    conversation = relationship("ChatConversation", back_populates="messages")

    def __repr__(self):
        return f"<ChatMessage id={self.id} conversation={self.conversation_id} sender={self.sender_type.value}>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'sender_type': self.sender_type.value if self.sender_type else None,
            'sender_id': self.sender_id,
            'message': self.message,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'attachment_url': self.attachment_url,
            'attachment_type': self.attachment_type,
            'attachment_name': self.attachment_name,
        }
