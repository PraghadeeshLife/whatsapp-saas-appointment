import json
from datetime import datetime, timedelta
from typing import TypedDict, Annotated, List, Union, Dict, Any, Optional, Sequence
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from googleapiclient.errors import HttpError
from langgraph.graph import StateGraph, END, add_messages
from langgraph.prebuilt import ToolNode, InjectedState
from langgraph.checkpoint.memory import MemorySaver

from app.core.config import settings
from app.core.supabase_client import supabase
from app.services.calendar_service import calendar_service
from app.services.prompts import SYSTEM_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)

# --- State Definition ---

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    tenant_id: int

# --- Defined Tools ---

@tool
async def get_available_resources(state: Annotated[AgentState, InjectedState]) -> str:
    """Returns a list of available resources (e.g., staff, rooms, equipment, service providers) available."""
    try:
        tenant_id = state.get("tenant_id")
        logger.info(f"[TOOL CALL] get_available_resources | Tenant: {tenant_id}")
        resources = await calendar_service.get_available_resources(tenant_id)
        if not resources:
            logger.info(f"[TOOL RESULT] get_available_resources | No resources found for Tenant {tenant_id}")
            return "No resources are currently registered for this account."
        
        logger.info(f"[TOOL RESULT] get_available_resources | Found {len(resources)} resources for Tenant {tenant_id}")
        msg = "Available Resources:\n"
        for r in resources:
            msg += f"- {r['name']} ({r.get('description', 'No description')})\n"
        return msg
    except Exception as e:
        logger.exception(f"[TOOL ERROR] get_available_resources | Error: {e}")
        return "Could not fetch resources at this time. Please try again."

@tool
async def check_availability(
    resource_name: str, 
    date_str: str, 
    state: Annotated[AgentState, InjectedState]
) -> str:
    """
    Check availability for a specific resource on a specific date.
    resource_name: Name of the resource or provider
    date_str: Date in YYYY-MM-DD format
    """
    tenant_id = state.get("tenant_id")
    logger.info(f"[TOOL CALL] check_availability | Resource: {resource_name}, Date: {date_str}, Tenant: {tenant_id}")
    try:
        resources = await calendar_service.get_available_resources(tenant_id)
        resource = next((r for r in resources if resource_name.lower() in r["name"].lower()), None)
        
        if not resource:
            logger.warning(f"[TOOL RESULT] check_availability | Resource '{resource_name}' not found for Tenant {tenant_id}")
            return f"Resource '{resource_name}' not found. Available: {', '.join([r['name'] for r in resources])}"

        # Get all busy slots for the day from DB
        day_start = f"{date_str}T00:00:00"
        day_end = f"{date_str}T23:59:59"
        
        logger.info(f"[TOOL] check_availability | Fetching DB overlapping slots for Resource {resource['id']} on {date_str}")
        # 1. Check DB for existing bookings
        res = supabase.table("appointments")\
            .select("start_time, end_time, status")\
            .eq("tenant_id", tenant_id)\
            .eq("resource_id", resource['id'])\
            .in_("status", ["confirmed", "pending"])\
            .lt("start_time", day_end)\
            .gt("end_time", day_start)\
            .execute()
        
        busy_slots = []
        for b in res.data:
            s = datetime.fromisoformat(b['start_time'].replace('Z', '+00:00')).strftime("%I:%M %p")
            e = datetime.fromisoformat(b['end_time'].replace('Z', '+00:00')).strftime("%I:%M %p")
            busy_slots.append(f"{s} - {e} ({b['status']})")

        # 2. Check GCal for this resource
        service, tenant_cal_id, use_mock = calendar_service.get_service_for_tenant(tenant_id)
        if not use_mock:
            target_cal = resource.get("external_id") if resource.get("external_id") and "@" in resource.get("external_id") else tenant_cal_id
            logger.info(f"[TOOL] check_availability | Listing GCal events for Calendar: {target_cal}")
            g_res = service.events().list(
                calendarId=target_cal,
                timeMin=calendar_service._ensure_timezone(day_start),
                timeMax=calendar_service._ensure_timezone(day_end),
                singleEvents=True
            ).execute()
            
            for event in g_res.get('items', []):
                # Filter for this resource if shared
                if target_cal == tenant_cal_id:
                    desc = event.get('description', '')
                    if "ResourceID:" in desc and f"ResourceID: {resource['id']}" not in desc:
                        continue # Someone else's appt
                
                s_dict = event.get('start', {})
                e_dict = event.get('end', {})
                s_str = s_dict.get('dateTime') or s_dict.get('date')
                e_str = e_dict.get('dateTime') or e_dict.get('date')
                
                # Format for display
                try:
                    s_disp = datetime.fromisoformat(s_str.replace('Z', '+00:00')).strftime("%I:%M %p")
                    e_disp = datetime.fromisoformat(e_str.replace('Z', '+00:00')).strftime("%I:%M %p")
                    busy_slots.append(f"{s_disp} - {e_disp} (External)")
                except Exception as format_err:
                    logger.warning(f"Error formatting GCal time: {format_err}")
                    busy_slots.append(f"GCal Event: {event.get('summary')}")

        logger.info(f"[TOOL RESULT] check_availability | Found {len(busy_slots)} busy intervals for {resource_name}")
        if not busy_slots:
            return f"{resource_name} is fully available on {date_str}!"
        
        return f"On {date_str}, {resource_name} has the following busy slots:\n" + "\n".join(busy_slots) + "\n\nAll other times are available. What time would you like to book?"
        
    except Exception as e:
        logger.exception(f"[TOOL ERROR] check_availability | Error: {e}")
        return f"I had trouble checking historical availability: {str(e)}. However, you can try to reserve a specific slot and I will check it then."

@tool
async def reserve_slot(
    resource_name: str, 
    appointment_time: str, 
    user_name: str, 
    user_phone: str,
    state: Annotated[AgentState, InjectedState]
) -> str:
    """
    Phase 1: Reserve (hold) a slot for 5 minutes.
    resource_name: Resource/Doctor
    appointment_time: ISO format (2026-01-10T14:30:00)
    user_name: Client Name
    user_phone: Client Phone
    """
    tenant_id = state.get("tenant_id")
    logger.info(f"[TOOL CALL] reserve_slot | Resource: {resource_name}, Time: {appointment_time}, User: {user_name} ({user_phone}), Tenant: {tenant_id}")
    try:
        resources = await calendar_service.get_available_resources(tenant_id)
        resource = next((r for r in resources if resource_name.lower() in r["name"].lower()), None)
        
        if not resource:
            logger.warning(f"[TOOL RESULT] reserve_slot | Resource '{resource_name}' not found for Tenant {tenant_id}")
            return f"Resource '{resource_name}' not found."

        # Calculate end time (1 hour default)
        start_dt = datetime.fromisoformat(appointment_time)
        end_dt = start_dt + timedelta(hours=1)
        
        reservation = await calendar_service.reserve_appointment(
            tenant_id=tenant_id,
            resource_id=int(resource['id']),
            customer_name=user_name,
            customer_phone=user_phone,
            start_time=appointment_time,
            end_time=end_dt.isoformat()
        )
        
        logger.info(f"[TOOL RESULT] reserve_slot | SUCCESS | Reservation ID: {reservation['id']}")
        return f"Slot held! Reservation ID: {reservation['id']}. Please confirm YES to finalize this booking within 5 minutes."
    except ValueError as ve:
        logger.warning(f"[TOOL RESULT] reserve_slot | UNAVAILABLE: {ve}")
        return f"Slot not available: {ve}"
    except Exception as e:
        logger.exception(f"[TOOL ERROR] reserve_slot | Error: {e}")
        return f"Failed to reserve slot: {str(e)}"

@tool
async def confirm_booking(reservation_id: str) -> str:
    """
    Phase 2: Confirm a specific reservation ID.
    Only call this after user says YES or CONFIRM to a held slot.
    """
    logger.info(f"[TOOL CALL] confirm_booking | Reservation ID: {reservation_id}")
    try:
        booking = await calendar_service.confirm_appointment(reservation_id)
        # Handle 'Z' or offset
        t_str = booking['start_time'].replace('Z', '+00:00')
        start_dt = datetime.fromisoformat(t_str)
        logger.info(f"[TOOL RESULT] confirm_booking | SUCCESS | Booking ID: {booking['id']}, GCal ID: {booking.get('google_event_id')}")
        return f"Confirmed! Appointment secured for {start_dt.strftime('%B %d at %I:%M %p')}. Ref: {booking['id']}"
    except Exception as e:
        logger.exception(f"[TOOL ERROR] confirm_booking | Error: {e}")
        return f"Failed to confirm booking: {e}"

@tool
async def cancel_appointment(appointment_id: str) -> str:
    """Cancels an existing appointment/reservation by ID."""
    logger.info(f"[TOOL CALL] cancel_appointment | Appointment ID: {appointment_id}")
    try:
        success = await calendar_service.cancel_appointment(appointment_id)
        if success:
            logger.info(f"[TOOL RESULT] cancel_appointment | SUCCESS | ID: {appointment_id}")
            return f"Appointment {appointment_id} has been cancelled."
        logger.warning(f"[TOOL RESULT] cancel_appointment | FAILED | ID: {appointment_id} not found or mismatch")
        return f"Could not find or cancel appointment {appointment_id}."
    except Exception as e:
         logger.exception(f"[TOOL ERROR] cancel_appointment | Error: {e}")
         return f"Error cancelling: {e}"

# --- Agent Class ---

class AppointmentAgent:
    def __init__(self):
        self.tools = [get_available_resources, check_availability, reserve_slot, confirm_booking, cancel_appointment]
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            openai_api_key=settings.openai_api_key
        ).bind_tools(self.tools)
        
        # Memory persistence
        self.memory = MemorySaver()
        
        # Build the graph
        workflow = StateGraph(AgentState)
        
        workflow.add_node("agent", self.call_model)
        workflow.add_node("action", ToolNode(self.tools))
        
        workflow.set_entry_point("agent")
        
        workflow.add_conditional_edges(
            "agent",
            self.should_continue,
            {
                "continue": "action",
                "end": END
            }
        )
        
        workflow.add_edge("action", "agent")
        
        self.app = workflow.compile(checkpointer=self.memory)

    def should_continue(self, state: AgentState):
        messages = state['messages']
        last_message = messages[-1]
        if last_message.tool_calls:
            return "continue"
        return "end"

    async def call_model(self, state: AgentState):
        messages = state['messages']
        response = await self.llm.ainvoke(messages)
        return {"messages": [response]}

    async def get_response(self, text: str, sender_number: str, tenant_id: int) -> str:
        """Process a message and return the AI's response."""
        config = {"configurable": {"thread_id": f"{tenant_id}_{sender_number}"}}
        now = datetime.now()
        
        # Get existing state to check if we should prepend the system message
        state = self.app.get_state(config)
            
        if not state or not state.values or not state.values.get("messages"):
            # Initial conversation start
            current_dt_str = now.strftime('%A, %B %d, %Y %I:%M %p')
            system_content = SYSTEM_PROMPT_TEMPLATE.format(
                current_datetime=current_dt_str,
                timezone=settings.timezone
            )
            system_msg = SystemMessage(content=system_content)
            # IMPORTANT: We store tenant_id in the initial state so tools can access it via 'state'
            initial_state = {
                "messages": [system_msg, HumanMessage(content=text)],
                "tenant_id": tenant_id
            }
            result = await self.app.ainvoke(initial_state, config)
        else:
            # Continue conversation
            result = await self.app.ainvoke({"messages": [HumanMessage(content=text)]}, config)
        
        last_message = result['messages'][-1]
        return last_message.content

# Singleton instance
agent = AppointmentAgent()
