"""
Transport Management Models
Multi-tenant transport management system for school buses, routes, stops, and student assignments
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Time, Date, Enum, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from models import Base
from datetime import datetime, date, time
import enum


# ===== ENUMS =====
class AssignmentTypeEnum(enum.Enum):
    PICKUP = "Pickup"
    DROP = "Drop"
    BOTH = "Both"


class VehicleStatusEnum(enum.Enum):
    ACTIVE = "Active"
    MAINTENANCE = "Under Maintenance"
    INACTIVE = "Inactive"


# ===== MODELS =====

class TransportVehicle(Base):
    """Transport vehicles/buses"""
    __tablename__ = 'transport_vehicles'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    
    # Vehicle Information
    vehicle_number = Column(String(20), nullable=False)  # Registration number
    vehicle_name = Column(String(100), nullable=True)  # Bus name/identifier
    vehicle_type = Column(String(50), default='Bus')  # Bus, Van, etc.
    model = Column(String(100), nullable=True)
    capacity = Column(Integer, default=40)  # Seating capacity
    
    # Driver Information
    driver_name = Column(String(100), nullable=True)
    driver_phone = Column(String(20), nullable=True)
    driver_license = Column(String(50), nullable=True)
    
    # Helper/Conductor Information
    helper_name = Column(String(100), nullable=True)
    helper_phone = Column(String(20), nullable=True)
    
    # Status
    status = Column(Enum(VehicleStatusEnum, values_callable=lambda obj: [e.value for e in obj]), 
                   default=VehicleStatusEnum.ACTIVE)
    is_active = Column(Boolean, default=True)
    
    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    routes = relationship("TransportRoute", back_populates="vehicle")
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'vehicle_number', name='uq_transport_vehicle_tenant_number'),
        Index('idx_transport_vehicle_tenant', 'tenant_id'),
        Index('idx_transport_vehicle_status', 'tenant_id', 'is_active'),
    )
    
    def __repr__(self):
        return f'<TransportVehicle {self.vehicle_number}>'
    
    @property
    def assigned_students_count(self):
        """Count students assigned to routes using this vehicle"""
        count = 0
        for route in self.routes:
            count += len(route.assignments)
        return count


class TransportRoute(Base):
    """Transport routes"""
    __tablename__ = 'transport_routes'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    vehicle_id = Column(Integer, ForeignKey('transport_vehicles.id'), nullable=True)
    
    # Route Information
    route_name = Column(String(100), nullable=False)
    route_code = Column(String(20), nullable=True)  # Short code like R1, R2
    description = Column(Text, nullable=True)
    
    # Timing
    start_time = Column(Time, nullable=True)  # Morning pickup start
    end_time = Column(Time, nullable=True)  # Morning arrival at school
    return_start_time = Column(Time, nullable=True)  # Afternoon departure
    return_end_time = Column(Time, nullable=True)  # Afternoon drop end
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    vehicle = relationship("TransportVehicle", back_populates="routes")
    stops = relationship("TransportStop", back_populates="route", cascade="all, delete-orphan", 
                        order_by="TransportStop.sequence_order")
    assignments = relationship("TransportAssignment", back_populates="route", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'route_name', name='uq_transport_route_tenant_name'),
        Index('idx_transport_route_tenant', 'tenant_id'),
        Index('idx_transport_route_active', 'tenant_id', 'is_active'),
    )
    
    def __repr__(self):
        return f'<TransportRoute {self.route_name}>'
    
    @property
    def total_stops(self):
        return len(self.stops)
    
    @property
    def total_students(self):
        return len(self.assignments)


class TransportStop(Base):
    """Stops on transport routes"""
    __tablename__ = 'transport_stops'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    route_id = Column(Integer, ForeignKey('transport_routes.id'), nullable=False)
    
    # Stop Information
    stop_name = Column(String(100), nullable=False)
    landmark = Column(String(200), nullable=True)  # Nearby landmark
    address = Column(Text, nullable=True)
    
    # Timing
    pickup_time = Column(Time, nullable=True)  # Morning pickup time
    drop_time = Column(Time, nullable=True)  # Afternoon drop time
    
    # Sequence
    sequence_order = Column(Integer, default=1)  # Order of stop in route
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    route = relationship("TransportRoute", back_populates="stops")
    assignments = relationship("TransportAssignment", back_populates="stop")
    
    __table_args__ = (
        Index('idx_transport_stop_tenant', 'tenant_id'),
        Index('idx_transport_stop_route', 'route_id'),
    )
    
    def __repr__(self):
        return f'<TransportStop {self.stop_name} on Route#{self.route_id}>'
    
    @property
    def students_count(self):
        return len(self.assignments)


class TransportAssignment(Base):
    """Student transport assignments - links students to routes and stops"""
    __tablename__ = 'transport_assignments'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    route_id = Column(Integer, ForeignKey('transport_routes.id'), nullable=False)
    stop_id = Column(Integer, ForeignKey('transport_stops.id'), nullable=True)  # Optional specific stop
    
    # Assignment Type
    assignment_type = Column(Enum(AssignmentTypeEnum, values_callable=lambda obj: [e.value for e in obj]),
                            default=AssignmentTypeEnum.BOTH)
    
    # Validity
    start_date = Column(Date, default=date.today)
    end_date = Column(Date, nullable=True)  # NULL means ongoing
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    student = relationship("Student")
    route = relationship("TransportRoute", back_populates="assignments")
    stop = relationship("TransportStop", back_populates="assignments")
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'student_id', 'route_id', name='uq_transport_assignment_student_route'),
        Index('idx_transport_assignment_tenant', 'tenant_id'),
        Index('idx_transport_assignment_student', 'tenant_id', 'student_id'),
        Index('idx_transport_assignment_route', 'tenant_id', 'route_id'),
        Index('idx_transport_assignment_active', 'tenant_id', 'is_active'),
    )
    
    def __repr__(self):
        return f'<TransportAssignment Student#{self.student_id} on Route#{self.route_id}>'
