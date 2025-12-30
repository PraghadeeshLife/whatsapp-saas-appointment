from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import enum

class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class Appointment(Base):
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenant.id"))
    customer_name = Column(String, nullable=True)
    customer_phone = Column(String, index=True, nullable=False)
    appointment_time = Column(DateTime, nullable=False)
    status = Column(SQLEnum(AppointmentStatus), default=AppointmentStatus.SCHEDULED)
    
    tenant = relationship("Tenant", back_populates="appointments")
