import asyncio
import sys
import os
import logging
from app.core.logging import setup_logging

# Add the current directory to sys.path to allow importing from app
sys.path.append(os.getcwd())

from app.services.agent import agent
from app.services.calendar_service import calendar_service

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

async def main():
    logger.info("--- Appointment AI Agent CLI ---")
    logger.info("Type your message to interact with the booking agent.")
    logger.info("Type 'exit' or 'quit' to stop.")
    logger.info("---")
    
    # Mock context
    sender_number = "+1234567890"
    tenant_id = "test_tenant_1"
    
    while True:
        try:
            # interactive input still uses built-in input() 
            # but we can log the prompt if needed, though input() handles display.
            user_input = input("\nYou: ")
            if user_input.lower() in ["exit", "quit", "q"]:
                logger.info("Goodbye!")
                break
            
            if not user_input.strip():
                continue
                
            logger.info("AI is thinking...")
            # For testing, we use a fixed tenant_id (1) and sender_number (user)
            response = await agent.get_response(user_input, sender_number="test_user", tenant_id=1)
            logger.info(f"AI: {response}")
            
        except KeyboardInterrupt:
            logger.info("\nGoodbye!")
            break
        except Exception as e:
            logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
