import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Database settings
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/aphrc_db")
    
    # API Endpoints
    WEBSITE_API_URL = os.getenv("WEBSITE_API_URL")
    DSPACE_API_URL = os.getenv("DSPACE_API_URL")
    ORCID_API_URL = os.getenv("ORCID_API_URL")
    OPENALEX_API_URL = os.getenv("OPENALEX_API_URL")
    
    # API Keys
    ORCID_API_KEY = os.getenv("ORCID_API_KEY")
    
    # DSpace Database
    DSPACE_DB_URL = os.getenv("DSPACE_DB_URL")

settings = Settings()