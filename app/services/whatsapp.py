import httpx
from app.core.config import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

async def send_text_message(
    phone_number_id: str,
    recipient_number: str,
    text: str,
    access_token: Optional[str] = None,
    tenant_id: Optional[int] = None
):
    """
    Sends a text message using the WhatsApp Business API.
    """
    from app.services.message_logger import log_message
    
    token = access_token or settings.meta_access_token
    if not token:
        logger.error("No WhatsApp access token provided or configured.")
        return False

    url = f"https://graph.facebook.com/{settings.meta_api_version}/{phone_number_id}/messages"
    logger.info(f"Sending message to {url}")
    
    # Use real headers for the actual request
    real_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_number,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    logger.info(f"Message payload: {payload}")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=real_headers, json=payload)
            response_data = response.json()
            
            if response.status_code != 200:
                logger.error(f"Error sending message (Status {response.status_code}): {response_data}")
                return False
                
            logger.info(f"Message sent successfully to {recipient_number}")
            resp_json = response_data # Use the already parsed response_data
            whatsapp_message_id = resp_json.get("messages", [{}])[0].get("id")
            
            # --- LOG OUTBOUND MESSAGE ---
            if tenant_id:
                await log_message(
                    tenant_id=tenant_id,
                    sender_number=phone_number_id,
                    recipient_number=recipient_number,
                    text=text,
                    direction="outbound",
                    status="sent",
                    whatsapp_message_id=whatsapp_message_id
                )
            return resp_json
        except Exception as e:
            logger.exception(f"Exception during message sending: {e}")
            return False
