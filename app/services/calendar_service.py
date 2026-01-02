import os
import json
import datetime
import uuid
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import pytz

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import settings
from app.core.supabase_client import supabase

logger = logging.getLogger(__name__)

# If modifying these SCOPES, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

class CalendarService:
    """
    Wrapper for Calendar interactions (Postgres SSOT + Google Calendar Sync).
    Implements Two-Phase Commit and Hybrid Availability.
    """
    def __init__(self):
        # In-memory mock data (only used if no credentials found for a tenant)
        # TODO: Refactor mock logic if needed, but primary path should be Postgres
        pass

    def _get_credentials_for_tenant(self, tenant_id: int) -> Optional[Dict[str, Any]]:
        """Fetch credentials from Supabase for a specific tenant."""
        try:
            response = supabase.table("tenants").select("google_service_account_json", "google_calendar_id").eq("id", tenant_id).execute()
            if response.data and response.data[0].get("google_service_account_json"):
                data = response.data[0]
                creds_info = json.loads(data["google_service_account_json"])
                return {
                    "creds_info": creds_info,
                    "calendar_id": data.get("google_calendar_id") or "primary"
                }
        except Exception as e:
            logger.error(f"Failed to fetch credentials for tenant {tenant_id}: {e}")
        return None

    def get_service_for_tenant(self, tenant_id: int):
        """Initializes a Google Calendar service for the specific tenant."""
        tenant_creds = self._get_credentials_for_tenant(tenant_id)
        
        if not tenant_creds:
            return None, "primary", True # use_mock = True

        try:
            creds = service_account.Credentials.from_service_account_info(
                tenant_creds["creds_info"], scopes=SCOPES
            )
            service = build("calendar", "v3", credentials=creds)
            return service, tenant_creds["calendar_id"], False # use_mock = False
        except Exception as e:
            logger.error(f"Auth failed for tenant {tenant_id}: {e}")
            return None, "primary", True

    def _ensure_timezone(self, time_str: str) -> str:
        """
        Parses a time string and ensures it has a valid timezone offset.
        If naive, assumes it belongs to the application's configured timezone (settings.timezone).
        """
        if not time_str:
            return time_str
        
        try:
            # 1. Try parsing as full ISO (potentially with TZ)
            # replacing Z with +00:00 to handle standard UTC notation if present
            dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            
            # 2. If valid and has tzinfo, return as is (or formatted consistently)
            if dt.tzinfo is not None:
                return dt.isoformat()
            
            # 3. If naive, localize to settings.timezone
            tz = pytz.timezone(settings.timezone) # "Asia/Kolkata" or similar
            localized_dt = tz.localize(dt)
            return localized_dt.isoformat()
            
        except ValueError:
            # If standard parsing fails, fallback logic (e.g. if partial string)
            # but usually for 'YYYY-MM-DDTHH:MM:SS' the above works.
            # If it fails, we might just return it and let API fail or try appending offset.
            return f"{time_str}Z" # Fallback to UTC if all else fails
        except Exception as e:
            logger.error(f"Timezone conversion error for {time_str}: {e}")
            return time_str

    async def get_available_resources(self, tenant_id: int) -> List[Dict[str, Any]]:
        """Returns the list of resources for this tenant from DB."""
        try:
            logger.debug(f"Fetching resources for tenant {tenant_id}...")
            response = supabase.table("resources").select("*").eq("tenant_id", tenant_id).execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Failed to fetch resources for tenant {tenant_id}: {e}")
            return []

    async def check_availability(self, tenant_id: int, start_time: str, end_time: str, resource_id: int) -> bool:
        """
        Hyper-Availability Check (Multi-Staff Supported):
        Returns False if:
        1. Postgres has a 'confirmed' booking for THIS resource.
        2. Postgres has a 'pending' booking for THIS resource.
        3. Google Calendar has a busy slot for THIS resource (via specific ID or shared calendar tag).
        """
        logger.info(f"Checking availability for Resource {resource_id} from {start_time} to {end_time}")

        # 1. DB CHECK (Pending or Confirmed)
        try:
            now_iso = datetime.now(pytz.utc).isoformat()
            
            res = supabase.table("appointments")\
                .select("status, expires_at, start_time, end_time")\
                .eq("tenant_id", tenant_id)\
                .eq("resource_id", resource_id)\
                .lt("start_time", end_time)\
                .gt("end_time", start_time)\
                .execute()
                
            for booking in res.data:
                status = booking['status']
                expires_at = booking.get('expires_at')
                
                if status == 'confirmed':
                    logger.info("Slot blocked by CONFIRMED appointment in DB.")
                    return False
                if status == 'pending':
                    if expires_at and expires_at > now_iso:
                        logger.info("Slot blocked by PENDING reservation in DB.")
                        return False
                        
        except Exception as e:
            logger.exception(f"DB Availability check failed for Resource {resource_id}: {e}")

        # 2. GOOGLE CALENDAR CHECK
        resource_external_id = None
        try:
            r_res = supabase.table("resources").select("external_id").eq("id", resource_id).single().execute()
            if r_res.data:
                resource_external_id = r_res.data.get("external_id")
        except:
            pass
            
        service, tenant_calendar_id, use_mock = self.get_service_for_tenant(tenant_id)
        if use_mock:
            return True 

        # Logic: If resource has a specific external_id that looks like a calendar (email), use it.
        # Otherwise use tenant primary calendar.
        target_calendar_id = tenant_calendar_id
        if resource_external_id and "@" in resource_external_id:
             target_calendar_id = resource_external_id

        # Sanitize timestamps for GCal API
        gcal_start = self._ensure_timezone(start_time)
        gcal_end = self._ensure_timezone(end_time)

        try:
            events_result = service.events().list(
                calendarId=target_calendar_id,
                timeMin=gcal_start,
                timeMax=gcal_end,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            
            for event in events:
                # If we are checking the resource's OWN calendar, any event is a block.
                if target_calendar_id != tenant_calendar_id:
                     logger.info(f"Slot blocked by GCal event on {target_calendar_id}")
                     return False
                
                # If we are checking the SHARED tenant calendar, we must check description tags.
                # Format: "ResourceID: <id>"
                description = event.get('description', '')
                
                # If event has NO ResourceID tag, assume it's a general holiday/block that affects EVERYONE.
                if "ResourceID:" not in description:
                    logger.info(f"Slot blocked by General/Shared Event: {event.get('summary')}")
                    return False
                
                # If event has a ResourceID tag, only block if it matches OUR resource.
                if f"ResourceID: {resource_id}" in description:
                    logger.info(f"Slot blocked by event for this resource: {event.get('summary')}")
                    return False
                
                # If it has a DIFFERENT ResourceID, it's for someone else -> Free (continue loop)
                
        except HttpError as e:
            logger.exception(f"GCal check failed for Resource {resource_id}: {e}")
            # Fail safe decision? Assuming DB is filtered correctly, GCal error shouldn't block 
            # unless we are strict. For now, log and return True (rely on DB).

        return True

    async def reserve_appointment(self, tenant_id: int, resource_id: int, customer_name: str, customer_phone: str, start_time: str, end_time: str) -> Dict[str, Any]:
        """
        Phase 1: Soft Reservation.
        - UUID lock.
        - Status: pending.
        - Expires: NOW + 5 mins.
        """
        # 1. Sanitize timestamps
        start_iso = self._ensure_timezone(start_time)
        end_iso = self._ensure_timezone(end_time)

        # 2. Check availability
        is_free = await self.check_availability(tenant_id, start_iso, end_iso, resource_id)
        if not is_free:
             raise ValueError("Slot is not available.")

        # 3. Insert Pending Record
        expires_at = (datetime.now(pytz.utc) + timedelta(minutes=5)).isoformat()
        
        try:
            data = {
                "tenant_id": tenant_id,
                "resource_id": resource_id,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "start_time": start_iso,
                "end_time": end_iso,
                "status": "pending",
                "expires_at": expires_at
            }
            logger.info(f"Inserting pending reservation into DB for Tenant {tenant_id}, Resource {resource_id}")
            response = supabase.table("appointments").insert(data).execute()
            if response.data:
                res_obj = response.data[0]
                logger.info(f"SUCCESS: Reservation created in DB. ID: {res_obj['id']}")
                return res_obj
            raise Exception("Failed to insert reservation into DB.")
        except Exception as e:
            logger.exception(f"Reservation Error in DB for Tenant {tenant_id}, Resource {resource_id}: {e}")
            raise e

    async def confirm_appointment(self, reservation_id: str) -> Dict[str, Any]:
        """
        Phase 2: Hard Confirmation.
        - Check if pending and valid.
        - Sync to GCal.
        - Update DB to confirmed.
        """
        try:
            # 1. Fetch Reservation
            res = supabase.table("appointments").select("*").eq("id", reservation_id).single().execute()
            if not res.data:
                raise ValueError("Reservation not found.")
            
            booking = res.data
            
            # 2. Validate Status & Expiry
            if booking['status'] == 'confirmed':
                return booking # Already confirmed
            
            if booking['status'] == 'cancelled':
                raise ValueError("Reservation was cancelled.")
                
            now_iso = datetime.now(pytz.utc).isoformat()
            if booking['expires_at'] and booking['expires_at'] < now_iso:
                # Auto-cancel in DB if we caught it now
                supabase.table("appointments").update({"status": "cancelled"}).eq("id", reservation_id).execute()
                raise ValueError("Reservation expired.")

            # 3. Sync to Google Calendar
            google_event_id = None
            try:
                logger.info(f"Syncing confirmation for reservation {reservation_id} to Google Calendar")
                g_evt = await self._sync_create_to_google(booking)
                google_event_id = g_evt.get('id')
                logger.info(f"SUCCESS: Synced to GCal. Event ID: {google_event_id}")
            except Exception as e:
                logger.exception(f"Failed to sync confirmation to Google Calendar for reservation {reservation_id}: {e}")
                # We typically still confirm in DB but mark sync error? 
                # Or fail? SSOT says DB is truth. So we confirm, but log warning.

            # 4. Update DB to Confirmed
            update_data = {
                "status": "confirmed", 
                "google_event_id": google_event_id
            }
            logger.info(f"Updating reservation {reservation_id} to 'confirmed' in DB")
            upd = supabase.table("appointments").update(update_data).eq("id", reservation_id).execute()
            if upd.data:
                logger.info(f"SUCCESS: Reservation {reservation_id} marked as confirmed in DB")
                return upd.data[0]
            raise Exception(f"Failed to update reservation {reservation_id} in DB")
            
        except Exception as e:
            logger.exception(f"Confirmation failed for reservation {reservation_id}: {e}")
            raise e

    async def cancel_appointment(self, appointment_id: str) -> bool:
        """
        Cancels appointment in DB and deletes from GCal.
        """
        try:
            # 1. Get Booking
            res = supabase.table("appointments").select("*").eq("id", appointment_id).single().execute()
            if not res.data:
                return False
            booking = res.data
            
            # 2. Cancel in DB
            supabase.table("appointments").update({"status": "cancelled"}).eq("id", appointment_id).execute()
            
            # 3. Cancel in GCal
            if booking.get('google_event_id'):
                try:
                    service, calendar_id, use_mock = self.get_service_for_tenant(booking['tenant_id'])
                    if not use_mock:
                         service.events().delete(calendarId=calendar_id, eventId=booking['google_event_id']).execute()
                except Exception as e:
                    logger.warning(f"Failed to delete GCal event {booking.get('google_event_id')}: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Cancel failed: {e}")
            return False

    async def _sync_create_to_google(self, booking: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to push a confirmed booking to Google Calendar."""
        service, tenant_calendar_id, use_mock = self.get_service_for_tenant(booking['tenant_id'])
        if use_mock:
            return {"id": "mock_gcal_id"}

        # Determine target calendar
        target_calendar_id = tenant_calendar_id
        # Fetch resource to see if it has a specific calendar
        try:
            r_res = supabase.table("resources").select("external_id").eq("id", booking['resource_id']).single().execute()
            if r_res.data:
                rid = r_res.data.get("external_id")
                if rid and "@" in rid:
                    target_calendar_id = rid
        except:
            pass

        # Sanitize timestamps for GCal API
        gcal_start = self._ensure_timezone(booking['start_time'])
        gcal_end = self._ensure_timezone(booking['end_time'])

        event_body = {
            'summary': f"Appt: {booking['customer_name']}",
            'description': f"Phone: {booking['customer_phone']}\nResourceID: {booking['resource_id']}",
            'start': {
                'dateTime': gcal_start, 
                'timeZone': settings.timezone
            },
            'end': {
                'dateTime': gcal_end,
                'timeZone': settings.timezone
            }
        }
        
        return service.events().insert(calendarId=target_calendar_id, body=event_body).execute()

    async def list_events(self, tenant_id: int, time_min: str, time_max: str, resource_external_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Deprecated/Legacy list method. Prefer checking specific availability."""
        # For agent compatibility, we can list from DB + GCal if needed, or simplified DB list.
        # This function was mainly used by check_availability in the old agent.
        # We'll implement a simple DB list for context if agent asks "what slots are taken?"
        
        # ... logic similar to check_availability but returning list ...
        return []

# Singleton
calendar_service = CalendarService()
