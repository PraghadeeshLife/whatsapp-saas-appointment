from fastapi import APIRouter, Request, Header, HTTPException, Query
from typing import Optional
from app.core.config import settings
from app.core.supabase_client import supabase
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
    In a multi-tenant SaaS, check against a master token.
    """
    print(f"--- Verification attempt ---")
    
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        print("Verification SUCCESS (Master Token)")
        return int(hub_challenge)
        
    print("Verification FAILED")
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/")
async def handle_webhook(
    request: Request, 
    x_hub_signature: Optional[str] = Header(None)
):
    """
    Handles incoming messages from Meta and generates AI responses
    after identifying the tenant using the Supabase client.
    """
    print(f"--- Incoming Webhook POST ---")
    
    try:
        payload = await request.json()
    except Exception:
        return {"status": "error", "message": "Invalid JSON"}
    
    try:
        entries = payload.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                phone_number_id = value.get("metadata", {}).get("phone_number_id")
                
                if not phone_number_id:
                    continue

                # --- MULTI-TENANT LOOKUP (Supabase Client) ---
                response = supabase.table("tenants").select("*").eq("whatsapp_phone_number_id", phone_number_id).execute()
                
                if not response.data:
                    print(f"Tenant not found for phone_number_id: {phone_number_id}")
                    continue
                
                tenant_data = response.data[0]
                print(f"Processing message for tenant: {tenant_data.get('name')}")

                messages = value.get("messages", [])
                for message in messages:
                    sender_number = message.get("from")
                    if message.get("type") == "text":
                        text_body = message.get("text", {}).get("body")
                        if text_body:
                            print(f"Generating AI response for: '{text_body}'")
                            ai_response = await agent.get_response(text_body)
                            
                            await send_text_message(
                                phone_number_id=phone_number_id,
                                recipient_number=sender_number,
                                text=ai_response,
                                access_token=tenant_data.get("whatsapp_access_token")
                            )
                            
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return {"status": "error", "message": str(e)}

    return {"status": "success"}
