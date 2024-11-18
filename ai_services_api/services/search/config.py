from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Enhanced Search"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    GEMINI_API_KEY: str  # Replacing OpenAI API key with Gemini API key
    MODEL_PATH: str = "distilbert-base-uncased"
    DIMENSION: int = 768
    INDEX_PATH: str = "static/faiss_index.idx"
    CHUNK_MAPPING_PATH: str = "static/index_to_chunk.pkl"
    PDF_FOLDER: str = "ai_services_api/services/search/pdf"  # Folder containing PDFs
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
