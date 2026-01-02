import os
import json
import datetime
import os.path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import settings
from app.core.supabase_client import supabase
import logging

logger = logging.getLogger(__name__)

# If modifying these SCOPES, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

class CalendarService:
    """
    Wrapper for Google Calendar API interactions.
    Handles dynamic authentication and generic resource management per tenant.
    """
    def __init__(self):
        # In-memory mock data (only used if no credentials found for a tenant)
        self.mock_events = []
        self._load_mock_data()

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

    def _load_mock_data(self):
        now = datetime.now()
        self.mock_events = [
            {
                "id": "mock_evt_1",
                "resource_id": "dr_smith",
                "summary": "Sample Appointment with Dr. Smith",
                "start": (now + timedelta(days=1, hours=9)).isoformat(),
                "end": (now + timedelta(days=1, hours=10)).isoformat(),
                "description": "Initial sample for testing"
            }
        ]

    async def get_available_resources(self, tenant_id: int) -> List[Dict[str, str]]:
        """Returns the list of resources (Doctors, Rooms, Staff) for this tenant from DB."""
        try:
            logger.debug(f"Fetching resources for tenant {tenant_id}...")
            response = supabase.table("resources").select("*").eq("tenant_id", tenant_id).execute()
            if response.data:
                # Map DB format to Agent/Calendar expected format
                return [
                    {
                        "id": str(r["id"]),
                        "external_id": r.get("external_id"),
                        "name": r["name"],
                        "description": r.get("description", "")
                    }
                    for r in response.data
                ]
        except Exception as e:
            logger.error(f"Failed to fetch resources for tenant {tenant_id}: {e}")
        
        # Fallback to empty list or basic mock if needed
        return []

    async def list_events(self, tenant_id: int, time_min: str, time_max: str, resource_external_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List events for a specific resource using its external_id (Google Calendar ID).
        """
        service, calendar_id, use_mock = self.get_service_for_tenant(tenant_id)

        if use_mock:
            logger.debug(f"Using mock data for tenant {tenant_id}")
            events = self.mock_events
            filtered = []
            for event in events:
                if event["start"] >= time_min and event["end"] <= time_max:
                    if not resource_external_id or event.get("resource_id") == resource_external_id:
                        filtered.append(event)
            return filtered

        try:
            logger.debug(f"Executing list call for {calendar_id} (Tenant: {tenant_id})...")
            # Note: We use the resource_external_id to filter events in the description or via specific logic if needed.
            # For simplicity, we list all events on the tenant's primary calendar and filter.
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            # logger.debug(f"API Response Keys: {list(events_result.keys())}")
            events = events_result.get('items', [])
            logger.debug(f"Found {len(events)} events in Google Calendar.")
            if len(events) > 0:
                logger.debug(f"First event summary: {events[0].get('summary')}")
            
            # Map Google events to our internal format
            mapped_events = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                
                # Simple extraction of resource_id from description if we stored it there
                desc = event.get('description', '')
                res_id = None
                if "ResourceID:" in desc:
                    res_id = desc.split("ResourceID:")[1].strip().split()[0]
                
                mapped_events.append({
                    "id": event['id'],
                    "summary": event.get('summary'),
                    "start": start,
                    "end": end,
                    "resource_id": res_id,
                    "description": desc
                })
            
            if resource_external_id:
                mapped_events = [e for e in mapped_events if e["resource_id"] == resource_external_id]
                
            return mapped_events
        except HttpError as error:
            logger.error(f"Google Calendar list_events failed: {error}")
            logger.debug(f"Error response content: {error.content.decode() if error.content else 'No content'}")
            return []

    async def create_event(self, tenant_id: int, summary: str, start_time: str, end_time: str, resource_id: str, description: str = "") -> Dict[str, Any]:
        """
        Create a new event in the calendar.
        """
        service, calendar_id, use_mock = self.get_service_for_tenant(tenant_id)

        if use_mock:
            logger.debug(f"MOCK CREATE for tenant {tenant_id}")
            new_event = {
                "id": f"evt_{int(datetime.now().timestamp())}",
                "resource_id": resource_id,
                "summary": summary,
                "start": start_time,
                "end": end_time,
                "description": description
            }
            self.mock_events.append(new_event)
            return new_event

        # Add ResourceID to description for tracking
        enhanced_description = f"{description}\n\nResourceID: {resource_id}"
        
        event = {
            'summary': summary,
            'description': enhanced_description,
            'start': {
                'dateTime': start_time,
                'timeZone': settings.timezone,
            },
            'end': {
                'dateTime': end_time,
                'timeZone': settings.timezone,
            },
        }

        try:
            logger.debug(f"Inserting event into {calendar_id}: {summary}")
            event_response = service.events().insert(calendarId=calendar_id, body=event).execute()
            logger.debug(f"Create Response ID: {event_response.get('id')}")
            logger.debug(f"Create Response Link: {event_response.get('htmlLink')}")
            return {
                "id": event_response['id'],
                "summary": event_response.get('summary'),
                "start": start_time,
                "end": end_time,
                "resource_id": resource_id,
                "description": enhanced_description
            }
        except HttpError as error:
            logger.error(f"Google Calendar create_event failed: {error}")
            raise Exception(f"Failed to create Google Calendar event: {error}")

    async def delete_event(self, tenant_id: int, event_id: str):
        """
        Delete an event from the calendar.
        """
        service, calendar_id, use_mock = self.get_service_for_tenant(tenant_id)

        if use_mock:
            self.mock_events = [e for e in self.mock_events if e["id"] != event_id]
            return True

        try:
            service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            return True
        except HttpError as error:
            logger.error(f"Google Calendar delete_event failed: {error}")
            logger.debug(f"Error response content: {error.content.decode() if error.content else 'No content'}")
            return False

# Singleton
calendar_service = CalendarService()
