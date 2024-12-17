
# ai_services_api/services/message/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # Required settings
    GEMINI_API_KEY: str = os.getenv('GEMINI_API_KEY')
    DATABASE_URL: str = "postgresql://postgres:p0stgres@postgres:5432/aphrc"
    
    # Application settings
    APP_NAME: Optional[str] = "Expert Recommendation System"
    DEBUG: Optional[bool] = True
    API_V1_STR: Optional[str] = "/api/v1"
    
    # Database settings
    POSTGRES_HOST: Optional[str] = "postgres"
    POSTGRES_DB: Optional[str] = "aphrc"
    POSTGRES_USER: Optional[str] = "postgres"
    POSTGRES_PASSWORD: Optional[str] = "p0stgres"

    class Config:
        env_file = ".env"
        case_sensitive = True
        use_enum_values = True

        # Very important: this allows extra fields
        extra = "allow"

    @property
    def validate_gemini_key(self) -> bool:
        if not self.GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY not found")
            return False
        return True

@lru_cache()
def get_settings() -> Settings:
    try:
        settings = Settings()
        if not settings.validate_gemini_key:
            raise ValueError("GEMINI_API_KEY is not configured")
        return settings
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        raise
