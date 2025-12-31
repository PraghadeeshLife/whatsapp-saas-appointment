from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.api.deps import get_current_user
from app.core.supabase_client import supabase
from app.schemas.resource import ResourceCreate, ResourceResponse

router = APIRouter()

@router.get("/", response_model=List[ResourceResponse])
async def list_resources(
    current_user = Depends(get_current_user)
):
    """
    List all resources for the authenticated user's tenant.
    """
    # 1. Get tenant_id for the current user
    tenant_res = supabase.table("tenants").select("id").eq("user_id", current_user.id).execute()
    if not tenant_res.data:
        raise HTTPException(status_code=404, detail="Tenant not found for this user.")
    
    tenant_id = tenant_res.data[0]["id"]
    
    # 2. Fetch resources
    res = supabase.table("resources").select("*").eq("tenant_id", tenant_id).execute()
    return res.data

@router.post("/", response_model=ResourceResponse)
async def create_resource(
    resource_in: ResourceCreate,
    current_user = Depends(get_current_user)
):
    """
    Create a new resource for the authenticated user's tenant.
    """
    # 1. Get tenant_id
    tenant_res = supabase.table("tenants").select("id").eq("user_id", current_user.id).execute()
    if not tenant_res.data:
        raise HTTPException(status_code=404, detail="Tenant not found for this user.")
    
    tenant_id = tenant_res.data[0]["id"]
    
    # 2. Insert resource
    data = resource_in.model_dump()
    data["tenant_id"] = tenant_id
    
    res = supabase.table("resources").insert(data).execute()
    
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to create resource.")
        
    return res.data[0]

@router.delete("/{resource_id}")
async def delete_resource(
    resource_id: int,
    current_user = Depends(get_current_user)
):
    """
    Delete a resource. Ensures the resource belongs to the user's tenant.
    """
    # 1. Get tenant_id
    tenant_res = supabase.table("tenants").select("id").eq("user_id", current_user.id).execute()
    if not tenant_res.data:
        raise HTTPException(status_code=404, detail="Tenant not found for this user.")
    
    tenant_id = tenant_res.data[0]["id"]
    
    # 2. Delete with tenant_id check
    res = supabase.table("resources").delete().eq("id", resource_id).eq("tenant_id", tenant_id).execute()
    
    # Supabase delete returns the deleted rows. If empty, it means nothing was deleted (not found or permission denied)
    if not res.data:
        raise HTTPException(status_code=404, detail="Resource not found or does not belong to your tenant.")
        
    return {"message": "Resource deleted successfully"}
