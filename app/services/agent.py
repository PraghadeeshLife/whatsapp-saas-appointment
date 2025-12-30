from typing import TypedDict, Annotated, List, Union
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from app.core.config import settings

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], lambda x, y: x + y]

class WhatsAppAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            openai_api_key=settings.openai_api_key
        )
        
        # Build the graph
        workflow = StateGraph(AgentState)
        
        workflow.add_node("agent", self.call_model)
        workflow.set_entry_point("agent")
        workflow.add_edge("agent", END)
        
        self.app = workflow.compile()

    async def call_model(self, state: AgentState):
        messages = state['messages']
        response = await self.llm.ainvoke(messages)
        return {"messages": [response]}

    async def get_response(self, text: str) -> str:
        """
        Processes a text message and returns an LLM-generated response.
        """
        # For now, we'll use a simple system prompt to keep it focused
        system_msg = SystemMessage(content="You are a helpful assistant for a WhatsApp SaaS. Keep your responses concise and friendly.")
        user_msg = HumanMessage(content=text)
        
        inputs = {"messages": [system_msg, user_msg]}
        
        # In a real app, we might use thread_id for conversation state
        result = await self.app.ainvoke(inputs)
        
        # The last message in the state should be our AI response
        last_message = result['messages'][-1]
        return last_message.content

# Singleton instance
agent = WhatsAppAgent()
