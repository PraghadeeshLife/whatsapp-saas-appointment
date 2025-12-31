from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class ResourceBase(BaseModel):
    name: str
    description: Optional[str] = None
    external_id: Optional[str] = None

class ResourceCreate(ResourceBase):
    pass

class ResourceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    external_id: Optional[str] = None

class ResourceResponse(ResourceBase):
    id: int
    tenant_id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
