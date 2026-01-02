from typing import Optional
from app.core.supabase_client import supabase
import logging

logger = logging.getLogger(__name__)

async def log_message(
    tenant_id: int,
    sender_number: str,
    recipient_number: str,
    text: str,
    direction: str,
    status: Optional[str] = None,
    whatsapp_message_id: Optional[str] = None
):
    """
    Logs an inbound or outbound message to the Supabase 'messages' table.
    """
    try:
        data = {
            "tenant_id": tenant_id,
            "sender_number": sender_number,
            "recipient_number": recipient_number,
            "text": text,
            "direction": direction,
            "status": status,
            "whatsapp_message_id": whatsapp_message_id
        }
        
        # Using .execute() on the rpc or table insert
        supabase.table("messages").insert(data).execute()
        logger.info(f"Message logged: {direction} | {sender_number} -> {recipient_number}")
        
    except Exception as e:
        logger.error(f"Failed to log message to Supabase: {e}")
