from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    app_name: str = "WhatsApp Appointment SaaS"
    api_v1_str: str = "/api/v1"
    
    # Meta API configuration
    meta_verify_token: str = "default_verify_token"
    meta_app_secret: str = "your_app_secret_here"
    meta_access_token: str = "your_access_token_here"
    meta_api_version: str = "v18.0"
    
    # Database configuration
    database_url: str = "sqlite:///./sql_app.db"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()
