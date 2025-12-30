from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from app.api.deps import get_current_user
from app.core.supabase_client import supabase
from app.schemas.message import MessageResponse

router = APIRouter()

@router.get("/", response_model=List[MessageResponse])
async def list_messages(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    direction: Optional[str] = Query(None, regex="^(inbound|outbound)$"),
    current_user = Depends(get_current_user)
):
    """
    Retrieve message history for the authenticated tenant.
    """
    # 1. Get the tenant_id for the current user
    tenant_res = supabase.table("tenants").select("id").eq("user_id", current_user.id).execute()
    if not tenant_res.data:
        raise HTTPException(status_code=404, detail="Tenant profile not found.")
    
    tenant_id = tenant_res.data[0]["id"]
    
    # 2. Build query
    query = supabase.table("messages").select("*").eq("tenant_id", tenant_id).order("created_at", desc=True)
    
    if direction:
        query = query.eq("direction", direction)
        
    res = query.range(offset, offset + limit - 1).execute()
    
    return res.data
