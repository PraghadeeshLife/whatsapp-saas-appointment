from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class MessageResponse(BaseModel):
    id: int
    tenant_id: int
    sender_number: str
    recipient_number: str
    text: Optional[str]
    direction: str
    status: Optional[str]
    whatsapp_message_id: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
