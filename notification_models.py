"""
Notification Models for Multi-Tenant School Management System
This file contains models for notifications, templates, recipients, and attachments
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Date, Enum, BigInteger, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from models import Base
import enum


# ===== ENUMS =====

class NotificationStatusEnum(enum.Enum):
    DRAFT = "Draft"
    SCHEDULED = "Scheduled"
    SENT = "Sent"
    CANCELLED = "Cancelled"


class NotificationPriorityEnum(enum.Enum):
    LOW = "Low"
    NORMAL = "Normal"
    HIGH = "High"
    URGENT = "Urgent"


class RecipientTypeEnum(enum.Enum):
    ALL_STUDENTS = "All Students"
    ALL_TEACHERS = "All Teachers"
    ALL = "All Teachers & Students"
    CLASS = "Class"
    SPECIFIC_STUDENTS = "Specific Students"
    SPECIFIC_TEACHERS = "Specific Teachers"


class RecipientStatusEnum(enum.Enum):
    PENDING = "Pending"
    SENT = "Sent"
    READ = "Read"
    FAILED = "Failed"


# ===== NOTIFICATION TEMPLATE MODEL =====

class NotificationTemplate(Base):
    """Pre-defined notification templates for quick sending"""
    __tablename__ = 'notification_templates'
    __table_args__ = (
        Index('idx_template_tenant', 'tenant_id'),
        Index('idx_template_active', 'is_active'),
        Index('idx_template_category', 'category'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_notif_template_tenant'), nullable=False)
    
    # Template details
    name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=True)  # Fee, Attendance, Exam, General, etc.
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    
    # Template settings
    default_priority = Column(Enum(NotificationPriorityEnum, values_callable=lambda obj: [e.value for e in obj]), 
                            default=NotificationPriorityEnum.NORMAL)
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    tenant = relationship("Tenant")
    notifications = relationship("Notification", back_populates="template")

    def __repr__(self):
        return f"<NotificationTemplate id={self.id} name={self.name}>"


# ===== NOTIFICATION MODEL =====

class Notification(Base):
    """Main notification record - can be sent to multiple recipients"""
    __tablename__ = 'notifications'
    __table_args__ = (
        Index('idx_notification_tenant', 'tenant_id'),
        Index('idx_notification_status', 'status'),
        Index('idx_notification_created', 'created_at'),
        Index('idx_notification_scheduled', 'scheduled_at'),
        Index('idx_notification_sent', 'sent_at'),
        Index('idx_notification_tenant_status', 'tenant_id', 'status'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_notification_tenant'), nullable=False)
    template_id = Column(BigInteger, ForeignKey('notification_templates.id', ondelete='SET NULL', name='fk_notification_template'), nullable=True)
    
    # Notification content
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=False)
    
    # Recipient targeting
    recipient_type = Column(Enum(RecipientTypeEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    class_id = Column(Integer, ForeignKey('classes.id', ondelete='SET NULL', name='fk_notification_class'), nullable=True)  # If targeting a class
    
    # Notification settings
    priority = Column(Enum(NotificationPriorityEnum, values_callable=lambda obj: [e.value for e in obj]), 
                     default=NotificationPriorityEnum.NORMAL)
    status = Column(Enum(NotificationStatusEnum, values_callable=lambda obj: [e.value for e in obj]), 
                   default=NotificationStatusEnum.DRAFT)
    
    # Timing
    scheduled_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    
    # Email option
    send_as_email = Column(Boolean, default=False)  # Whether to also send as email
    email_sent_at = Column(DateTime, nullable=True)  # When email was sent
    
    # WhatsApp option
    send_as_whatsapp = Column(Boolean, default=False)  # Whether to also send via WhatsApp
    whatsapp_sent_at = Column(DateTime, nullable=True)  # When WhatsApp was sent
    
    # Metadata
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    tenant = relationship("Tenant")
    template = relationship("NotificationTemplate", back_populates="notifications")
    target_class = relationship("Class")
    recipients = relationship("NotificationRecipient", back_populates="notification", cascade="all, delete-orphan")
    documents = relationship("NotificationDocument", back_populates="notification", cascade="all, delete-orphan")

    @property
    def total_recipients(self):
        """Count total recipients"""
        return len(self.recipients)
    
    @property
    def sent_count(self):
        """Count sent recipients"""
        return sum(1 for r in self.recipients if r.status in [RecipientStatusEnum.SENT, RecipientStatusEnum.READ])
    
    @property
    def read_count(self):
        """Count read recipients"""
        return sum(1 for r in self.recipients if r.status == RecipientStatusEnum.READ)

    def __repr__(self):
        return f"<Notification id={self.id} title={self.title[:50]}... status={self.status.value}>"


# ===== NOTIFICATION RECIPIENT MODEL =====

class NotificationRecipient(Base):
    """Individual notification recipient tracking"""
    __tablename__ = 'notification_recipients'
    __table_args__ = (
        Index('idx_recipient_notification', 'notification_id'),
        Index('idx_recipient_tenant', 'tenant_id'),
        Index('idx_recipient_student', 'student_id'),
        Index('idx_recipient_teacher', 'teacher_id'),
        Index('idx_recipient_status', 'status'),
        Index('idx_recipient_notif_status', 'notification_id', 'status'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_recipient_tenant'), nullable=False)
    notification_id = Column(BigInteger, ForeignKey('notifications.id', ondelete='CASCADE', name='fk_recipient_notification'), nullable=False)
    
    # Recipient (one of these will be set based on recipient type)
    student_id = Column(Integer, ForeignKey('students.id', ondelete='CASCADE', name='fk_recipient_student'), nullable=True)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE', name='fk_recipient_teacher'), nullable=True)
    
    # Delivery tracking
    status = Column(Enum(RecipientStatusEnum, values_callable=lambda obj: [e.value for e in obj]), 
                   default=RecipientStatusEnum.PENDING)
    sent_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    failed_reason = Column(String(500), nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    tenant = relationship("Tenant")
    notification = relationship("Notification", back_populates="recipients")
    student = relationship("Student", backref="notifications_received")
    teacher = relationship("Teacher", backref="notifications_received")

    @property
    def recipient_name(self):
        """Get recipient's name"""
        if self.student:
            return self.student.full_name
        elif self.teacher:
            return self.teacher.full_name
        return "Unknown"
    
    @property
    def recipient_type_label(self):
        """Get recipient type label"""
        if self.student_id:
            return "Student"
        elif self.teacher_id:
            return "Teacher"
        return "Unknown"

    def __repr__(self):
        return f"<NotificationRecipient id={self.id} notification={self.notification_id} status={self.status.value}>"


# ===== NOTIFICATION DOCUMENT MODEL =====

class NotificationDocument(Base):
    """Document/Attachment for notifications"""
    __tablename__ = 'notification_documents'
    __table_args__ = (
        Index('idx_notif_doc_notification', 'notification_id'),
        Index('idx_notif_doc_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_notif_doc_tenant'), nullable=False)
    notification_id = Column(BigInteger, ForeignKey('notifications.id', ondelete='CASCADE', name='fk_notif_doc_notification'), nullable=False)
    
    # File details
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size_kb = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    
    # Metadata
    uploaded_by = Column(BigInteger, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    tenant = relationship("Tenant")
    notification = relationship("Notification", back_populates="documents")

    def __repr__(self):
        return f"<NotificationDocument id={self.id} file={self.file_name}>"


# ===== WHATSAPP API PROVIDER ENUM =====

class WhatsAppProviderEnum(enum.Enum):
    TWILIO = "Twilio"
    META_CLOUD_API = "Meta Cloud API"
    GUPSHUP = "Gupshup"
    WATI = "WATI"
    INTERAKT = "Interakt"
    AISENSY = "AiSensy"
    OTHER = "Other"


# ===== WHATSAPP SETTINGS MODEL =====

class WhatsAppSettings(Base):
    """WhatsApp API configuration for each tenant/school"""
    __tablename__ = 'whatsapp_settings'
    __table_args__ = (
        Index('idx_whatsapp_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_whatsapp_tenant'), nullable=False, unique=True)
    
    # Provider selection
    provider = Column(Enum(WhatsAppProviderEnum, values_callable=lambda obj: [e.value for e in obj]), 
                     default=WhatsAppProviderEnum.META_CLOUD_API)
    
    # API Credentials (encrypted storage recommended in production)
    api_key = Column(String(500), nullable=True)  # Primary API key
    api_secret = Column(String(500), nullable=True)  # API secret/token
    phone_number_id = Column(String(100), nullable=True)  # WhatsApp Business Phone Number ID
    business_account_id = Column(String(100), nullable=True)  # WhatsApp Business Account ID
    access_token = Column(Text, nullable=True)  # Long-lived access token (for Meta)
    
    # Webhook configuration
    webhook_url = Column(String(500), nullable=True)
    webhook_verify_token = Column(String(200), nullable=True)
    
    # Settings
    is_enabled = Column(Boolean, default=False)
    sandbox_mode = Column(Boolean, default=True)  # Test mode
    daily_limit = Column(Integer, default=1000)  # Daily message limit
    messages_sent_today = Column(Integer, default=0)
    last_reset_date = Column(Date, nullable=True)
    
    # Template settings (for WhatsApp Business API)
    default_template_name = Column(String(200), nullable=True)
    default_template_language = Column(String(10), default='en')
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    updated_by = Column(BigInteger, nullable=True)

    # Relationships
    tenant = relationship("Tenant")

    def __repr__(self):
        return f"<WhatsAppSettings tenant_id={self.tenant_id} provider={self.provider.value if self.provider else 'None'} enabled={self.is_enabled}>"
    
    def is_configured(self):
        """Check if WhatsApp is properly configured"""
        if not self.is_enabled:
            return False
        
        # Check required fields based on provider
        if self.provider == WhatsAppProviderEnum.META_CLOUD_API:
            return bool(self.phone_number_id and self.access_token)
        elif self.provider == WhatsAppProviderEnum.TWILIO:
            return bool(self.api_key and self.api_secret and self.phone_number_id)
        elif self.provider in [WhatsAppProviderEnum.GUPSHUP, WhatsAppProviderEnum.WATI, 
                               WhatsAppProviderEnum.INTERAKT, WhatsAppProviderEnum.AISENSY]:
            return bool(self.api_key)
        else:
            return bool(self.api_key)
    
    def can_send_message(self):
        """Check if we can send more messages today"""
        from datetime import date
        today = date.today()
        
        # Reset counter if it's a new day
        if self.last_reset_date != today:
            self.messages_sent_today = 0
            self.last_reset_date = today
        
        return self.messages_sent_today < self.daily_limit
    
    def increment_message_count(self, count=1):
        """Increment the daily message counter"""
        from datetime import date
        today = date.today()
        
        if self.last_reset_date != today:
            self.messages_sent_today = count
            self.last_reset_date = today
        else:
            self.messages_sent_today += count


# ===== WHATSAPP MESSAGE LOG MODEL =====

class WhatsAppMessageLog(Base):
    """Log of WhatsApp messages sent"""
    __tablename__ = 'whatsapp_message_logs'
    __table_args__ = (
        Index('idx_wa_log_tenant', 'tenant_id'),
        Index('idx_wa_log_notification', 'notification_id'),
        Index('idx_wa_log_status', 'status'),
        Index('idx_wa_log_created', 'created_at'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE', name='fk_wa_log_tenant'), nullable=False)
    notification_id = Column(BigInteger, ForeignKey('notifications.id', ondelete='SET NULL', name='fk_wa_log_notification'), nullable=True)
    
    # Recipient info
    recipient_phone = Column(String(20), nullable=False)
    recipient_name = Column(String(200), nullable=True)
    recipient_type = Column(String(20), nullable=True)  # 'student', 'teacher', 'parent'
    recipient_id = Column(Integer, nullable=True)  # student_id or teacher_id
    
    # Message details
    message_content = Column(Text, nullable=True)
    template_name = Column(String(200), nullable=True)
    
    # API response
    provider_message_id = Column(String(200), nullable=True)  # Message ID from WhatsApp API
    status = Column(String(50), default='pending')  # pending, sent, delivered, read, failed
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)

    # Relationships
    tenant = relationship("Tenant")
    notification = relationship("Notification")

    def __repr__(self):
        return f"<WhatsAppMessageLog id={self.id} phone={self.recipient_phone} status={self.status}>"

