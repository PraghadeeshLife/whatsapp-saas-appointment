from fastapi import APIRouter, Request, Header, HTTPException, Query
from typing import Optional
from app.core.config import settings
from app.services.whatsapp import send_text_message

router = APIRouter()

@router.get("/")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """
    Handles the webhook verification from Meta.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        try:
            return int(hub_challenge)
        except (TypeError, ValueError):
            return hub_challenge
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/")
async def handle_webhook(request: Request, x_hub_signature: Optional[str] = Header(None)):
    """
    Handles incoming messages from Meta and echoes them back.
    """
    payload = await request.json()
    
    # TODO: Validate signature using x_hub_signature and settings.meta_app_secret
    
    try:
        # Navigate through the complex Meta payload structure
        entries = payload.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                metadata = value.get("metadata", {})
                phone_number_id = metadata.get("phone_number_id")
                
                messages = value.get("messages", [])
                for message in messages:
                    sender_number = message.get("from")
                    message_type = message.get("type")
                    
                    if message_type == "text":
                        text_body = message.get("text", {}).get("body")
                        if text_body and phone_number_id and sender_number:
                            print(f"Echoing message: '{text_body}' back to {sender_number}")
                            await send_text_message(
                                phone_number_id=phone_number_id,
                                recipient_number=sender_number,
                                text=f"Echo: {text_body}"
                            )
                            
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return {"status": "error", "message": str(e)}

    return {"status": "success"}
