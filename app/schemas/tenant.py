from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class TenantBase(BaseModel):
    name: str
    whatsapp_phone_number_id: str
    whatsapp_access_token: str
    webhook_verify_token: Optional[str] = None

class TenantCreate(TenantBase):
    pass

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    whatsapp_access_token: Optional[str] = None
    webhook_verify_token: Optional[str] = None

class TenantResponse(TenantBase):
    id: int
    user_id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
