from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.api.deps import get_current_user
from app.core.supabase_client import supabase
from app.schemas.tenant import TenantCreate, TenantUpdate, TenantResponse

router = APIRouter()

@router.post("/", response_model=TenantResponse)
async def create_tenant(
    tenant_in: TenantCreate,
    current_user = Depends(get_current_user)
):
    """
    Onboard a new tenant. Links the tenant to the authenticated Supabase user.
    """
    # Check if tenant already exists for this phone number
    existing = supabase.table("tenants").select("*").eq("whatsapp_phone_number_id", tenant_in.whatsapp_phone_number_id).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="A tenant with this WhatsApp Phone Number ID already exists.")

    data = tenant_in.model_dump()
    data["user_id"] = str(current_user.id)
    
    res = supabase.table("tenants").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to create tenant.")
    
    return res.data[0]

@router.get("/me", response_model=TenantResponse)
async def get_my_tenant(
    current_user = Depends(get_current_user)
):
    """
    Get the tenant profile for the authenticated user.
    """
    res = supabase.table("tenants").select("*").eq("user_id", current_user.id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Tenant profile not found.")
    
    return res.data[0]

@router.patch("/me", response_model=TenantResponse)
async def update_my_tenant(
    tenant_patch: TenantUpdate,
    current_user = Depends(get_current_user)
):
    """
    Update the tenant profile for the authenticated user.
    """
    # Verify profile exists
    res_get = supabase.table("tenants").select("*").eq("user_id", current_user.id).execute()
    if not res_get.data:
        raise HTTPException(status_code=404, detail="Tenant profile not found.")
    
    data = tenant_patch.model_dump(exclude_unset=True)
    res = supabase.table("tenants").update(data).eq("user_id", current_user.id).execute()
    
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to update tenant.")
        
    return res.data[0]
