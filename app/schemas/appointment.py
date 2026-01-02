from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from datetime import datetime

class AppointmentBase(BaseModel):
    resource_id: int
    customer_name: str
    customer_phone: str
    start_time: datetime
    end_time: datetime
    status: str
    google_event_id: Optional[str] = None

class AppointmentResponse(AppointmentBase):
    id: int
    tenant_id: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    resources: Optional[Any] = None # For nested resource info

    model_config = ConfigDict(from_attributes=True)
