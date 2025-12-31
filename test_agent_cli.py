import asyncio
import sys
import os

# Add the current directory to sys.path to allow importing from app
sys.path.append(os.getcwd())

from app.services.agent import agent
from app.services.calendar_service import calendar_service

async def main():
    print("--- Appointment AI Agent CLI ---")
    print("Type your message to interact with the booking agent.")
    print("Type 'exit' or 'quit' to stop.")
    print("---")
    
    # Mock context
    sender_number = "+1234567890"
    tenant_id = "test_tenant_1"
    
    while True:
        try:
            user_input = input("\nYou: ")
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Goodbye!")
                break
            
            if not user_input.strip():
                continue
                
            print("AI is thinking...")
            # For testing, we use a fixed tenant_id (1) and sender_number (user)
            response = await agent.get_response(user_input, sender_number="test_user", tenant_id=1)
            print(f"AI: {response}")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
