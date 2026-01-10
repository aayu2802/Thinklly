"""
Timetable Management Models
Handles class schedules, time slots, teacher assignments, and room management
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Date, Time, ForeignKey, Enum, Index, UniqueConstraint, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from db_single import Base


# ===== ENUMS =====

class DayOfWeekEnum(enum.Enum):
    MONDAY = 'Monday'
    TUESDAY = 'Tuesday'
    WEDNESDAY = 'Wednesday'
    THURSDAY = 'Thursday'
    FRIDAY = 'Friday'
    SATURDAY = 'Saturday'
    SUNDAY = 'Sunday'


class SlotTypeEnum(enum.Enum):
    REGULAR = 'Regular'
    BREAK = 'Break'
    LUNCH = 'Lunch'
    ASSEMBLY = 'Assembly'
    OTHER = 'Other'


class RoomTypeEnum(enum.Enum):
    CLASSROOM = 'Classroom'
    LAB = 'Lab'
    LIBRARY = 'Library'
    AUDITORIUM = 'Auditorium'
    SPORTS = 'Sports'
    OTHER = 'Other'


# ===== MODELS =====

class TimeSlot(Base):
    """Time slots for daily schedule"""
    __tablename__ = 'time_slots'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'day_of_week', 'start_time', 'end_time', name='unique_tenant_day_time'),
        Index('idx_timeslot_tenant', 'tenant_id'),
        Index('idx_timeslot_day', 'day_of_week'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    day_of_week = Column(Enum(DayOfWeekEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    slot_name = Column(String(50), nullable=True)  # e.g., "Period 1", "Lunch Break"
    slot_type = Column(Enum(SlotTypeEnum, values_callable=lambda obj: [e.value for e in obj]), default=SlotTypeEnum.REGULAR)
    slot_order = Column(Integer, nullable=True)  # Order of periods in a day
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    schedules = relationship("TimetableSchedule", back_populates="time_slot", cascade="all, delete-orphan")
    class_assignments = relationship("TimeSlotClass", back_populates="time_slot", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TimeSlot {self.day_of_week.value} {self.start_time}-{self.end_time}>"

    def to_dict(self):
        return {
            'id': self.id,
            'day_of_week': self.day_of_week.value if self.day_of_week else None,
            'start_time': self.start_time.strftime('%H:%M') if self.start_time else None,
            'end_time': self.end_time.strftime('%H:%M') if self.end_time else None,
            'slot_name': self.slot_name,
            'slot_type': self.slot_type.value if self.slot_type else None,
            'slot_order': self.slot_order,
            'is_active': self.is_active
        }


class ClassTeacherAssignment(Base):
    """Teacher-Class-Subject Assignment"""
    __tablename__ = 'class_teachers'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'class_id', 'subject_id', 'teacher_id', name='unique_class_subject_teacher'),
        Index('idx_classteacher_tenant', 'tenant_id'),
        Index('idx_classteacher_class', 'class_id'),
        Index('idx_classteacher_teacher', 'teacher_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    class_id = Column(Integer, ForeignKey('classes.id', ondelete='CASCADE'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False)
    subject_id = Column(BigInteger, ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False)
    is_class_teacher = Column(Boolean, default=False)  # Homeroom teacher flag
    academic_year = Column(String(20), nullable=True)  # Optional - for historical reference
    assigned_date = Column(Date, nullable=False)
    removed_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    class_ref = relationship("Class", foreign_keys=[class_id])
    teacher = relationship("Teacher")
    subject = relationship("Subject")

    def __repr__(self):
        return f"<ClassTeacherAssignment teacher_id={self.teacher_id} class_id={self.class_id} subject_id={self.subject_id}>"

    def to_dict(self):
        return {
            'id': self.id,
            'class_id': self.class_id,
            'teacher_id': self.teacher_id,
            'subject_id': self.subject_id,
            'is_class_teacher': self.is_class_teacher,
            'academic_year': self.academic_year,
            'assigned_date': self.assigned_date.isoformat() if self.assigned_date else None,
            'removed_date': self.removed_date.isoformat() if self.removed_date else None,
            'teacher_name': f"{self.teacher.first_name} {self.teacher.last_name}" if self.teacher else '',
            'subject_name': self.subject.name if self.subject else '',
            'class_name': f"{self.class_ref.class_name}-{self.class_ref.section}" if self.class_ref else ''
        }


class TimeSlotClass(Base):
    """Junction table - assigns time slots to specific classes"""
    __tablename__ = 'time_slot_classes'
    __table_args__ = (
        UniqueConstraint('time_slot_id', 'class_id', name='unique_timeslot_class'),
        Index('idx_timeslotclass_slot', 'time_slot_id'),
        Index('idx_timeslotclass_class', 'class_id'),
        Index('idx_timeslotclass_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    time_slot_id = Column(BigInteger, ForeignKey('time_slots.id', ondelete='CASCADE'), nullable=False)
    class_id = Column(Integer, ForeignKey('classes.id', ondelete='CASCADE'), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    time_slot = relationship("TimeSlot", back_populates="class_assignments")
    class_ref = relationship("Class")

    def __repr__(self):
        return f"<TimeSlotClass slot_id={self.time_slot_id} class_id={self.class_id}>"


class TimetableSchedule(Base):
    """Weekly Timetable Schedule"""
    __tablename__ = 'timetable_schedules'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'class_id', 'day_of_week', 'time_slot_id', 'academic_year', name='unique_class_day_slot'),
        Index('idx_timetable_tenant', 'tenant_id'),
        Index('idx_timetable_class', 'class_id'),
        Index('idx_timetable_teacher', 'teacher_id'),
        Index('idx_timetable_day_slot', 'day_of_week', 'time_slot_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    class_id = Column(Integer, ForeignKey('classes.id', ondelete='CASCADE'), nullable=False)
    time_slot_id = Column(BigInteger, ForeignKey('time_slots.id', ondelete='CASCADE'), nullable=False)
    day_of_week = Column(Enum(DayOfWeekEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False)
    subject_id = Column(BigInteger, ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False)
    room_number = Column(String(50), nullable=True)
    academic_year = Column(String(20), nullable=True)  # e.g., "2024-25"
    effective_from = Column(Date, nullable=True)
    effective_to = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    class_ref = relationship("Class", foreign_keys=[class_id])
    time_slot = relationship("TimeSlot", back_populates="schedules")
    teacher = relationship("Teacher")
    subject = relationship("Subject")

    def __repr__(self):
        return f"<TimetableSchedule {self.day_of_week.value} slot={self.time_slot_id} teacher={self.teacher_id}>"

    def to_dict(self):
        return {
            'id': self.id,
            'class_id': self.class_id,
            'time_slot_id': self.time_slot_id,
            'day_of_week': self.day_of_week.value if self.day_of_week else None,
            'teacher_id': self.teacher_id,
            'subject_id': self.subject_id,
            'room_number': self.room_number,
            'academic_year': self.academic_year,
            'effective_from': self.effective_from.isoformat() if self.effective_from else None,
            'effective_to': self.effective_to.isoformat() if self.effective_to else None,
            'notes': self.notes,
            'is_active': self.is_active
        }


class ClassRoom(Base):
    """Class Room Management"""
    __tablename__ = 'class_rooms'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'room_number', name='unique_tenant_room'),
        Index('idx_room_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    room_number = Column(String(50), nullable=False)
    room_name = Column(String(100), nullable=True)
    building = Column(String(100), nullable=True)
    floor_number = Column(Integer, nullable=True)
    capacity = Column(Integer, nullable=True)
    room_type = Column(Enum(RoomTypeEnum, values_callable=lambda obj: [e.value for e in obj]), default=RoomTypeEnum.CLASSROOM)
    facilities = Column(Text, nullable=True)  # JSON or comma-separated
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")

    def __repr__(self):
        return f"<ClassRoom {self.room_number} - {self.room_name}>"

    def to_dict(self):
        return {
            'id': self.id,
            'room_number': self.room_number,
            'room_name': self.room_name,
            'building': self.building,
            'floor_number': self.floor_number,
            'capacity': self.capacity,
            'room_type': self.room_type.value if self.room_type else None,
            'facilities': self.facilities,
            'is_active': self.is_active
        }


class TimeSlotGroup(Base):
    """Groups of classes with similar schedules (e.g., Pre-Primary, Primary)"""
    __tablename__ = 'time_slot_groups'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='unique_tenant_slotgroup_name'),
        Index('idx_slotgroup_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)  # e.g., "Pre-Primary", "Primary 1-5"
    display_order = Column(Integer, default=0)  # For UI ordering
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    group_classes = relationship("TimeSlotGroupClass", back_populates="group", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TimeSlotGroup {self.name}>"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'display_order': self.display_order,
            'is_active': self.is_active,
            'class_count': len(self.group_classes) if self.group_classes else 0
        }


class TimeSlotGroupClass(Base):
    """Junction table - assigns classes to time slot groups"""
    __tablename__ = 'time_slot_group_classes'
    __table_args__ = (
        UniqueConstraint('group_id', 'class_id', name='unique_slotgroup_class'),
        Index('idx_slotgroupclass_group', 'group_id'),
        Index('idx_slotgroupclass_class', 'class_id'),
        Index('idx_slotgroupclass_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    group_id = Column(BigInteger, ForeignKey('time_slot_groups.id', ondelete='CASCADE'), nullable=False)
    class_id = Column(Integer, ForeignKey('classes.id', ondelete='CASCADE'), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    group = relationship("TimeSlotGroup", back_populates="group_classes")
    class_ref = relationship("Class")

    def __repr__(self):
        return f"<TimeSlotGroupClass group_id={self.group_id} class_id={self.class_id}>"


class SubstituteAssignment(Base):
    """Track substitute teacher assignments for specific dates"""
    __tablename__ = 'substitute_assignments'
    __table_args__ = (
        UniqueConstraint('schedule_id', 'date', name='unique_schedule_date'),
        Index('idx_substitute_tenant', 'tenant_id'),
        Index('idx_substitute_date', 'date'),
        Index('idx_substitute_original_teacher', 'original_teacher_id'),
        Index('idx_substitute_teacher', 'substitute_teacher_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    schedule_id = Column(BigInteger, ForeignKey('timetable_schedules.id', ondelete='CASCADE'), nullable=False)
    original_teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False)
    substitute_teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False)
    date = Column(Date, nullable=False)  # The specific date of substitution
    leave_application_id = Column(BigInteger, nullable=True)  # Optional link to leave application
    reason = Column(String(255), nullable=True)
    created_by = Column(BigInteger, nullable=True)  # User who created the assignment
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant")
    schedule = relationship("TimetableSchedule")
    original_teacher = relationship("Teacher", foreign_keys=[original_teacher_id])
    substitute_teacher = relationship("Teacher", foreign_keys=[substitute_teacher_id])

    def __repr__(self):
        return f"<SubstituteAssignment date={self.date} original={self.original_teacher_id} substitute={self.substitute_teacher_id}>"

    def to_dict(self):
        return {
            'id': self.id,
            'schedule_id': self.schedule_id,
            'original_teacher_id': self.original_teacher_id,
            'substitute_teacher_id': self.substitute_teacher_id,
            'date': self.date.isoformat() if self.date else None,
            'leave_application_id': self.leave_application_id,
            'reason': self.reason,
            'original_teacher_name': f"{self.original_teacher.first_name} {self.original_teacher.last_name}" if self.original_teacher else '',
            'substitute_teacher_name': f"{self.substitute_teacher.first_name} {self.substitute_teacher.last_name}" if self.substitute_teacher else ''
        }


class WorkloadSettings(Base):
    """Workload threshold configuration per tenant"""
    __tablename__ = 'workload_settings'
    __table_args__ = (
        UniqueConstraint('tenant_id', name='unique_tenant_workload_settings'),
        Index('idx_workload_tenant', 'tenant_id'),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    
    # Global Thresholds
    max_periods_per_week = Column(Integer, default=35, nullable=False)
    max_consecutive_periods = Column(Integer, default=4, nullable=False)
    optimal_min_percent = Column(Integer, default=60, nullable=False)  # Minimum % for optimal status
    optimal_max_percent = Column(Integer, default=85, nullable=False)  # Maximum % for optimal status
    
    # Department Overrides (JSON)
    # Format: {"Physical Education": {"max_periods_per_week": 40}, "Art": {"max_periods_per_week": 25}}
    department_overrides = Column(Text, nullable=True)  # JSON string
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")

    def __repr__(self):
        return f"<WorkloadSettings tenant_id={self.tenant_id} max={self.max_periods_per_week}>"

    def get_department_overrides(self):
        """Parse JSON department overrides"""
        if not self.department_overrides:
            return {}
        try:
            import json
            return json.loads(self.department_overrides)
        except:
            return {}

    def set_department_overrides(self, overrides_dict):
        """Set department overrides as JSON"""
        import json
        self.department_overrides = json.dumps(overrides_dict) if overrides_dict else None

    def get_max_periods_for_department(self, department_name):
        """Get max periods for specific department, with fallback to global"""
        overrides = self.get_department_overrides()
        if department_name in overrides and 'max_periods_per_week' in overrides[department_name]:
            return overrides[department_name]['max_periods_per_week']
        return self.max_periods_per_week

    def to_dict(self):
        return {
            'id': self.id,
            'max_periods_per_week': self.max_periods_per_week,
            'max_consecutive_periods': self.max_consecutive_periods,
            'optimal_min_percent': self.optimal_min_percent,
            'optimal_max_percent': self.optimal_max_percent,
            'department_overrides': self.get_department_overrides()
        }
