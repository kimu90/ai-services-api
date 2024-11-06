# config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "Expert Recommendation System"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6380  # Changed to match RedisGraph port
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = None
    REDIS_GRAPH_URL: str = "redis://localhost:6380"  # Added RedisGraph URL
    OPENALEX_API_URL: str = "https://api.openalex.org"
    
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    PGADMIN_EMAIL: str
    PGADMIN_PASSWORD: str
    GEMINI_API_KEY: str
    
    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache()
def get_settings():
    return Settings()