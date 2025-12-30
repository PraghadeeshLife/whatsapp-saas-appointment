from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    app_name: str = "WhatsApp Appointment SaaS"
    api_v1_str: str = "/api/v1"
    
    # Meta API configuration
    meta_verify_token: str = "default_verify_token"
    meta_app_secret: str = "your_app_secret_here"
    meta_access_token: Optional[str] = None # Now managed per tenant in DB
    meta_api_version: str = "v18.0"
    
    openai_api_key: str = "your_openai_api_key_here"
    
    # Supabase configuration
    supabase_url: str = "your_supabase_url_here"
    supabase_key: str = "your_supabase_key_here"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()
