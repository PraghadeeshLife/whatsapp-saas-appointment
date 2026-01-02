from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List

class Settings(BaseSettings):
    app_name: str = "WhatsApp Appointment SaaS"
    api_v1_str: str = "/api/v1"

    # New Relic configuration
    new_relic_license_key: Optional[str] = None
    new_relic_app_name: str = "whatsapp-saas-appointment"
    
    # Meta API configuration
    meta_verify_token: str = "default_verify_token"
    meta_app_secret: str = "your_app_secret_here"
    meta_access_token: Optional[str] = None # Now managed per tenant in DB
    meta_api_version: str = "v18.0"
    
    openai_api_key: str = "your_openai_api_key_here"
    
    # Supabase configuration
    supabase_url: str = "your_supabase_url_here"
    supabase_key: str = "your_supabase_key_here"
    
    # Google Calendar configuration
    google_calendar_credentials: Optional[str] = None
    google_calendar_token: Optional[str] = None
    google_calendar_id: str = "primary"
    timezone: str = "Asia/Kolkata"
    
    # CORS configuration
    backend_cors_origins: List[str] = ["*"]
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()
