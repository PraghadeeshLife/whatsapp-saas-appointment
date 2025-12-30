import httpx
from app.core.config import settings

async def send_text_message(phone_number_id: str, recipient_number: str, text: str):
    """
    Sends a text message using the WhatsApp Business API.
    """
    url = f"https://graph.facebook.com/{settings.meta_api_version}/{phone_number_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {settings.meta_access_token}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_number,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        response_data = response.json()
        
        if response.status_code != 200:
            print(f"Error sending message: {response_data}")
            return False
            
        print(f"Message sent successfully: {response_data}")
        return True
