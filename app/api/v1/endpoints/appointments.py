from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from app.api.deps import get_current_user
from app.core.supabase_client import supabase
from app.schemas.appointment import AppointmentResponse
from app.services.calendar_service import calendar_service

router = APIRouter()

@router.get("/", response_model=List[AppointmentResponse])
async def list_appointments(
    resource_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    current_user = Depends(get_current_user)
):
    """
    List all appointments for the authenticated user's tenant with optional filters.
    """
    # 1. Get tenant_id for the current user
    tenant_res = supabase.table("tenants").select("id").eq("user_id", current_user.id).execute()
    if not tenant_res.data:
        raise HTTPException(status_code=404, detail="Tenant not found for this user.")
    
    tenant_id = tenant_res.data[0]["id"]
    
    # 2. Fetch appointments using calendar_service
    appointments = await calendar_service.get_appointments(
        tenant_id=tenant_id,
        resource_id=resource_id,
        status=status,
        start_time=start_time,
        end_time=end_time
    )
    
    return appointments

@router.delete("/{appointment_id}")
async def cancel_appointment_api(
    appointment_id: int,
    current_user = Depends(get_current_user)
):
    """
    Cancel an appointment. Checks if the appointment belongs to the user's tenant.
    """
    # 1. Get tenant_id
    tenant_res = supabase.table("tenants").select("id").eq("user_id", current_user.id).execute()
    if not tenant_res.data:
        raise HTTPException(status_code=404, detail="Tenant not found for this user.")
    
    tenant_id = tenant_res.data[0]["id"]
    
    # 2. Check if the appointment belongs to the tenant
    appt_res = supabase.table("appointments").select("tenant_id").eq("id", appointment_id).execute()
    if not appt_res.data:
         raise HTTPException(status_code=404, detail="Appointment not found.")
    
    if appt_res.data[0]["tenant_id"] != tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this appointment.")

    # 3. Cancel via service
    success = await calendar_service.cancel_appointment(appointment_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to cancel appointment.")
        
    return {"message": "Appointment cancelled successfully"}
