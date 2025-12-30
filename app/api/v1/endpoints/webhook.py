from fastapi import APIRouter, Request, Header, HTTPException, Query, Depends
from typing import Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_db
from app.models.tenant import Tenant
from app.services.whatsapp import send_text_message
from app.services.agent import agent

router = APIRouter()

@router.get("/")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    db: Session = Depends(get_db)
):
    """
    Handles the webhook verification from Meta.
    In a multi-tenant SaaS, you might check against a master token 
    or lookup the tenant if a specific identifier is passed in the URL.
    """
    print(f"--- Verification attempt ---")
    
    # 1. Check against Master Token (Standard for Meta Apps)
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        print("Verification SUCCESS (Master Token)")
        return int(hub_challenge)
        
    # 2. Optional: Lookup tenant-specific verify token if needed
    # (Usually not required if you use one Meta App for all tenants)

    print("Verification FAILED")
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/")
async def handle_webhook(
    request: Request, 
    x_hub_signature: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Handles incoming messages from Meta and generates AI responses
    after identifying the tenant from the database.
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

                # --- MULTI-TENANT LOOKUP ---
                tenant = db.query(Tenant).filter(Tenant.whatsapp_phone_number_id == phone_number_id).first()
                if not tenant:
                    print(f"Tenant not found for phone_number_id: {phone_number_id}")
                    continue
                
                print(f"Processing message for tenant: {tenant.name}")

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
                                access_token=tenant.whatsapp_access_token
                            )
                            
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return {"status": "error", "message": str(e)}

    return {"status": "success"}
