from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class Tenant(Base):
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    whatsapp_phone_number_id = Column(String, unique=True, index=True, nullable=False)
    whatsapp_access_token = Column(Text, nullable=False)
    webhook_verify_token = Column(String, nullable=True)
    
    appointments = relationship("Appointment", back_populates="tenant", cascade="all, delete-orphan")
