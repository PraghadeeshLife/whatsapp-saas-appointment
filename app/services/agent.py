import json
from datetime import datetime, timedelta
from typing import TypedDict, Annotated, List, Union, Dict, Any, Optional, Sequence

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END, add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from app.core.config import settings
from app.services.calendar_service import calendar_service
from app.services.prompts import SYSTEM_PROMPT_TEMPLATE

# --- State Definition ---

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    tenant_id: int

# --- Defined Tools ---

@tool
async def get_available_resources(state: AgentState) -> str:
    """Returns a list of available resources (e.g., staff, rooms, equipment, service providers) available."""
    tenant_id = state.get("tenant_id")
    print(f"TENANT ID: {tenant_id}")
    resources = await calendar_service.get_available_resources(tenant_id)
    if not resources:
        return "No resources are currently registered for this account."
    
    msg = "Available Resources:\n"
    for r in resources:
        msg += f"- {r['name']} ({r.get('description', 'No description')})\n"
    return msg

@tool
async def check_availability(state: AgentState, resource_name: str, date_str: str) -> str:
    """
    Check availability for a specific resource on a specific date.
    resource_name: Name of the resource or provider
    date_str: Date in YYYY-MM-DD format
    """
    tenant_id = state.get("tenant_id")
    resources = await calendar_service.get_available_resources(tenant_id)
    resource = next((r for r in resources if resource_name.lower() in r["name"].lower()), None)
    
    if not resource:
        return f"Resource '{resource_name}' not found. Available: {', '.join([r['name'] for r in resources])}"

    time_min = f"{date_str}T00:00:00Z"
    time_max = f"{date_str}T23:59:59Z"
    
    # Use external_id (e.g., Google Calendar ID) if available
    external_id = resource.get("external_id")
    events = await calendar_service.list_events(tenant_id, time_min, time_max, external_id)
    
    if not events:
        return f"{resource_name} is fully available on {date_str} during business hours."
    
    # Simple summary of booked slots
    booked = []
    for e in events:
        start_time = e["start"]
        try:
            dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            booked.append(dt.strftime("%I:%M %p"))
        except:
            booked.append(start_time)
    
    return f"{resource_name} is booked at: {', '.join(booked)} on {date_str}. Other slots are available."

@tool
async def book_appointment(state: AgentState, resource_name: str, appointment_time: str, user_name: str, user_phone: str) -> str:
    """
    Book an appointment/slot.
    resource_name: Name of the resource or provider
    appointment_time: ISO format string (e.g., 2023-10-25T14:30:00)
    user_name: Name of the person booking
    user_phone: Phone number of the user
    """
    tenant_id = state.get("tenant_id")
    resources = await calendar_service.get_available_resources(tenant_id)
    resource = next((r for r in resources if resource_name.lower() in r["name"].lower()), None)
    
    if not resource:
        return f"Resource '{resource_name}' not found."

    # End time 1 hour later
    try:
        start_dt = datetime.fromisoformat(appointment_time)
    except ValueError:
        return f"Invalid time format: {appointment_time}. Please use ISO format."
        
    end_dt = start_dt + timedelta(hours=1)
    end_time = end_dt.isoformat()

    try:
        event = await calendar_service.create_event(
            tenant_id=tenant_id,
            summary=f"Booking for {resource_name}: {user_name}",
            start_time=appointment_time,
            end_time=end_time,
            resource_id=resource.get("external_id") or resource["id"],
            description=f"Client: {user_name}\nPhone: {user_phone}"
        )
        return f"Confirmed! Booking for {resource_name} confirmed for {start_dt.strftime('%B %d at %I:%M %p')}. Ticket ID: {event['id']}"
    except Exception as e:
        return f"Error booking: {str(e)}"

@tool
async def cancel_appointment(state: AgentState, appointment_id: str) -> str:
    """Cancels an existing appointment by ID."""
    tenant_id = state.get("tenant_id")
    success = await calendar_service.delete_event(tenant_id, appointment_id)
    if success:
        return f"Appointment {appointment_id} has been cancelled."
    return f"Could not find or cancel appointment {appointment_id}."

# --- Agent Class ---

class AppointmentAgent:
    def __init__(self):
        self.tools = [get_available_resources, check_availability, book_appointment, cancel_appointment]
        self.llm = ChatOpenAI(
            model="gpt-4o",
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
