from fastapi import APIRouter, Request, Header, HTTPException, Query
from typing import Optional, Set
from collections import deque
from app.core.config import settings
from app.core.supabase_client import supabase
from app.services.whatsapp import send_text_message
from app.services.agent import agent
from app.services.message_logger import log_message
import logging

logger = logging.getLogger(__name__)

# Processed Message ID Cache (In-Memory Deduplication)
# Stores the last 1000 message IDs to prevent redundant processing during Meta retries.
PROCESSED_IDS = set()
PROCESSED_IDS_QUEUE = deque(maxlen=1000)

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
    logger.info(f"--- Verification attempt ---")
    
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        logger.info("Verification SUCCESS (Master Token)")
        return int(hub_challenge)
        
    logger.warning("Verification FAILED")
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
    logger.info(f"--- Incoming Webhook POST ---")
    
    try:
        payload = await request.json()
    except Exception:
        return {"status": "error", "message": "Invalid JSON"}
    
    try:
        entries = payload.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                
                # --- 1. FILTER STATUS UPDATES ---
                # Meta sends webhooks for 'sent', 'delivered', 'read'. 
                # We only want to process the 'messages' array.
                if "messages" not in value:
                    if "statuses" in value:
                        logger.info("Skipping status update notification (sent/delivered/read)")
                    continue

                metadata = value.get("metadata", {})
                phone_number_id = metadata.get("phone_number_id")
                
                if not phone_number_id:
                    continue

                messages_data = value.get("messages", [])
                for msg in messages_data:
                    msg_id = msg.get("id")
                    if not msg_id:
                        continue
                    
                    # --- 2. IN-MEMORY DEDUPLICATION CHECK ---
                    # Check if we've already started processing this ID (Meta retry)
                    if msg_id in PROCESSED_IDS:
                        logger.info(f"Skipping cached message: {msg_id}")
                        continue
                    
                    # Add to cache immediately
                    PROCESSED_IDS.add(msg_id)
                    PROCESSED_IDS_QUEUE.append(msg_id)
                    if len(PROCESSED_IDS) > 1000:
                        # Safety: remove oldest if queue didn't handle it (set and deque sync)
                        pass

                    # --- 3. DATABASE DEDUPLICATION CHECK (Optional/Safety) ---
                    # Only do this if you need 100% persistence across restarts.
                    # existing = supabase.table("messages").select("id").eq("whatsapp_message_id", msg_id).execute()
                    # if existing.data:
                    #     print(f"Skipping duplicate message (DB): {msg_id}")
                    #     continue

                # --- MULTI-TENANT LOOKUP (Supabase Client) ---
                response = supabase.table("tenants").select("*").eq("whatsapp_phone_number_id", phone_number_id).execute()
                
                if not response.data:
                    logger.error(f"Tenant not found for phone_number_id: {phone_number_id}")
                    continue
                
                tenant_data = response.data[0]
                logger.info(f"Processing message for tenant: {tenant_data.get('name')}")

                messages = value.get("messages", [])
                for message in messages:
                    sender_number = message.get("from")
                    if message.get("type") == "text":
                        text_body = message.get("text", {}).get("body")
                        if text_body:
                            # --- LOG INBOUND MESSAGE ---
                            await log_message(
                                tenant_id=tenant_data.get("id"),
                                sender_number=sender_number,
                                recipient_number=tenant_data.get("whatsapp_phone_number_id"),
                                text=text_body,
                                direction="inbound",
                                status="received",
                                whatsapp_message_id=message.get("id")
                            )

                            logger.info(f"Generating AI response for: '{text_body}'")
                            ai_response = await agent.get_response(
                                text=text_body, 
                                sender_number=sender_number,
                                tenant_id=tenant_data.get("id")
                            )
                            
                            await send_text_message(
                                phone_number_id=phone_number_id,
                                recipient_number=sender_number,
                                text=ai_response,
                                access_token=tenant_data.get("whatsapp_access_token"),
                                tenant_id=tenant_data.get("id")
                            )
                            
    except Exception as e:
        logger.exception(f"Error processing webhook: {e}")
        return {"status": "error", "message": str(e)}

    return {"status": "success"}
