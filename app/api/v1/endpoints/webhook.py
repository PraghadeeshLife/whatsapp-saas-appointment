from app.core.config import settings
from app.services.whatsapp import send_text_message
from app.services.agent import agent

router = APIRouter()

@router.get("/")
async def verify_webhook(
# ... existing code for verify_webhook ...
):
# ... existing code ...
    pass # placeholder for brevity in replace, but I'll replace the whole block

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
