import httpx
from app.core.config import settings

async def send_text_message(phone_number_id: str, recipient_number: str, text: str, access_token: str = None):
    """
    Sends a text message using the WhatsApp Business API.
    Uses the provided access_token or falls back to the system default.
    """
    token = access_token or settings.meta_access_token
    if not token:
        print("Error: No WhatsApp access token provided or configured.")
        return False

    url = f"https://graph.facebook.com/{settings.meta_api_version}/{phone_number_id}/messages"
    print(f"Sending message to {url}")
    
    # Use real headers for the actual request
    real_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_number,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    print(f"Message payload: {payload}")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=real_headers, json=payload)
            response_data = response.json()
            
            if response.status_code != 200:
                print(f"Error sending message (Status {response.status_code}): {response_data}")
                return False
                
            print(f"Message sent successfully: {response_data}")
            return True
        except Exception as e:
            print(f"Exception during message sending: {e}")
            return False
