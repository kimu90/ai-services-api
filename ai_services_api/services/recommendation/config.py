from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "Expert Recommendation System"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = None
    REDIS_GRAPH_URL: str = f"redis://redis-graph:6380"  
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
