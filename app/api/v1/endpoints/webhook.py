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
    Handles incoming messages from Meta and echoes them back.
    """
    print(f"--- Incoming Webhook POST ---")
    print(f"X-Hub-Signature: {x_hub_signature}")
    
    try:
        payload = await request.json()
        print(f"Payload received: {payload}")
    except Exception as e:
        print(f"Error reading JSON payload: {e}")
        return {"status": "error", "message": "Invalid JSON"}
    
    try:
        # Navigate through the complex Meta payload structure
        entries = payload.get("entry", [])
        print(f"Number of entries: {len(entries)}")
        
        for entry in entries:
            changes = entry.get("changes", [])
            print(f"Number of changes in entry: {len(changes)}")
            
            for change in changes:
                value = change.get("value", {})
                metadata = value.get("metadata", {})
                phone_number_id = metadata.get("phone_number_id")
                print(f"Processing change for phone_number_id: {phone_number_id}")
                
                messages = value.get("messages", [])
                print(f"Number of messages: {len(messages)}")
                
                for message in messages:
                    sender_number = message.get("from")
                    message_type = message.get("type")
                    print(f"Message from {sender_number}, type: {message_type}")
                    
                    if message_type == "text":
                        text_body = message.get("text", {}).get("body")
                        print(f"Text body: {text_body}")
                        
                        if text_body and phone_number_id and sender_number:
                            print(f"Echoing message: '{text_body}' back to {sender_number}")
                            success = await send_text_message(
                                phone_number_id=phone_number_id,
                                recipient_number=sender_number,
                                text=f"Echo: {text_body}"
                            )
                            print(f"Message send success: {success}")
                        else:
                            print("Missing required fields (text_body/phone_number_id/sender_number) for echo")
                            
    except Exception as e:
        print(f"Error processing webhook contents: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

    return {"status": "success"}
