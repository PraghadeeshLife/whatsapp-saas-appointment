from fastapi import APIRouter, Request, Header, HTTPException, Query
from typing import Optional
from app.core.config import settings
from app.services.whatsapp import send_text_message
from app.services.agent import agent

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
    print(f"--- Verification attempt ---")
    print(f"hub.mode: {hub_mode}")
    print(f"hub.verify_token: {hub_verify_token}")
    print(f"hub.challenge: {hub_challenge}")
    
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        print("Verification SUCCESS")
        try:
            return int(hub_challenge)
        except (TypeError, ValueError):
            return hub_challenge
            
    print("Verification FAILED")
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/")
async def handle_webhook(request: Request, x_hub_signature: Optional[str] = Header(None)):
    """
    Handles incoming messages from Meta and generates AI responses.
    """
    print(f"--- Incoming Webhook POST ---")
    
    try:
        payload = await request.json()
        print(f"Payload received: {payload}")
    except Exception as e:
        print(f"Error reading JSON payload: {e}")
        return {"status": "error", "message": "Invalid JSON"}
    
    try:
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
                            print(f"Generating AI response for: '{text_body}'")
                            
                            ai_response = await agent.get_response(text_body)
                            print(f"AI response: {ai_response}")
                            
                            success = await send_text_message(
                                phone_number_id=phone_number_id,
                                recipient_number=sender_number,
                                text=ai_response
                            )
                            print(f"Message send success: {success}")
                            
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return {"status": "error", "message": str(e)}

    return {"status": "success"}
